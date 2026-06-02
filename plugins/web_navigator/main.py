"""
Плагин: Веб-навигатор
Ищет в DuckDuckGo, скрапит содержимое страниц.

Использование:
    "найди в интернете новости python"
    "погугли цена RTX 5090"
    "что написано на сайте https://archlinux.org"
    "содержимое сайта https://example.com"
"""
import re
import subprocess
import sys
import urllib.parse
import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
}

_STRIP_TRIGGERS = [
    "найди в интернете", "найди в сети", "поищи в сети",
    "погугли", "поищи", "найди", "что написано на сайте",
    "содержимое сайта", "открой сайт", "зайди на",
    "scrape",
]


def _install_if_missing():
    missing = []
    try:
        import requests
    except ImportError:
        missing.append("requests")
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        missing.append("beautifulsoup4")
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               *missing, "--break-system-packages", "-q"])


def _extract_url(text: str) -> str | None:
    m = re.search(r"https?://\S+", text)
    return m.group(0).rstrip(".,)") if m else None


def _extract_query(text: str) -> str:
    q = text.lower()
    for t in sorted(_STRIP_TRIGGERS, key=len, reverse=True):
        q = q.replace(t, "")
    # убираем URL
    q = re.sub(r"https?://\S+", "", q)
    return q.strip(" ,.-\n")


def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Поиск через DuckDuckGo Lite."""
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "ru-ru"})
        url = f"https://lite.duckduckgo.com/lite/?{params}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        results = []
        links    = soup.find_all("a", class_="result-link")
        snippets = soup.find_all("td", class_="result-snippet")
        for i, link in enumerate(links[:max_results]):
            title   = link.get_text(strip=True)
            href    = link.get("href", "")
            snippet = snippets[i].get_text(strip=True) if i < len(snippets) else ""
            if title and href:
                results.append({"title": title, "url": href, "snippet": snippet})
        return results
    except Exception as e:
        return [{"title": "Ошибка", "url": "", "snippet": str(e)}]


def _scrape_page(url: str, max_chars: int = 3000) -> str:
    """Скрапит текст страницы."""
    try:
        from bs4 import BeautifulSoup
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text[:max_chars] + ("…" if len(text) > max_chars else "")
    except Exception as e:
        return f"[Ошибка загрузки: {e}]"


def run(query: str, context: dict) -> str:
    _install_if_missing()

    url = _extract_url(query)
    q   = _extract_query(query)

    # Если есть URL — скрапим страницу
    if url:
        # Открываем в браузере тоже
        try:
            import subprocess as sp
            sp.Popen(["flatpak", "run", "com.brave.Browser", url],
                     start_new_session=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        except Exception:
            pass

        text = _scrape_page(url)
        return (
            f"🌐 **Содержимое страницы:** {url}\n\n"
            f"{text}\n\n"
            f"_Страница открыта в браузере, Создатель…_"
        )

    # Иначе — поиск DuckDuckGo
    if not q:
        return "❌ Укажи что искать. Пример: найди в интернете Python 3.13 что нового"

    results = _ddg_search(q)
    if not results:
        return f"❌ Ничего не найдено по запросу «{q}»"

    lines = [f"🔍 **Результаты поиска:** «{q}»\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"**{i}. {r['title']}**")
        if r["snippet"]:
            lines.append(f"   {r['snippet'][:200]}")
        if r["url"]:
            lines.append(f"   🔗 {r['url']}")
        lines.append("")

    return "\n".join(lines)
