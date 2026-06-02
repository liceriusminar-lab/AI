"""
Плагин: Генерация изображений через Pollinations AI
Бесплатно, без API ключа.

Использование:
    "нарисуй закат над морем"
    "сгенерируй изображение кот в шляпе"
"""
import re
import subprocess
import urllib.parse
import urllib.request
import os


# Стоп-слова которые убираем из промпта
_STRIP = [
    "нарисуй", "сгенерируй изображение", "создай картинку",
    "generate image", "нарисуй картинку", "генерируй картинку",
    "генерируй", "создай", "картинку", "изображение",
]

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width=512&height=512&nologo=true"


def _extract_prompt(query: str) -> str:
    q = query.lower()
    for word in sorted(_STRIP, key=len, reverse=True):
        q = q.replace(word, "")
    return q.strip(" ,.-\n") or query.strip()


def _download_image(url: str, save_path: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SylvietteAI/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(save_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"  ImageGen: download error: {e}")
        return False


def run(query: str, context: dict) -> str:
    prompt = _extract_prompt(query)
    if not prompt:
        return "❌ Укажи что нарисовать. Пример: нарисуй закат над морем"

    encoded = urllib.parse.quote(prompt)
    url = POLLINATIONS_URL.format(prompt=encoded)

    # Сохраняем в ~/Pictures/sylviette/
    save_dir = os.path.expanduser("~/Pictures/sylviette")
    os.makedirs(save_dir, exist_ok=True)

    # Безопасное имя файла
    safe_name = re.sub(r"[^\w\s-]", "", prompt)[:40].strip().replace(" ", "_")
    save_path = os.path.join(save_dir, f"{safe_name}.png")

    # Открываем браузер с изображением (самый простой способ показать)
    try:
        subprocess.Popen(
            ["flatpak", "run", "com.brave.Browser", url],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        browser_opened = True
    except Exception:
        browser_opened = False

    # Скачиваем файл в фоне
    downloaded = _download_image(url, save_path)

    lines = [f"🎨 Генерирую изображение по запросу: **{prompt}**\n"]
    lines.append(f"🔗 Ссылка: {url}\n")

    if browser_opened:
        lines.append("🌐 Открываю в браузере, Создатель…")
    if downloaded:
        lines.append(f"💾 Сохранено: `{save_path}`")
    else:
        lines.append("⏳ Изображение генерируется, откройте ссылку выше через несколько секунд")

    return "\n".join(lines)
