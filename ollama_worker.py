import json
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from config import OLLAMA_URL


class OllamaWorker(QThread):
    token_received = pyqtSignal(str)   # каждый токен стриминга
    finished       = pyqtSignal(str)   # полный ответ по завершению
    error          = pyqtSignal(str)   # ошибка

    def __init__(self, model, messages):
        super().__init__()
        self.model    = model
        self.messages = messages

    def run(self):
        try:
            resp = requests.post(OLLAMA_URL, json={
                "model":    self.model,
                "messages": self.messages,
                "stream":   True
            }, stream=True, timeout=120)

            if resp.status_code != 200:
                self.error.emit(f"Ошибка сервера: {resp.status_code}")
                return

            full = ""
            for line in resp.iter_lines():
                if line:
                    data    = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        full += content
                        self.token_received.emit(content)
                    if data.get("done"):
                        break

            self.finished.emit(full)

        except requests.exceptions.ConnectionError:
            self.error.emit("Ollama не запущена. Выполни: ollama serve")
        except requests.exceptions.Timeout:
            self.error.emit("Таймаут — модель слишком долго думает")
        except Exception as e:
            self.error.emit(str(e))
