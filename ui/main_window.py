import os
import base64
import mimetypes
import requests

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QSplitter, QLabel, QComboBox, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTextCursor
from PyQt6.QtGui import QIcon

from config import COLORS, STYLESHEET, ICON_PATH
from personality import SYSTEM_PROMPT, ASSISTANT_NAME, APP_TITLE, APP_SUBTITLE
from chat_manager import ChatManager
from ollama_worker import OllamaWorker
import markdown


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sylfiette AI")
        self.resize(1150, 740)
        self.setMinimumSize(800, 500)

        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self.chat_mgr        = ChatManager()
        self.current_chat_id = None
        self.worker          = None
        self.stream_buffer   = ""
        self.pending_files   = []   # [(имя_файла, ollama_content)]

        self._build_ui()
        self._refresh_chat_list()

        ids = self.chat_mgr.get_sorted_ids()
        self._load_chat(ids[0]) if ids else self._new_chat()
        self._load_models()

    # ── Построение интерфейса ─────────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet(STYLESHEET)
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

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget(); sidebar.setObjectName("sidebar")
        layout  = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title    = QLabel(APP_TITLE);    title.setObjectName("app_title")
        subtitle = QLabel(APP_SUBTITLE); subtitle.setObjectName("app_subtitle")

        new_btn = QPushButton("＋  Новый чат")
        new_btn.setObjectName("new_chat_btn")
        new_btn.clicked.connect(self._new_chat)

        self.chat_list = QListWidget()
        self.chat_list.setObjectName("chat_list")
        self.chat_list.itemClicked.connect(self._on_chat_selected)

        model_lbl = QLabel("Модель:")
        model_lbl.setStyleSheet(
            f"color:{COLORS['text_dim']};font-size:11px;padding:8px 16px 2px 16px;")

        self.model_selector = QComboBox()
        self.model_selector.setObjectName("model_selector")

        del_btn = QPushButton("🗑  Удалить чат")
        del_btn.setObjectName("delete_btn")
        del_btn.clicked.connect(self._delete_current_chat)

        for w in [title, subtitle, new_btn, self.chat_list,
                  model_lbl, self.model_selector, del_btn]:
            layout.addWidget(w)
        layout.addSpacing(12)

        return sidebar

    def _build_chat_area(self) -> QWidget:
        chat_w   = QWidget()
        chat_lay = QVBoxLayout(chat_w)
        chat_lay.setContentsMargins(0, 0, 0, 0)
        chat_lay.setSpacing(0)

        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chat_display")
        self.chat_display.setReadOnly(True)

        chat_lay.addWidget(self.chat_display)
        chat_lay.addWidget(self._build_input_panel())

        self.status_label = QLabel("")
        self.status_label.setObjectName("status_bar")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chat_lay.addWidget(self.status_label)

        return chat_w

    def _build_input_panel(self) -> QWidget:
        panel  = QWidget(); panel.setObjectName("input_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.attach_label = QLabel("")
        self.attach_label.setObjectName("attach_label")
        self.attach_label.hide()

        row = QHBoxLayout(); row.setSpacing(10)

        attach_btn = QPushButton("📎")
        attach_btn.setObjectName("attach_btn")
        attach_btn.setToolTip("Прикрепить файл или изображение")
        attach_btn.clicked.connect(self._attach_file)

        self.input_box = QTextEdit()
        self.input_box.setObjectName("input_box")
        self.input_box.setPlaceholderText(
            "Напишите сообщение… (Enter — отправить, Shift+Enter — новая строка)")
        self.input_box.setFixedHeight(46)
        self.input_box.installEventFilter(self)

        self.send_btn = QPushButton("Отправить")
        self.send_btn.setObjectName("send_btn")
        self.send_btn.clicked.connect(self._send_message)

        row.addWidget(attach_btn)
        row.addWidget(self.input_box)
        row.addWidget(self.send_btn)

        layout.addWidget(self.attach_label)
        layout.addLayout(row)
        return panel

    # ── Enter для отправки ────────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.input_box and event.type() == QEvent.Type.KeyPress:
            if (event.key() == Qt.Key.Key_Return and
                    not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
                self._send_message()
                return True
        return super().eventFilter(obj, event)

    # ── Модели ────────────────────────────────────────────────────────────────
    def _load_models(self):
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                self.model_selector.clear()
                if models:
                    self.model_selector.addItems(models)
                    self.status_label.setText(
                        f"✓ Ollama подключена · {len(models)} модел(ей)")
                else:
                    self.model_selector.addItem("Нет моделей")
                    self.status_label.setText("⚠ Запустите: ollama pull qwen2.5:7b")
        except Exception:
            self.model_selector.addItem("Ollama не запущена")
            self.status_label.setText("✗ Запустите в терминале: ollama serve")

    # ── Управление чатами ─────────────────────────────────────────────────────
    def _new_chat(self):
        cid = self.chat_mgr.new_chat()
        self._refresh_chat_list()
        self._load_chat(cid)

    def _delete_current_chat(self):
        if not self.current_chat_id:
            return
        reply = QMessageBox.question(
            self, "Удалить?", "Удалить этот чат?",
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

    def _load_chat(self, cid: str):
        self.current_chat_id = cid
        self.chat_display.clear()

        for i in range(self.chat_list.count()):
            it = self.chat_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == cid:
                self.chat_list.setCurrentItem(it)
                break

        for msg in self.chat_mgr.get_messages(cid):
            self._render_message(msg["role"], msg["content"])

    # ── Отображение сообщений ─────────────────────────────────────────────────
    def _render_message(self, role: str, content):
        """Рендерит сообщение из истории."""
        if isinstance(content, list):
            text    = next((p["text"] for p in content if p.get("type") == "text"), "")
            has_img = any(p.get("type") == "image_url" for p in content)
            display = ("📎 [изображение]\n" if has_img else "") + text
        else:
            display = content
        self._append_bubble(role, display)

    def _append_bubble(self, role: str, text: str, raw: bool = False):
        """Добавляет пузырь сообщения в чат."""
        if role == "user":
            color, name, bg = COLORS['accent2'], "Вы", COLORS['user_msg']
        else:
            color, name, bg = COLORS['accent'], ASSISTANT_NAME, COLORS['ai_msg']

        body = text if raw else markdown.convert(text)

        html = (
            f'<div style="margin:8px 0;padding:12px 16px;background-color:{bg};'
            f'border-radius:10px;border-left:3px solid {color};">'
            f'<div style="color:{color};font-size:12px;font-weight:bold;'
            f'margin-bottom:6px;letter-spacing:1px;">{name}</div>'
            f'<div style="color:{COLORS["text_bright"]};line-height:1.6;">{body}</div>'
            f'</div>'
        )
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        cursor.insertText("\n")
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _rebuild_display(self):
        """Перерисовывает весь чат из истории."""
        self.chat_display.clear()
        for msg in self.chat_mgr.get_messages(self.current_chat_id):
            self._render_message(msg["role"], msg["content"])

    # ── Прикрепление файлов ───────────────────────────────────────────────────
    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл", "",
            "Изображения (*.png *.jpg *.jpeg *.gif *.webp);;"
            "Текст (*.txt *.py *.js *.ts *.cpp *.h *.md *.json *.csv);;"
            "Все файлы (*)"
        )
        if not path:
            return

        fname = os.path.basename(path)
        mime  = mimetypes.guess_type(path)[0] or ""

        if mime.startswith("image/"):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            content = {
                "type":      "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"}
            }
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                file_text = f.read()
            content = {
                "type": "text",
                "text": f"[Файл: {fname}]\n```\n{file_text}\n```"
            }

        self.pending_files.append((fname, content))
        names = ", ".join(n for n, _ in self.pending_files)
        self.attach_label.setText(f"📎 {names}")
        self.attach_label.show()

    # ── Отправка сообщения ────────────────────────────────────────────────────
    def _send_message(self):
        text = self.input_box.toPlainText().strip()
        if (not text and not self.pending_files) or not self.current_chat_id:
            return
        if self.worker and self.worker.isRunning():
            return

        model = self.model_selector.currentText()
        if any(x in model for x in ["не запущена", "Нет"]):
            self.status_label.setText("⚠ Запустите ollama serve и загрузите модель")
            return

        self.input_box.clear()

        # Формируем контент сообщения
        if self.pending_files:
            parts        = [{"type": "text", "text": text or "Что на этом?"}]
            parts       += [c for _, c in self.pending_files]
            user_content = parts
            display      = "📎 " + ", ".join(n for n, _ in self.pending_files)
            if text:
                display += "\n" + text
            self.pending_files = []
            self.attach_label.hide()
        else:
            user_content = text
            display      = text

        self.chat_mgr.add_message(self.current_chat_id, "user", user_content)
        self._append_bubble("user", display)
        self._refresh_chat_list()

        # Отправляем в Ollama с системным промптом
        history  = self.chat_mgr.get_messages(self.current_chat_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        self.send_btn.setEnabled(False)
        self.status_label.setText(f"✦ {ASSISTANT_NAME} думает…")
        self.stream_buffer = ""

        self.worker = OllamaWorker(model, messages)
        self.worker.token_received.connect(self._on_token)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    # ── Обработка стриминга ───────────────────────────────────────────────────
    def _on_token(self, token: str):
        self.stream_buffer += token
        self._rebuild_display()
        self._append_bubble("assistant", self.stream_buffer + " ▌", raw=True)

    def _on_finished(self, full: str):
        self.chat_mgr.add_message(self.current_chat_id, "assistant", full)
        self._rebuild_display()
        self.send_btn.setEnabled(True)
        self.status_label.setText("✓ Готово")
        self._refresh_chat_list()

    def _on_error(self, err: str):
        self.chat_display.append(
            f'<div style="color:{COLORS["accent"]};padding:8px;">⚠ Ошибка: {err}</div>')
        self.send_btn.setEnabled(True)
        self.status_label.setText(f"✗ {err}")
