# Backwards-compat shim — use `fuel.providers` directly
from fuel.providers import *  # noqa: F401, F403
from fuel.providers import (
    ProviderConfig, ProviderError, CompositeFuelProvider,
    OfficialRestProvider, OfficialMirrorProvider,
    OfficialCsvProvider, SnapshotProvider, PrecioilProvider,
)
