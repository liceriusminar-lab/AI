"""
stt.py — голосовой ввод для Сильфиетты
Использует SpeechRecognition + Google STT (онлайн) или Vosk (офлайн)
"""
import threading
import queue
from typing import Callable, Optional


class STTWorker(threading.Thread):
    """Фоновый поток записи и распознавания голоса."""

    def __init__(self, on_result: Callable[[str], None],
                 on_error: Callable[[str], None],
                 language: str = "ru-RU"):
        super().__init__(daemon=True)
        self.on_result = on_result
        self.on_error  = on_error
        self.language  = language
        self._stop     = threading.Event()

    def run(self):
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.energy_threshold    = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold     = 0.8

            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                try:
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
                except sr.WaitTimeoutError:
                    self.on_error("Тишина — попробуйте ещё раз")
                    return

            # Пробуем Google STT
            try:
                text = recognizer.recognize_google(audio, language=self.language)
                if text:
                    self.on_result(text)
                return
            except sr.UnknownValueError:
                self.on_error("Не удалось распознать речь")
            except sr.RequestError:
                # Офлайн fallback — Vosk
                self._try_vosk(audio)

        except ImportError as e:
            self.on_error(f"Библиотека недоступна: {e}")
        except Exception as e:
            self.on_error(f"Ошибка микрофона: {e}")

    def _try_vosk(self, audio):
        try:
            import vosk, json as _json
            import os
            model_path = os.path.expanduser("~/.ai-assistant/vosk-model-ru")
            if not os.path.exists(model_path):
                self.on_error("Нет интернета и нет офлайн-модели Vosk")
                return
            model = vosk.Model(model_path)
            rec   = vosk.KaldiRecognizer(model, 16000)
            raw   = audio.get_raw_data(convert_rate=16000, convert_width=2)
            rec.AcceptWaveform(raw)
            result = _json.loads(rec.FinalResult())
            text   = result.get("text", "")
            if text:
                self.on_result(text)
            else:
                self.on_error("Не удалось распознать речь (офлайн)")
        except Exception as e:
            self.on_error(f"Vosk ошибка: {e}")


def check_microphone() -> tuple[bool, str]:
    """Проверяет доступность микрофона."""
    try:
        import speech_recognition as sr
        mics = sr.Microphone.list_microphone_names()
        if mics:
            return True, f"Найдено микрофонов: {len(mics)}"
        return False, "Микрофон не найден"
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    ok, msg = check_microphone()
    print(f"Микрофон: {msg}")
    if ok:
        def on_result(text): print(f"Распознано: {text}")
        def on_error(err):   print(f"Ошибка: {err}")
        print("Говорите...")
        w = STTWorker(on_result, on_error)
        w.start()
        w.join()
