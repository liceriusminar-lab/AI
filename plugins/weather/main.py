"""Плагин погоды — использует wttr.in (без API ключа)"""
import urllib.request
import json

def run(query: str, context: dict) -> str:
    city = context.get("city", "Москва")
    # Пробуем извлечь город из запроса
    words = query.lower().replace("погода", "").replace("weather", "").replace("в", "").strip().split()
    if words:
        city = words[0].capitalize()
    try:
        url = f"https://wttr.in/{urllib.request.quote(city)}?format=j1&lang=ru"
        req = urllib.request.Request(url, headers={"User-Agent": "SylvietteAI/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        current = data["current_condition"][0]
        temp    = current["temp_C"]
        feels   = current["FeelsLikeC"]
        desc    = current["lang_ru"][0]["value"] if current.get("lang_ru") else current["weatherDesc"][0]["value"]
        humidity = current["humidity"]
        wind    = current["windspeedKmph"]
        return (
            f"Погода в {city}:\n"
            f"🌡 Температура: {temp}°C (ощущается как {feels}°C)\n"
            f"☁ {desc}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind} км/ч"
        )
    except Exception as e:
        return f"Не удалось получить погоду для {city}: {e}"
