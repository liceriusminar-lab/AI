"""
memory.py — сжатая память Сильфиетты
Сохраняет краткое резюме разговоров в JSON
"""
import json
import gzip
import os
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path.home() / ".ai-assistant" / "memory.json.gz"
MAX_ENTRIES = 50  # максимум записей
MAX_SUMMARY_LEN = 200  # максимум символов на резюме

def load_memory() -> list:
    """Загружает память из сжатого файла."""
    if not MEMORY_FILE.exists():
        return []
    try:
        with gzip.open(MEMORY_FILE, 'rt', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_memory(entries: list):
    """Сохраняет память в сжатый файл."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Оставляем только последние MAX_ENTRIES
    entries = entries[-MAX_ENTRIES:]
    with gzip.open(MEMORY_FILE, 'wt', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False)

def summarize_dialog(messages: list) -> str:
    """Делает краткое резюме диалога."""
    summary_parts = []
    for msg in messages:
        if msg.get('role') == 'user':
            content = msg.get('content', '')
            if isinstance(content, list):
                content = next((p['text'] for p in content if p.get('type') == 'text'), '')
            if content and len(content) > 3:
                summary_parts.append(f"спросил: {content[:80]}")
        elif msg.get('role') == 'assistant':
            content = msg.get('content', '')
            if isinstance(content, str) and len(content) > 3:
                summary_parts.append(f"ответила: {content[:80]}")
    summary = ' | '.join(summary_parts[:4])  # берём первые 4 реплики
    return summary[:MAX_SUMMARY_LEN]

def add_to_memory(messages: list):
    """Добавляет резюме диалога в память. Не дублирует."""
    if not messages:
        return
    summary = summarize_dialog(messages)
    if not summary:
        return
    entries = load_memory()
    # Не дублируем — если последняя запись за эту же минуту, обновляем её
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if entries and entries[-1]["time"] == now:
        entries[-1]["summary"] = summary
    else:
        entries.append({"time": now, "summary": summary})
    save_memory(entries)

def get_memory_context() -> str:
    """Возвращает контекст из памяти для промпта."""
    entries = load_memory()
    if not entries:
        return ""
    # Берём последние 5 записей
    recent = entries[-5:]
    lines = [f"- [{e['time']}] {e['summary']}" for e in recent]
    return "Из прошлых разговоров:\n" + "\n".join(lines)

def memory_size() -> str:
    """Размер файла памяти."""
    if not MEMORY_FILE.exists():
        return "0 KB"
    size = MEMORY_FILE.stat().st_size
    return f"{size/1024:.1f} KB (сжато)"
