"""
macros_conditions.py — движок условий для макросов Сильфиетты
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Использование в macros.py — просто добавь "if" к любому действию:

    {"type": "open_url", "url": "https://...", "if": "browser not running"}
    {"type": "launch_app", "cmd": "discord",   "if": "discord not running"}
    {"type": "notify", ...,                    "if": "evening"}
    {"type": "shell", ...,                     "if": "пятница"}

Поддерживаемые условия (русский и английский):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Процессы:
    "steam running"          / "steam запущен"
    "steam not running"      / "steam не запущен"
    "browser running"        / "браузер запущен"
    "browser not running"    / "браузер не запущен"
    "discord running"        / "discord запущен"
    "discord not running"    / "discord не запущен"
    "spotify running"        / "spotify запущен"
    "spotify not running"    / "spotify не запущен"
    "<любое слово> running"  — проверяет есть ли процесс с таким именем
    "<любое слово> not running"

  Время суток:
    "morning"  / "утро"      — 06:00–11:59
    "day"      / "день"      — 12:00–17:59
    "evening"  / "вечер"     — 18:00–22:59
    "night"    / "ночь"      — 23:00–05:59

  День недели:
    "weekday"  / "будний"    — пн–пт
    "weekend"  / "выходной"  — сб–вс
    "monday"   / "понедельник"
    "tuesday"  / "вторник"
    "wednesday"/ "среда"
    "thursday" / "четверг"
    "friday"   / "пятница"
    "saturday" / "суббота"
    "sunday"   / "воскресенье"

  Отрицание — добавь "not" / "не" перед любым условием:
    "not evening"    / "не вечер"
    "not weekend"    / "не выходной"
    "not friday"     / "не пятница"

  Комбинации через "and" / "и":
    "evening and friday"
    "steam not running and weekend"
    "вечер и пятница"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import re
import subprocess
from datetime import datetime
from typing import Optional


# ── Таблицы синонимов ─────────────────────────────────────────────────────────

# Процессы: ключевое слово → список имён процессов для поиска
PROCESS_ALIASES = {
    "steam":    ["steam", "steam.sh", "steamwebhelper"],
    "browser":  ["brave", "firefox", "chromium", "chrome", "opera"],
    "discord":  ["discord", "Discord"],
    "spotify":  ["spotify", "Spotify"],
    "telegram": ["telegram", "telegram-desktop", "Telegram"],
    "vscode":   ["code", "code-oss"],
    "vlc":      ["vlc"],
    "htop":     ["htop"],
    "konsole":  ["konsole"],
}

# Время суток: имя → (час_от, час_до включительно)
TIME_OF_DAY = {
    "morning":  (6,  11),
    "утро":     (6,  11),
    "день":     (12, 17),
    "day":      (12, 17),
    "вечер":    (18, 22),
    "evening":  (18, 22),
    "ночь":     (23,  5),   # особый случай — переходит через полночь
    "night":    (23,  5),
}

# День недели: имя → weekday() (0=пн, 6=вс)
WEEKDAYS = {
    "monday":        0, "понедельник": 0,
    "tuesday":       1, "вторник":     1,
    "wednesday":     2, "среда":       2,
    "thursday":      3, "четверг":     3,
    "friday":        4, "пятница":     4,
    "saturday":      5, "суббота":     5,
    "sunday":        6, "воскресенье": 6,
}


# ── Проверка процесса ─────────────────────────────────────────────────────────

def _is_process_running(keyword: str) -> bool:
    """
    Проверяет запущен ли процесс по ключевому слову.
    Сначала ищет в PROCESS_ALIASES, потом ищет напрямую по имени.
    """
    keyword = keyword.lower().strip()

    # Известные алиасы
    names = PROCESS_ALIASES.get(keyword, [keyword])

    try:
        result = subprocess.run(
            ["pgrep", "-f", keyword],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass

    # Fallback через ps
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True
        )
        ps_output = result.stdout.lower()
        for name in names:
            if name.lower() in ps_output:
                return True
    except Exception:
        pass

    return False


# ── Проверка времени суток ────────────────────────────────────────────────────

def _check_time_of_day(name: str) -> bool:
    """Проверяет текущее время суток."""
    now = datetime.now()
    h   = now.hour

    if name not in TIME_OF_DAY:
        return False

    start, end = TIME_OF_DAY[name]

    # Ночь переходит через полночь
    if start > end:
        return h >= start or h <= end
    return start <= h <= end


# ── Проверка дня недели ───────────────────────────────────────────────────────

def _check_weekday(name: str) -> bool:
    """Проверяет текущий день недели."""
    now = datetime.now()
    wd  = now.weekday()   # 0 = пн

    if name == "weekday" or name == "будний":
        return wd <= 4
    if name == "weekend" or name == "выходной":
        return wd >= 5

    if name in WEEKDAYS:
        return wd == WEEKDAYS[name]

    return False


# ── Парсер одного условия ─────────────────────────────────────────────────────

def _eval_single(token: str) -> bool:
    """
    Вычисляет одно условие без AND/OR.
    Возвращает True если условие выполнено.
    """
    token = token.strip().lower()

    # ── Отрицание: "not X" / "не X" ──────────────────────────────────────
    negated = False
    for neg_prefix in ("not ", "не "):
        if token.startswith(neg_prefix):
            token   = token[len(neg_prefix):].strip()
            negated = True
            break

    # ── Процесс: "X running" / "X not running" ───────────────────────────
    #   "not running" уже снято выше если было "not X running"
    #   Но "X not running" — другая форма
    if token.endswith(" not running"):
        proc = token[: -len(" not running")].strip()
        result = not _is_process_running(proc)
        return (not result) if negated else result

    if token.endswith(" running"):
        proc = token[: -len(" running")].strip()
        result = _is_process_running(proc)
        return (not result) if negated else result

    # ── Время суток ───────────────────────────────────────────────────────
    if token in TIME_OF_DAY:
        result = _check_time_of_day(token)
        return (not result) if negated else result

    # ── День недели ───────────────────────────────────────────────────────
    if token in WEEKDAYS or token in ("weekday", "weekend", "будний", "выходной"):
        result = _check_weekday(token)
        return (not result) if negated else result

    # ── Неизвестное условие — True чтобы не блокировать макрос ───────────
    print(f"  ⚠ macros_conditions: неизвестное условие «{token}» → True")
    return True


# ── Главная функция проверки ──────────────────────────────────────────────────

def check_condition(condition: Optional[str]) -> bool:
    """
    Проверяет условие из поля "if" действия макроса.

    Если условие не задано (None / "") — возвращает True (выполнять).
    Если условие не выполнено — возвращает False (пропустить).

    Поддерживает:
      - одиночные условия: "steam not running"
      - AND через "and" / "и": "evening and friday"
      - NOT через "not" / "не": "not evening"
    """
    if not condition:
        return True

    original = condition
    condition = condition.strip()

    # Разбиваем по AND
    and_sep = re.compile(r"\s+(?:and|и)\s+", re.IGNORECASE)
    parts   = and_sep.split(condition)

    for part in parts:
        if not _eval_single(part.strip()):
            print(f"  ⏭ Условие не выполнено: «{original}» → пропускаю действие")
            return False

    return True


# ── Диагностика ───────────────────────────────────────────────────────────────

def debug_conditions():
    """Выводит состояние всех условий — для отладки."""
    now = datetime.now()
    print(f"\n=== Текущее состояние условий ===")
    print(f"Время:      {now.strftime('%H:%M')} ({now.strftime('%A')})")
    print()

    print("Время суток:")
    for name in ["утро", "день", "вечер", "ночь"]:
        mark = "✓" if _check_time_of_day(name) else "✗"
        print(f"  [{mark}] {name}")

    print("\nДень недели:")
    for name in ["понедельник", "вторник", "среда", "четверг",
                 "пятница", "суббота", "воскресенье"]:
        mark = "✓" if _check_weekday(name) else "✗"
        print(f"  [{mark}] {name}")
    mark = "✓" if _check_weekday("будний") else "✗"
    print(f"  [{mark}] будний")
    mark = "✓" if _check_weekday("выходной") else "✗"
    print(f"  [{mark}] выходной")

    print("\nПроцессы:")
    for name in PROCESS_ALIASES:
        running = _is_process_running(name)
        mark = "✓" if running else "✗"
        print(f"  [{mark}] {name}")

    print("\nПримеры проверки:")
    examples = [
        "steam not running",
        "browser running",
        "evening",
        "не вечер",
        "пятница",
        "вечер and пятница",
        "weekend",
        "steam running and evening",
    ]
    for ex in examples:
        result = check_condition(ex)
        mark = "✓ выполнить" if result else "⏭ пропустить"
        print(f"  «{ex}» → {mark}")


if __name__ == "__main__":
    debug_conditions()
