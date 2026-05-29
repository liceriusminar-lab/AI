import json
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from config import OLLAMA_URL


class OllamaWorker(QThread):
    token_received = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error          = pyqtSignal(str)

    def __init__(self, model, messages):
        super().__init__()
        self.model    = model
        self.messages = messages

    def _convert_messages(self):
        """Конвертирует сообщения в формат который понимает ollama."""
        converted = []
        for msg in self.messages:
            role    = msg["role"]
            content = msg["content"]

            if isinstance(content, list):
                text   = ""
                images = []
                for part in content:
                    if part.get("type") == "text":
                        text += part["text"]
                    elif part.get("type") == "image_url":
                        url = part["image_url"]["url"]
                        # Извлекаем base64 из data URL
                        if "base64," in url:
                            b64 = url.split("base64,")[1]
                            images.append(b64)
                entry = {"role": role, "content": text}
                if images:
                    entry["images"] = images
                converted.append(entry)
            else:
                converted.append({"role": role, "content": content})
        return converted

    def run(self):
        try:
            messages = self._convert_messages()
            resp = requests.post(OLLAMA_URL, json={
                "model":    self.model,
                "messages": messages,
                "stream":   True
            }, stream=True, timeout=120)

            if resp.status_code != 200:
                self.error.emit(f"Ошибка сервера {resp.status_code}: {resp.text[:200]}")
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
            self.error.emit("Не удалось подключиться к Ollama. Запустите: ollama serve")
        except requests.exceptions.Timeout:
            self.error.emit("Ollama не отвечает (timeout)")
        except Exception as e:
            self.error.emit(str(e))
