SUPPORTED_LANGUAGES = {"en": "English", "es": "Español", "ru": "Русский"}

_T = {
    "en": {
        "welcome": (
            "⛽ Geo Info Bot\n\n"
            "Fuel:\n"
            "  /fuel — current prices  /check — same\n"
            "  /home <lat> <lon> — set home location\n"
            "  /province <name> — change province (e.g. Madrid)\n"
            "  /municipio <name> — change municipality\n"
            "  /predict — tomorrow's price forecast\n"
            "  /statistics — price history\n\n"
            "Environment:\n"
            "  /weather — air conditions\n"
            "  /sea — sea temperature & waves\n"
            "  /air — air quality index\n"
            "  /pollen — pollen levels\n"
            "  /fire — active forest fires nearby\n\n"
            "City:\n"
            "  /electricity — electricity spot price\n"
            "  /ev — EV charging stations\n"
            "  /traffic — traffic incidents\n"
            "  /beaches — beach quality\n"
            "  /parking — parking lots\n\n"
            "Overview:\n"
            "  /around — combined snapshot\n"
            "  /location — your current location\n\n"
            "Alerts:\n"
            "  /earthquake — latest earthquakes in the region\n\n"
            "Settings:\n"
            "  /time <HH:MM> — daily notification time\n"
            "  /timezone <+N> — timezone offset (e.g. +2, -3)\n"
            "  /language — change language\n"
            "  /stop — disable daily notifications"
        ),
        "fetching": "Fetching prices...",
        "fetch_error": "Error fetching prices: {e}",
        "home_set": "Home set to {lat}, {lon}. Use /check to see nearest station.",
        "home_usage": "Usage: /home <lat> <lon>\nExample: /home 36.7213 -4.4214",
        "home_invalid_numbers": "Both lat and lon must be numbers.",
        "home_invalid_range": "Invalid coordinates. Lat: -90..90, Lon: -180..180.",
        "municipio_usage": "Usage: /municipio <name>\nExample: /municipio Torremolinos",
        "municipio_not_found": "Municipality '{name}' not found in province {province}. No changes made.",
        "municipio_updated": "Municipality updated to {name}.",
        "province_usage": "Usage: /province <name>\nExample: /province Madrid\nExample: /province Zaragoza",
        "province_not_found": "Province '{name}' not found. Try a Spanish province name, e.g. Madrid, Malaga, Zaragoza, Sevilla.",
        "province_updated": "Province changed to {name} (code {code}). Municipality cleared — use /municipio to set one.",
        "time_usage": "Usage: /time <HH:MM>\nExample: /time 08:30",
        "time_invalid": "Invalid time format. Use HH:MM, e.g. /time 08:30",
        "time_set": "Daily notification time set to {time}.",
        "language_choose": "Choose language:",
        "language_set": "Language set to English.",
        "stop_done": "Daily notifications disabled. You can still use /check any time.\nSend /start to re-enable them.",
        "weather_error": "Error fetching weather: {e}",
        "no_history": "No price history yet. Use /check to start recording data.",
        "not_enough_history": "Not enough history yet (need at least {n} days of data). Use /check daily to build up history.",
        # fuel message
        "fuel_header": "⛽ Fuel prices — {scope} ({date})",
        "fuel_avg": "{label} (avg): {price} €/L",
        "cheapest": "Cheapest {label}: {price} €/L — {name}",
        "nearest_header": "📍 Nearest station to you: {name} ({dist:.1f} km)",
        "gasoline_95": "Gasoline 95",
        "diesel": "Diesel",
        "stations_reporting": "({n} stations reporting)",
        # statistics
        "stats_header": "📊 Price Statistics — {scope}",
        "stats_latest": "  Latest:         {val}",
        "stats_week_ago": "  Week ago:       {val}{trend}",
        "stats_this_month": "  This month avg: {val}",
        "stats_last_month": "  Last month avg: {val}",
        "stats_footer": "(Based on {n} days of recorded data)",
        # predict
        "predict_header": "📈 Price forecast for {date} — {scope}",
        "predict_caveat": "⚠️ Based on {n}-day linear trend. Fuel prices are volatile — treat as rough estimate only.",
        # weather
        "weather_header": "🌤 Weather ({lat:.4f}, {lon:.4f})",
        # geo platform
        "geo_error": "Error fetching {provider}: {e}",
        "geo_no_data": "No data available.",
        "geo_around_fetching": "Fetching all data sources...",
        "geo_location_set": "📍 Your location: {lat:.4f}, {lon:.4f}",
        "geo_location_default": "📍 Default location: {lat:.4f}, {lon:.4f}. Use /home <lat> <lon> to set yours.",
        "geo_air_temp": "Air",
        "geo_wind": "Wind",
        "geo_humidity": "Humidity",
        "geo_sea_header": "Sea conditions",
        "geo_sea_temp": "Sea temp",
        "geo_waves": "Waves",
        "geo_air_header": "Air quality",
        "geo_aqi": "AQI",
        "geo_pollen_header": "Pollen levels",
        "geo_electricity_header": "Electricity price today (REE)",
        "geo_avg": "Avg",
        "geo_min": "Min",
        "geo_max": "Max",
        "geo_ev_header": "{count} EV stations within {radius} km",
        "geo_fire_none": "No active fires within {radius} km",
        "geo_fire_header": "⚠️ {count} active fire(s) within {radius} km",
        "geo_traffic_clear": "No traffic incidents nearby",
        "geo_traffic_header": "{count} traffic incident(s) nearby",
        "geo_beaches_none": "No beach data within {radius} km",
        "geo_beaches_header": "{count} beach(es) within {radius} km",
        "geo_parking_none": "No parking lots found nearby",
        "geo_parking_header": "{count} parking lot(s) nearby",
        # earthquake
        "earthquake_fetching": "Fetching latest earthquakes…",
        "earthquake_none": "No recent earthquakes in the monitored region.",
        "earthquake_message": (
            "\U0001F30D <b>Earthquake detected</b>\n"
            "Magnitude: <b>{mag} {magtype}</b>\n"
            "Location: {location}\n"
            "Depth: {depth} km\n"
            "Time: {time_str}\n"
            '<a href="{maps_url}">View on map</a>'
        ),
        # timezone
        "timezone_usage": "Usage: /timezone <offset>\nExamples: /timezone +2  /timezone -3  /timezone 0\nValid range: -12 to +14",
        "timezone_set": "Timezone set to UTC{offset}.",
        "timezone_invalid": "Invalid timezone. Use a number like +2, -3 or 0. Range: -12 to +14.",
        # daily weather forecast
        "daily_forecast_header": "Weather today",
        "daily_temp": "Temperature",
        "daily_rain": "Rain",
        "daily_wind": "Wind",
        "daily_uv": "UV",
        "daily_sunrise": "Sunrise",
        "daily_sunset": "Sunset",
        "daily_waves": "Waves",
        "hourly_forecast_header": "⏰ Hourly forecast",
    },
    "es": {
        "welcome": (
            "⛽ Bot de Información Geográfica\n\n"
            "Combustible:\n"
            "  /fuel — precios actuales  /check — igual\n"
            "  /home <lat> <lon> — establecer ubicación\n"
            "  /province <nombre> — cambiar provincia (p. ej. Madrid)\n"
            "  /municipio <nombre> — cambiar municipio\n"
            "  /predict — previsión mañana\n"
            "  /statistics — historial de precios\n\n"
            "Medio ambiente:\n"
            "  /weather — condiciones del aire\n"
            "  /sea — temperatura mar y oleaje\n"
            "  /air — índice calidad del aire\n"
            "  /pollen — niveles de polen\n"
            "  /fire — incendios forestales cercanos\n\n"
            "Ciudad:\n"
            "  /electricity — precio electricidad\n"
            "  /ev — cargadores eléctricos\n"
            "  /traffic — incidencias de tráfico\n"
            "  /beaches — calidad de playas\n"
            "  /parking — aparcamientos\n\n"
            "Resumen:\n"
            "  /around — resumen combinado\n"
            "  /location — tu ubicación actual\n\n"
            "Alertas:\n"
            "  /earthquake — últimos terremotos en la región\n\n"
            "Ajustes:\n"
            "  /time <HH:MM> — hora de notificación\n"
            "  /timezone <+N> — desfase horario (p. ej. +2, -3)\n"
            "  /language — cambiar idioma\n"
            "  /stop — desactivar notificaciones"
        ),
        "fetching": "Obteniendo precios...",
        "fetch_error": "Error al obtener precios: {e}",
        "home_set": "Ubicación establecida en {lat}, {lon}. Usa /check para ver la gasolinera más cercana.",
        "home_usage": "Uso: /home <lat> <lon>\nEjemplo: /home 36.7213 -4.4214",
        "home_invalid_numbers": "Latitud y longitud deben ser números.",
        "home_invalid_range": "Coordenadas no válidas. Lat: -90..90, Lon: -180..180.",
        "municipio_usage": "Uso: /municipio <nombre>\nEjemplo: /municipio Torremolinos",
        "municipio_not_found": "Municipio '{name}' no encontrado en la provincia {province}. Sin cambios.",
        "municipio_updated": "Municipio actualizado a {name}.",
        "province_usage": "Uso: /province <nombre>\nEjemplo: /province Madrid\nEjemplo: /province Zaragoza",
        "province_not_found": "Provincia '{name}' no encontrada. Prueba con un nombre de provincia española, p. ej. Madrid, Malaga, Zaragoza, Sevilla.",
        "province_updated": "Provincia cambiada a {name} (código {code}). Municipio borrado — usa /municipio para establecer uno.",
        "time_usage": "Uso: /time <HH:MM>\nEjemplo: /time 08:30",
        "time_invalid": "Formato de hora no válido. Usa HH:MM, p. ej. /time 08:30",
        "time_set": "Hora de notificación diaria establecida a las {time}.",
        "language_choose": "Elige idioma:",
        "language_set": "Idioma establecido en Español.",
        "stop_done": "Notificaciones diarias desactivadas. Puedes usar /check en cualquier momento.\nEnvía /start para reactivarlas.",
        "weather_error": "Error al obtener el tiempo: {e}",
        "no_history": "Sin historial de precios. Usa /check para empezar a registrar datos.",
        "not_enough_history": "Historial insuficiente (se necesitan al menos {n} días). Usa /check cada día.",
        "fuel_header": "⛽ Precios de combustible — {scope} ({date})",
        "fuel_avg": "{label} (media): {price} €/L",
        "cheapest": "Más barato {label}: {price} €/L — {name}",
        "nearest_header": "📍 Gasolinera más cercana: {name} ({dist:.1f} km)",
        "gasoline_95": "Gasolina 95",
        "diesel": "Diésel",
        "stations_reporting": "({n} estaciones reportando)",
        "stats_header": "📊 Estadísticas de precios — {scope}",
        "stats_latest": "  Último:          {val}",
        "stats_week_ago": "  Hace una semana: {val}{trend}",
        "stats_this_month": "  Media este mes:  {val}",
        "stats_last_month": "  Media mes ant.:  {val}",
        "stats_footer": "(Basado en {n} días de datos registrados)",
        "predict_header": "📈 Previsión para {date} — {scope}",
        "predict_caveat": "⚠️ Basado en tendencia lineal de {n} días. Los precios son volátiles — solo orientativo.",
        "weather_header": "🌤 Tiempo ({lat:.4f}, {lon:.4f})",
        # geo platform
        "geo_error": "Error al obtener {provider}: {e}",
        "geo_no_data": "Sin datos disponibles.",
        "geo_around_fetching": "Obteniendo todas las fuentes de datos...",
        "geo_location_set": "📍 Tu ubicación: {lat:.4f}, {lon:.4f}",
        "geo_location_default": "📍 Ubicación por defecto: {lat:.4f}, {lon:.4f}. Usa /home <lat> <lon> para establecer la tuya.",
        "geo_air_temp": "Aire",
        "geo_wind": "Viento",
        "geo_humidity": "Humedad",
        "geo_sea_header": "Condiciones marinas",
        "geo_sea_temp": "Temp. mar",
        "geo_waves": "Oleaje",
        "geo_air_header": "Calidad del aire",
        "geo_aqi": "ICA",
        "geo_pollen_header": "Niveles de polen",
        "geo_electricity_header": "Precio electricidad hoy (REE)",
        "geo_avg": "Media",
        "geo_min": "Mín",
        "geo_max": "Máx",
        "geo_ev_header": "{count} cargadores eléctricos a menos de {radius} km",
        "geo_fire_none": "Sin incendios activos a menos de {radius} km",
        "geo_fire_header": "⚠️ {count} incendio(s) activo(s) a menos de {radius} km",
        "geo_traffic_clear": "Sin incidencias de tráfico cercanas",
        "geo_traffic_header": "{count} incidencia(s) de tráfico cercanas",
        "geo_beaches_none": "Sin datos de playas a menos de {radius} km",
        "geo_beaches_header": "{count} playa(s) a menos de {radius} km",
        "geo_parking_none": "Sin aparcamientos encontrados cercanos",
        "geo_parking_header": "{count} aparcamiento(s) cercano(s)",
        # earthquake
        "earthquake_fetching": "Obteniendo últimos terremotos…",
        "earthquake_none": "No hay terremotos recientes en la región monitoreada.",
        "earthquake_message": (
            "\U0001F30D <b>Terremoto detectado</b>\n"
            "Magnitud: <b>{mag} {magtype}</b>\n"
            "Ubicación: {location}\n"
            "Profundidad: {depth} km\n"
            "Hora: {time_str}\n"
            '<a href="{maps_url}">Ver en el mapa</a>'
        ),
        # timezone
        "timezone_usage": "Uso: /timezone <desfase>\nEjemplos: /timezone +2  /timezone -3  /timezone 0\nRango válido: -12 a +14",
        "timezone_set": "Zona horaria establecida en UTC{offset}.",
        "timezone_invalid": "Zona horaria no válida. Usa un número como +2, -3 o 0. Rango: -12 a +14.",
        # daily weather forecast
        "daily_forecast_header": "Tiempo hoy",
        "daily_temp": "Temperatura",
        "daily_rain": "Lluvia",
        "daily_wind": "Viento",
        "daily_uv": "UV",
        "daily_sunrise": "Amanecer",
        "daily_sunset": "Atardecer",
        "daily_waves": "Oleaje",
        "hourly_forecast_header": "⏰ Previsión horaria",
    },
    "ru": {
        "welcome": (
            "⛽ Гео-информационный бот\n\n"
            "Топливо:\n"
            "  /fuel — текущие цены  /check — то же\n"
            "  /home <lat> <lon> — домашнее местоположение\n"
            "  /province <название> — сменить провинцию (напр. Madrid)\n"
            "  /municipio <название> — изменить муниципалитет\n"
            "  /predict — прогноз на завтра\n"
            "  /statistics — история цен\n\n"
            "Окружающая среда:\n"
            "  /weather — погода\n"
            "  /sea — температура моря и волны\n"
            "  /air — индекс качества воздуха\n"
            "  /pollen — уровень пыльцы\n"
            "  /fire — лесные пожары поблизости\n\n"
            "Город:\n"
            "  /electricity — цена электроэнергии\n"
            "  /ev — зарядные станции\n"
            "  /traffic — дорожные инциденты\n"
            "  /beaches — качество пляжей\n"
            "  /parking — парковки\n\n"
            "Обзор:\n"
            "  /around — сводка всех данных\n"
            "  /location — текущее местоположение\n\n"
            "Оповещения:\n"
            "  /earthquake — последние землетрясения в регионе\n\n"
            "Настройки:\n"
            "  /time <ЧЧ:ММ> — время уведомления\n"
            "  /timezone <+N> — смещение часового пояса (напр. +2, -3)\n"
            "  /language — сменить язык\n"
            "  /stop — отключить уведомления"
        ),
        "fetching": "Получаю цены...",
        "fetch_error": "Ошибка получения цен: {e}",
        "home_set": "Домашнее местоположение установлено: {lat}, {lon}. Используйте /check для ближайшей АЗС.",
        "home_usage": "Использование: /home <lat> <lon>\nПример: /home 36.7213 -4.4214",
        "home_invalid_numbers": "Широта и долгота должны быть числами.",
        "home_invalid_range": "Неверные координаты. Широта: -90..90, Долгота: -180..180.",
        "municipio_usage": "Использование: /municipio <название>\nПример: /municipio Torremolinos",
        "municipio_not_found": "Муниципалитет '{name}' не найден в провинции {province}. Изменений нет.",
        "municipio_updated": "Муниципалитет обновлён: {name}.",
        "province_usage": "Использование: /province <название>\nПример: /province Madrid\nПример: /province Zaragoza",
        "province_not_found": "Провинция '{name}' не найдена. Попробуйте название испанской провинции, например Madrid, Malaga, Zaragoza, Sevilla.",
        "province_updated": "Провинция изменена на {name} (код {code}). Муниципалитет сброшен — используйте /municipio для выбора.",
        "time_usage": "Использование: /time <ЧЧ:ММ>\nПример: /time 08:30",
        "time_invalid": "Неверный формат времени. Используйте ЧЧ:ММ, например /time 08:30",
        "time_set": "Время ежедневного уведомления установлено на {time}.",
        "language_choose": "Выберите язык:",
        "language_set": "Язык изменён на Русский.",
        "stop_done": "Ежедневные уведомления отключены. Команда /check доступна в любое время.\nОтправьте /start, чтобы включить снова.",
        "weather_error": "Ошибка получения погоды: {e}",
        "no_history": "История цен отсутствует. Используйте /check для начала записи данных.",
        "not_enough_history": "Недостаточно данных (нужно минимум {n} дней). Используйте /check каждый день.",
        "fuel_header": "⛽ Цены на топливо — {scope} ({date})",
        "fuel_avg": "{label} (средняя): {price} €/л",
        "cheapest": "Дешевле всего {label}: {price} €/л — {name}",
        "nearest_header": "📍 Ближайшая АЗС: {name} ({dist:.1f} км)",
        "gasoline_95": "Бензин 95",
        "diesel": "Дизель",
        "stations_reporting": "({n} станций в отчёте)",
        "stats_header": "📊 Статистика цен — {scope}",
        "stats_latest": "  Последняя:       {val}",
        "stats_week_ago": "  Неделю назад:    {val}{trend}",
        "stats_this_month": "  Ср. этот месяц:  {val}",
        "stats_last_month": "  Ср. прошл. мес.: {val}",
        "stats_footer": "(На основе {n} дней данных)",
        "predict_header": "📈 Прогноз на {date} — {scope}",
        "predict_caveat": "⚠️ На основе линейного тренда за {n} дней. Цены волатильны — только ориентир.",
        "weather_header": "🌤 Погода ({lat:.4f}, {lon:.4f})",
        # geo platform
        "geo_error": "Ошибка получения {provider}: {e}",
        "geo_no_data": "Данные недоступны.",
        "geo_around_fetching": "Получаю данные из всех источников...",
        "geo_location_set": "📍 Ваше местоположение: {lat:.4f}, {lon:.4f}",
        "geo_location_default": "📍 Местоположение по умолчанию: {lat:.4f}, {lon:.4f}. Используйте /home <lat> <lon> для установки своего.",
        "geo_air_temp": "Воздух",
        "geo_wind": "Ветер",
        "geo_humidity": "Влажность",
        "geo_sea_header": "Морские условия",
        "geo_sea_temp": "Темп. моря",
        "geo_waves": "Волны",
        "geo_air_header": "Качество воздуха",
        "geo_aqi": "ИКВ",
        "geo_pollen_header": "Уровень пыльцы",
        "geo_electricity_header": "Цена электроэнергии сегодня (REE)",
        "geo_avg": "Средняя",
        "geo_min": "Мин",
        "geo_max": "Макс",
        "geo_ev_header": "{count} зарядных станций в радиусе {radius} км",
        "geo_fire_none": "Активных пожаров в радиусе {radius} км нет",
        "geo_fire_header": "⚠️ {count} активный(-ых) пожар(ов) в радиусе {radius} км",
        "geo_traffic_clear": "Дорожных инцидентов поблизости нет",
        "geo_traffic_header": "{count} дорожный(-ых) инцидент(ов) поблизости",
        "geo_beaches_none": "Данных о пляжах в радиусе {radius} км нет",
        "geo_beaches_header": "{count} пляж(ей) в радиусе {radius} км",
        "geo_parking_none": "Парковок поблизости не найдено",
        "geo_parking_header": "{count} парковка(-ок) поблизости",
        # earthquake
        "earthquake_fetching": "Получаю данные о последних землетрясениях…",
        "earthquake_none": "Последних землетрясений в отслеживаемом регионе нет.",
        "earthquake_message": (
            "\U0001F30D <b>Обнаружено землетрясение</b>\n"
            "Магнитуда: <b>{mag} {magtype}</b>\n"
            "Местоположение: {location}\n"
            "Глубина: {depth} км\n"
            "Время: {time_str}\n"
            '<a href="{maps_url}">Показать на карте</a>'
        ),
        # timezone
        "timezone_usage": "Использование: /timezone <смещение>\nПримеры: /timezone +2  /timezone -3  /timezone 0\nДопустимый диапазон: от -12 до +14",
        "timezone_set": "Часовой пояс установлен: UTC{offset}.",
        "timezone_invalid": "Неверный часовой пояс. Введите число, например +2, -3 или 0. Диапазон: от -12 до +14.",
        # daily weather forecast
        "daily_forecast_header": "Погода сегодня",
        "daily_temp": "Температура",
        "daily_rain": "Дождь",
        "daily_wind": "Ветер",
        "daily_uv": "УФ",
        "daily_sunrise": "Восход",
        "daily_sunset": "Закат",
        "daily_waves": "Волны",
        "hourly_forecast_header": "⏰ Почасовой прогноз",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    text = _T.get(lang, _T["en"]).get(key) or _T["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
