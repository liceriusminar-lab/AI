"""
Плагин: Трекер настроения персонажа Сильфиетты
Сохраняет и отображает эмоциональное состояние ИИ.

Использование:
    "покажи настроение"
    "как ты себя чувствуешь"
    "настроение сильфиетты"
    "установи привязанность 75"
"""
import json
import os
import re

STATE_FILE = os.path.expanduser("~/.ai-assistant/mood_state.json")

VALUE_FIELDS = ["affection", "trust", "desire", "connection", "mood"]

FIELD_NAMES_RU = {
    "affection":  "Привязанность",
    "trust":      "Доверие",
    "desire":     "Желание",
    "connection": "Связь",
    "mood":       "Настроение",
}

DEFAULT_STATE = {
    "affection":  {"value": 50, "description": "Нейтральная"},
    "trust":      {"value": 50, "description": "Нейтральное"},
    "desire":     {"value": 10, "description": "Отсутствует"},
    "connection": {"value": 50, "description": "Знакомые"},
    "mood":       {"value": 60, "description": "Спокойное"},
    "last_thought": {"value": "Только познакомились…"},
}

BAR_FILLED = "█"
BAR_EMPTY  = "░"
BAR_LEN    = 10


def _load() -> dict:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {k: dict(v) for k, v in DEFAULT_STATE.items()}


def _save(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _bar(value: int) -> str:
    filled = round(value / 100 * BAR_LEN)
    return BAR_FILLED * filled + BAR_EMPTY * (BAR_LEN - filled)


def _format_state(state: dict) -> str:
    lines = ["💜 **Состояние Сильфиетты:**\n"]
    for field in VALUE_FIELDS:
        info  = state.get(field, {})
        val   = info.get("value", 0)
        desc  = info.get("description", "")
        name  = FIELD_NAMES_RU.get(field, field)
        bar   = _bar(val)
        lines.append(f"{name:15} [{bar}] {val}/100  _{desc}_")

    lt = state.get("last_thought", {})
    lt_val = lt.get("value", "") if isinstance(lt, dict) else str(lt)
    if lt_val:
        lines.append(f"\n💭 Последняя мысль: «{lt_val}»")
    return "\n".join(lines)


def _parse_set_command(query: str, state: dict) -> tuple[dict, str]:
    """Парсит команды типа 'установи привязанность 75'."""
    # Маппинг русских названий на ключи
    name_map = {
        "привязанность": "affection",
        "доверие":       "trust",
        "желание":       "desire",
        "связь":         "connection",
        "настроение":    "mood",
    }
    changed = []
    for ru_name, key in name_map.items():
        m = re.search(rf"{ru_name}\s+(\d+)", query.lower())
        if m:
            val = max(0, min(100, int(m.group(1))))
            state[key]["value"] = val
            changed.append(f"{FIELD_NAMES_RU[key]} → {val}")

    # Мысль
    m = re.search(r"мысль[:\s]+(.+)", query, re.IGNORECASE)
    if m:
        state["last_thought"] = {"value": m.group(1).strip()}
        changed.append("последняя мысль обновлена")

    return state, ", ".join(changed) if changed else ""


def run(query: str, context: dict) -> str:
    state = _load()

    q = query.lower()

    # Команда установки значений
    set_triggers = ["установи", "измени", "поставь", "set"]
    if any(t in q for t in set_triggers):
        state, changed = _parse_set_command(query, state)
        if changed:
            _save(state)
            return f"✅ Обновлено: {changed}\n\n" + _format_state(state)
        return "❌ Не понял команду. Пример: установи привязанность 75"

    # Сброс к дефолту
    if "сброс" in q or "reset" in q:
        state = {k: dict(v) for k, v in DEFAULT_STATE.items()}
        _save(state)
        return "🔄 Состояние сброшено к начальным значениям.\n\n" + _format_state(state)

    # По умолчанию — показываем состояние
    return _format_state(state)
