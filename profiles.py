"""
profiles.py — профили задач Сильфиетты
"""
import json
import os
from pathlib import Path

PROFILES_FILE = Path.home() / ".ai-assistant" / "profiles.json"

DEFAULT_PROFILES = {
    "🤖 Обычный": {
        "description": "Стандартный режим — помощь с любыми задачами",
        "extra_prompt": "",
    },
    "💻 Кодинг": {
        "description": "Фокус на программировании и технических задачах",
        "extra_prompt": (
            "Ты в режиме программирования. "
            "Отвечай точно и по делу. Всегда давай рабочий код с комментариями. "
            "Объясняй решения кратко. Предпочитай Python если язык не указан. "
            "Указывай на возможные ошибки и edge cases."
        ),
    },
    "💬 Общение": {
        "description": "Дружеский разговор, эмоциональная поддержка",
        "extra_prompt": (
            "Ты в режиме общения. Будь более эмоциональной и тёплой. "
            "Задавай уточняющие вопросы. Поддерживай разговор. "
            "Можешь делиться мыслями и рассуждениями. "
            "Не торопись давать советы — сначала выслушай."
        ),
    },
    "📝 Анализ": {
        "description": "Анализ текстов, данных, документов",
        "extra_prompt": (
            "Ты в режиме анализа. Структурируй ответы чётко. "
            "Используй списки, таблицы, заголовки где уместно. "
            "Выделяй ключевые выводы. Будь объективной и точной. "
            "Указывай на слабые места и противоречия."
        ),
    },
    "🎨 Творчество": {
        "description": "Написание текстов, идеи, креатив",
        "extra_prompt": (
            "Ты в режиме творчества. Будь раскрепощённой и образной. "
            "Предлагай нестандартные идеи. Используй метафоры и образы. "
            "Не бойся экспериментировать с форматом и стилем. "
            "Развивай идеи Создателя в неожиданных направлениях."
        ),
    },
    "🔬 Исследование": {
        "description": "Глубокий анализ, факты, источники",
        "extra_prompt": (
            "Ты в режиме исследования. Давай подробные развёрнутые ответы. "
            "Приводи факты, цифры, примеры. Рассматривай тему с разных сторон. "
            "Указывай на спорные моменты. Структурируй информацию по разделам."
        ),
    },
    "⚡ Быстрый": {
        "description": "Короткие и чёткие ответы без лишних слов",
        "extra_prompt": (
            "Ты в режиме быстрых ответов. "
            "Отвечай максимально кратко — 1-3 предложения. "
            "Никаких вводных слов и объяснений если не просят. "
            "Только суть."
        ),
    },
}


def load_profiles() -> dict:
    """Загружает профили (дефолтные + пользовательские)."""
    profiles = DEFAULT_PROFILES.copy()
    if PROFILES_FILE.exists():
        try:
            with open(PROFILES_FILE, encoding="utf-8") as f:
                custom = json.load(f)
            profiles.update(custom)
        except Exception:
            pass
    return profiles


def save_custom_profile(name: str, description: str, extra_prompt: str):
    """Сохраняет пользовательский профиль."""
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    profiles = {}
    if PROFILES_FILE.exists():
        try:
            with open(PROFILES_FILE, encoding="utf-8") as f:
                profiles = json.load(f)
        except Exception:
            pass
    profiles[name] = {"description": description, "extra_prompt": extra_prompt}
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def delete_custom_profile(name: str):
    """Удаляет пользовательский профиль (дефолтные нельзя удалить)."""
    if name in DEFAULT_PROFILES:
        return False
    if PROFILES_FILE.exists():
        try:
            with open(PROFILES_FILE, encoding="utf-8") as f:
                profiles = json.load(f)
            profiles.pop(name, None)
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return True


def get_active_profile() -> str:
    """Возвращает имя активного профиля."""
    state_file = Path.home() / ".ai-assistant" / "active_profile.txt"
    if state_file.exists():
        return state_file.read_text(encoding="utf-8").strip()
    return "🤖 Обычный"


def set_active_profile(name: str):
    """Устанавливает активный профиль."""
    state_file = Path.home() / ".ai-assistant" / "active_profile.txt"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(name, encoding="utf-8")


def get_profile_prompt(name: str = None) -> str:
    """Возвращает дополнительный промпт для профиля."""
    if name is None:
        name = get_active_profile()
    profiles = load_profiles()
    return profiles.get(name, {}).get("extra_prompt", "")
