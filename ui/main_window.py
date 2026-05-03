import os
import base64
import requests
import re

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QSplitter, QLabel, QComboBox, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QTextCursor

from config import COLORS, ICON_PATH
from personality import SYSTEM_PROMPT, ASSISTANT_NAME, APP_TITLE, APP_SUBTITLE
from chat_manager import ChatManager
from ollama_worker import OllamaWorker
from filesystem import parse_ai_actions
from ui.settings_window import SettingsWindow, load_settings, build_stylesheet
import markdown


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sylviette AI")
        self.resize(1150, 740)
        self.setMinimumSize(800, 500)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self.chat_mgr        = ChatManager()
        self.current_chat_id = None
        self.worker          = None
        self.stream_buffer   = ""
        self.pending_files   = []
        self._current_settings = load_settings()
        self._build_ui()
        self.setStyleSheet(build_stylesheet(self._current_settings))
        self._refresh_chat_list()
        ids = self.chat_mgr.get_sorted_ids()
        self._load_chat(ids[0]) if ids else self._new_chat()
        self._load_models()

    def _build_ui(self):
        central = QWidget()
        root    = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_chat_area())
        splitter.setSizes([240, 910])
        splitter.setHandleWidth(1)
        root.addWidget(splitter)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout  = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title    = QLabel(APP_TITLE);    title.setObjectName("app_title")
        subtitle = QLabel(APP_SUBTITLE); subtitle.setObjectName("app_subtitle")
        new_btn  = QPushButton("+ Новый чат"); new_btn.setObjectName("new_chat_btn")
        new_btn.clicked.connect(self._new_chat)
        self.chat_list = QListWidget(); self.chat_list.setObjectName("chat_list")
        self.chat_list.itemClicked.connect(self._on_chat_selected)
        self.chat_list.currentItemChanged.connect(
            lambda cur, prev: self._load_chat(cur.data(Qt.ItemDataRole.UserRole)) if cur else None
        )
        self.model_selector = QComboBox(); self.model_selector.setObjectName("model_selector")
        del_btn = QPushButton("Удалить чат"); del_btn.setObjectName("delete_btn")
        del_btn.clicked.connect(self._delete_current_chat)
        settings_btn = QPushButton("Настройки"); settings_btn.setObjectName("delete_btn")
        settings_btn.clicked.connect(self._open_settings)
        for w in [title, subtitle, new_btn, self.chat_list, self.model_selector, del_btn, settings_btn]:
            layout.addWidget(w)
        layout.addSpacing(12)
        return sidebar

    def _build_chat_area(self):
        chat_w   = QWidget()
        chat_lay = QVBoxLayout(chat_w)
        chat_lay.setContentsMargins(0, 0, 0, 0)
        chat_lay.setSpacing(0)
        self.chat_display = QTextEdit(); self.chat_display.setObjectName("chat_display")
        self.chat_display.setReadOnly(True)
        chat_lay.addWidget(self.chat_display, stretch=1)
        chat_lay.addWidget(self._build_input_panel())
        self.status_label = QLabel(""); self.status_label.setObjectName("status_bar")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chat_lay.addWidget(self.status_label)
        return chat_w

    def _build_input_panel(self):
        panel  = QWidget(); panel.setObjectName("input_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.attach_label = QLabel(""); self.attach_label.setObjectName("attach_label")
        self.attach_label.hide()
        row = QHBoxLayout(); row.setSpacing(10)
        attach_btn = QPushButton("📎"); attach_btn.setObjectName("attach_btn")
        attach_btn.setToolTip("Прикрепить файл или картинку")
        attach_btn.clicked.connect(self._attach_file)
        self.input_box = QTextEdit(); self.input_box.setObjectName("input_box")
        self.input_box.setPlaceholderText("Напишите сообщение… (Enter — отправить, Shift+Enter — новая строка)")
        self.input_box.setFixedHeight(40)
        self.input_box.setMaximumHeight(40)
        self.input_box.installEventFilter(self)
        self.send_btn = QPushButton("Отправить"); self.send_btn.setObjectName("send_btn")
        self.send_btn.setFixedHeight(40)
        self.send_btn.clicked.connect(self._send_message)
        row.addWidget(attach_btn); row.addWidget(self.input_box); row.addWidget(self.send_btn)
        layout.addWidget(self.attach_label)
        layout.addLayout(row)
        return panel

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.input_box and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message(); return True
        return super().eventFilter(obj, event)

    def _load_models(self):
        self.model_selector.clear()
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if models:
                    self.model_selector.addItems(models)
                    self.status_label.setText("Сильфиетта подключена!")
                else:
                    self.model_selector.addItem("sylviette-125m")
                    self.status_label.setText("Сильфиетта готова!")
        except Exception:
            self.model_selector.addItem("Сервер не запущен")
            self.status_label.setText("Запустите: python -m sylviette_ai.inference --checkpoint checkpoints/sylviette-chat/latest.pt")

    def _new_chat(self):
        cid = self.chat_mgr.new_chat()
        self._refresh_chat_list(); self._load_chat(cid)

    def _delete_current_chat(self):
        if not self.current_chat_id: return
        reply = QMessageBox.question(self, "Удалить?", "Удалить этот чат?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.chat_mgr.delete_chat(self.current_chat_id)
            self.current_chat_id = None
            self._refresh_chat_list()
            ids = self.chat_mgr.get_sorted_ids()
            self._load_chat(ids[0]) if ids else self._new_chat()

    def _refresh_chat_list(self):
        self.chat_list.clear()
        for cid in self.chat_mgr.get_sorted_ids():
            item = QListWidgetItem("💬  " + self.chat_mgr.get_title(cid))
            item.setData(Qt.ItemDataRole.UserRole, cid)
            self.chat_list.addItem(item)

    def _on_chat_selected(self, item):
        self._load_chat(item.data(Qt.ItemDataRole.UserRole))

    def _load_chat(self, cid):
        self.current_chat_id = cid
        self.chat_display.clear()
        for i in range(self.chat_list.count()):
            it = self.chat_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == cid:
                self.chat_list.setCurrentItem(it); break
        for msg in self.chat_mgr.get_messages(cid):
            self._render_message(msg["role"], msg["content"])

    def _render_message(self, role, content):
        if isinstance(content, list):
            text    = next((p["text"] for p in content if p.get("type") == "text"), "")
            has_img = any(p.get("type") == "image_url" for p in content)
            display = ("📷 [картинка]\n" if has_img else "") + text
        else:
            display = content
        self._append_bubble(role, display)

    def _append_bubble(self, role, text, raw=False):
        if role == "user":
            color, name, bg = COLORS["accent2"], "Создатель", COLORS["user_msg"]
        else:
            color, name, bg = COLORS["accent"], ASSISTANT_NAME, COLORS["ai_msg"]
        body = text if raw else markdown.convert(text)
        html = (
            f'<div style="margin:4px 0;padding:8px 12px;background-color:{bg};'
            f'border-radius:10px;border-left:3px solid {color};">'
            f'<div style="color:{color};font-size:11px;font-weight:bold;'
            f'margin-bottom:5px;letter-spacing:1px;">{name}</div>'
            f'<div style="color:{COLORS["text_bright"]};line-height:1.6;">{body}</div>'
            f'</div>'
        )
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        cursor.insertBlock()
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _append_action_result(self, action_type, target, result):
        icons = {"read_file": "📖", "write_file": "💾", "run_command": "⚡", "list_dir": "📁"}
        icon  = icons.get(action_type, "🔧")
        html  = (
            f'<div style="margin:4px 0;padding:8px 16px;background-color:#1a1f2e;'
            f'border-radius:8px;border-left:3px solid {COLORS["purple"]};">'
            f'<div style="color:{COLORS["purple"]};font-size:11px;margin-bottom:4px;">'
            f'{icon} {action_type}: <code style="color:{COLORS["accent2"]};">{target}</code></div>'
            f'<pre style="color:{COLORS["text"]};font-size:12px;white-space:pre-wrap;margin:0;">{result[:800]}</pre>'
            f'</div>'
        )
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        cursor.insertBlock()
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _rebuild_display(self):
        self.chat_display.clear()
        for msg in self.chat_mgr.get_messages(self.current_chat_id):
            self._render_message(msg["role"], msg["content"])

    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "",
            "Изображения (*.png *.jpg *.jpeg *.webp);;Текст (*.txt *.py *.js *.md *.json *.csv);;Все файлы (*)")
        if not path: return
        fname = os.path.basename(path)
        ext   = os.path.splitext(path)[1].lower()
        if ext in [".png", ".jpg", ".jpeg", ".webp"]:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            mime    = "image/png" if ext == ".png" else "image/jpeg"
            content = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                file_text = f.read()
            content = {"type": "text", "text": f"[Файл: {fname}]\n```\n{file_text}\n```"}
        self.pending_files.append((fname, content))
        names = ", ".join(n for n, _ in self.pending_files)
        self.attach_label.setText(f"📎 {names}"); self.attach_label.show()

    def _send_message(self):
        text = self.input_box.toPlainText().strip()
        if (not text and not self.pending_files) or not self.current_chat_id: return
        if self.worker and self.worker.isRunning(): return
        model = self.model_selector.currentText()
        if "не запущен" in model: return
        self.input_box.clear()
        if self.pending_files:
            parts        = [{"type": "text", "text": text or "Проанализируй"}]
            parts       += [c for _, c in self.pending_files]
            user_content = parts
            display      = "📎 " + ", ".join(n for n, _ in self.pending_files) + ("\n" + text if text else "")
            self.pending_files = []; self.attach_label.hide()
        else:
            user_content = text
            display      = text
        self.chat_mgr.add_message(self.current_chat_id, "user", user_content)
        self._append_bubble("user", display)
        self._refresh_chat_list()
        history  = self.chat_mgr.get_messages(self.current_chat_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        self.send_btn.setEnabled(False)
        self.status_label.setText(f"Сильфиетта думает…")
        self.stream_buffer = ""
        self.worker = OllamaWorker(model, messages)
        self.worker.token_received.connect(self._on_token)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_token(self, token):
        self.stream_buffer += token
        self._rebuild_display()
        self._append_bubble("assistant", self.stream_buffer + " ▌", raw=True)

    def _on_finished(self, full):
        actions = parse_ai_actions(full)
        clean   = re.sub(r'<action:[^>]+>.*?</action:[^>]+>', '', full, flags=re.DOTALL)
        clean   = re.sub(r'<action:[^/]*/>', '', clean).strip()
        self.chat_mgr.add_message(self.current_chat_id, "assistant", clean)
        self._rebuild_display()
        for action_type, target, result in actions:
            self._append_action_result(action_type, target, result)
        self.send_btn.setEnabled(True)
        self.status_label.setText("Готово")
        self._refresh_chat_list()

    def _on_error(self, err):
        self._append_bubble("assistant", f"Ошибка: {err}")
        self.send_btn.setEnabled(True)
        self.status_label.setText(f"Ошибка: {err}")

    def _open_settings(self):
        w = SettingsWindow(self)
        w.settings_changed.connect(self._apply_settings)
        w.exec()

    def _apply_settings(self, s):
        self.setStyleSheet(build_stylesheet(s))
