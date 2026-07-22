SUPPORTED_LANGUAGES = {"en": "English", "es": "Español", "ru": "Русский"}

_T = {
    "en": {
        "welcome": (
            "⛽ Fuel Price Bot\n\n"
            "Commands:\n"
            "  /check — current prices\n"
            "  /home <lat> <lon> — set your home location\n"
            "  /municipio <name> — change municipality\n"
            "  /time <HH:MM> — set daily notification time\n"
            "  /language — change language\n"
            "  /predict — tomorrow's price forecast\n"
            "  /statistics — price history\n"
            "  /stop — disable daily notifications\n"
            "  /weather — current air & sea conditions"
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
    },
    "es": {
        "welcome": (
            "⛽ Bot de Precios de Combustible\n\n"
            "Comandos:\n"
            "  /check — precios actuales\n"
            "  /home <lat> <lon> — establecer ubicación\n"
            "  /municipio <nombre> — cambiar municipio\n"
            "  /time <HH:MM> — hora de notificación diaria\n"
            "  /language — cambiar idioma\n"
            "  /predict — previsión de precios para mañana\n"
            "  /statistics — historial de precios\n"
            "  /stop — desactivar notificaciones diarias\n"
            "  /weather — condiciones meteorológicas"
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
    },
    "ru": {
        "welcome": (
            "⛽ Бот цен на топливо\n\n"
            "Команды:\n"
            "  /check — текущие цены\n"
            "  /home <lat> <lon> — установить домашнее местоположение\n"
            "  /municipio <название> — изменить муниципалитет\n"
            "  /time <ЧЧ:ММ> — время ежедневного уведомления\n"
            "  /language — сменить язык\n"
            "  /predict — прогноз цен на завтра\n"
            "  /statistics — история цен\n"
            "  /stop — отключить ежедневные уведомления\n"
            "  /weather — погода и море"
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
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    text = _T.get(lang, _T["en"]).get(key) or _T["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
