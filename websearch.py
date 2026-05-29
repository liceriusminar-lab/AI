"""
websearch.py — веб-поиск для Сильфиетты
Использует DuckDuckGo (без API ключа)
"""
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime


CACHE_FILE = None  # используем rag.py кэш если нужно
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
}


def search_ddg(query: str, max_results: int = 5) -> list:
    """
    Ищет в DuckDuckGo через Lite версию.
    Возвращает список {"title": ..., "url": ..., "snippet": ...}
    """
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "ru-ru"})
        url    = f"https://lite.duckduckgo.com/lite/?{params}"
        req    = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        return _parse_ddg(html, max_results)
    except Exception as e:
        return [{"title": "Ошибка", "url": "", "snippet": str(e)}]


def _parse_ddg(html: str, max_results: int) -> list:
    """Парсит результаты DuckDuckGo Lite."""
    from bs4 import BeautifulSoup
    soup    = BeautifulSoup(html, "html.parser")
    results = []
    links   = soup.find_all("a", class_="result-link")
    snippets = soup.find_all("td", class_="result-snippet")
    for i, link in enumerate(links[:max_results]):
        title   = link.get_text(strip=True)
        url     = link.get("href", "")
        snippet = snippets[i].get_text(strip=True) if i < len(snippets) else ""
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
    return results


def fetch_page(url: str, max_chars: int = 3000) -> str:
    """Загружает страницу и извлекает текст."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Удаляем скрипты и стили
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        # Чистим пробелы
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"[Ошибка загрузки: {e}]"


def search_and_summarize(query: str) -> dict:
    """
    Ищет запрос и возвращает структурированный результат.
    Returns: {
        "query": str,
        "results": [...],
        "summary": str,   # текст для промпта
        "found": bool,
    }
    """
    results = search_ddg(query, max_results=4)
    if not results or (len(results) == 1 and results[0]["title"] == "Ошибка"):
        return {"query": query, "results": [], "summary": "", "found": False}

    # Формируем краткое резюме для промпта
    lines = [f"Результаты поиска по запросу «{query}»:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        if r["snippet"]:
            lines.append(f"   {r['snippet'][:200]}")
        if r["url"]:
            lines.append(f"   {r['url']}")
        lines.append("")

    summary = "\n".join(lines)
    return {
        "query":   query,
        "results": results,
        "summary": summary,
        "found":   True,
        "time":    datetime.now().isoformat(),
    }


def should_search_web(question: str) -> bool:
    """Определяет нужен ли веб-поиск."""
    q = question.lower()
    triggers = [
        "найди", "поищи", "загугли", "search", "найти",
        "что случилось", "последние новости", "новости",
        "сегодня", "вчера", "сейчас", "текущий", "актуальный",
        "погода", "курс", "цена", "стоимость",
        "последняя версия", "новая версия", "вышел", "вышла",
        "сколько стоит", "где купить", "как скачать",
    ]
    return any(t in q for t in triggers)


if __name__ == "__main__":
    result = search_and_summarize("Python 3.13 новые возможности")
    print(result["summary"])
    print(f"Найдено: {len(result['results'])} результатов")
