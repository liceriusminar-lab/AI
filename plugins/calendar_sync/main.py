"""
Плагин: Синхронизация .ics календаря
Читает файлы iCalendar (.ics) из Evolution, Thunderbird и т.д.
и импортирует события в систему Сильфиетты.

Использование:
    "загрузи ics"
    "синхронизируй календарь"
    "события из evolution"
    "импорт календаря /path/to/file.ics"
"""
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Путь к системе напоминаний Сильфиетты
REMINDERS_FILE = Path.home() / ".ai-assistant" / "reminders.json"

# Стандартные пути к .ics файлам
DEFAULT_ICS_PATHS = [
    "~/.local/share/evolution/calendar/system/calendar.ics",
    "~/.local/share/gnome-calendar/local.ics",
    "~/.thunderbird/*/calendar-data/local.ics",
    "~/Calendar.ics",
]


def _install_if_missing():
    try:
        import icalendar
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "icalendar", "--break-system-packages", "-q"])


def _load_sylviette_calendar() -> list:
    try:
        if REMINDERS_FILE.exists():
            with open(REMINDERS_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_sylviette_calendar(events: list):
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def _find_ics_files() -> list[str]:
    """Ищет .ics файлы на стандартных путях."""
    found = []
    import glob
    for pattern in DEFAULT_ICS_PATHS:
        expanded = os.path.expanduser(pattern)
        matches  = glob.glob(expanded)
        found.extend(matches)
    return found


def _parse_ics(path: str) -> list[dict]:
    """Парсит .ics файл и возвращает список событий."""
    from icalendar import Calendar
    events = []
    try:
        with open(path, "rb") as f:
            cal = Calendar.from_ical(f.read())
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            try:
                summary = str(component.get("SUMMARY", "Без названия"))
                desc    = str(component.get("DESCRIPTION", ""))
                dtstart = component.get("DTSTART")
                if dtstart is None:
                    continue
                dt = dtstart.dt
                # Если только дата — делаем datetime
                if not isinstance(dt, datetime):
                    dt = datetime(dt.year, dt.month, dt.day, 9, 0)
                # Убираем timezone для совместимости
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                events.append({
                    "id":          str(uuid.uuid4())[:8],
                    "title":       summary,
                    "datetime":    dt.isoformat(),
                    "description": desc[:200],
                    "remind_min":  15,
                    "done":        False,
                    "created":     datetime.now().isoformat(),
                    "source":      "ics_import",
                })
            except Exception:
                continue
    except Exception as e:
        print(f"  ICS parse error {path}: {e}")
    return events


def _extract_path(query: str) -> str | None:
    """Ищет путь к файлу в запросе."""
    m = re.search(r"(/[^\s]+\.ics|~/[^\s]+\.ics)", query)
    return m.group(1) if m else None


def run(query: str, context: dict) -> str:
    _install_if_missing()

    try:
        from icalendar import Calendar
    except ImportError:
        return "❌ Не удалось установить icalendar. Запустите: pip install icalendar"

    # Проверяем указан ли конкретный файл
    explicit_path = _extract_path(query)

    if explicit_path:
        path = os.path.expanduser(explicit_path)
        if not os.path.exists(path):
            return f"❌ Файл не найден: `{path}`"
        ics_files = [path]
    else:
        ics_files = _find_ics_files()

    if not ics_files:
        return (
            "❌ .ics файлы не найдены на стандартных путях.\n\n"
            "Укажи путь явно: `загрузи ics ~/Мой_Календарь.ics`\n\n"
            "Стандартные пути:\n"
            + "\n".join(f"• `{p}`" for p in DEFAULT_ICS_PATHS)
        )

    # Загружаем существующие события Сильфиетты
    existing = _load_sylviette_calendar()
    existing_ids = {e.get("title", "") + e.get("datetime", "") for e in existing}

    imported_total = 0
    skipped_total  = 0
    report         = []
    now            = datetime.now()

    for ics_path in ics_files:
        events = _parse_ics(ics_path)
        new_events = []
        for e in events:
            key = e["title"] + e["datetime"]
            # Пропускаем прошедшие и дубликаты
            try:
                dt = datetime.fromisoformat(e["datetime"])
                if dt < now - timedelta(days=1):
                    skipped_total += 1
                    continue
            except Exception:
                pass
            if key in existing_ids:
                skipped_total += 1
                continue
            new_events.append(e)
            existing_ids.add(key)

        if new_events:
            existing.extend(new_events)
            imported_total += len(new_events)
            report.append(f"✅ `{os.path.basename(ics_path)}` — импортировано: {len(new_events)}")
        else:
            report.append(f"⏭ `{os.path.basename(ics_path)}` — новых событий нет")

    if imported_total > 0:
        _save_sylviette_calendar(existing)

    lines = [f"📅 **Импорт календаря завершён**\n"]
    lines += report
    lines.append(f"\n📊 Импортировано: **{imported_total}** событий")
    lines.append(f"⏭ Пропущено: {skipped_total} (прошедшие или уже есть)")

    if imported_total > 0:
        lines.append("\n_События добавлены в календарь Сильфиетты, Создатель ✦_")

    return "\n".join(lines)
