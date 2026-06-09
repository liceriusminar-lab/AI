"""
macros.py — макросы Сильфиетты
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Поле "if" — условие выполнения действия (необязательно).
Если условие не выполнено — действие тихо пропускается.

Условия (русский и английский):
  Процессы:   "steam running"       / "steam not running"
              "browser not running" / "discord running"
  Время:      "утро" "день" "вечер" "ночь"
              "morning" "day" "evening" "night"
  День:       "пятница" "выходной" "будний"
              "friday" "weekend" "weekday"
  Отрицание:  "не вечер" / "not evening"
  Комбо:      "вечер and пятница" / "steam not running and weekend"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ══ НАСТРОЙКИ ════════════════════════════════════════════════

STEAM_MAIN_ACCOUNT = "licerius"
WAR_THUNDER_APP_ID = "236390"
STEAM_PATH         = "/usr/bin/steam"
BROWSER            = "flatpak run com.brave.Browser"

# ══ МАКРОСЫ ══════════════════════════════════════════════════

MACROS = [

    # ─── "Я дома" в пятницу вечером — ставь ВЫШЕ обычного ───
    {
        "name": "пятница_вечер",
        "description": "Пятничный вечер — режим отдыха",
        "triggers": ["я дома", "вернулся домой", "дома"],
        "condition": "вечер and пятница",
        "response": "О, пятница вечером… Включаю режим отдыха, Создатель ✦",
        "actions": [
            {
                "type": "open_url",
                "url": "https://open.spotify.com",
                "if": "browser not running",
            },
            {
                "type": "steam_switch_and_launch",
                "account": STEAM_MAIN_ACCOUNT,
                "app_id": WAR_THUNDER_APP_ID,
                "if": "steam not running",
            },
            {
                "type": "steam_game",
                "app_id": WAR_THUNDER_APP_ID,
                "if": "steam running",
            },
            {
                "type": "notify",
                "title": "Сильфиетта",
                "message": "Пятница вечером — хорошего отдыха ✦"
            },
        ]
    },

    # ─── "Я дома" — обычный сценарий ─────────────────────────
    {
        "name": "я_дома",
        "description": "Домашний режим с проверкой что уже запущено",
        "triggers": ["я дома", "вернулся домой", "дома", "home mode"],
        "response": "С возвращением, Создатель… Запускаю всё ✦",
        "actions": [
            {
                "type": "open_url",
                "url": "https://open.spotify.com",
                "if": "browser not running",
                "comment": "Spotify — только если браузер не открыт"
            },
            {
                "type": "open_url",
                "url": "https://open.spotify.com",
                "if": "browser running",
                "comment": "Spotify в уже открытом браузере"
            },
            {"type": "delay", "seconds": 2},
            {
                "type": "steam_switch_and_launch",
                "account": STEAM_MAIN_ACCOUNT,
                "app_id": WAR_THUNDER_APP_ID,
                "if": "steam not running",
                "comment": "Steam + War Thunder если Steam не запущен"
            },
            {
                "type": "steam_game",
                "app_id": WAR_THUNDER_APP_ID,
                "if": "steam running",
                "comment": "War Thunder — Steam уже запущен"
            },
            {
                "type": "notify",
                "title": "Сильфиетта",
                "message": "Домашний режим активирован ✦"
            },
        ]
    },

    # ─── Режим работы ─────────────────────────────────────────
    {
        "name": "работа",
        "description": "Рабочий режим — только в будние дни",
        "triggers": ["режим работы", "начинаю работать", "work mode", "рабочий режим"],
        "response": "Включаю рабочий режим, Создатель… Удачи! ✦",
        "actions": [
            {
                "type": "launch_app",
                "cmd": "code",
                "if": "vscode not running",
            },
            {
                "type": "open_url",
                "url": "https://github.com",
                "if": "утро",
                "comment": "GitHub только утром"
            },
            {
                "type": "shell",
                "cmd": "pkill -f steam || true",
                "if": "steam running",
                "comment": "Закрыть Steam — не отвлекаться"
            },
            {
                "type": "shell",
                "cmd": "pkill -f discord || true",
                "if": "discord running",
            },
            {
                "type": "notify",
                "title": "Сильфиетта",
                "message": "Рабочий режим включён ✦"
            },
        ]
    },

    # ─── Спокойной ночи ───────────────────────────────────────
    {
        "name": "спокойной_ночи",
        "description": "Ночной режим — закрывает всё запущенное",
        "triggers": ["спокойной ночи", "иду спать", "night mode", "ночной режим"],
        "response": "Спокойной ночи, Создатель… Закрываю всё ✦",
        "actions": [
            {"type": "shell", "cmd": "pkill -f steam    || true", "if": "steam running"},
            {"type": "shell", "cmd": "pkill -f discord  || true", "if": "discord running"},
            {"type": "shell", "cmd": "pkill -f telegram || true", "if": "telegram running"},
            {"type": "notify", "title": "Сильфиетта", "message": "Спокойной ночи… ✦"},
        ]
    },

    # ─── Шаблон для своих макросов ────────────────────────────
    # {
    #     "name": "мой_макрос",
    #     "triggers": ["фраза 1", "фраза 2"],
    #     "condition": "вечер",            # условие на ВЕСЬ макрос
    #     "response": "Ответ Сильфиетты",
    #     "actions": [
    #         {"type": "open_url",    "url": "https://...", "if": "browser not running"},
    #         {"type": "launch_app",  "cmd": "discord",     "if": "discord not running"},
    #         {"type": "steam_game",  "app_id": "XXXXXX",   "if": "steam running"},
    #         {"type": "delay",       "seconds": 2},
    #         {"type": "shell",       "cmd": "команда",     "if": "выходной"},
    #         {"type": "notify",      "title": "...", "message": "..."},
    #     ]
    # },
]
