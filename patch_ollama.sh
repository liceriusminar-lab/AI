#!/bin/bash
# patch_ollama.sh — добавляет поддержку макросов в ollama_worker.py
# Запуск: bash patch_ollama.sh

set -e
cd ~/ai-assistant

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Патч ollama_worker.py — макросы ✦     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Копируем файлы макросов ───────────────────────────────────
echo "[1/3] Копируем macros.py и macros_engine.py…"

# Файлы должны лежать рядом с ollama_worker.py (в ~/ai-assistant/)
# Если ты положил их в другое место — поменяй пути ниже:
MACROS_SRC="$HOME/ai-assistant/macros.py"
ENGINE_SRC="$HOME/ai-assistant/macros_engine.py"

if [ ! -f "$MACROS_SRC" ]; then
    echo "  ⚠ macros.py не найден в ~/ai-assistant/"
    echo "  Положи macros.py и macros_engine.py в ~/ai-assistant/ и запусти снова"
    exit 1
fi

if [ ! -f "$ENGINE_SRC" ]; then
    echo "  ⚠ macros_engine.py не найден в ~/ai-assistant/"
    exit 1
fi

echo "  ✓ Файлы на месте"

# ── Бэкап ollama_worker.py ────────────────────────────────────
echo "[2/3] Бэкап ollama_worker.py…"
cp ollama_worker.py ollama_worker.py.bak
echo "  ✓ ollama_worker.py.bak создан"

# ── Патч: добавляем импорт и логику макросов ─────────────────
echo "[3/3] Патчим ollama_worker.py…"

python3 - << 'PYEOF'
import re

path = "ollama_worker.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

# ── Шаг 1: добавляем импорт после блока импортов ─────────────
import_line = "from macros_engine import find_macro, run_macro"
if import_line in src:
    print("  ✓ Импорт уже добавлен — пропускаем")
else:
    # Вставляем после последнего import в начале файла
    src = src.replace(
        "from calendar_manager import handle_calendar_command\n",
        "from calendar_manager import handle_calendar_command\n"
        "from macros_engine import find_macro, run_macro\n",
        1
    )
    print("  ✓ Импорт добавлен")

# ── Шаг 2: добавляем проверку макросов в run() ───────────────
macro_block = '''
            # ── Макросы ──────────────────────────────────────────────
            macro = find_macro(last_msg)
            if macro:
                import threading
                def _run_macro_bg():
                    run_macro(macro)
                t = threading.Thread(target=_run_macro_bg, daemon=True)
                t.start()
                self.finished.emit(macro.get("response", "Выполняю, Создатель… ✦"))
                return
            # ─────────────────────────────────────────────────────────
'''

if "find_macro(last_msg)" in src:
    print("  ✓ Логика макросов уже добавлена — пропускаем")
else:
    # Вставляем ПЕРЕД проверкой question_words
    target = "            # Не выполняем hardcode если это вопрос"
    if target in src:
        src = src.replace(target, macro_block + "            # Не выполняем hardcode если это вопрос", 1)
        print("  ✓ Логика макросов добавлена")
    else:
        # Запасной вариант — перед _try_hardcode
        target2 = "            if not is_question and self._try_hardcode(last_msg):"
        if target2 in src:
            src = src.replace(target2, macro_block + "            if not is_question and self._try_hardcode(last_msg):", 1)
            print("  ✓ Логика макросов добавлена (запасной вариант)")
        else:
            print("  ⚠ Не удалось найти место для вставки — добавь вручную")
            print("  Смотри PATCH_README.py для инструкции")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

print("  ✓ ollama_worker.py сохранён")
PYEOF

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       ✦ Патч успешно применён!          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Теперь Сильфиетта понимает макросы!"
echo ""
echo "  Тест — напиши в чате: «я дома»"
echo "  Она запустит Spotify + Steam + War Thunder"
echo ""
echo "  Диагностика Steam аккаунтов:"
echo "  python3 macros_engine.py"
echo ""
echo "  Добавить новый макрос:"
echo "  nano macros.py"
echo ""
