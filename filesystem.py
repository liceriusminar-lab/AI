import os
import subprocess
import re

HOME = os.path.expanduser("~")

def read_file(path: str) -> str:
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return f"[Ошибка: файл {path} не найден]"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"[Ошибка чтения: {e}]"

def write_file(path: str, content: str) -> str:
    path = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✓ Файл сохранён: {path}"
    except Exception as e:
        return f"[Ошибка записи: {e}]"

def list_dir(path: str) -> str:
    path = os.path.expanduser(path)
    try:
        items = os.listdir(path)
        files = [f"📄 {i}" if os.path.isfile(os.path.join(path, i)) else f"📁 {i}" for i in sorted(items)]
        return "\n".join(files) or "[Папка пуста]"
    except Exception as e:
        return f"[Ошибка: {e}]"

def run_command(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=30, cwd=HOME
        )
        out = (result.stdout + result.stderr).strip()
        return out or "[Команда выполнена без вывода]"
    except subprocess.TimeoutExpired:
        return "[Таймаут: команда выполнялась слишком долго]"
    except Exception as e:
        return f"[Ошибка: {e}]"

def parse_ai_actions(text: str) -> list:
    """Парсит теги действий из ответа ИИ."""
    actions = []

    for m in re.finditer(r'<action:read_file path="([^"]+)"/>', text):
        path = m.group(1)
        actions.append(("read_file", path, read_file(path)))

    for m in re.finditer(r'<action:write_file path="([^"]+)">(.*?)</action:write_file>', text, re.DOTALL):
        path, content = m.group(1), m.group(2)
        actions.append(("write_file", path, write_file(path, content)))

    for m in re.finditer(r'<action:run_command cmd="([^"]+)"/>', text):
        cmd = m.group(1)
        actions.append(("run_command", cmd, run_command(cmd)))

    for m in re.finditer(r'<action:list_dir path="([^"]+)"/>', text):
        path = m.group(1)
        actions.append(("list_dir", path, list_dir(path)))

    return actions