"""
Tests for the multi-level fuel price provider fallback chain.

Run with:  pytest tests/test_fuel_providers.py -v
"""

import gzip
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from fuel_providers import (
    CompositeFuelProvider,
    OfficialCsvProvider,
    OfficialMirrorProvider,
    OfficialRestProvider,
    ProviderConfig,
    ProviderError,
    SnapshotProvider,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PAYLOAD = {
    "Fecha": "01/01/2026",
    "ListaEESSPrecio": [
        {
            "Rótulo": "REPSOL",
            "Dirección": "CALLE MAYOR 1",
            "Municipio": "MÁLAGA",
            "C.P.": "29001",
            "Latitud": "36,720",
            "Longitud (WGS84)": "-4,420",
            "Precio Gasolina 95 E5": "1,659",
            "Precio Gasoleo A": "1,489",
        }
    ],
}

SAMPLE_DATA = {
    "date": "01/01/2026",
    "stations": [
        {
            "name": "REPSOL",
            "address": "CALLE MAYOR 1",
            "town": "MÁLAGA",
            "postal_code": "29001",
            "lat": 36.72,
            "lon": -4.42,
            "gasoline_95": 1.659,
            "diesel": 1.489,
        }
    ],
}


def _cfg(**kwargs) -> ProviderConfig:
    defaults = {
        "rest_primary_url": "https://primary.example",
        "rest_secondary_url": "https://secondary.example",
        "csv_url": "",
        "snapshot_directory": "",
        "cache_retention_days": 30,
        "enable_precioil_fallback": False,
        "precioil_api_url": "",
        "request_timeout": 5,
    }
    defaults.update(kwargs)
    return ProviderConfig(**defaults)


def _mock_response(json_data=None, status=200, exc=None):
    if exc:
        m = MagicMock()
        m.side_effect = exc
        return m
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(response=r)
    return r


# ---------------------------------------------------------------------------
# Scenario 1: L1 succeeds — returns data directly
# ---------------------------------------------------------------------------

class TestScenario1_PrimarySucceeds:
    def test_fetch_returns_data(self):
        cfg = _cfg()
        composite = CompositeFuelProvider(cfg)

        with patch.object(
            composite._rest_providers[0], "fetch", return_value=SAMPLE_DATA
        ) as mock_fetch:
            result = composite.fetch("29", "MÁLAGA")

        mock_fetch.assert_called_once_with("29", "MÁLAGA")
        assert result["date"] == "01/01/2026"
        assert len(result["stations"]) == 1

    def test_secondary_not_called_when_primary_works(self):
        cfg = _cfg()
        composite = CompositeFuelProvider(cfg)

        with patch.object(
            composite._rest_providers[0], "fetch", return_value=SAMPLE_DATA
        ):
            with patch.object(composite._rest_providers[1], "fetch") as mock_secondary:
                composite.fetch("29")

        mock_secondary.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 2: L1 fails → L2 succeeds
# ---------------------------------------------------------------------------

class TestScenario2_MirrorFallback:
    def test_falls_back_to_mirror(self):
        cfg = _cfg()
        composite = CompositeFuelProvider(cfg)

        with patch.object(
            composite._rest_providers[0],
            "fetch",
            side_effect=ProviderError("primary down"),
        ):
            with patch.object(
                composite._rest_providers[1], "fetch", return_value=SAMPLE_DATA
            ) as mock_mirror:
                result = composite.fetch("29", "MÁLAGA")

        mock_mirror.assert_called_once()
        assert result["stations"][0]["name"] == "REPSOL"

    def test_ssl_error_triggers_fallback(self):
        cfg = _cfg()
        composite = CompositeFuelProvider(cfg)

        ssl_exc = requests.exceptions.SSLError("UNEXPECTED_EOF_WHILE_READING")
        with patch.object(
            composite._rest_providers[0],
            "fetch",
            side_effect=ProviderError(f"ssl: {ssl_exc}"),
        ):
            with patch.object(
                composite._rest_providers[1], "fetch", return_value=SAMPLE_DATA
            ):
                result = composite.fetch("29")

        assert result["date"] == "01/01/2026"


# ---------------------------------------------------------------------------
# Scenario 3: L1 + L2 fail → L3 CSV succeeds
# ---------------------------------------------------------------------------

CSV_CONTENT = (
    "Fecha;Rótulo;Dirección;Municipio;C.P.;Latitud;Longitud (WGS84);"
    "Precio Gasolina 95 E5;Precio Gasoleo A\n"
    "01/01/2026;REPSOL;CALLE MAYOR 1;MÁLAGA;29001;36,720;-4,420;1,659;1,489\n"
)


class TestScenario3_CsvFallback:
    def test_falls_back_to_csv(self):
        cfg = _cfg(csv_url="https://csv.example/data.csv")
        composite = CompositeFuelProvider(cfg)

        for p in composite._rest_providers:
            p.fetch = MagicMock(side_effect=ProviderError("rest down"))

        mock_resp = MagicMock()
        mock_resp.content = CSV_CONTENT.encode("utf-8")
        mock_resp.raise_for_status = MagicMock()

        with patch.object(
            composite._csv._session, "get", return_value=mock_resp
        ):
            result = composite.fetch("29", "MÁLAGA")

        assert len(result["stations"]) == 1
        assert result["stations"][0]["name"] == "REPSOL"

    def test_csv_skipped_when_url_not_configured(self):
        cfg = _cfg()  # csv_url="" by default
        composite = CompositeFuelProvider(cfg)

        for p in composite._rest_providers:
            p.fetch = MagicMock(side_effect=ProviderError("rest down"))

        with pytest.raises(RuntimeError, match="All fuel price providers failed"):
            composite.fetch("29", "MÁLAGA")


# ---------------------------------------------------------------------------
# Scenario 4: L1–L3 fail → L4 snapshot loaded
# ---------------------------------------------------------------------------

class TestScenario4_SnapshotFallback:
    def test_loads_snapshot(self):
        from datetime import date as _date
        with tempfile.TemporaryDirectory() as tmpdir:
            # _normalize("MÁLAGA") → "MALAGA"; safe-name keeps alphanums unchanged
            snap = Path(tmpdir) / f"fuel_29_MALAGA_{_date.today().isoformat()}.json.gz"
            with gzip.open(snap, "wt") as fh:
                json.dump(SAMPLE_DATA, fh)

            cfg = _cfg(snapshot_directory=tmpdir)
            composite = CompositeFuelProvider(cfg)

            for p in composite._rest_providers:
                p.fetch = MagicMock(side_effect=ProviderError("rest down"))
            composite._csv.fetch = MagicMock(side_effect=ProviderError("csv down"))

            result = composite.fetch("29", "MÁLAGA")

        assert result["date"] == "01/01/2026"

    def test_snapshot_saved_after_successful_fetch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = _cfg(snapshot_directory=tmpdir)
            composite = CompositeFuelProvider(cfg)

            with patch.object(
                composite._rest_providers[0], "fetch", return_value=SAMPLE_DATA
            ):
                composite.fetch("29", "MÁLAGA")

            snaps = list(Path(tmpdir).glob("fuel_29_*.json.gz"))
            assert len(snaps) == 1


# ---------------------------------------------------------------------------
# Scenario 5: L1–L4 fail, Precioil disabled → RuntimeError
# ---------------------------------------------------------------------------

class TestScenario5_AllFail:
    def test_raises_when_all_fail(self):
        cfg = _cfg()
        composite = CompositeFuelProvider(cfg)

        for p in composite._rest_providers:
            p.fetch = MagicMock(side_effect=ProviderError("down"))
        composite._csv.fetch = MagicMock(side_effect=ProviderError("down"))
        composite._snapshot.fetch = MagicMock(side_effect=ProviderError("no snapshot"))

        with pytest.raises(RuntimeError, match="All fuel price providers failed"):
            composite.fetch("29", "MÁLAGA")


# ---------------------------------------------------------------------------
# Scenario 6: L1–L4 fail, Precioil enabled + succeeds
# ---------------------------------------------------------------------------

class TestScenario6_PrecioilFallback:
    def test_falls_back_to_precioil(self):
        cfg = _cfg(
            enable_precioil_fallback=True,
            precioil_api_url="https://precioil.example/api",
        )
        composite = CompositeFuelProvider(cfg)

        for p in composite._rest_providers:
            p.fetch = MagicMock(side_effect=ProviderError("down"))
        composite._csv.fetch = MagicMock(side_effect=ProviderError("down"))
        composite._snapshot.fetch = MagicMock(side_effect=ProviderError("no snapshot"))

        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_DATA
        mock_resp.raise_for_status = MagicMock()

        with patch.object(
            composite._precioil._session, "get", return_value=mock_resp
        ):
            result = composite.fetch("29", "MÁLAGA")

        assert result["stations"][0]["name"] == "REPSOL"

    def test_precioil_not_called_when_disabled(self):
        cfg = _cfg(enable_precioil_fallback=False)
        composite = CompositeFuelProvider(cfg)

        for p in composite._rest_providers:
            p.fetch = MagicMock(side_effect=ProviderError("down"))
        composite._csv.fetch = MagicMock(side_effect=ProviderError("down"))
        composite._snapshot.fetch = MagicMock(side_effect=ProviderError("no snapshot"))

        with patch.object(composite._precioil, "fetch") as mock_precioil:
            with pytest.raises(RuntimeError):
                composite.fetch("29")

        mock_precioil.assert_not_called()
