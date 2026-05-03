"""
sylviette_ai/rag.py
────────────────────
RAG — поиск информации в интернете + кэш в zip файле.

Как работает:
1. Получаем вопрос
2. Ищем в кэше (zip файл)
3. Если нет — ищем в Wikipedia/интернете
4. Сохраняем в кэш
5. Передаём контекст модели для ответа
"""

import re
import json
import zipfile
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime


CACHE_FILE = Path("data/rag_cache.zip")
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _key(query: str) -> str:
    """Ключ для кэша — хэш запроса."""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()


def _load_cache(key: str) -> str | None:
    """Загружает из кэша."""
    if not CACHE_FILE.exists():
        return None
    try:
        with zipfile.ZipFile(CACHE_FILE, "r") as zf:
            if key in zf.namelist():
                return zf.read(key).decode("utf-8")
    except:
        pass
    return None


def _save_cache(key: str, content: str):
    """Сохраняет в кэш."""
    try:
        # Открываем существующий zip или создаём новый
        mode = "a" if CACHE_FILE.exists() else "w"
        with zipfile.ZipFile(CACHE_FILE, mode, compression=zipfile.ZIP_DEFLATED) as zf:
            # Если ключ уже есть — пересоздаём (zip не поддерживает замену)
            if mode == "a" and key in zf.namelist():
                return  # уже есть
            zf.writestr(key, content)
    except Exception as e:
        print(f"  ⚠ Ошибка кэша: {e}")


def search_wikipedia(query: str, lang: str = "ru", sentences: int = 5) -> str:
    """Ищет в Wikipedia и возвращает краткое описание."""
    try:
        # Wikipedia API
        params = urllib.parse.urlencode({
            "action":   "query",
            "format":   "json",
            "prop":     "extracts",
            "exsentences": sentences,
            "exintro":  True,
            "explaintext": True,
            "redirects": 1,
            "titles":   query,
        })
        url = f"https://{lang}.wikipedia.org/w/api.php?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "SylvietteAI/1.0"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "").strip()
            if extract and "missing" not in page:
                return extract

        # Если не нашли — пробуем поиск
        return _wikipedia_search(query, lang)

    except Exception as e:
        return f"[Ошибка поиска: {e}]"


def _wikipedia_search(query: str, lang: str = "ru") -> str:
    """Поиск по Wikipedia если прямой запрос не дал результата."""
    try:
        params = urllib.parse.urlencode({
            "action":   "opensearch",
            "format":   "json",
            "search":   query,
            "limit":    3,
        })
        url = f"https://{lang}.wikipedia.org/w/api.php?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "SylvietteAI/1.0"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # data = [query, [titles], [descriptions], [urls]]
        if len(data) >= 3 and data[1]:
            # Берём первый результат
            first_title = data[1][0]
            return search_wikipedia(first_title, lang)

        return "[Информация не найдена в Wikipedia]"

    except Exception as e:
        return f"[Ошибка поиска: {e}]"


def get_context(query: str, use_cache: bool = True) -> dict:
    """
    Главная функция — получает контекст для вопроса.

    Returns:
        {
            "query": str,
            "context": str,       # найденная информация
            "source": str,        # "cache" или "wikipedia"
            "found": bool,
        }
    """
    key = _key(query)

    # Проверяем кэш
    if use_cache:
        cached = _load_cache(key)
        if cached:
            data = json.loads(cached)
            print(f"  📦 Из кэша: {query[:50]}...")
            return {**data, "source": "cache"}

    # Ищем в Wikipedia
    print(f"  🌐 Ищем в Wikipedia: {query[:50]}...")
    context = search_wikipedia(query)

    result = {
        "query":   query,
        "context": context,
        "source":  "wikipedia",
        "found":   not context.startswith("["),
        "time":    datetime.now().isoformat(),
    }

    # Сохраняем в кэш
    if result["found"]:
        _save_cache(key, json.dumps(result, ensure_ascii=False))
        print(f"  💾 Сохранено в кэш ({CACHE_FILE})")

    return result


def should_search(question: str) -> bool:
    """
    Определяет нужно ли искать информацию для ответа на вопрос.
    Ищем для вопросов о людях, событиях, фактах.
    """
    question_lower = question.lower()

    # Триггеры поиска
    triggers = [
        "кто такой", "кто такая", "что такое", "что такой",
        "расскажи о", "расскажи про", "кто это", "что это",
        "когда", "где", "почему", "зачем", "как работает",
        "история", "биография", "изобрёл", "открыл", "основал",
        "столица", "население", "площадь", "президент", "король",
        "фильм", "книга", "автор", "написал", "снял",
    ]

    return any(t in question_lower for t in triggers)


def build_prompt_with_context(question: str, context: str) -> str:
    """Строит промпт с найденным контекстом."""
    return (
        f"Информация из Wikipedia:\n{context}\n\n"
        f"Вопрос: {question}\n"
        f"Ответ (на основе информации выше):"
    )


def cache_stats() -> dict:
    """Статистика кэша."""
    if not CACHE_FILE.exists():
        return {"entries": 0, "size_kb": 0}
    with zipfile.ZipFile(CACHE_FILE, "r") as zf:
        entries = len(zf.namelist())
    size_kb = CACHE_FILE.stat().st_size / 1024
    return {"entries": entries, "size_kb": round(size_kb, 1)}


if __name__ == "__main__":
    # Тест
    print("=== Тест RAG системы ===\n")

    queries = [
        "Лев Толстой",
        "Python programming language",
        "Москва",
    ]

    for q in queries:
        print(f"Запрос: {q}")
        result = get_context(q)
        print(f"Источник: {result['source']}")
        print(f"Найдено: {result['found']}")
        print(f"Контекст: {result['context'][:200]}...")
        print()

    print(f"Статистика кэша: {cache_stats()}")
