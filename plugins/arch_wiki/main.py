"""
Плагин: Arch Wiki
Ищет и возвращает информацию со страниц Arch Linux Wiki.

Использование:
    "arch wiki systemd"
    "найди в arch wiki pulseaudio"
    "как настроить arch bluetooth"
"""
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import json


def _install_if_missing():
    try:
        import markdownify
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "markdownify", "--break-system-packages", "-q"])


def _extract_search_term(query: str) -> str:
    stop = [
        "arch wiki", "найди в arch", "arch linux wiki",
        "archwiki", "как настроить arch", "пакет arch",
        "найди в arch wiki", "arch",
    ]
    q = query.lower()
    for s in sorted(stop, key=len, reverse=True):
        q = q.replace(s, "")
    return q.strip(" ,.-\n") or query.strip()


def _search_wiki(term: str) -> str | None:
    """Ищет страницу в Arch Wiki через opensearch API."""
    params = urllib.parse.urlencode({
        "action": "opensearch",
        "search": term,
        "limit": 1,
        "format": "json",
    })
    url = f"https://wiki.archlinux.org/api.php?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SylvietteAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        titles = data[1]
        return titles[0] if titles else None
    except Exception:
        return None


def _get_page_content(title: str) -> str | None:
    """Получает текст страницы."""
    params = urllib.parse.urlencode({
        "action": "parse",
        "page": title,
        "format": "json",
        "prop": "text",
    })
    url = f"https://wiki.archlinux.org/api.php?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SylvietteAI/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["parse"]["text"]["*"]
    except Exception:
        return None


def _clean(text: str) -> str:
    """Очищает HTML/Markdown от мусора."""
    # Убираем URL
    text = re.sub(r"https?://\S+", "", text)
    # Убираем HTML теги
    text = re.sub(r"<[^>]+>", "", text)
    # Убираем пустые строки
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Убираем строки только из знаков
    text = re.sub(r"^[#\-=\*\[\]()|\s]+$", "", text, flags=re.MULTILINE)
    # Обрезаем
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[:80])  # первые 80 строк


def run(query: str, context: dict) -> str:
    _install_if_missing()

    try:
        import markdownify
    except ImportError:
        return "❌ Не удалось установить markdownify"

    term = _extract_search_term(query)
    if not term:
        return "❌ Укажи что искать. Пример: arch wiki bluetooth"

    title = _search_wiki(term)
    if not title:
        return f"❌ Страница по запросу «{term}» не найдена в Arch Wiki"

    html = _get_page_content(title)
    if not html:
        return f"❌ Не удалось загрузить страницу «{title}»"

    md = markdownify.markdownify(html)
    clean = _clean(md)

    page_url = "https://wiki.archlinux.org/title/" + urllib.parse.quote(title.replace(" ", "_"))

    return (
        f"📖 **Arch Wiki: {title}**\n"
        f"🔗 {page_url}\n\n"
        f"{clean}\n\n"
        f"_Источник: Arch Linux Wiki_"
    )
