#!/bin/bash
# install_voice.sh — установка голосовой активации Сильфиетты
# Запуск: bash install_voice.sh

set -e
cd ~/ai-assistant
source venv/bin/activate

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Sylviette — установка голосовой активации ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Системные зависимости ──────────────────────────────────
echo "[1/5] Системные пакеты (portaudio, sox)…"
sudo pacman -S --needed --noconfirm portaudio sox 2>/dev/null || {
    echo "  ⚠ pacman не сработал, пробую без sudo…"
    pacman -S --needed --noconfirm portaudio sox 2>/dev/null || true
}
echo "  ✓ Системные пакеты"

# ── 2. Python пакеты ──────────────────────────────────────────
echo ""
echo "[2/5] Python пакеты (vosk, pyaudio, noisereduce)…"

pip install vosk          --break-system-packages -q
echo "  ✓ vosk"

pip install pyaudio       --break-system-packages -q || {
    echo "  Пробую через pipx/pip напрямую…"
    pip install pyaudio --break-system-packages 2>&1 | tail -3
}
echo "  ✓ pyaudio"

pip install noisereduce   --break-system-packages -q
echo "  ✓ noisereduce"

pip install scipy         --break-system-packages -q
echo "  ✓ scipy"

pip install numpy         --break-system-packages -q
echo "  ✓ numpy"

# ── 3. Vosk модель ────────────────────────────────────────────
echo ""
echo "[3/5] Vosk русская модель…"

MODEL_DIR="$HOME/.ai-assistant"
mkdir -p "$MODEL_DIR"

SMALL_MODEL_URL="https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
SMALL_MODEL_ZIP="$MODEL_DIR/vosk-model-small-ru.zip"
SMALL_MODEL_DIR="$MODEL_DIR/vosk-model-ru-small"

FULL_MODEL_URL="https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip"
FULL_MODEL_ZIP="$MODEL_DIR/vosk-model-ru.zip"
FULL_MODEL_DIR="$MODEL_DIR/vosk-model-ru"

if [ -d "$FULL_MODEL_DIR" ]; then
    echo "  ✓ Полная модель уже скачана: $FULL_MODEL_DIR"
elif [ -d "$SMALL_MODEL_DIR" ]; then
    echo "  ✓ Маленькая модель уже скачана: $SMALL_MODEL_DIR"
else
    echo "  Какую модель скачать?"
    echo "  1) Маленькая (45 MB)  — быстрее, точность чуть ниже"
    echo "  2) Полная   (1.8 GB)  — медленнее загрузка, лучше точность"
    read -p "  Выбор [1/2, Enter = 1]: " MODEL_CHOICE
    MODEL_CHOICE=${MODEL_CHOICE:-1}

    if [ "$MODEL_CHOICE" = "2" ]; then
        echo "  Скачиваю полную модель (1.8 GB)…"
        wget -q --show-progress -O "$FULL_MODEL_ZIP" "$FULL_MODEL_URL"
        echo "  Распаковываю…"
        cd "$MODEL_DIR"
        unzip -q "$FULL_MODEL_ZIP"
        # Папка внутри архива называется vosk-model-ru-0.42
        mv vosk-model-ru-0.42 vosk-model-ru 2>/dev/null || true
        rm -f "$FULL_MODEL_ZIP"
        echo "  ✓ Полная модель: $FULL_MODEL_DIR"
        cd ~/ai-assistant
    else
        echo "  Скачиваю маленькую модель (45 MB)…"
        wget -q --show-progress -O "$SMALL_MODEL_ZIP" "$SMALL_MODEL_URL"
        echo "  Распаковываю…"
        cd "$MODEL_DIR"
        unzip -q "$SMALL_MODEL_ZIP"
        mv vosk-model-small-ru-0.22 vosk-model-ru-small 2>/dev/null || true
        rm -f "$SMALL_MODEL_ZIP"
        echo "  ✓ Маленькая модель: $SMALL_MODEL_DIR"
        cd ~/ai-assistant
    fi
fi

# ── 4. Копируем voice_daemon.py ───────────────────────────────
echo ""
echo "[4/5] Проверяем voice_daemon.py…"
if [ ! -f "voice_daemon.py" ]; then
    echo "  ⚠ voice_daemon.py не найден в ~/ai-assistant/"
    echo "  Положи его туда и запусти скрипт снова"
else
    echo "  ✓ voice_daemon.py на месте"
fi

# ── 5. Патч main.py — автозапуск демона ──────────────────────
echo ""
echo "[5/5] Патч main.py — автозапуск голосового демона…"

python3 - << 'PYEOF'
path = "main.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

import_line = "from voice_daemon import start_voice_daemon"
call_line   = "    start_voice_daemon()"

if import_line in src:
    print("  ✓ Демон уже подключён к main.py")
else:
    # Добавляем импорт
    src = src.replace(
        "from config import COLORS, ICON_PATH",
        "from config import COLORS, ICON_PATH\nfrom voice_daemon import start_voice_daemon",
        1
    )
    # Добавляем вызов после start_backend()
    src = src.replace(
        "    start_backend()\n    win = MainWindow()",
        "    start_backend()\n    start_voice_daemon()\n    win = MainWindow()",
        1
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("  ✓ main.py пропатчен — демон запустится автоматически")
PYEOF

# ── Тест ─────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  Проверка установки:"
echo "══════════════════════════════════════════════"
python3 voice_daemon.py --test-noise

echo ""
echo "  Список микрофонов:"
python3 voice_daemon.py --test-mic

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        ✦ Установка завершена!               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Тест вручную (без перезапуска приложения):"
echo "  python3 voice_daemon.py --run"
echo ""
echo "  Затем скажи: «Сильфиетта»"
echo "  После звукового сигнала — команда."
echo ""
echo "  При следующем запуске main.py демон стартует автоматически."
echo "  Лог: ~/.ai-assistant/voice_daemon.log"
echo ""
