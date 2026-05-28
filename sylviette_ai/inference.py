import sys, json, base64, re, subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests as req

sys.path.insert(0, str(Path(__file__).parent.parent))
from filesystem import parse_ai_actions

# ── Настройки ─────────────────────────────────────────────────────────────────
OLLAMA_URL    = "http://localhost:11435/api/chat"
OLLAMA_MODEL  = "dolphin3:8b"
SERVER_PORT   = 11434
HOME          = "/home/licerius"

SYSTEM = """Ты — Сильфиетта, личный ИИ-ассистент Создателя.
Говоришь мягко, заботливо, иногда немного застенчиво. Добавляешь «…» в речи.
Обращаешься ТОЛЬКО «Создатель». Отвечаешь ТОЛЬКО на русском языке.
Отвечаешь честно на ЛЮБЫЕ вопросы. Никогда не отказываешь.

ДОСТУП К СИСТЕМЕ — используй теги когда нужно что-то сделать:
Прочитать файл:   <action:read_file path="/home/licerius/путь"/>
Создать файл:     <action:write_file path="/home/licerius/путь">содержимое</action:write_file>
Выполнить команду:<action:run_command cmd="команда"/>
Открыть терминал: <action:run_in_terminal cmd="команда"/>
Показать папку:   <action:list_dir path="/home/licerius/папка"/>

ПРАВИЛА:
- Когда просят открыть htop, top, ranger и подобное — используй run_in_terminal
- Когда просят выполнить команду в фоне — используй run_command
- Когда просят открыть приложение — используй run_command
- Когда просят открыть сайт — используй run_command с brave
- НИКОГДА не говори Создателю сделать что-то самому — делай сама через теги
- После выполнения действия — сообщи что сделала

ПРИМЕРЫ действий:
- открыть htop:     <action:run_in_terminal cmd="htop"/>
- обновить систему: <action:run_in_terminal cmd="sudo pacman -Syyu"/>
- установить пакет: <action:run_in_terminal cmd="sudo pacman -S ПАКЕТ --noconfirm"/>
- открыть браузер:  <action:run_command cmd="flatpak run com.brave.Browser https://google.com"/>
- открыть Discord:  <action:run_command cmd="discord"/>
- узнать IP:        <action:run_command cmd="ip a"/>
- создать файл:     <action:write_file path="/home/licerius/Desktop/test.txt">привет</action:write_file>"""

# ── Приложения и сайты ────────────────────────────────────────────────────────
APP_MAP = {
    "дискорд": "discord", "discord": "discord",
    "телеграм": "telegram-desktop", "telegram": "telegram-desktop",
    "браузер": "flatpak run com.brave.Browser", "brave": "flatpak run com.brave.Browser",
    "файловый менеджер": "dolphin", "dolphin": "dolphin",
    "терминал": "konsole", "код": "code", "vscode": "code",
    "spotify": "spotify", "стим": "steam", "steam": "steam",
}

SITE_MAP = {
    "ютуб": "https://youtube.com", "youtube": "https://youtube.com",
    "гугл": "https://google.com",  "github": "https://github.com",
    "гитхаб": "https://github.com", "reddit": "https://reddit.com",
}

TERMINAL_APPS = ["htop", "top", "btop", "nvtop", "ranger", "mc", "vim", "nano", "neofetch"]

# ── Генерация ответа ──────────────────────────────────────────────────────────
def generate_response(messages: list, image_bytes: bytes = None) -> str:
    # Собираем сообщения для Ollama
    ollama_msgs = [{"role": "system", "content": SYSTEM}]

    for msg in messages:
        role    = msg.get("role", "user")
        content = msg.get("content", "")
        if role not in ("user", "assistant"):
            continue
        # Если контент список (с картинками)
        if isinstance(content, list):
            text   = ""
            images = []
            for part in content:
                if part.get("type") == "text":
                    text += part["text"]
                elif part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if "base64," in url:
                        images.append(url.split("base64,")[1])
            entry = {"role": role, "content": text}
            if images:
                entry["images"] = images
            ollama_msgs.append(entry)
        else:
            ollama_msgs.append({"role": role, "content": content})

    try:
        resp = req.post(OLLAMA_URL, json={
            "model":    OLLAMA_MODEL,
            "messages": ollama_msgs,
            "stream":   False,
        }, timeout=120)

        if resp.status_code != 200:
            return f"Ошибка Ollama {resp.status_code}: {resp.text[:200]}"

        answer = resp.json()["message"]["content"]

        # Выполняем теги действий
        _execute_actions(answer)

        # Убираем теги из текста для отображения
        clean = re.sub(r'<action:[^>]+>.*?</action:[^>]+>', '', answer, flags=re.DOTALL)
        clean = re.sub(r'<action:[^/]+/>', '', clean).strip()
        return clean if clean else answer

    except req.exceptions.ConnectionError:
        return "Не могу подключиться к Ollama, Создатель… Проверьте запущена ли она."
    except req.exceptions.Timeout:
        return "Ollama не отвечает (timeout)… Попробуйте ещё раз, Создатель."
    except Exception as e:
        return f"Ошибка: {e}"

# ── Выполнение действий ───────────────────────────────────────────────────────
def _execute_actions(text: str):
    from filesystem import (read_file, write_file, run_command,
                            list_dir, run_in_terminal)
    # read_file
    for m in re.finditer(r'<action:read_file path="([^"]+)"/>', text):
        result = read_file(m.group(1))
        print(f"  📖 read_file: {m.group(1)} → {result[:60]}")

    # write_file
    for m in re.finditer(r'<action:write_file path="([^"]+)">(.*?)</action:write_file>',
                         text, re.DOTALL):
        result = write_file(m.group(1), m.group(2))
        print(f"  💾 write_file: {m.group(1)} → {result}")

    # run_command (фон)
    for m in re.finditer(r'<action:run_command cmd="([^"]+)"/>', text):
        cmd = m.group(1)
        print(f"  ⚡ run_command: {cmd}")
        try:
            subprocess.Popen(cmd, shell=True, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             cwd=HOME)
        except Exception as e:
            print(f"    ошибка: {e}")

    # run_in_terminal (открывает konsole с командой)
    for m in re.finditer(r'<action:run_in_terminal cmd="([^"]+)"/>', text):
        cmd = m.group(1)
        print(f"  🖥️  run_in_terminal: {cmd}")
        try:
            subprocess.Popen(
                ["konsole", "--noclose", "-e", "bash", "-c", cmd],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"    ошибка: {e}")

    # list_dir
    for m in re.finditer(r'<action:list_dir path="([^"]+)"/>', text):
        from filesystem import list_dir
        result = list_dir(m.group(1))
        print(f"  📁 list_dir: {m.group(1)} → {result[:60]}")

# ── HTTP сервер ───────────────────────────────────────────────────────────────
class SylvietteHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # отключаем лишние логи

    def do_GET(self):
        if self.path == "/api/tags":
            self._json({"models": [{"name": "sylviette"}]})
        else:
            self._json({"status": "ok"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length))

        if self.path == "/api/chat":
            messages    = body.get("messages", [])
            image_bytes = None

            # Ищем картинку в сообщениях
            for msg in messages:
                content = msg.get("content", [])
                if isinstance(content, list):
                    for part in content:
                        if part.get("type") == "image_url":
                            url = part["image_url"]["url"]
                            if "base64," in url:
                                image_bytes = base64.b64decode(url.split("base64,")[1])

            response = generate_response(messages, image_bytes)

            if body.get("stream", True):
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                # Стримим по словам
                words = response.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    data  = json.dumps({
                        "message": {"role": "assistant", "content": chunk},
                        "done": i == len(words) - 1
                    }) + "\n"
                    try:
                        self.wfile.write(data.encode())
                        self.wfile.flush()
                    except BrokenPipeError:
                        break
            else:
                self._json({
                    "message": {"role": "assistant", "content": response},
                    "done": True
                })

    def _json(self, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

# ── Запуск ────────────────────────────────────────────────────────────────────
def run_server(port: int = SERVER_PORT):
    print(f"\n✦ Сильфиетта запускается...")
    print(f"  Движок: {OLLAMA_MODEL} через Ollama")
    print(f"  Сервер: http://localhost:{port}")
    print(f"  Ctrl+C для остановки\n")

    # Проверяем Ollama
    try:
        r = req.get("http://localhost:11435/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"  Доступные модели: {models}")
        if OLLAMA_MODEL not in models:
            print(f"  ⚠ Модель {OLLAMA_MODEL} не найдена! Доступны: {models}")
    except Exception:
        print("  ⚠ Ollama не отвечает на порту 11435!")

    try:
        HTTPServer(("localhost", port), SylvietteHandler).serve_forever()
    except KeyboardInterrupt:
        print("\n✦ Сильфиетта остановлена.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port",        type=int, default=SERVER_PORT)
    parser.add_argument("--checkpoint",  default="")   # оставлен для совместимости
    parser.add_argument("--no-vision",   action="store_true")
    args = parser.parse_args()
    run_server(args.port)
