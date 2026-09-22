# Backwards-compat shim — use `fuel` package directly
from fuel.api import *  # noqa: F401, F403
from fuel.api import (
    PROVINCE_CODES, find_province_code, get_municipio_id,
    fetch_stations, summarize, haversine_km, find_nearest_station,
    predict_next_price, format_message, _maps_link,
)
