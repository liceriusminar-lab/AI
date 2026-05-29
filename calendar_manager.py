"""
calendar_manager.py — календарь и напоминания Сильфиетты
Хранит события в ~/.ai-assistant/calendar.ics (стандарт iCalendar)
"""
import json
import uuid
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

try:
    from icalendar import Calendar, Event, vDatetime
    HAS_ICAL = True
except ImportError:
    HAS_ICAL = False

CALENDAR_FILE = Path.home() / ".ai-assistant" / "calendar.ics"
REMINDERS_FILE = Path.home() / ".ai-assistant" / "reminders.json"


# ── Работа с событиями ────────────────────────────────────────────────────────

def load_calendar() -> list:
    """Загружает все события из файла."""
    if not REMINDERS_FILE.exists():
        return []
    try:
        with open(REMINDERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_calendar(events: list):
    """Сохраняет события."""
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    # Также экспортируем в .ics для KOrganizer
    if HAS_ICAL:
        _export_ics(events)


def _export_ics(events: list):
    """Экспортирует события в .ics файл."""
    try:
        cal = Calendar()
        cal.add("prodid", "-//Sylviette AI//sylviette//RU")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        for e in events:
            evt = Event()
            evt.add("uid", e.get("id", str(uuid.uuid4())))
            evt.add("summary", e["title"])
            evt.add("description", e.get("description", ""))
            try:
                dt = datetime.fromisoformat(e["datetime"])
                evt.add("dtstart", dt)
                evt.add("dtend", dt + timedelta(hours=1))
            except Exception:
                continue
            cal.add_component(evt)
        CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
        CALENDAR_FILE.write_bytes(cal.to_ical())
    except Exception as e:
        print(f"ICS export error: {e}")


def add_event(title: str, dt: datetime, description: str = "",
              remind_minutes: int = 15) -> dict:
    """Добавляет событие."""
    events = load_calendar()
    event = {
        "id":          str(uuid.uuid4())[:8],
        "title":       title,
        "datetime":    dt.isoformat(),
        "description": description,
        "remind_min":  remind_minutes,
        "done":        False,
        "created":     datetime.now().isoformat(),
    }
    events.append(event)
    save_calendar(events)
    return event


def delete_event(event_id: str) -> bool:
    """Удаляет событие по id."""
    events = load_calendar()
    new = [e for e in events if e["id"] != event_id]
    if len(new) == len(events):
        return False
    save_calendar(new)
    return True


def get_upcoming(days: int = 7) -> list:
    """Возвращает события на ближайшие N дней."""
    events = load_calendar()
    now    = datetime.now()
    limit  = now + timedelta(days=days)
    result = []
    for e in events:
        try:
            dt = datetime.fromisoformat(e["datetime"])
            if now <= dt <= limit and not e.get("done"):
                result.append({**e, "_dt": dt})
        except Exception:
            pass
    return sorted(result, key=lambda x: x["_dt"])


def get_today() -> list:
    """События на сегодня."""
    return get_upcoming(days=1)


def format_events(events: list) -> str:
    """Форматирует список событий для отображения."""
    if not events:
        return "Нет предстоящих событий"
    lines = []
    for e in events:
        try:
            dt = datetime.fromisoformat(e["datetime"])
            time_str = dt.strftime("%d.%m %H:%M")
        except Exception:
            time_str = e["datetime"]
        remind = f" (напомнить за {e['remind_min']} мин)" if e.get("remind_min") else ""
        desc   = f"\n   {e['description']}" if e.get("description") else ""
        lines.append(f"📅 [{e['id']}] {time_str} — {e['title']}{remind}{desc}")
    return "\n".join(lines)


def parse_datetime(text: str) -> Optional[datetime]:
    """
    Парсит дату/время из текста на русском.
    Примеры: 'завтра в 15:00', '25.12 в 10:30', 'через 2 часа'
    """
    import re
    now = datetime.now()
    text = text.lower().strip()

    # Через N минут/часов
    m = re.search(r'через\s+(\d+)\s*(минут|час|мин)', text)
    if m:
        n    = int(m.group(1))
        unit = m.group(2)
        if "час" in unit:
            return now + timedelta(hours=n)
        return now + timedelta(minutes=n)

    # Сегодня/завтра/послезавтра
    base = now
    if "послезавтра" in text:
        base = now + timedelta(days=2)
    elif "завтра" in text:
        base = now + timedelta(days=1)
    elif "сегодня" in text:
        base = now

    # Время HH:MM
    m = re.search(r'(\d{1,2})[:\.](\d{2})', text)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        return base.replace(hour=h, minute=mn, second=0, microsecond=0)

    # Дата DD.MM или DD.MM.YYYY
    m = re.search(r'(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?', text)
    if m:
        day  = int(m.group(1))
        mon  = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        # Время если есть
        tm = re.search(r'в\s+(\d{1,2})[:\.](\d{2})', text)
        h, mn = (int(tm.group(1)), int(tm.group(2))) if tm else (9, 0)
        return datetime(year, mon, day, h, mn)

    return None


# ── Фоновый поток напоминаний ─────────────────────────────────────────────────

class ReminderDaemon(threading.Thread):
    """Фоновый поток который проверяет напоминания."""

    def __init__(self, on_reminder: Callable[[dict], None]):
        super().__init__(daemon=True)
        self.on_reminder = on_reminder
        self._notified   = set()

    def run(self):
        import time
        while True:
            try:
                self._check()
            except Exception as e:
                print(f"Reminder error: {e}")
            time.sleep(30)  # проверяем каждые 30 секунд

    def _check(self):
        events = load_calendar()
        now    = datetime.now()
        for e in events:
            if e.get("done") or e["id"] in self._notified:
                continue
            try:
                dt      = datetime.fromisoformat(e["datetime"])
                remind  = timedelta(minutes=e.get("remind_min", 15))
                trigger = dt - remind
                if trigger <= now <= dt:
                    self._notified.add(e["id"])
                    self.on_reminder(e)
            except Exception:
                pass


# ── Парсер команд для Сильфиетты ─────────────────────────────────────────────

def handle_calendar_command(text: str) -> Optional[str]:
    """
    Обрабатывает команды календаря из текста.
    Возвращает ответ или None если не команда календаря.
    """
    t = text.lower()

    # Показать события
    if any(w in t for w in ["покажи календарь", "мои события", "что запланировано",
                              "расписание", "напоминания", "покажи события"]):
        events = get_upcoming(days=7)
        return "📅 События на ближайшую неделю:\n" + format_events(events)

    if any(w in t for w in ["сегодня", "на сегодня"]) and any(w in t for w in ["события", "планы", "расписание"]):
        events = get_today()
        return "📅 События на сегодня:\n" + format_events(events)

    # Удалить событие
    import re
    m = re.search(r'удали\s+(?:событие\s+)?(?:с\s+id\s+)?([a-f0-9]{8})', t)
    if m:
        eid = m.group(1)
        if delete_event(eid):
            return f"✓ Событие {eid} удалено"
        return f"Событие {eid} не найдено"

    # Добавить событие
    add_triggers = ["напомни", "добавь событие", "запланируй", "создай событие",
                    "поставь напоминание", "добавь в календарь"]
    if any(w in t for w in add_triggers):
        # Извлекаем название
        title = text
        for w in add_triggers:
            title = re.sub(w, "", title, flags=re.IGNORECASE)
        # Убираем временные указатели
        dt = parse_datetime(text)
        if dt:
            time_patterns = [
                r'завтра', r'сегодня', r'послезавтра',
                r'через\s+\d+\s*(?:минут|час\w*)',
                r'\d{1,2}[.:]\d{2}', r'\d{1,2}\.\d{1,2}',
                r'в\s+\d{1,2}[.:]\d{2}',
            ]
            for p in time_patterns:
                title = re.sub(p, "", title, flags=re.IGNORECASE)
            title = title.strip(" ,.-\n")
            if not title:
                title = "Событие"
            event = add_event(title, dt)
            dt_str = dt.strftime("%d.%m.%Y в %H:%M")
            return (
                f"✓ Добавлено в календарь:\n"
                f"📅 {title}\n"
                f"🕐 {dt_str}\n"
                f"🔔 Напомню за 15 минут\n"
                f"ID: {event['id']}"
            )
        else:
            return (
                "Не могу определить дату… Укажи точнее, например:\n"
                "• «напомни встреча завтра в 15:00»\n"
                "• «запланируй звонок 25.06 в 10:30»\n"
                "• «напомни через 2 часа поесть»"
            )

    return None
