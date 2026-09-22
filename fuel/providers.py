"""
Multi-level fallback providers for Spanish fuel price data.

Fallback chain:
  L1  Official REST (sedeaplicaciones.minetur.gob.es)
  L2  Mirror  REST (energia.serviciosmin.gob.es)
  L3  Official CSV dataset (configurable URL, UTF-8, semicolon-separated)
  L4  Local snapshot cache (gzip JSON, timestamped)
  L5  Precioil API (optional, enabled when ENABLE_PRECIOIL_FALLBACK=1)
"""

import csv
import gzip
import io
import json
import logging
import os
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FuelPriceBot/1.0)",
    "Accept": "application/json",
}
_RETRYABLE_STATUS = [500, 502, 503, 504]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class ProviderConfig:
    rest_primary_url: str = (
        "https://sedeaplicaciones.minetur.gob.es"
        "/ServiciosRESTCarburantes/PreciosCarburantes"
    )
    rest_secondary_url: str = (
        "https://energia.serviciosmin.gob.es"
        "/ServiciosRestCarburantes/PreciosCarburantes"
    )
    csv_url: str = ""
    snapshot_directory: str = ""
    cache_retention_days: int = 30
    enable_precioil_fallback: bool = False
    precioil_api_url: str = ""
    request_timeout: int = 5
    csv_timeout: int = 10

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        return cls(
            rest_primary_url=os.getenv(
                "REST_PRIMARY_URL",
                "https://sedeaplicaciones.minetur.gob.es"
                "/ServiciosRESTCarburantes/PreciosCarburantes",
            ),
            rest_secondary_url=os.getenv(
                "REST_SECONDARY_URL",
                "https://energia.serviciosmin.gob.es"
                "/ServiciosRestCarburantes/PreciosCarburantes",
            ),
            csv_url=os.getenv("CSV_URL", ""),
            snapshot_directory=os.getenv("SNAPSHOT_DIRECTORY", ""),
            cache_retention_days=int(os.getenv("CACHE_RETENTION_DAYS", "30")),
            enable_precioil_fallback=os.getenv("ENABLE_PRECIOIL_FALLBACK", "").lower()
            in ("1", "true", "yes"),
            precioil_api_url=os.getenv("PRECIOIL_API_URL", ""),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "5")),
        )


# ---------------------------------------------------------------------------
# Exceptions & shared helpers
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """A provider failed; the composite should try the next one."""


def _make_session(retries: int = 2, backoff_factor: float = 0.5) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=_RETRYABLE_STATUS,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _normalize(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper().strip()


def _parse_number(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _station_from_row(row: dict) -> dict:
    return {
        "name": (row.get("Rótulo") or "").strip(),
        "address": (row.get("Dirección") or "").strip(),
        "town": (row.get("Municipio") or "").strip(),
        "postal_code": (row.get("C.P.") or "").strip(),
        "lat": _parse_number(row.get("Latitud")),
        "lon": _parse_number(row.get("Longitud (WGS84)")),
        "gasoline_95": _parse_number(row.get("Precio Gasolina 95 E5")),
        "diesel": _parse_number(row.get("Precio Gasoleo A")),
    }


# ---------------------------------------------------------------------------
# L1 / L2 — REST providers (shared implementation)
# ---------------------------------------------------------------------------

class _RestProvider:
    def __init__(self, name: str, base_url: str, config: ProviderConfig):
        self.name = name
        self._base = base_url.rstrip("/")
        self._config = config
        self._session = _make_session()

    def get_municipio_id(self, province_code: str, municipio_name: str) -> str:
        url = f"{self._base}/Listados/MunicipiosPorProvincia/{province_code}"
        try:
            resp = self._session.get(
                url, headers=_HEADERS, timeout=self._config.request_timeout
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ProviderError(f"{self.name}: municipio lookup failed: {exc}") from exc

        target = _normalize(municipio_name)
        for m in resp.json():
            raw_name = m.get("Municipio") or m.get("municipio") or ""
            if _normalize(raw_name) == target:
                mid = m.get("IDMunicipio")
                if mid:
                    return mid
        raise ValueError(
            f"Municipality '{municipio_name}' not found in province {province_code}."
        )

    def fetch(self, province_code: str, municipio_name: str = "") -> dict:
        try:
            if municipio_name:
                municipio_id = self.get_municipio_id(province_code, municipio_name)
                url = f"{self._base}/EstacionesTerrestres/FiltroMunicipio/{municipio_id}"
            else:
                url = f"{self._base}/EstacionesTerrestres/FiltroProvincia/{province_code}"

            resp = self._session.get(
                url, headers=_HEADERS, timeout=self._config.request_timeout
            )
            resp.raise_for_status()
        except (requests.RequestException, ProviderError) as exc:
            raise ProviderError(f"{self.name}: {exc}") from exc

        payload = resp.json()
        raw_stations = payload.get("ListaEESSPrecio", [])
        if not raw_stations:
            raise ProviderError(f"{self.name}: empty station list")

        return {
            "date": payload.get("Fecha"),
            "stations": [_station_from_row(s) for s in raw_stations],
        }


class OfficialRestProvider(_RestProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__("official_rest_primary", config.rest_primary_url, config)


class OfficialMirrorProvider(_RestProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__("official_rest_mirror", config.rest_secondary_url, config)


# ---------------------------------------------------------------------------
# L3 — CSV provider
# ---------------------------------------------------------------------------

class OfficialCsvProvider:
    name = "official_csv"

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._session = _make_session(retries=2, backoff_factor=1.0)

    def fetch(self, province_code: str, municipio_name: str = "") -> dict:
        if not self._config.csv_url:
            raise ProviderError("official_csv: CSV_URL not configured")
        if not municipio_name:
            raise ProviderError(
                "official_csv: province-only queries not supported (no municipality name)"
            )

        try:
            resp = self._session.get(
                self._config.csv_url,
                headers={**_HEADERS, "Accept": "text/csv, text/plain, */*"},
                timeout=self._config.csv_timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ProviderError(f"official_csv: download failed: {exc}") from exc

        content = resp.content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(content), delimiter=";")
        target = _normalize(municipio_name)
        stations = []
        for row in reader:
            row_muni = row.get("Municipio") or row.get("Localidad") or ""
            if _normalize(row_muni) == target:
                stations.append(_station_from_row(row))

        if not stations:
            raise ProviderError(
                f"official_csv: no stations for municipio '{municipio_name}'"
            )

        fecha = next(
            (row.get("Fecha") for row in csv.DictReader(
                io.StringIO(content), delimiter=";"
            )),
            None,
        )
        return {"date": fecha, "stations": stations}


# ---------------------------------------------------------------------------
# L4 — Snapshot (local gzip JSON cache)
# ---------------------------------------------------------------------------

class SnapshotProvider:
    name = "snapshot"

    def __init__(self, config: ProviderConfig):
        self._config = config

    def _snap_dir(self) -> Optional[Path]:
        d = self._config.snapshot_directory
        if not d:
            return None
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _key(self, province_code: str, municipio_name: str) -> str:
        muni = _normalize(municipio_name) or "all"
        safe = "".join(c if c.isalnum() else "_" for c in muni)
        return f"fuel_{province_code}_{safe}"

    def fetch(self, province_code: str, municipio_name: str = "") -> dict:
        snap_dir = self._snap_dir()
        if snap_dir is None:
            raise ProviderError("snapshot: SNAPSHOT_DIRECTORY not configured")

        key = self._key(province_code, municipio_name)
        cutoff = date.today() - timedelta(days=self._config.cache_retention_days)
        candidates = sorted(snap_dir.glob(f"{key}_*.json.gz"), reverse=True)
        for path in candidates:
            try:
                # path.stem strips .gz → "name.json"; strip .json next
                bare = Path(path.stem).stem
                snap_date = date.fromisoformat(bare.rsplit("_", 1)[-1])
            except ValueError:
                continue
            if snap_date < cutoff:
                break
            try:
                with gzip.open(path, "rt", encoding="utf-8") as fh:
                    data = json.load(fh)
                logger.info("snapshot: loaded %s", path.name)
                return data
            except Exception as exc:  # noqa: BLE001
                logger.warning("snapshot: could not read %s: %s", path.name, exc)

        raise ProviderError(
            f"snapshot: no usable snapshot for {province_code}/{municipio_name or 'all'}"
        )

    def save(self, data: dict, province_code: str, municipio_name: str = "") -> None:
        snap_dir = self._snap_dir()
        if snap_dir is None:
            return

        key = self._key(province_code, municipio_name)
        filename = snap_dir / f"{key}_{date.today().isoformat()}.json.gz"
        try:
            with gzip.open(filename, "wt", encoding="utf-8") as fh:
                json.dump(data, fh)
            logger.debug("snapshot: saved %s", filename.name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("snapshot: could not save %s: %s", filename.name, exc)

        self._cleanup(snap_dir, key)

    def _cleanup(self, snap_dir: Path, key: str) -> None:
        cutoff = date.today() - timedelta(days=self._config.cache_retention_days)
        for path in snap_dir.glob(f"{key}_*.json.gz"):
            try:
                bare = Path(path.stem).stem
                snap_date = date.fromisoformat(bare.rsplit("_", 1)[-1])
                if snap_date < cutoff:
                    path.unlink()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# L5 — Precioil (optional third-party)
# ---------------------------------------------------------------------------

class PrecioilProvider:
    name = "precioil"

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._session = _make_session()

    def fetch(self, province_code: str, municipio_name: str = "") -> dict:
        if not self._config.enable_precioil_fallback or not self._config.precioil_api_url:
            raise ProviderError("precioil: not configured")

        params = {"province": province_code}
        if municipio_name:
            params["municipio"] = municipio_name

        try:
            resp = self._session.get(
                self._config.precioil_api_url,
                params=params,
                headers=_HEADERS,
                timeout=self._config.request_timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ProviderError(f"precioil: {exc}") from exc

        payload = resp.json()
        # Expects {"date": "...", "stations": [...]} with pre-normalised fields.
        stations = payload.get("stations") or payload.get("ListaEESSPrecio")
        if not stations:
            raise ProviderError("precioil: empty station list")

        if payload.get("stations"):
            return payload  # already in our format
        return {
            "date": payload.get("Fecha"),
            "stations": [_station_from_row(s) for s in stations],
        }


# ---------------------------------------------------------------------------
# Composite provider — public entry point
# ---------------------------------------------------------------------------

class CompositeFuelProvider:
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._rest_providers: List[_RestProvider] = [
            OfficialRestProvider(config),
            OfficialMirrorProvider(config),
        ]
        self._csv = OfficialCsvProvider(config)
        self._snapshot = SnapshotProvider(config)
        self._precioil = PrecioilProvider(config)

    def get_municipio_id(self, province_code: str, municipio_name: str) -> str:
        last_exc: Optional[Exception] = None
        for provider in self._rest_providers:
            try:
                return provider.get_municipio_id(province_code, municipio_name)
            except ProviderError as exc:
                logger.warning("%s", exc)
                last_exc = exc
        raise last_exc or ProviderError("all REST providers failed for municipio lookup")

    def fetch(self, province_code: str, municipio_name: str = "") -> dict:
        saveable_providers = [*self._rest_providers, self._csv]

        for provider in saveable_providers:
            try:
                data = provider.fetch(province_code, municipio_name)
                self._snapshot.save(data, province_code, municipio_name)
                logger.info("fuel data via %s", provider.name)
                return data
            except ProviderError as exc:
                logger.warning("%s", exc)

        # L4 — snapshot
        try:
            data = self._snapshot.fetch(province_code, municipio_name)
            logger.info("fuel data via snapshot (cached)")
            return data
        except ProviderError as exc:
            logger.warning("%s", exc)

        # L5 — Precioil (optional)
        if self._config.enable_precioil_fallback:
            try:
                data = self._precioil.fetch(province_code, municipio_name)
                logger.info("fuel data via precioil")
                return data
            except ProviderError as exc:
                logger.warning("%s", exc)

        raise RuntimeError(
            f"All fuel price providers failed for province={province_code} "
            f"municipio={municipio_name or '(all)'}."
        )
