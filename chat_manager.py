import json
import os
import datetime
from config import HISTORY_FILE


class ChatManager:
    CACHE_SIZE = 5  # сколько чатов держим в быстром кэше

    def __init__(self):
        self.chats      = {}
        self._msg_cache = {}   # cid -> messages (только последние CACHE_SIZE)
        self._dirty     = set() # cid которые изменились и нужно сохранить
        self.load()

    def load(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.chats = json.load(f)
                # Прогреваем кэш последних чатов
                for cid in self.get_sorted_ids()[:self.CACHE_SIZE]:
                    self._msg_cache[cid] = self.chats[cid]["messages"]
            except Exception:
                self.chats = {}

    def save(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.chats, f, ensure_ascii=False, indent=2)
        self._dirty.clear()

    def save_if_dirty(self):
        if self._dirty:
            self.save()

    def new_chat(self):
        cid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chats[cid] = {
            "title":    "Новый чат",
            "created":  cid,
            "messages": [],
            "pinned":   False,
        }
        self.save()
        return cid

    def delete_chat(self, cid):
        self.chats.pop(cid, None)
        self._msg_cache.pop(cid, None)
        self._dirty.discard(cid)
        self.save()

    def add_message(self, cid, role, content):
        self.chats[cid]["messages"].append({"role": role, "content": content})
        # Обновляем кэш если он есть
        if cid in self._msg_cache:
            self._msg_cache[cid] = self.chats[cid]["messages"]
        if role == "user" and self.chats[cid]["title"] == "Новый чат":
            if isinstance(content, str):
                text = content
            else:
                text = next((p["text"] for p in content if p.get("type") == "text"), "файл")
            self.chats[cid]["title"] = text[:40] + ("…" if len(text) > 40 else "")
        self._dirty.add(cid)
        self.save()

    def edit_message(self, cid, index, new_content):
        """Редактирует сообщение по индексу."""
        msgs = self.chats[cid]["messages"]
        if 0 <= index < len(msgs):
            msgs[index]["content"] = new_content
            msgs[index]["edited"] = True
            # Сбрасываем кэш для этого чата
            if cid in self._msg_cache:
                self._msg_cache[cid] = msgs
            self._dirty.add(cid)
            self.save()
            return True
        return False

    def get_messages(self, cid):
        if cid in self._msg_cache:
            return self._msg_cache[cid]
        msgs = self.chats[cid]["messages"]
        # Добавляем в кэш, выталкиваем старый если переполнен
        if len(self._msg_cache) >= self.CACHE_SIZE:
            oldest = next(iter(self._msg_cache))
            del self._msg_cache[oldest]
        self._msg_cache[cid] = msgs
        return msgs

    def get_title(self, cid):
        return self.chats[cid].get("title", "Чат")

    def is_pinned(self, cid):
        return self.chats.get(cid, {}).get("pinned", False)

    def toggle_pin(self, cid):
        self.chats[cid]["pinned"] = not self.chats[cid].get("pinned", False)
        self.save()

    def get_stats(self, cid):
        """Возвращает статистику чата."""
        msgs = self.chats[cid]["messages"]
        user_msgs = [m for m in msgs if m["role"] == "user"]
        ai_msgs   = [m for m in msgs if m["role"] == "assistant"]

        # Примерный подсчёт токенов (1 токен ≈ 4 символа)
        total_chars = sum(
            len(m["content"]) if isinstance(m["content"], str)
            else sum(len(p.get("text", "")) for p in m["content"] if p.get("type") == "text")
            for m in msgs
        )
        approx_tokens = total_chars // 4

        created = self.chats[cid].get("created", cid)
        try:
            dt = datetime.datetime.strptime(created, "%Y%m%d_%H%M%S")
            created_str = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            created_str = created

        return {
            "total":        len(msgs),
            "user":         len(user_msgs),
            "ai":           len(ai_msgs),
            "tokens":       approx_tokens,
            "created":      created_str,
        }

    def search(self, query: str) -> list:
        """Ищет query по заголовкам и содержимому чатов."""
        query_lower = query.lower().strip()
        if not query_lower:
            return self.get_sorted_ids()
        results = []
        for cid in self.get_sorted_ids():
            title = self.get_title(cid).lower()
            if query_lower in title:
                results.append(cid)
                continue
            for msg in self.chats[cid]["messages"]:
                content = msg.get("content", "")
                text = content if isinstance(content, str) else \
                    " ".join(p.get("text", "") for p in content if p.get("type") == "text")
                if query_lower in text.lower():
                    results.append(cid)
                    break
        return results

    def export_md(self, cid) -> str:
        """Экспортирует чат в Markdown строку."""
        title = self.get_title(cid)
        stats = self.get_stats(cid)
        lines = [
            f"# {title}",
            f"",
            f"*Создан: {stats['created']} · Сообщений: {stats['total']}*",
            f"",
            f"---",
            f"",
        ]
        for msg in self.get_messages(cid):
            role = msg["role"]
            content = msg.get("content", "")
            text = content if isinstance(content, str) else \
                " ".join(p.get("text", "") for p in content if p.get("type") == "text")
            name = "**Создатель**" if role == "user" else "**Сильфиетта**"
            edited = " *(изменено)*" if msg.get("edited") else ""
            lines.append(f"{name}{edited}")
            lines.append(f"")
            lines.append(text)
            lines.append(f"")
            lines.append(f"---")
            lines.append(f"")
        return "\n".join(lines)

    def get_sorted_ids(self):
        return sorted(self.chats.keys(), reverse=True)

    def get_grouped_ids(self, pinned_first=True):
        """Возвращает чаты сгруппированные по датам, закреплённые вверху."""
        from datetime import datetime, timedelta
        now       = datetime.now()
        today     = now.date()
        yesterday = (now - timedelta(days=1)).date()
        week_ago  = (now - timedelta(days=7)).date()

        pinned = []
        groups = {"Сегодня": [], "Вчера": [], "На этой неделе": [], "Раньше": []}

        for cid in self.get_sorted_ids():
            if self.is_pinned(cid):
                pinned.append(cid)
                continue
            try:
                dt = datetime.strptime(cid, "%Y%m%d_%H%M%S").date()
            except Exception:
                groups["Раньше"].append(cid)
                continue
            if dt == today:
                groups["Сегодня"].append(cid)
            elif dt == yesterday:
                groups["Вчера"].append(cid)
            elif dt >= week_ago:
                groups["На этой неделе"].append(cid)
            else:
                groups["Раньше"].append(cid)

        result = {}
        if pinned:
            result["📌 Закреплённые"] = pinned
        for k, v in groups.items():
            if v:
                result[k] = v
        return result
