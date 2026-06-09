#!/bin/bash
# fix2.sh — прямое исправление без патч-скриптов
cd ~/ai-assistant

echo "[1/3] Жёстко прописываем PipeWire в voice_daemon.py..."
# Меняем SAMPLE_RATE на 44100 — его поддерживают все устройства включая hw:
sed -i 's/^SAMPLE_RATE.*=.*16000/SAMPLE_RATE      = 44100/' voice_daemon.py
echo "  ✓ SAMPLE_RATE = 44100"

# Принудительно выбираем pipewire (устройство 10) через переменную окружения
# и жёстко прописываем индекс pipewire если он найден
python3 - << 'PYEOF'
with open("voice_daemon.py", encoding="utf-8") as f:
    src = f.read()

# Заменяем всю функцию find_best_microphone на простую версию
# которая ищет pipewire/pulse и берёт первый найденный
old = "        if usb_devices:\n            log.info(f\"✦ Выбран USB микрофон: [{usb_devices[0]}]\")\n            return usb_devices[0]\n        if bt_devices:\n            log.info(f\"✦ Выбрана BT гарнитура: [{bt_devices[0]}]\")\n            return bt_devices[0]\n        if any_devices:\n            log.info(f\"✦ Выбран микрофон: [{any_devices[0]}]\")\n            return any_devices[0]\n\n        log.info(\"✦ Используется микрофон по умолчанию\")\n        return None\n\n    except Exception as e:\n        log.warning(f\"Ошибка при выборе микрофона: {e}\")\n        return None"

new = """        # Приоритет: pipewire > pulse > usb > bt > остальные (не hw:)
        for label, lst in [
            ("PipeWire", [i for i in usb_devices + bt_devices + any_devices
                          if "pipewire" in pa.get_device_info_by_index(i)["name"].lower()]),
            ("PulseAudio",[i for i in usb_devices + bt_devices + any_devices
                          if "pulse" in pa.get_device_info_by_index(i)["name"].lower()]),
            ("USB",  usb_devices),
            ("BT",   bt_devices),
            ("other",any_devices),
        ]:
            if lst:
                log.info(f"✦ Выбран микрофон [{label}]: [{lst[0]}]")
                return lst[0]

        log.info("✦ Используется микрофон по умолчанию")
        return None

    except Exception as e:
        log.warning(f"Ошибка при выборе микрофона: {e}")
        return None"""

# Более простой подход — полностью заменяем тело функции
import re
new_func = '''def find_best_microphone() -> Optional[int]:
    """Выбирает микрофон: PipeWire > Pulse > USB > BT > остальные."""
    try:
        import pyaudio
        pa    = pyaudio.PyAudio()
        count = pa.get_device_count()

        pipewire = []
        pulse    = []
        usb      = []
        bt       = []
        other    = []

        for i in range(count):
            try:
                info = pa.get_device_info_by_index(i)
                if info["maxInputChannels"] < 1:
                    continue
                name = info["name"].lower()
                log.info(f"  Устройство [{i}]: {info['name']} "
                         f"(вх. каналов: {info['maxInputChannels']})")
                if "pipewire" in name:
                    pipewire.append(i)
                elif "pulse" in name:
                    pulse.append(i)
                elif any(k in name for k in ["usb", "usb mic"]):
                    usb.append(i)
                elif any(k in name for k in ["bluetooth","bt","wireless","headset"]):
                    bt.append(i)
                elif "hw:" not in name:
                    other.append(i)
            except Exception:
                continue

        pa.terminate()

        for label, lst in [("PipeWire", pipewire), ("PulseAudio", pulse),
                            ("USB", usb), ("BT", bt), ("other", other)]:
            if lst:
                log.info(f"✦ Выбран микрофон [{label}]: [{lst[0]}]")
                return lst[0]

        log.info("✦ Используется микрофон по умолчанию")
        return None

    except Exception as e:
        log.warning(f"Ошибка при выборе микрофона: {e}")
        return None

'''

src = re.sub(
    r'def find_best_microphone\(\).*?(?=\n# ──)',
    new_func,
    src, flags=re.DOTALL, count=1
)

with open("voice_daemon.py", "w", encoding="utf-8") as f:
    f.write(src)
print("  ✓ find_best_microphone() заменена")
PYEOF

echo ""
echo "[2/3] Добавляем _toggle_voice в main_window.py..."
python3 - << 'PYEOF'
with open("ui/main_window.py", encoding="utf-8") as f:
    src = f.read()

if "def _toggle_voice" in src:
    print("  ✓ _toggle_voice уже есть")
else:
    method = '''    def _toggle_voice(self, checked):
        try:
            from voice_daemon import get_daemon
            daemon = get_daemon()
            if checked:
                daemon.start()
                self._voice_btn.setText("🎙 Голос: слушаю")
                self.status_label.setText("✦ Голосовая активация включена")
            else:
                daemon.stop()
                self._voice_btn.setText("🎙 Голос: пауза")
                self.status_label.setText("🎙 Голосовая активация на паузе")
        except Exception as e:
            self.status_label.setText(f"🎙 Ошибка: {e}")
        QTimer.singleShot(3000, lambda: self.status_label.setText("Готово ✦"))

    def _toggle_stt(self, checked):'''

    src = src.replace("    def _toggle_stt(self, checked):", method, 1)

    with open("ui/main_window.py", "w", encoding="utf-8") as f:
        f.write(src)
    print("  ✓ _toggle_voice добавлен")
PYEOF

echo ""
echo "[3/3] Проверяем результат..."
grep -n "SAMPLE_RATE" voice_daemon.py | head -3
grep -n "def find_best_microphone" voice_daemon.py
grep -n "def _toggle_voice" ui/main_window.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✦ Готово! Запускай: python3 main.py"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
