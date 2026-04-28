import json
import os
import datetime
from config import HISTORY_FILE


class ChatManager:
    def __init__(self):
        self.chats = {}
        self.load()

    def load(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.chats = json.load(f)
            except Exception:
                self.chats = {}

    def save(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.chats, f, ensure_ascii=False, indent=2)

    def new_chat(self):
        cid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chats[cid] = {
            "title":    "Новый чат",
            "created":  cid,
            "messages": []
        }
        self.save()
        return cid

    def delete_chat(self, cid):
        self.chats.pop(cid, None)
        self.save()

    def add_message(self, cid, role, content):
        self.chats[cid]["messages"].append({"role": role, "content": content})
        # Автозаголовок из первого сообщения пользователя
        if role == "user" and self.chats[cid]["title"] == "Новый чат":
            if isinstance(content, str):
                text = content
            else:
                text = next((p["text"] for p in content if p.get("type") == "text"), "файл")
            self.chats[cid]["title"] = text[:40] + ("…" if len(text) > 40 else "")
        self.save()

    def get_messages(self, cid):
        return self.chats[cid]["messages"]

    def get_title(self, cid):
        return self.chats[cid].get("title", "Чат")

    def get_sorted_ids(self):
        return sorted(self.chats.keys(), reverse=True)
