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

    for m in re.finditer(r'<action:run_in_terminal cmd="([^"]+)"/>', text):
        cmd = m.group(1)
        actions.append(("run_in_terminal", cmd, run_in_terminal(cmd)))

    for m in re.finditer(r'<action:list_dir path="([^"]+)"/>', text):
        path = m.group(1)
        actions.append(("list_dir", path, list_dir(path)))

    return actions
def send_telegram(to: str, message: str) -> str:
    """Отправка сообщения через xdg-open telegram."""
    try:
        import urllib.parse
        msg = urllib.parse.quote(message)
        result = subprocess.run(
            f'xdg-open "tg://resolve?domain={to}&text={msg}"',
            shell=True, capture_output=True, text=True, timeout=10
        )
        return f"✓ Сообщение отправлено {to}"
    except Exception as e:
        return f"[Ошибка: {e}]"

def open_url(url: str) -> str:
    """Открывает URL в браузере."""
    try:
        subprocess.Popen(
            ["flatpak", "run", "com.brave.Browser", url],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return f"✓ Открыт: {url}"
    except Exception as e:
        return f"[Ошибка: {e}]"

def run_in_terminal(cmd: str) -> str:
    """Открывает команду в новом окне терминала."""
    try:
        # Команды которые требуют sudo — запускаем в konsole
        subprocess.Popen(
            ["konsole", "--noclose", "-e", "bash", "-c",
             f"{cmd}; echo '--- Готово. Нажмите Enter ---'; read"],
            start_new_session=True
        )
        return f"✓ Открыто в терминале: {cmd}"
    except Exception as e:
        return f"[Ошибка: {e}]"
