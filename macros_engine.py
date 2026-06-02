"""
macros_engine.py — движок макросов Сильфиетты
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Подключается к ollama_worker.py автоматически.
Отдельно запускать не нужно.
"""

import subprocess
import time
import os
import re
from pathlib import Path
from typing import Optional


# ── Steam helpers ─────────────────────────────────────────────────────────────

def _find_steam_loginusers() -> Optional[Path]:
    """Ищет файл loginusers.vdf где хранятся аккаунты Steam."""
    candidates = [
        Path.home() / ".steam/steam/config/loginusers.vdf",
        Path.home() / ".local/share/Steam/config/loginusers.vdf",
        Path("/var/lib/flatpak/app/com.valvesoftware.Steam") / "current/active/files/Steam/config/loginusers.vdf",
    ]
    for p in candidates:
        if p.exists():
            return p
    # Поиск через find если стандартные пути не сработали
    try:
        result = subprocess.run(
            ["find", str(Path.home()), "-name", "loginusers.vdf", "-maxdepth", "8"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().splitlines():
            p = Path(line.strip())
            if p.exists():
                return p
    except Exception:
        pass
    return None


def _get_steam_accounts() -> list[dict]:
    """
    Читает loginusers.vdf и возвращает список аккаунтов.
    Каждый: {"steamid": str, "accountname": str, "personaname": str}
    """
    vdf_path = _find_steam_loginusers()
    if not vdf_path:
        return []

    accounts = []
    try:
        content = vdf_path.read_text(encoding="utf-8", errors="replace")
        # Простой парсер VDF — ищем блоки steamid → accountname
        blocks = re.split(r'"(\d{17})"', content)
        i = 1
        while i < len(blocks) - 1:
            steamid = blocks[i]
            block   = blocks[i + 1]
            acc = {"steamid": steamid, "accountname": "", "personaname": ""}
            m = re.search(r'"AccountName"\s+"([^"]+)"', block, re.IGNORECASE)
            if m:
                acc["accountname"] = m.group(1)
            m = re.search(r'"PersonaName"\s+"([^"]+)"', block, re.IGNORECASE)
            if m:
                acc["personaname"] = m.group(1)
            if acc["accountname"]:
                accounts.append(acc)
            i += 2
    except Exception as e:
        print(f"  ⚠ Не удалось прочитать loginusers.vdf: {e}")

    return accounts


def steam_switch_account(account_login: str) -> bool:
    """
    Переключает Steam на нужный аккаунт через steam://open/switchuser/<steamid>.
    Возвращает True если аккаунт найден.
    """
    accounts = _get_steam_accounts()
    target = None

    for acc in accounts:
        if acc["accountname"].lower() == account_login.lower():
            target = acc
            break

    if not target:
        # Пробуем по части имени
        for acc in accounts:
            if account_login.lower() in acc["accountname"].lower() \
               or account_login.lower() in acc["personaname"].lower():
                target = acc
                break

    if not target:
        print(f"  ⚠ Аккаунт Steam '{account_login}' не найден.")
        print(f"  Доступные аккаунты: {[a['accountname'] for a in accounts]}")
        return False

    steamid = target["steamid"]
    print(f"  ✦ Переключаю Steam → {target['accountname']} (steamid={steamid})")

    # Закрываем Steam если запущен
    subprocess.run(["pkill", "-f", "steam"], capture_output=True)
    time.sleep(2)

    # Запускаем Steam с нужным аккаунтом
    # -login <accountname> работает только если пароль сохранён (remember me)
    try:
        subprocess.Popen(
            ["steam", f"-login", target["accountname"]],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        # Пробуем через flatpak
        try:
            subprocess.Popen(
                ["flatpak", "run", "com.valvesoftware.Steam", f"-login", target["accountname"]],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            print(f"  ⚠ Не удалось запустить Steam: {e}")
            return False


def steam_launch_game(app_id: str, wait_for_steam: int = 12) -> bool:
    """
    Запускает игру через steam://rungameid/<app_id>.
    wait_for_steam — секунд ожидания пока Steam запустится.
    """
    print(f"  ⏳ Жду {wait_for_steam}с пока Steam инициализируется…")
    time.sleep(wait_for_steam)

    url = f"steam://rungameid/{app_id}"
    print(f"  🎮 Запускаю игру: {url}")
    try:
        subprocess.Popen(
            ["xdg-open", url],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        print(f"  ⚠ Ошибка запуска игры: {e}")
        return False


# ── Действия ──────────────────────────────────────────────────────────────────

def _notify(title: str, message: str):
    """KDE уведомление."""
    try:
        subprocess.Popen(
            ["notify-send", title, message,
             "--icon=dialog-information",
             "--app-name=Сильфиетта",
             "--expire-time=5000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _open_url(url: str, browser: str = "flatpak run com.brave.Browser"):
    """Открывает URL в браузере."""
    cmd = browser.split() + [url]
    subprocess.Popen(
        cmd, start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"  🌐 Открываю: {url}")


def _launch_app(cmd: str):
    """Запускает приложение."""
    subprocess.Popen(
        cmd.split(), start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"  🚀 Запускаю: {cmd}")


def _shell(cmd: str):
    """Выполняет shell команду."""
    subprocess.run(cmd, shell=True, capture_output=True)
    print(f"  ⚡ Shell: {cmd}")


# ── Выполнение макроса ────────────────────────────────────────────────────────

def run_macro(macro: dict) -> str:
    """
    Выполняет все действия макроса последовательно.
    Возвращает ответ для отображения в чате.
    """
    name = macro.get("name", "?")
    print(f"\n✦ Макрос [{name}] запущен", flush=True)

    for i, action in enumerate(macro.get("actions", []), 1):
        atype   = action.get("type", "")
        comment = action.get("comment", "")
        label   = comment or atype
        print(f"  [{i}] {label}…", flush=True)

        if atype == "delay":
            secs = action.get("seconds", 1)
            print(f"      ⏳ пауза {secs}с")
            time.sleep(secs)

        elif atype == "notify":
            _notify(action.get("title", "Сильфиетта"), action.get("message", ""))

        elif atype == "open_url":
            from macros import BROWSER
            _open_url(action["url"], BROWSER)

        elif atype == "launch_app":
            _launch_app(action["cmd"])

        elif atype == "shell":
            _shell(action["cmd"])

        elif atype == "steam_switch_and_launch":
            account = action.get("account", "")
            app_id  = action.get("app_id", "")
            # Переключаем аккаунт
            ok = steam_switch_account(account)
            # Запускаем игру (с ожиданием пока Steam стартует)
            if app_id:
                steam_launch_game(app_id, wait_for_steam=14)

        elif atype == "steam_game":
            app_id = action.get("app_id", "")
            steam_launch_game(app_id, wait_for_steam=5)

        elif atype == "steam_switch":
            steam_switch_account(action.get("account", ""))

        else:
            print(f"      ⚠ Неизвестный тип действия: {atype}")

    print(f"✦ Макрос [{name}] завершён\n", flush=True)
    return macro.get("response", f"Макрос «{name}» выполнен, Создатель ✦")


# ── Поиск макроса по фразе ────────────────────────────────────────────────────

def find_macro(text: str) -> Optional[dict]:
    """
    Ищет макрос в MACROS по триггерным фразам.
    Регистронезависимо, проверяет вхождение подстроки.
    """
    try:
        from macros import MACROS
    except ImportError:
        return None

    text_lower = text.lower().strip()

    for macro in MACROS:
        for trigger in macro.get("triggers", []):
            # Точное совпадение или вхождение триггера в текст
            if trigger.lower() == text_lower or trigger.lower() in text_lower:
                return macro

    return None


# ── Утилита: список аккаунтов Steam (для диагностики) ─────────────────────────

def print_steam_accounts():
    """Выводит все найденные аккаунты Steam — для отладки."""
    accounts = _get_steam_accounts()
    if not accounts:
        print("Аккаунты Steam не найдены. Проверь путь к loginusers.vdf")
        return
    print(f"Найдено аккаунтов Steam: {len(accounts)}")
    for i, acc in enumerate(accounts, 1):
        print(f"  {i}. login={acc['accountname']:20s} | persona={acc['personaname']:20s} | steamid={acc['steamid']}")


if __name__ == "__main__":
    # Диагностика — запусти python macros_engine.py
    print("=== Диагностика macros_engine ===\n")

    print("Steam аккаунты:")
    print_steam_accounts()

    vdf = _find_steam_loginusers()
    print(f"\nПуть loginusers.vdf: {vdf}")

    print("\nДоступные макросы:")
    try:
        from macros import MACROS
        for m in MACROS:
            print(f"  [{m['name']}] триггеры: {m['triggers']}")
    except ImportError:
        print("  macros.py не найден рядом")
