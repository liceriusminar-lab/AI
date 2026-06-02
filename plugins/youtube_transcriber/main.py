"""
Плагин: YouTube Транскрипция
Транскрибирует YouTube видео по ссылке.

Установка зависимости:
    pip install youtube-transcript-api

Использование:
    "транскрибируй https://youtube.com/watch?v=..."
    "расшифруй видео https://youtu.be/..."
"""
import re
import subprocess
import sys


def _install_if_missing():
    try:
        import youtube_transcript_api
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "youtube-transcript-api", "--break-system-packages", "-q"])


def _extract_video_id(text: str) -> str | None:
    """Извлекает video_id из любой ссылки на YouTube."""
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/watch\?.*v=([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"youtube\.com/v/([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def run(query: str, context: dict) -> str:
    _install_if_missing()

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return "❌ Не удалось установить youtube-transcript-api. Запустите: pip install youtube-transcript-api"

    video_id = _extract_video_id(query)
    if not video_id:
        # Пробуем найти в строке просто 11-символьный id
        m = re.search(r"\b([A-Za-z0-9_-]{11})\b", query)
        if m:
            video_id = m.group(1)

    if not video_id:
        return (
            "❌ Не нашёл ссылку на YouTube видео.\n"
            "Пример: транскрибируй https://youtube.com/watch?v=dQw4w9WgXcQ"
        )

    languages = ["ru", "en", "uk", "de", "fr"]

    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=languages)
        text = " ".join(t.text for t in transcript)
        preview = text[:200] + "…" if len(text) > 200 else text
        return (
            f"🎬 Транскрипция видео `{video_id}`:\n\n"
            f"{text}\n\n"
            f"📊 Длина: {len(text)} символов"
        )
    except Exception as e:
        return f"❌ Не удалось транскрибировать видео `{video_id}`:\n{e}"
