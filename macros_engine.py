"""
macros_engine.py — движок выполнения макросов Сильфиетты
Версия 2 — с поддержкой условий через macros_conditions.py
"""

import subprocess
import time
import os
import re
from pathlib import Path
from typing import Optional

from macros_conditions import check_condition


# ── Steam helpers ─────────────────────────────────────────────────────────────

def _find_steam_loginusers() -> Optional[Path]:
    candidates = [
        Path.home() / ".steam/steam/config/loginusers.vdf",
        Path.home() / ".local/share/Steam/config/loginusers.vdf",
    ]
    for p in candidates:
        if p.exists():
            return p
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
    vdf_path = _find_steam_loginusers()
    if not vdf_path:
        return []
    accounts = []
    try:
        content = vdf_path.read_text(encoding="utf-8", errors="replace")
        blocks  = re.split(r'"(\d{17})"', content)
        i = 1
        while i < len(blocks) - 1:
            steamid = blocks[i]
            block   = blocks[i + 1]
            acc = {"steamid": steamid, "accountname": "", "personaname": ""}
            m = re.search(r'"AccountName"\s+"([^"]+)"', block, re.IGNORECASE)
            if m: acc["accountname"] = m.group(1)
            m = re.search(r'"PersonaName"\s+"([^"]+)"', block, re.IGNORECASE)
            if m: acc["personaname"] = m.group(1)
            if acc["accountname"]:
                accounts.append(acc)
            i += 2
    except Exception as e:
        print(f"  ⚠ loginusers.vdf: {e}")
    return accounts


def steam_switch_account(account_login: str) -> bool:
    accounts = _get_steam_accounts()
    target   = None
    for acc in accounts:
        if acc["accountname"].lower() == account_login.lower():
            target = acc
            break
    if not target:
        for acc in accounts:
            if account_login.lower() in acc["accountname"].lower():
                target = acc
                break
    if not target:
        print(f"  ⚠ Аккаунт '{account_login}' не найден. "
              f"Доступны: {[a['accountname'] for a in accounts]}")
        return False

    print(f"  ✦ Переключаю Steam → {target['accountname']}")
    subprocess.run(["pkill", "-f", "steam"], capture_output=True)
    time.sleep(2)

    for cmd in [["steam", f"-login", target["accountname"]],
                ["flatpak", "run", "com.valvesoftware.Steam",
                 f"-login", target["accountname"]]]:
        try:
            subprocess.Popen(cmd, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            continue
    return False


def steam_launch_game(app_id: str, wait_for_steam: int = 12) -> bool:
    print(f"  ⏳ Жду {wait_for_steam}с пока Steam загрузится…")
    time.sleep(wait_for_steam)
    url = f"steam://rungameid/{app_id}"
    print(f"  🎮 Запускаю: {url}")
    try:
        subprocess.Popen(["xdg-open", url], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"  ⚠ {e}")
        return False


# ── Базовые действия ──────────────────────────────────────────────────────────

def _notify(title: str, message: str):
    try:
        subprocess.Popen(
            ["notify-send", title, message,
             "--icon=dialog-information",
             "--app-name=Сильфиетта",
             "--expire-time=5000"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _open_url(url: str, browser: str = "flatpak run com.brave.Browser"):
    subprocess.Popen(browser.split() + [url], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  🌐 Открываю: {url}")


def _launch_app(cmd: str):
    subprocess.Popen(cmd.split(), start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  🚀 Запускаю: {cmd}")


def _shell(cmd: str):
    subprocess.run(cmd, shell=True, capture_output=True)
    print(f"  ⚡ Shell: {cmd}")


# ── Выполнение одного действия ────────────────────────────────────────────────

def _run_action(action: dict):
    """
    Выполняет одно действие.
    Перед выполнением проверяет поле "if" через check_condition.
    """
    condition = action.get("if", None)

    # Проверяем условие — если не выполнено, пропускаем
    if not check_condition(condition):
        return

    atype   = action.get("type", "")
    comment = action.get("comment", "")
    label   = comment or atype
    print(f"    ▸ {label}", flush=True)

    if atype == "delay":
        time.sleep(action.get("seconds", 1))

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
        steam_switch_account(action.get("account", ""))
        if action.get("app_id"):
            steam_launch_game(action["app_id"], wait_for_steam=14)

    elif atype == "steam_game":
        steam_launch_game(action.get("app_id", ""), wait_for_steam=5)

    elif atype == "steam_switch":
        steam_switch_account(action.get("account", ""))

    else:
        print(f"    ⚠ Неизвестный тип: {atype}")


# ── Выполнение макроса ────────────────────────────────────────────────────────

def run_macro(macro: dict) -> str:
    """
    Выполняет все действия макроса.
    Сначала проверяет глобальное условие макроса (поле "condition"),
    потом для каждого действия проверяет его локальное "if".
    """
    name = macro.get("name", "?")
    print(f"\n✦ Макрос [{name}]", flush=True)

    # Глобальное условие макроса
    global_cond = macro.get("condition")
    if global_cond and not check_condition(global_cond):
        print(f"  ⏭ Глобальное условие не выполнено: «{global_cond}» → пропускаю макрос")
        return ""

    for i, action in enumerate(macro.get("actions", []), 1):
        print(f"  [{i}/{len(macro['actions'])}]", end=" ", flush=True)
        _run_action(action)

    print(f"✦ [{name}] завершён\n", flush=True)
    return macro.get("response", f"Готово, Создатель ✦")


# ── Поиск макроса по фразе ────────────────────────────────────────────────────

def find_macro(text: str) -> Optional[dict]:
    """
    Ищет подходящий макрос по триггеру.
    Если у макроса есть "condition" — проверяет его сразу,
    чтобы выбрать правильный вариант (например пятница_вечер vs я_дома).
    """
    try:
        from macros import MACROS
    except ImportError:
        return None

    text_lower = text.lower().strip()

    for macro in MACROS:
        # Проверяем триггер
        triggered = any(
            t.lower() == text_lower or t.lower() in text_lower
            for t in macro.get("triggers", [])
        )
        if not triggered:
            continue

        # Если у макроса есть глобальное условие — проверяем его
        # Если не выполнено — ищем следующий подходящий макрос
        global_cond = macro.get("condition")
        if global_cond and not check_condition(global_cond):
            print(f"  ⏭ Макрос [{macro['name']}]: условие «{global_cond}» не выполнено, ищу дальше…")
            continue

        return macro

    return None


# ── Диагностика ───────────────────────────────────────────────────────────────

def print_steam_accounts():
    accounts = _get_steam_accounts()
    if not accounts:
        print("Steam аккаунты не найдены")
        return
    print(f"Steam аккаунтов: {len(accounts)}")
    for i, acc in enumerate(accounts, 1):
        print(f"  {i}. {acc['accountname']:20s} | {acc['personaname']:20s} | {acc['steamid']}")


if __name__ == "__main__":
    print("=== Диагностика macros_engine ===\n")
    print_steam_accounts()
    print("\nДоступные макросы:")
    try:
        from macros import MACROS
        for m in MACROS:
            cond = f" [если: {m['condition']}]" if m.get("condition") else ""
            print(f"  [{m['name']}]{cond} → триггеры: {m['triggers']}")
    except ImportError:
        print("  macros.py не найден")

    print("\nТекущие условия:")
    from macros_conditions import debug_conditions
    debug_conditions()
