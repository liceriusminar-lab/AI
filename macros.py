"""
macros.py — макросы Сильфиетты
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Как добавить свой макрос:
  1. Придумай имя, триггеры (фразы), действия
  2. Добавь блок в MACROS ниже по образцу
  3. Сохрани — работает сразу, перезапуск не нужен

Типы действий:
  launch_app     — запустить приложение
  open_url       — открыть URL в браузере
  steam_game     — запустить игру в Steam (нужен app_id)
  steam_switch   — переключить аккаунт Steam перед запуском
  delay          — пауза в секундах перед следующим действием
  notify         — показать уведомление
  shell          — выполнить shell-команду
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ══ НАСТРОЙКИ ════════════════════════════════════════════════

# Твой основной аккаунт Steam (логин, как он отображается при выборе)
STEAM_MAIN_ACCOUNT = "licerius"   # ← поменяй на свой логин

# War Thunder App ID в Steam
WAR_THUNDER_APP_ID = "236390"

# Путь к Steam (обычно этот, на Arch/Manjaro)
STEAM_PATH = "/usr/bin/steam"

# Браузер
BROWSER = "flatpak run com.brave.Browser"

# ══ МАКРОСЫ ══════════════════════════════════════════════════

MACROS = [

    # ─── "Я дома" ────────────────────────────────────────────
    {
        "name": "я_дома",
        "description": "Домашний режим: браузер со Spotify + Steam + War Thunder",
        "triggers": [
            "я дома",
            "вернулся домой",
            "дома",
            "home mode",
        ],
        "response": "С возвращением, Создатель… Запускаю всё как обычно ✦",
        "actions": [
            # 1. Открываем браузер со Spotify
            {
                "type": "open_url",
                "url": "https://open.spotify.com",
                "comment": "Spotify в браузере"
            },
            # 2. Пауза чтобы браузер успел открыться
            {
                "type": "delay",
                "seconds": 2
            },
            # 3. Переключаем Steam на основной аккаунт и запускаем War Thunder
            {
                "type": "steam_switch_and_launch",
                "account": STEAM_MAIN_ACCOUNT,
                "app_id": WAR_THUNDER_APP_ID,
                "comment": "Steam: основной аккаунт → War Thunder"
            },
            # 4. Уведомление
            {
                "type": "notify",
                "title": "Сильфиетта",
                "message": "Домашний режим активирован ✦"
            },
        ]
    },

    # ─── "Режим работы" ──────────────────────────────────────
    {
        "name": "работа",
        "description": "Рабочий режим: открыть VS Code + браузер",
        "triggers": [
            "режим работы",
            "начинаю работать",
            "work mode",
            "рабочий режим",
        ],
        "response": "Включаю рабочий режим, Создатель… Удачи! ✦",
        "actions": [
            {
                "type": "launch_app",
                "cmd": "code",
                "comment": "VS Code"
            },
            {
                "type": "open_url",
                "url": "https://github.com",
                "comment": "GitHub в браузере"
            },
            {
                "type": "notify",
                "title": "Сильфиетта",
                "message": "Рабочий режим включён ✦"
            },
        ]
    },

    # ─── "Спокойной ночи" ────────────────────────────────────
    {
        "name": "спокойной_ночи",
        "description": "Закрыть Steam, выключить уведомления",
        "triggers": [
            "спокойной ночи",
            "иду спать",
            "night mode",
            "ночной режим",
        ],
        "response": "Спокойной ночи, Создатель… Закрываю всё ✦",
        "actions": [
            {
                "type": "shell",
                "cmd": "pkill -f steam || true",
                "comment": "Закрыть Steam"
            },
            {
                "type": "shell",
                "cmd": "pkill -f spotify || true",
                "comment": "Закрыть Spotify (если десктоп)"
            },
            {
                "type": "notify",
                "title": "Сильфиетта",
                "message": "Ночной режим… Спокойной ночи ✦"
            },
        ]
    },

    # ─── Добавляй свои макросы ниже по образцу ───────────────
    # {
    #     "name": "мой_макрос",
    #     "description": "Что делает",
    #     "triggers": ["фраза 1", "фраза 2"],
    #     "response": "Ответ Сильфиетты",
    #     "actions": [
    #         {"type": "open_url", "url": "https://..."},
    #         {"type": "launch_app", "cmd": "discord"},
    #         {"type": "delay", "seconds": 1},
    #         {"type": "notify", "title": "...", "message": "..."},
    #     ]
    # },

]
