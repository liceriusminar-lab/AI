"""
voice_daemon.py — фоновый демон голосовой активации Сильфиетты
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Работает в фоне всегда, даже когда окно скрыто в трей.

Стек:
  • Vosk        — офлайн распознавание, ~50MB модель
  • noisereduce — спектральный шумодав (убирает вентилятор)
  • pyaudio     — захват микрофона (USB/BT автовыбор)
  • requests    — отправка команды в inference-сервер

Поток:
  mic → шумодав → vosk wake-word «сильфиетта»
                        ↓
                  звуковой сигнал активации
                        ↓
                  слушать команду (до 8 сек)
                        ↓
                  шумодав → vosk распознать текст
                        ↓
                  POST /api/chat на localhost:11434
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import time
import wave
import queue
import struct
import threading
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import requests

# ── Логирование ───────────────────────────────────────────────────────────────
LOG_FILE = Path.home() / ".ai-assistant" / "voice_daemon.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("VoiceDaemon")

# ── Настройки ─────────────────────────────────────────────────────────────────

WAKE_WORDS = [
    "сильфиетта",
    "sylviette",
    "силь",          # короткий вариант если vosk режет
    "эй сильфиетта",
]

VOSK_MODEL_PATH  = Path.home() / ".ai-assistant" / "vosk-model-ru"
VOSK_MODEL_SMALL = Path.home() / ".ai-assistant" / "vosk-model-ru-small"

SAMPLE_RATE      = 44100   # Hz — оптимально для Vosk
CHUNK_SIZE       = 4000    # ~250ms чанк
WAKE_TIMEOUT     = 0.5     # сек тишины до сброса wake-буфера
COMMAND_TIMEOUT  = 8.0     # сек максимум на команду после wake-word
SILENCE_CHUNKS   = 12      # чанков тишины = конец команды (~3 сек)
ENERGY_THRESHOLD = 200     # порог энергии для детекции тишины

INFERENCE_URL    = "http://localhost:11434/api/chat"

# Шумодав
NOISE_REDUCE_ENABLED    = True
NOISE_SAMPLE_DURATION   = 1.5   # сек для снятия профиля шума при старте
NOISE_PROP_DECREASE     = 0.85  # агрессивность подавления (0.0–1.0)
NOISE_FREQ_MASK_SMOOTH  = 6     # сглаживание частотной маски


# ── Автовыбор микрофона ───────────────────────────────────────────────────────

def find_best_microphone() -> Optional[int]:
    """Выбирает микрофон: сначала из env (выбор пользователя), потом PipeWire > Pulse."""
    # Если пользователь выбрал через диалог — берём его выбор
    env_idx = os.environ.get("SYLVIETTE_MIC_INDEX")
    if env_idx is not None:
        try:
            idx = int(env_idx)
            log.info(f"✦ Микрофон из настроек пользователя: [{idx}]")
            return idx
        except ValueError:
            pass

    # Читаем сохранённый файл настроек напрямую
    settings_file = Path.home() / ".ai-assistant" / "mic_settings.json"
    if settings_file.exists():
        try:
            import json
            data = json.loads(settings_file.read_text())
            if "index" in data:
                idx = data["index"]
                log.info(f"✦ Микрофон из файла настроек: [{idx}] ({data.get('name','')})")
                return idx
        except Exception:
            pass

    # Авто: PipeWire > Pulse > остальные
    try:
        import pyaudio
        pa    = pyaudio.PyAudio()
        count = pa.get_device_count()
        pipewire = []; pulse = []; other = []
        for i in range(count):
            try:
                info = pa.get_device_info_by_index(i)
                if info["maxInputChannels"] < 1:
                    continue
                name = info["name"].lower()
                log.info(f"  Устройство [{i}]: {info['name']}")
                if "pipewire" in name: pipewire.append(i)
                elif "pulse"  in name: pulse.append(i)
                elif "hw:"   not in name: other.append(i)
            except Exception:
                continue
        pa.terminate()
        for label, lst in [("PipeWire", pipewire), ("PulseAudio", pulse), ("other", other)]:
            if lst:
                log.info(f"✦ Авто-выбор [{label}]: [{lst[0]}]")
                return lst[0]
    except Exception as e:
        log.warning(f"Ошибка выбора микрофона: {e}")
    return None


# ── Шумодав ───────────────────────────────────────────────────────────────────

class NoiseReducer:
    """
    Спектральный шумодав.
    Снимает профиль фонового шума (вентилятор, гул) при старте
    и вычитает его из входящего аудио.
    """

    def __init__(self):
        self._noise_profile: Optional[np.ndarray] = None
        self._enabled = NOISE_REDUCE_ENABLED
        self._lock = threading.Lock()

    def capture_noise_profile(self, audio_data: np.ndarray):
        """Записывает профиль шума из тихого фрагмента."""
        if not self._enabled:
            return
        try:
            import noisereduce as nr
            # Используем сам фрагмент как профиль шума
            with self._lock:
                self._noise_profile = audio_data.copy()
            log.info(f"  ✓ Профиль шума записан "
                     f"({len(audio_data)/SAMPLE_RATE:.1f}с, "
                     f"RMS={np.sqrt(np.mean(audio_data**2)):.1f})")
        except ImportError:
            log.warning("  noisereduce не установлен — шумодав отключён")
            self._enabled = False

    def process(self, audio_data: np.ndarray) -> np.ndarray:
        """Применяет шумодав к чанку аудио."""
        if not self._enabled or self._noise_profile is None:
            return audio_data
        try:
            import noisereduce as nr
            with self._lock:
                noise = self._noise_profile

            cleaned = nr.reduce_noise(
                y=audio_data.astype(np.float32),
                y_noise=noise.astype(np.float32),
                sr=SAMPLE_RATE,
                prop_decrease=NOISE_PROP_DECREASE,
                freq_mask_smooth_hz=NOISE_FREQ_MASK_SMOOTH,
                stationary=True,   # вентилятор — стационарный шум
                use_tqdm=False,
            )
            return cleaned.astype(np.int16)
        except Exception as e:
            log.debug(f"Шумодав: ошибка обработки: {e}")
            return audio_data

    @property
    def ready(self) -> bool:
        return self._noise_profile is not None or not self._enabled


# ── Vosk распознавание ────────────────────────────────────────────────────────

def load_vosk_model():
    """Загружает Vosk модель — сначала полную, потом маленькую."""
    try:
        from vosk import Model, KaldiRecognizer
    except ImportError:
        log.error("Vosk не установлен! Запусти: pip install vosk")
        return None, None

    for model_path in [VOSK_MODEL_PATH, VOSK_MODEL_SMALL]:
        if model_path.exists():
            log.info(f"✦ Загружаем Vosk модель: {model_path}")
            try:
                model = Model(str(model_path))
                log.info("  ✓ Vosk модель загружена")
                return model, KaldiRecognizer
            except Exception as e:
                log.warning(f"  Ошибка загрузки {model_path}: {e}")

    log.error(
        "Vosk модель не найдена!\n"
        "Скачай и распакуй в ~/.ai-assistant/vosk-model-ru/\n"
        "Ссылки:\n"
        "  Полная (1.8GB): https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip\n"
        "  Маленькая (45MB): https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
    )
    return None, None


def audio_to_text(audio_bytes: bytes, model, KaldiRecognizer) -> str:
    """Распознаёт речь из байтов PCM16 через Vosk."""
    try:
        rec = KaldiRecognizer(model, SAMPLE_RATE)
        rec.AcceptWaveform(audio_bytes)
        result = json.loads(rec.FinalResult())
        return result.get("text", "").strip().lower()
    except Exception as e:
        log.debug(f"Распознавание: {e}")
        return ""


def is_wake_word(text: str) -> bool:
    """Проверяет содержит ли текст wake-word."""
    text = text.lower().strip()
    for ww in WAKE_WORDS:
        if ww in text:
            return True
    return False


# ── Звуковой сигнал активации ─────────────────────────────────────────────────

def play_activation_sound():
    """Короткий звуковой сигнал что Сильфиетта слушает."""
    # Пробуем системные звуки KDE
    sounds = [
        "/usr/share/sounds/freedesktop/stereo/message.oga",
        "/usr/share/sounds/freedesktop/stereo/bell.oga",
        "/usr/share/sounds/KDE-Im-Message-In.ogg",
    ]
    for s in sounds:
        if Path(s).exists():
            subprocess.Popen(
                ["paplay", s],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return

    # Fallback — beep через sox
    try:
        subprocess.Popen(
            ["play", "-n", "synth", "0.15", "sine", "880",
             "synth", "0.1", "sine", "1100"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def notify_listening():
    """KDE уведомление — Сильфиетта слушает."""
    subprocess.Popen(
        ["notify-send", "✦ Сильфиетта слушает…", "",
         "--icon=audio-input-microphone",
         "--app-name=Sylviette AI",
         "--expire-time=3000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def notify_recognized(text: str):
    """KDE уведомление с распознанной командой."""
    subprocess.Popen(
        ["notify-send", "✦ Сильфиетта", text,
         "--icon=dialog-information",
         "--app-name=Sylviette AI",
         "--expire-time=4000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ── Отправка команды в Сильфиетту ─────────────────────────────────────────────

def send_to_sylviette(text: str):
    if not text:
        return
    import sys, os, threading
    log.info(f"✦ Команда: «{text}»")
    notify_recognized(f"🎙 «{text}»")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from macros_engine import find_macro, run_macro
        macro = find_macro(text)
        if macro:
            log.info(f"  ↳ Макрос: [{macro['name']}]")
            threading.Thread(target=run_macro, args=(macro,), daemon=True).start()
            notify_recognized(f"✦ {macro.get('response', 'Выполняю ✦')}")
            return
    except Exception as e:
        log.warning(f"  Макросы: {e}")
    try:
        resp = requests.post(INFERENCE_URL, json={
            "model": "sylviette",
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        }, timeout=60)
        if resp.status_code == 200:
            answer = resp.json().get("message", {}).get("content", "")
            if answer:
                notify_recognized(f"✦ {answer[:120]}")
    except Exception as e:
        log.warning(f"  Ошибка: {e}")


def chunk_energy(data: bytes) -> float:
    """RMS энергия чанка PCM16."""
    if len(data) < 2:
        return 0.0
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples ** 2)))


# ── Главный демон ─────────────────────────────────────────────────────────────

class VoiceDaemon:
    """
    Фоновый демон голосовой активации.
    Постоянно слушает микрофон, ищет wake-word,
    после активации записывает команду и отправляет в Сильфиетту.
    """

    def __init__(self):
        self._running   = False
        self._thread    = None
        self._noise     = NoiseReducer()
        self._model     = None
        self._KaldiRec  = None
        self._mic_index = None

    def start(self):
        if self._running:
            log.info("Демон уже запущен")
            return

        log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log.info("✦ Запускаем голосовой демон Сильфиетты")
        log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Загружаем Vosk
        self._model, self._KaldiRec = load_vosk_model()
        if self._model is None:
            log.error("Демон не запущен — нет Vosk модели")
            return

        # Выбираем микрофон
        self._mic_index = find_best_microphone()

        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(f"✦ Демон запущен | wake-word: {WAKE_WORDS[0]}")

    def stop(self):
        self._running = False
        log.info("✦ Демон остановлен")

    def _open_stream(self, pa):
        """Открывает аудио-поток с нужным микрофоном."""
        kwargs = dict(
            format=__import__("pyaudio").paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        if self._mic_index is not None:
            kwargs["input_device_index"] = self._mic_index
        try:
            return pa.open(**kwargs)
        except Exception:
            # Если указанный индекс недоступен — пробуем дефолтный
            log.warning(f"  Устройство [{self._mic_index}] недоступно, "
                        "пробую дефолтный микрофон…")
            del kwargs["input_device_index"]
            return pa.open(**kwargs)

    def _capture_noise_profile(self, stream):
        """Записывает ~1.5с шума при старте для профиля шумодава."""
        log.info(f"  Записываю профиль шума ({NOISE_SAMPLE_DURATION}с)…")
        log.info("  [не говори ничего пока идёт запись шума]")

        frames = []
        n_chunks = int(SAMPLE_RATE / CHUNK_SIZE * NOISE_SAMPLE_DURATION)
        for _ in range(n_chunks):
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(np.frombuffer(data, dtype=np.int16))
            except Exception:
                break

        if frames:
            noise_audio = np.concatenate(frames)
            self._noise.capture_noise_profile(noise_audio)

    def _loop(self):
        """Основной цикл: слушаем → wake-word → команда → отправка."""
        import pyaudio
        pa = pyaudio.PyAudio()

        try:
            stream = self._open_stream(pa)
        except Exception as e:
            log.error(f"Не удалось открыть микрофон: {e}")
            pa.terminate()
            return

        # Снимаем профиль шума
        self._capture_noise_profile(stream)
        log.info(f"✦ Слушаю wake-word: «{WAKE_WORDS[0]}»")

        # Распознаватель для wake-word (постоянно слушает)
        wake_rec = self._KaldiRec(self._model, SAMPLE_RATE)
        wake_buf = b""

        while self._running:
            try:
                # ── Режим ожидания wake-word ──────────────────────────────
                raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)

                # Шумодав на чанк
                samples = np.frombuffer(raw, dtype=np.int16)
                cleaned = self._noise.process(samples)
                data    = cleaned.tobytes()

                # Кормим Vosk
                if wake_rec.AcceptWaveform(data):
                    result = json.loads(wake_rec.Result())
                    text   = result.get("text", "").lower()
                    if text:
                        log.debug(f"  [wake] «{text}»")
                    if is_wake_word(text):
                        log.info(f"✦ Wake-word услышан! ({text!r})")
                        self._handle_command(stream)
                        # Создаём новый распознаватель после команды
                        wake_rec = self._KaldiRec(self._model, SAMPLE_RATE)

                else:
                    # Промежуточный результат — тоже проверяем
                    partial = json.loads(wake_rec.PartialResult())
                    ptext   = partial.get("partial", "").lower()
                    if is_wake_word(ptext):
                        log.info(f"✦ Wake-word (partial): {ptext!r}")
                        # Сбрасываем буфер и слушаем команду
                        wake_rec = self._KaldiRec(self._model, SAMPLE_RATE)
                        self._handle_command(stream)
                        wake_rec = self._KaldiRec(self._model, SAMPLE_RATE)

            except IOError as e:
                log.warning(f"Ошибка чтения микрофона: {e}")
                time.sleep(0.5)
                # Переподключаем микрофон
                try:
                    stream.close()
                    self._mic_index = find_best_microphone()
                    stream = self._open_stream(pa)
                    wake_rec = self._KaldiRec(self._model, SAMPLE_RATE)
                    log.info("  ✓ Микрофон переподключён")
                except Exception as e2:
                    log.error(f"  Не удалось переподключиться: {e2}")
                    time.sleep(3)
            except Exception as e:
                log.error(f"Ошибка в цикле: {e}")
                time.sleep(0.5)

        stream.close()
        pa.terminate()
        log.info("✦ Поток микрофона закрыт")

    def _handle_command(self, stream):
        """
        После wake-word: играем звук, записываем команду, распознаём, отправляем.
        """
        play_activation_sound()
        notify_listening()

        log.info("  → Слушаю команду…")

        cmd_rec    = self._KaldiRec(self._model, SAMPLE_RATE)
        frames     = []
        silence    = 0
        start_time = time.time()
        got_speech = False

        while True:
            elapsed = time.time() - start_time
            if elapsed > COMMAND_TIMEOUT:
                log.info("  → Таймаут команды")
                break

            try:
                raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except IOError:
                break

            # Шумодав
            samples = np.frombuffer(raw, dtype=np.int16)
            cleaned = self._noise.process(samples)
            data    = cleaned.tobytes()

            energy = chunk_energy(data)

            # Детекция тишины
            if energy < ENERGY_THRESHOLD:
                silence += 1
                if got_speech and silence >= SILENCE_CHUNKS:
                    log.info(f"  → Тишина {silence} чанков — конец команды")
                    break
            else:
                silence    = 0
                got_speech = True

            frames.append(data)
            cmd_rec.AcceptWaveform(data)

        if not frames or not got_speech:
            log.info("  → Команда не распознана (тишина)")
            return

        # Финальное распознавание всей команды
        cmd_rec.AcceptWaveform(b"")
        result = json.loads(cmd_rec.FinalResult())
        text   = result.get("text", "").strip().lower()

        # Убираем wake-word из начала команды если он попал
        for ww in WAKE_WORDS:
            if text.startswith(ww):
                text = text[len(ww):].strip()
                break

        log.info(f"  → Распознано: «{text}»")

        if text and len(text) > 1:
            send_to_sylviette(text)
        else:
            log.info("  → Команда слишком короткая — игнорирую")


# ── Глобальный экземпляр ──────────────────────────────────────────────────────

_daemon: Optional[VoiceDaemon] = None


def get_daemon() -> VoiceDaemon:
    global _daemon
    if _daemon is None:
        _daemon = VoiceDaemon()
    return _daemon


def start_voice_daemon():
    """Запускает демон — вызывать из main.py."""
    get_daemon().start()


def stop_voice_daemon():
    """Останавливает демон."""
    if _daemon:
        _daemon.stop()


# ── Запуск как отдельный процесс ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sylviette Voice Daemon")
    parser.add_argument("--test-mic",   action="store_true", help="Проверить микрофоны")
    parser.add_argument("--test-noise", action="store_true", help="Тест шумодава")
    parser.add_argument("--run",        action="store_true", help="Запустить демон")
    args = parser.parse_args()

    if args.test_mic:
        print("\n=== Доступные микрофоны ===")
        find_best_microphone()

    elif args.test_noise:
        print("\n=== Тест шумодава ===")
        try:
            import noisereduce
            print("✓ noisereduce установлен")
        except ImportError:
            print("✗ noisereduce не установлен: pip install noisereduce")
        try:
            import pyaudio
            print("✓ pyaudio установлен")
        except ImportError:
            print("✗ pyaudio не установлен: pip install pyaudio")
        try:
            from vosk import Model
            print(f"✓ vosk установлен")
            for p in [VOSK_MODEL_PATH, VOSK_MODEL_SMALL]:
                if p.exists():
                    print(f"✓ Модель: {p}")
                else:
                    print(f"✗ Нет модели: {p}")
        except ImportError:
            print("✗ vosk не установлен: pip install vosk")

    elif args.run:
        daemon = VoiceDaemon()
        daemon.start()
        print(f"\n✦ Голосовой демон запущен")
        print(f"  Wake-word: «{WAKE_WORDS[0]}»")
        print(f"  Лог: {LOG_FILE}")
        print(f"  Ctrl+C для остановки\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            daemon.stop()
            print("\n✦ Остановлен")

    else:
        parser.print_help()
