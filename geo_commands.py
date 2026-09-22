# Backwards-compat shim — use `geo.commands` directly
from geo.commands import *  # noqa: F401, F403
from geo.commands import register_handlers, build_aggregator
