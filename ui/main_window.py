import os
import base64
import requests
import re

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QSplitter, QLabel, QComboBox, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QTextCursor, QKeySequence
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QShortcut

from config import COLORS, ICON_PATH
from personality import SYSTEM_PROMPT, ASSISTANT_NAME, APP_TITLE, APP_SUBTITLE
from chat_manager import ChatManager
from ollama_worker import OllamaWorker
from filesystem import parse_ai_actions
from ui.settings_window import SettingsWindow, load_settings, build_stylesheet, get_bubble_style
from ui.file_panel import FilePanel
from ui.dashboard import DashboardWindow
from websearch import search_and_summarize, should_search_web
from profiles import load_profiles, set_active_profile, get_active_profile, save_custom_profile, delete_custom_profile
from plugin_manager import list_plugins, toggle_plugin
from calendar_manager import handle_calendar_command, get_today, ReminderDaemon
from ui.calendar_widget import CalendarWidget
from ui.sysmon_widget import SysMonWidget
from encryption import get_encryption_status
try:
    from voice_daemon import start_voice_daemon, stop_voice_daemon, get_daemon
    _VOICE_AVAILABLE = True
except ImportError:
    _VOICE_AVAILABLE = False
from stt import STTWorker, check_microphone
import markdown


def _is_light(hex_color: str) -> bool:
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r * 0.299 + g * 0.587 + b * 0.114) > 140
    except Exception:
        return False


class MainWindow(QMainWindow):
    _stt_result_signal = __import__("PyQt6.QtCore", fromlist=["pyqtSignal"]).pyqtSignal(str)
    _stt_error_signal  = __import__("PyQt6.QtCore", fromlist=["pyqtSignal"]).pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sylviette AI")
        self.resize(1150, 740)
        self.setMinimumSize(800, 500)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self.chat_mgr          = ChatManager()
        self.current_chat_id   = None
        self.worker            = None
        self.stream_buffer     = ""
        self.pending_files     = []
        self._typing_timer     = None
        self._current_settings = load_settings()
        self._build_ui()
        self.setStyleSheet(build_stylesheet(self._current_settings))
        self._refresh_chat_list()
        ids = self.chat_mgr.get_sorted_ids()
        self._load_chat(ids[0]) if ids else self._new_chat()
        self._load_models()
        self._stt_result_signal.connect(self._on_stt_result)
        self._start_reminder_daemon()
        self._stt_error_signal.connect(self._on_stt_error)
        self._setup_shortcuts()
        self._setup_tray()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        root    = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_chat_area())
        self.file_panel = FilePanel()
        self.file_panel.send_to_chat.connect(self._file_to_chat)
        self.file_panel.setVisible(False)
        splitter.addWidget(self.file_panel)
        splitter.setSizes([240, 910, 0])
        splitter.setHandleWidth(1)
        self._splitter = splitter
        root.addWidget(splitter)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout  = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title    = QLabel(APP_TITLE);    title.setObjectName("app_title")
        subtitle = QLabel(APP_SUBTITLE); subtitle.setObjectName("app_subtitle")
        # Индикатор статуса сервера
        self.server_indicator = QLabel("⬤ Подключение…")
        self.server_indicator.setObjectName("server_indicator")
        self.server_indicator.setStyleSheet("color:#565c7a;font-size:11px;padding:2px 16px 6px 16px;")
        self._sysmon = SysMonWidget()
        new_btn  = QPushButton("+ Новый чат"); new_btn.setObjectName("new_chat_btn")
        new_btn.clicked.connect(self._new_chat)

        from PyQt6.QtWidgets import QLineEdit
        self.search_box = QLineEdit(); self.search_box.setObjectName("search_box")
        self.search_box.setPlaceholderText("🔍 Поиск по чатам…")
        self.search_box.textChanged.connect(self._on_search)

        self.chat_list = QListWidget(); self.chat_list.setObjectName("chat_list")
        self.chat_list.itemClicked.connect(self._on_chat_selected)
        self.chat_list.currentItemChanged.connect(
            lambda cur, prev: self._load_chat(cur.data(Qt.ItemDataRole.UserRole)) if cur else None
        )
        self.chat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self._chat_context_menu)

        self.model_selector = QComboBox(); self.model_selector.setObjectName("model_selector")

        # Профиль — виден в сайдбаре
        self.profile_btn = QPushButton(f"🎯 {get_active_profile()}")
        self.profile_btn.setObjectName("delete_btn")
        self.profile_btn.clicked.connect(self._open_profiles)

        # Файлы — виден в сайдбаре

        # Голосовая активация
        self._voice_btn = QPushButton("🎙 Голос: слушаю")
        self._voice_btn.setObjectName("delete_btn")
        self._voice_btn.setCheckable(True)
        self._voice_btn.setChecked(True)
        self._voice_btn.clicked.connect(self._toggle_voice)
        if not _VOICE_AVAILABLE:
            self._voice_btn.setText("🎙 Голос: не установлен")
            self._voice_btn.setEnabled(False)

        files_btn = QPushButton("📁 Файлы"); files_btn.setObjectName("delete_btn")
        files_btn.clicked.connect(self._toggle_files)

        # Доп. настройки — всё остальное внутри
        more_btn = QPushButton("⚙ Доп. настройки"); more_btn.setObjectName("delete_btn")
        more_btn.clicked.connect(self._open_more_menu)

        for w in [title, self.server_indicator, subtitle, new_btn, self.profile_btn,
                  self.search_box, self.chat_list, self.model_selector,
                  self._voice_btn, files_btn, more_btn, self._sysmon]:
            layout.addWidget(w)
        layout.addSpacing(12)
        layout.addSpacing(12)
        return sidebar

    def _build_chat_area(self):
        chat_w   = QWidget()
        chat_lay = QVBoxLayout(chat_w)
        chat_lay.setContentsMargins(0, 0, 0, 0)
        chat_lay.setSpacing(0)

        # Шапка чата
        self.chat_header = QWidget(); self.chat_header.setObjectName("chat_header")
        header_lay = QHBoxLayout(self.chat_header)
        header_lay.setContentsMargins(20, 12, 20, 12)
        self.chat_title_label = QLabel("Новый чат"); self.chat_title_label.setObjectName("chat_title_label")
        header_lay.addWidget(self.chat_title_label)
        header_lay.addStretch()
        chat_lay.addWidget(self.chat_header)

        self.chat_display = QTextEdit(); self.chat_display.setObjectName("chat_display")
        self.chat_display.setReadOnly(True)
        self.chat_display.mouseDoubleClickEvent = self._on_chat_double_click
        self.chat_display.mousePressEvent = self._on_chat_click
        self.chat_display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_display.customContextMenuRequested.connect(self._chat_display_context_menu)
        chat_lay.addWidget(self.chat_display, stretch=1)
        chat_lay.addWidget(self._build_input_panel())
        self.status_label = QLabel(""); self.status_label.setObjectName("status_bar")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chat_lay.addWidget(self.status_label)
        return chat_w

    def _build_input_panel(self):
        panel  = QWidget(); panel.setObjectName("input_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        self.attach_label = QLabel(""); self.attach_label.setObjectName("attach_label")
        self.attach_label.hide()
        layout.addWidget(self.attach_label)

        # Внешний контейнер — скруглённая рамка
        outer = QWidget(); outer.setObjectName("input_outer")
        outer_layout = QHBoxLayout(outer)
        outer_layout.setContentsMargins(8, 6, 6, 6)
        outer_layout.setSpacing(6)

        attach_btn = QPushButton("📎"); attach_btn.setObjectName("attach_btn")
        attach_btn.setToolTip("Прикрепить файл или картинку")
        attach_btn.setFixedSize(32, 32)
        attach_btn.clicked.connect(self._attach_file)

        self.input_box = QTextEdit(); self.input_box.setObjectName("input_box")
        self.input_box.setPlaceholderText("Напишите сообщение Сильфиетте…")
        self.input_box.setMinimumHeight(36)
        self.input_box.setMaximumHeight(160)
        self.input_box.setSizePolicy(
            self.input_box.sizePolicy().horizontalPolicy(),
            __import__("PyQt6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Policy.Expanding
        )
        self.input_box.installEventFilter(self)
        self.input_box.document().contentsChanged.connect(self._auto_resize_input)
        self.input_box.document().contentsChanged.connect(self._update_md_preview)

        # Markdown превью — скрыт по умолчанию
        self._md_preview = QTextEdit(); self._md_preview.setObjectName("md_preview")
        self._md_preview.setReadOnly(True)
        self._md_preview.setMaximumHeight(120)
        self._md_preview.hide()

        self.send_btn = QPushButton("↑"); self.send_btn.setObjectName("send_btn")
        self.send_btn.setFixedSize(36, 36)
        self.send_btn.setToolTip("Отправить (Enter)")
        self.send_btn.clicked.connect(self._send_message)

        self.mic_btn = QPushButton("🎤"); self.mic_btn.setObjectName("mic_btn")
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setToolTip("Голосовой ввод")
        self.mic_btn.setCheckable(True)
        self.mic_btn.clicked.connect(self._toggle_stt)

        outer_layout.addWidget(attach_btn)
        outer_layout.addWidget(self.input_box)
        outer_layout.addWidget(self.mic_btn, alignment=__import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.AlignmentFlag.AlignBottom)
        outer_layout.addWidget(self.send_btn, alignment=__import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self._md_preview)
        layout.addWidget(outer)

        # Кнопка переключения превью
        self._md_toggle = QPushButton("MD"); self._md_toggle.setObjectName("md_toggle_btn")
        self._md_toggle.setFixedSize(28, 28)
        self._md_toggle.setToolTip("Markdown превью")
        self._md_toggle.setCheckable(True)
        self._md_toggle.clicked.connect(self._toggle_md_preview)
        outer_layout.insertWidget(1, self._md_toggle)
        return panel

    def _toggle_voice(self, checked):
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

    def _toggle_stt(self, checked):
        if not checked:
            return
        ok, msg = check_microphone()
        if not ok:
            self.status_label.setText(f"Микрофон недоступен: {msg}")
            self.mic_btn.setChecked(False)
            return
        self.mic_btn.setStyleSheet("QPushButton{background:#e06c75;color:white;border:none;border-radius:18px;font-size:16px;}")
        self.status_label.setText("🎤 Говорите…")
        self._stt_worker = STTWorker(
            on_result=self._stt_result_signal.emit,
            on_error=self._stt_error_signal.emit,
        )
        self._stt_worker.start()

    def _on_stt_result(self, text):
        self.mic_btn.setChecked(False)
        self.mic_btn.setStyleSheet("")
        self.input_box.setPlainText(text)
        self.status_label.setText("✓ Распознано")
        QTimer.singleShot(1500, lambda: self.status_label.setText("Готово ✦"))

    def _on_stt_error(self, err):
        self.mic_btn.setChecked(False)
        self.mic_btn.setStyleSheet("")
        self.status_label.setText(f"🎤 {err}")
        QTimer.singleShot(3000, lambda: self.status_label.setText("Готово ✦"))

    def _toggle_md_preview(self, checked):
        self._md_preview.setVisible(checked)
        if checked:
            self._update_md_preview()

    def _update_md_preview(self):
        if not self._md_preview.isVisible():
            return
        text = self.input_box.toPlainText()
        if text.strip():
            self._md_preview.setHtml(markdown.convert(text))
        else:
            self._md_preview.clear()

    def _auto_resize_input(self):
        doc_height = int(self.input_box.document().size().height())
        new_height = max(36, min(doc_height + 12, 160))
        self.input_box.setFixedHeight(new_height)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.input_box and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message(); return True
        return super().eventFilter(obj, event)

    # ── Модели ───────────────────────────────────────────────────────────────

    def _load_models(self):
        self.model_selector.clear()
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if models:
                    self.model_selector.addItems(models)
                    self.status_label.setText("Сильфиетта подключена!")
                    self.server_indicator.setText("⬤ Онлайн")
                    self.server_indicator.setStyleSheet("color:#4ade80;font-size:11px;padding:2px 16px 6px 16px;")
                else:
                    self.model_selector.addItem("sylviette-125m")
                    self.status_label.setText("Сильфиетта готова!")
                    self.server_indicator.setText("⬤ Онлайн")
                    self.server_indicator.setStyleSheet("color:#4ade80;font-size:11px;padding:2px 16px 6px 16px;")
        except Exception:
            self.model_selector.addItem("Сервер не запущен")
            self.status_label.setText("Запустите inference сервер")
            self.server_indicator.setText("⬤ Офлайн")
            self.server_indicator.setStyleSheet("color:#e06c75;font-size:11px;padding:2px 16px 6px 16px;")
        # Перепроверяем каждые 30 секунд
        QTimer.singleShot(30000, self._load_models)

    # ── Чаты ─────────────────────────────────────────────────────────────────

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

    def _refresh_chat_list(self, query=""):
        from PyQt6.QtGui import QColor, QFont
        self.chat_list.clear()
        if query.strip():
            ids = self.chat_mgr.search(query)
            sep = QListWidgetItem(f"🔍 Результаты: {len(ids)}")
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            sep.setForeground(QColor("#565c7a"))
            font = sep.font(); font.setPointSize(9); font.setBold(True)
            sep.setFont(font)
            self.chat_list.addItem(sep)
            for cid in ids:
                pinned = self.chat_mgr.is_pinned(cid)
                prefix = "  📌  " if pinned else "  💬  "
                item = QListWidgetItem(prefix + self.chat_mgr.get_title(cid))
                item.setData(Qt.ItemDataRole.UserRole, cid)
                self.chat_list.addItem(item)
            return
        groups = self.chat_mgr.get_grouped_ids()
        for group_name, ids in groups.items():
            sep = QListWidgetItem(group_name)
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            sep.setForeground(QColor("#565c7a"))
            font = sep.font(); font.setPointSize(9); font.setBold(True)
            sep.setFont(font)
            self.chat_list.addItem(sep)
            for cid in ids:
                pinned = self.chat_mgr.is_pinned(cid)
                prefix = "  📌  " if pinned else "  💬  "
                item = QListWidgetItem(prefix + self.chat_mgr.get_title(cid))
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
        title = self.chat_mgr.get_title(cid)
        self.chat_title_label.setText(title)
        for i, msg in enumerate(self.chat_mgr.get_messages(cid)):
            self._render_message(msg["role"], msg["content"], index=i)

    # ── Рендеринг ─────────────────────────────────────────────────────────────

    def _render_message(self, role, content, index=None):
        if isinstance(content, list):
            text    = next((p["text"] for p in content if p.get("type") == "text"), "")
            has_img = any(p.get("type") == "image_url" for p in content)
            display = ("📷 [картинка]\n" if has_img else "") + text
        elif isinstance(content, dict) and "_display" in content:
            display = content["_display"]
        else:
            display = content
        self._append_bubble(role, display, msg_index=index)

    def _edit_message(self, index):
        if not self.current_chat_id: return
        msgs = self.chat_mgr.get_messages(self.current_chat_id)
        if index >= len(msgs): return
        msg  = msgs[index]
        if msg["role"] != "user": return
        content = msg["content"]
        text = content if isinstance(content, str) else             next((p["text"] for p in content if p.get("type") == "text"), "")
        from PyQt6.QtWidgets import QInputDialog
        new_text, ok = QInputDialog.getMultiLineText(
            self, "Редактировать сообщение", "Текст:", text)
        if not ok or new_text.strip() == text.strip(): return
        self.chat_mgr.edit_message(self.current_chat_id, index, new_text)
        self._rebuild_display()

    def _get_avatar_html(self, role: str) -> str:
        s = self._current_settings
        if not s.get("show_avatars", True):
            return ""
        if role == "user":
            emoji = s.get("avatar_user",    "👤")
            bg    = s.get("avatar_user_bg", "#61afef")
        else:
            emoji = s.get("avatar_ai",      "✦")
            bg    = s.get("avatar_ai_bg",   "#e06c75")
        tc = "#000" if _is_light(bg) else "#fff"
        return (
            f'<span style="display:inline-block;width:26px;height:26px;'
            f'background:{bg};border-radius:13px;text-align:center;'
            f'line-height:26px;font-size:13px;vertical-align:middle;'
            f'margin-right:6px;color:{tc};">{emoji}</span>'
        )

    def _append_bubble(self, role, text, raw=False, msg_index=None):
        s = self._current_settings
        bubble_style, name_color, text_color = get_bubble_style(s, role)
        name   = "Создатель" if role == "user" else ASSISTANT_NAME
        body   = text if raw else markdown.convert(text)
        avatar = self._get_avatar_html(role)
        timestamp = ""
        if s.get("show_timestamp", False):
            import datetime
            ts = datetime.datetime.now().strftime("%H:%M")
            timestamp = f'<span style="color:#565c7a;font-size:10px;margin-left:6px;">{ts}</span>'
        br      = s.get("bubble_radius", 10)
        shadow  = "box-shadow:0 1px 4px rgba(0,0,0,0.20);" if s.get("bubble_shadow", True) else ""
        is_light = _is_light(s.get("bg", "#1a1b26"))
        user_bg = "#dbeafe" if is_light else "#1e2a3a"
        ai_bg   = "#f0fdf4" if is_light else "#1e1f2e"

        if role == "user":
            cell_style = (
                f"background-color:{user_bg};"
                f"border-radius:{br}px {br}px 4px {br}px;"
                f"padding:10px 14px;{shadow}"
            )
            edit_btn = ""
            if msg_index is not None:
                edit_btn = f'<span style="color:#565c7a;font-size:10px;margin-right:6px;" title="edit_{msg_index}">✏</span>'
            header_html = (
                f'<div style="text-align:right;color:{name_color};font-size:11px;'
                f'font-weight:bold;margin-bottom:4px;letter-spacing:1px;">'
                f'{edit_btn}{timestamp}{name} {avatar}</div>'
            )
            html = (
                f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:3px 0;">'
                f'<tr><td width="20%"></td>'
                f'<td width="80%" style="{cell_style}">'
                f'{header_html}'
                f'<div style="color:{text_color};line-height:1.6;">{body}</div>'
                f'</td></tr></table>'
            )
        else:
            cell_style = (
                f"background-color:{ai_bg};"
                f"border-radius:4px {br}px {br}px {br}px;"
                f"padding:10px 14px;{shadow}"
            )
            header_html = (
                f'<div style="color:{name_color};font-size:11px;'
                f'font-weight:bold;margin-bottom:4px;letter-spacing:1px;">'
                f'{avatar}{name}{timestamp}</div>'
            )
            html = (
                f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:3px 0;">'
                f'<tr>'
                f'<td width="85%" style="{cell_style}">'
                f'{header_html}'
                f'<div style="color:{text_color};line-height:1.6;">{body}</div>'
                f'</td><td width="15%"></td></tr></table>'
            )
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        cursor.insertBlock()
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _append_action_result(self, action_type, target, result):
        icons  = {"read_file": "📖", "write_file": "💾", "run_command": "⚡", "list_dir": "📁"}
        icon   = icons.get(action_type, "🔧")
        purple = "#c678dd"
        bg     = self._current_settings.get("bg", "#1a1b26")
        html   = (
            f'<div style="margin:4px 0;padding:8px 16px;background-color:{bg};'
            f'border-radius:8px;border-left:3px solid {purple};">'
            f'<div style="color:{purple};font-size:11px;margin-bottom:4px;">'
            f'{icon} {action_type}: <code style="color:#61afef;">{target}</code></div>'
            f'<pre style="color:#abb2bf;font-size:12px;white-space:pre-wrap;margin:0;">{result[:800]}</pre>'
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
        for i, msg in enumerate(self.chat_mgr.get_messages(self.current_chat_id)):
            self._render_message(msg["role"], msg["content"], index=i)

    # ── Файлы ────────────────────────────────────────────────────────────────

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
            file_content = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}
            self.pending_files.append((fname, file_content))
            self._show_image_preview(path, fname)
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                file_text = f.read()
            file_content = {"type": "text", "text": f"[Файл: {fname}]\n```\n{file_text}\n```"}
            self.pending_files.append((fname, file_content))
            names = ", ".join(n for n, _ in self.pending_files)
            self.attach_label.setText(f"📎 {names}"); self.attach_label.show()

    def _show_image_preview(self, path, fname):
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton
        if not hasattr(self, "_preview_widget"):
            self._preview_widget = QWidget()
            self._preview_widget.setObjectName("preview_widget")
            self._preview_layout = QHBoxLayout(self._preview_widget)
            self._preview_layout.setContentsMargins(4, 4, 4, 4)
            self._preview_layout.setSpacing(6)
            # Вставляем превью над полем ввода
            parent_layout = self.input_box.parent().layout()
            parent_layout.insertWidget(0, self._preview_widget)
        # Чистим старые превью
        while self._preview_layout.count():
            item = self._preview_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for n, c in self.pending_files:
            if isinstance(c, dict) and c.get("type") == "image_url":
                container = QWidget()
                container.setStyleSheet("background:#252636;border-radius:8px;padding:2px;")
                cl = QHBoxLayout(container); cl.setContentsMargins(4,4,4,4); cl.setSpacing(4)
                thumb = QLabel()
                px = QPixmap(path).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                thumb.setPixmap(px)
                thumb.setFixedSize(60, 60)
                name_lbl = QLabel(n)
                name_lbl.setStyleSheet("color:#abb2bf;font-size:11px;max-width:80px;")
                name_lbl.setWordWrap(True)
                close_btn = QPushButton("✕")
                close_btn.setFixedSize(18, 18)
                close_btn.setStyleSheet("QPushButton{background:#e06c75;color:white;border:none;border-radius:9px;font-size:10px;}QPushButton:hover{background:#eb7a82;}")
                def remove_file(checked=False, name=n):
                    self.pending_files = [(fn, fc) for fn, fc in self.pending_files if fn != name]
                    if self.pending_files:
                        self._show_image_preview("", "")
                    else:
                        self._preview_widget.hide()
                        self.attach_label.hide()
                close_btn.clicked.connect(remove_file)
                cl.addWidget(thumb); cl.addWidget(name_lbl); cl.addWidget(close_btn)
                self._preview_layout.addWidget(container)
        self._preview_layout.addStretch()
        self._preview_widget.show()

    # ── Отправка ─────────────────────────────────────────────────────────────

    def _send_message(self):
        text = self.input_box.toPlainText().strip()
        if (not text and not self.pending_files) or not self.current_chat_id: return
        if self.worker and self.worker.isRunning(): return
        model = self.model_selector.currentText()
        if "не запущен" in model and "Сильфиетта" not in model: return
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
        self.stream_buffer = ""

        # Веб-поиск если нужен
        if should_search_web(text):
            self.status_label.setText("🌐 Ищу в интернете…")
            import threading
            def _search():
                result = search_and_summarize(text)
                if result["found"]:
                    # Добавляем контекст поиска в последнее сообщение
                    msgs = self.chat_mgr.get_messages(self.current_chat_id)
                    if msgs and msgs[-1]["role"] == "user":
                        orig = msgs[-1]["content"]
                        orig_text = orig if isinstance(orig, str) else                             next((p["text"] for p in orig if p.get("type") == "text"), "")
                        augmented = orig_text + "\n\n[Контекст из интернета]:\n" + result["summary"]

                        msgs[-1]["_search_context"] = result["summary"]
            t = threading.Thread(target=_search, daemon=True)
            t.start()
            t.join(timeout=8)

        # Типинг индикатор
        if self._current_settings.get("typing_dots", True):
            self._typing_frames = ["Сильфиетта думает ▌", "Сильфиетта думает  "]
            self._typing_frame  = 0
            self.status_label.setText(self._typing_frames[0])
            if self._typing_timer is None:
                self._typing_timer = QTimer()
                self._typing_timer.timeout.connect(self._tick_typing)
            self._typing_timer.start(500)
        else:
            self.status_label.setText("Сильфиетта думает…")

        self.worker = OllamaWorker(model, messages)
        self.worker.token_received.connect(self._on_token)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _tick_typing(self):
        self._typing_frame = (self._typing_frame + 1) % len(self._typing_frames)
        self.status_label.setText(self._typing_frames[self._typing_frame])

    def _stop_typing(self):
        if self._typing_timer:
            self._typing_timer.stop()

    def _on_token(self, token):
        self.stream_buffer += token
        self._rebuild_display()
        # Скрываем теги действий при стриминге
        display = re.sub(r'<action:[^>]+>.*?</action:[^>]+>', '', self.stream_buffer, flags=re.DOTALL)
        display = re.sub(r'<action:[^/]+/>', '', display).strip()
        cursor = " ▌" if self._current_settings.get("typing_dots", True) else ""
        self._append_bubble("assistant", display + cursor, raw=True)

    def _on_finished(self, full):
        self._stop_typing()
        actions = parse_ai_actions(full)
        clean   = re.sub(r'<action:[^>]+>.*?</action:[^>]+>', '', full, flags=re.DOTALL)
        clean   = re.sub(r'<action:[^/]*/>', '', clean).strip()
        self.chat_mgr.add_message(self.current_chat_id, "assistant", clean)
        self._rebuild_display()
        for action_type, target, result in actions:
            self._append_action_result(action_type, target, result)
        self.send_btn.setEnabled(True)
        self.status_label.setText("Готово ✦")
        self._refresh_chat_list()
        # TTS если окно скрыто
        if not self.isVisible() and clean:
            self._speak(clean[:200])
        # Показываем кнопку "Продолжить" если ответ похож на обрезанный
        if self._looks_truncated(clean):
            self._show_continue_btn()
        else:
            self._hide_continue_btn()

    def _looks_truncated(self, text: str) -> bool:
        if not text or len(text) < 100:
            return False
        # Признаки обрезанного ответа
        import re
        stripped = text.rstrip()
        if stripped.endswith(("...", "…")):
            return True
        # Незакрытый блок кода
        if stripped.count("```") % 2 != 0:
            return True
        # Обрезанное предложение (нет точки/вопроса/восклицания в конце)
        if len(stripped) > 200 and stripped[-1] not in ".!?»`":
            return True
        return False

    def _show_continue_btn(self):
        if not hasattr(self, "_continue_btn"):
            from PyQt6.QtWidgets import QPushButton
            self._continue_btn = QPushButton("▶ Продолжить ответ")
            self._continue_btn.setObjectName("continue_btn")
            self._continue_btn.clicked.connect(self._continue_generation)
            # Вставляем над полем ввода
            parent_layout = self.centralWidget().layout()
            chat_widget = parent_layout.itemAt(0).widget()
            if chat_widget:
                idx = chat_widget.layout().count() - 2
                chat_widget.layout().insertWidget(idx, self._continue_btn)
        self._continue_btn.show()

    def _hide_continue_btn(self):
        if hasattr(self, "_continue_btn"):
            self._continue_btn.hide()

    def _continue_generation(self):
        if not self.current_chat_id: return
        self._hide_continue_btn()
        msgs    = self.chat_mgr.get_messages(self.current_chat_id)
        history = [{"role": "system", "content": "Продолжи свой предыдущий ответ с того места где остановился. Не повторяй уже написанное."}] + list(msgs)
        model   = self.model_selector.currentText()
        self.send_btn.setEnabled(False)
        self.stream_buffer = ""
        self.status_label.setText("Продолжаю…")
        self.worker = OllamaWorker(model, history)
        self.worker.token_received.connect(self._on_continue_token)
        self.worker.finished.connect(self._on_continue_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_continue_token(self, token):
        self.stream_buffer += token
        display = re.sub(r'<action:[^>]+>.*?</action:[^>]+>', '', self.stream_buffer, flags=re.DOTALL)
        display = re.sub(r'<action:[^/]+/>', '', display).strip()
        cursor  = " ▌" if self._current_settings.get("typing_dots", True) else ""
        # Дописываем к последнему пузырьку AI
        msgs = self.chat_mgr.get_messages(self.current_chat_id)
        if msgs and msgs[-1]["role"] == "assistant":
            combined = msgs[-1]["content"] + display + cursor
            self._rebuild_display()
            self._append_bubble("assistant", combined, raw=True)
        else:
            self._append_bubble("assistant", display + cursor, raw=True)

    def _on_continue_finished(self, full):
        self._stop_typing()
        msgs = self.chat_mgr.get_messages(self.current_chat_id)
        if msgs and msgs[-1]["role"] == "assistant":
            combined = msgs[-1]["content"] + full
            self.chat_mgr.edit_message(self.current_chat_id, len(msgs)-1, combined)
        else:
            self.chat_mgr.add_message(self.current_chat_id, "assistant", full)
        self._rebuild_display()
        self.send_btn.setEnabled(True)
        self.status_label.setText("Готово ✦")
        if self._looks_truncated(full):
            self._show_continue_btn()

    def _on_error(self, err):
        self._stop_typing()
        self._append_bubble("assistant", f"Ошибка: {err}")
        self.send_btn.setEnabled(True)
        self.status_label.setText(f"Ошибка: {err}")

    # ── Настройки ────────────────────────────────────────────────────────────

    def _chat_display_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu, QApplication
        msgs = self.chat_mgr.get_messages(self.current_chat_id) if self.current_chat_id else []
        if not msgs: return
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#1e1f2e;color:#abb2bf;border:1px solid #2a2b3d;padding:4px;}QMenu::item{padding:6px 16px;}QMenu::item:selected{background:#2a2b3d;color:#dde3f0;}")
        # Копировать последнее сообщение AI
        ai_msgs = [(i, m) for i, m in enumerate(msgs) if m["role"] == "assistant"]
        user_msgs = [(i, m) for i, m in enumerate(msgs) if m["role"] == "user"]
        if ai_msgs:
            copy_ai = menu.addAction("⎘ Копировать ответ Сильфиетты")
        if user_msgs:
            copy_user = menu.addAction("⎘ Копировать моё сообщение")
        menu.addSeparator()
        copy_sel = menu.addAction("⎘ Копировать выделенное")
        action = menu.exec(self.chat_display.viewport().mapToGlobal(pos))
        if ai_msgs and action == copy_ai:
            i, m = ai_msgs[-1]
            text = m["content"] if isinstance(m["content"], str) else                 next((p["text"] for p in m["content"] if p.get("type") == "text"), "")
            QApplication.clipboard().setText(text)
            self.status_label.setText("Скопировано ✓")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Готово ✦"))
        elif user_msgs and action == copy_user:
            i, m = user_msgs[-1]
            text = m["content"] if isinstance(m["content"], str) else                 next((p["text"] for p in m["content"] if p.get("type") == "text"), "")
            QApplication.clipboard().setText(text)
            self.status_label.setText("Скопировано ✓")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Готово ✦"))
        elif action == copy_sel:
            QApplication.clipboard().setText(self.chat_display.textCursor().selectedText())
            self.status_label.setText("Скопировано ✓")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Готово ✦"))

    def _on_chat_click(self, event):
        from PyQt6.QtGui import QTextCursor
        cursor = self.chat_display.cursorForPosition(event.pos())
        # Ищем title с copy_ в ближайшем тексте
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        block_text = cursor.selectedText()
        import re
        m = re.search(r'copy_(\d+)', block_text)
        if m:
            self._copy_message(int(m.group(1)))
        # Передаём событие дальше
        QTextEdit.mousePressEvent(self.chat_display, event)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._new_chat)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(lambda: self.search_box.setFocus())
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._export_current)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.hide)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.search_box.clear)

    def _export_current(self):
        if self.current_chat_id:
            self._export_md(self.current_chat_id)

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        if os.path.exists(ICON_PATH):
            self._tray.setIcon(QIcon(ICON_PATH))
        else:
            from PyQt6.QtGui import QPixmap
            px = QPixmap(16, 16)
            px.fill(__import__("PyQt6.QtGui", fromlist=["QColor"]).QColor("#e06c75"))
            self._tray.setIcon(QIcon(px))
        tray_menu = QMenu()
        tray_menu.addAction("✦ Открыть", self.show)
        tray_menu.addAction("+ Новый чат", self._new_chat)
        tray_menu.addSeparator()
        tray_menu.addAction("Выйти", __import__("PyQt6.QtWidgets", fromlist=["QApplication"]).QApplication.quit)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(lambda r: self.show() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self._tray.setToolTip("Sylviette AI")
        self._tray.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self._tray.showMessage("Sylviette AI", "Сильфиетта свёрнута в трей… ✦",
            QSystemTrayIcon.MessageIcon.Information, 2000)

    def _speak(self, text):
        try:
            import pyttsx3, threading
            def _run():
                engine = pyttsx3.init()
                engine.setProperty("rate", 160)
                # Ищем русский голос
                for v in engine.getProperty("voices"):
                    if "ru" in v.id.lower() or "russian" in v.name.lower():
                        engine.setProperty("voice", v.id)
                        break
                engine.say(text[:300])
                engine.runAndWait()
            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            print(f"TTS error: {e}")

    def _copy_message(self, msg_index):
        if not self.current_chat_id: return
        msgs = self.chat_mgr.get_messages(self.current_chat_id)
        if msg_index >= len(msgs): return
        content = msgs[msg_index].get("content", "")
        text = content if isinstance(content, str) else             next((p["text"] for p in content if p.get("type") == "text"), "")
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.status_label.setText("Скопировано ✓")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Готово ✦"))

    def _on_chat_double_click(self, event):
        from PyQt6.QtWidgets import QInputDialog
        cursor = self.chat_display.cursorForPosition(event.pos())
        block  = cursor.block()
        # Ищем индекс сообщения по номеру блока
        if not self.current_chat_id:
            return
        msgs = self.chat_mgr.get_messages(self.current_chat_id)
        # Считаем блоки — каждое сообщение занимает несколько блоков
        # Находим ближайшее сообщение пользователя
        block_num = block.blockNumber()
        # Простой способ: показываем список сообщений пользователя для выбора
        user_msgs = [(i, m) for i, m in enumerate(msgs) if m["role"] == "user"]
        if not user_msgs:
            return
        # Если одно сообщение — редактируем сразу
        if len(user_msgs) == 1:
            idx, msg = user_msgs[0]
        else:
            # Показываем выбор
            titles = []
            for i, m in user_msgs:
                text = m["content"] if isinstance(m["content"], str) else                     next((p["text"] for p in m["content"] if p.get("type") == "text"), "")
                titles.append(f"{i+1}. {text[:50]}{'…' if len(text)>50 else ''}")
            choice, ok = QInputDialog.getItem(self, "Выберите сообщение",
                "Какое сообщение редактировать:", titles, 0, False)
            if not ok:
                return
            idx = user_msgs[titles.index(choice)][0]
            msg = msgs[idx]
        text = msg["content"] if isinstance(msg["content"], str) else             next((p["text"] for p in msg["content"] if p.get("type") == "text"), "")
        new_text, ok = QInputDialog.getMultiLineText(
            self, "Редактировать сообщение", "Текст:", text)
        if ok and new_text.strip() != text.strip():
            self.chat_mgr.edit_message(self.current_chat_id, idx, new_text)
            self._rebuild_display()

    def _on_chat_double_click(self, event):
        from PyQt6.QtWidgets import QInputDialog
        cursor = self.chat_display.cursorForPosition(event.pos())
        block  = cursor.block()
        # Ищем индекс сообщения по номеру блока
        if not self.current_chat_id:
            return
        msgs = self.chat_mgr.get_messages(self.current_chat_id)
        # Считаем блоки — каждое сообщение занимает несколько блоков
        # Находим ближайшее сообщение пользователя
        block_num = block.blockNumber()
        # Простой способ: показываем список сообщений пользователя для выбора
        user_msgs = [(i, m) for i, m in enumerate(msgs) if m["role"] == "user"]
        if not user_msgs:
            return
        # Если одно сообщение — редактируем сразу
        if len(user_msgs) == 1:
            idx, msg = user_msgs[0]
        else:
            # Показываем выбор
            titles = []
            for i, m in user_msgs:
                text = m["content"] if isinstance(m["content"], str) else                     next((p["text"] for p in m["content"] if p.get("type") == "text"), "")
                titles.append(f"{i+1}. {text[:50]}{'…' if len(text)>50 else ''}")
            choice, ok = QInputDialog.getItem(self, "Выберите сообщение",
                "Какое сообщение редактировать:", titles, 0, False)
            if not ok:
                return
            idx = user_msgs[titles.index(choice)][0]
            msg = msgs[idx]
        text = msg["content"] if isinstance(msg["content"], str) else             next((p["text"] for p in msg["content"] if p.get("type") == "text"), "")
        new_text, ok = QInputDialog.getMultiLineText(
            self, "Редактировать сообщение", "Текст:", text)
        if ok and new_text.strip() != text.strip():
            self.chat_mgr.edit_message(self.current_chat_id, idx, new_text)
            self._rebuild_display()

    def _on_chat_double_click(self, event):
        from PyQt6.QtWidgets import QInputDialog
        cursor = self.chat_display.cursorForPosition(event.pos())
        block  = cursor.block()
        # Ищем индекс сообщения по номеру блока
        if not self.current_chat_id:
            return
        msgs = self.chat_mgr.get_messages(self.current_chat_id)
        # Считаем блоки — каждое сообщение занимает несколько блоков
        # Находим ближайшее сообщение пользователя
        block_num = block.blockNumber()
        # Простой способ: показываем список сообщений пользователя для выбора
        user_msgs = [(i, m) for i, m in enumerate(msgs) if m["role"] == "user"]
        if not user_msgs:
            return
        # Если одно сообщение — редактируем сразу
        if len(user_msgs) == 1:
            idx, msg = user_msgs[0]
        else:
            # Показываем выбор
            titles = []
            for i, m in user_msgs:
                text = m["content"] if isinstance(m["content"], str) else                     next((p["text"] for p in m["content"] if p.get("type") == "text"), "")
                titles.append(f"{i+1}. {text[:50]}{'…' if len(text)>50 else ''}")
            choice, ok = QInputDialog.getItem(self, "Выберите сообщение",
                "Какое сообщение редактировать:", titles, 0, False)
            if not ok:
                return
            idx = user_msgs[titles.index(choice)][0]
            msg = msgs[idx]
        text = msg["content"] if isinstance(msg["content"], str) else             next((p["text"] for p in msg["content"] if p.get("type") == "text"), "")
        new_text, ok = QInputDialog.getMultiLineText(
            self, "Редактировать сообщение", "Текст:", text)
        if ok and new_text.strip() != text.strip():
            self.chat_mgr.edit_message(self.current_chat_id, idx, new_text)
            self._rebuild_display()

    def _on_search(self, query):
        self._refresh_chat_list(query=query)

    def _chat_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        item = self.chat_list.itemAt(pos)
        if not item: return
        cid = item.data(Qt.ItemDataRole.UserRole)
        if not cid: return
        menu = QMenu(self)
        s = self._current_settings
        bg = s.get("bg", "#1a1b26")
        menu.setStyleSheet(f"QMenu{{background:#1e1f2e;color:#abb2bf;border:1px solid #2a2b3d;padding:4px;}}QMenu::item{{padding:6px 16px;}}QMenu::item:selected{{background:#2a2b3d;color:#dde3f0;}}")
        pinned = self.chat_mgr.is_pinned(cid)
        pin_act    = menu.addAction("📌 Открепить" if pinned else "📌 Закрепить")
        menu.addSeparator()
        export_md  = menu.addAction("📄 Экспорт в Markdown")
        export_pdf = menu.addAction("📋 Экспорт в PDF")
        menu.addSeparator()
        stats_act  = menu.addAction("📊 Статистика")
        menu.addSeparator()
        del_act    = menu.addAction("🗑 Удалить")
        action = menu.exec(self.chat_list.viewport().mapToGlobal(pos))
        if action == pin_act:
            self.chat_mgr.toggle_pin(cid)
            self._refresh_chat_list()
        elif action == export_md:
            self._export_md(cid)
        elif action == export_pdf:
            self._export_pdf(cid)
        elif action == stats_act:
            self._show_stats(cid)
        elif action == del_act:
            self._delete_current_chat()

    def _export_md(self, cid):
        from PyQt6.QtWidgets import QFileDialog
        title = self.chat_mgr.get_title(cid).replace("/", "_")
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как Markdown",
            f"{title}.md", "Markdown (*.md)")
        if not path: return
        md = self.chat_mgr.export_md(cid)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        self.status_label.setText(f"Экспортировано: {path}")

    def _export_pdf(self, cid):
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtGui import QTextDocument
        title = self.chat_mgr.get_title(cid).replace("/", "_")
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как PDF",
            f"{title}.pdf", "PDF (*.pdf)")
        if not path: return
        md = self.chat_mgr.export_md(cid)
        doc = QTextDocument()
        doc.setMarkdown(md)
        printer = QPrinter()
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        doc.print(printer)
        self.status_label.setText(f"PDF сохранён: {path}")

    def _show_stats(self, cid):
        from PyQt6.QtWidgets import QMessageBox
        s = self.chat_mgr.get_stats(cid)
        title = self.chat_mgr.get_title(cid)
        QMessageBox.information(self, f"Статистика — {title}",
            f"📅 Создан:        {s['created']}\n"
            f"💬 Сообщений:     {s['total']}\n"
            f"👤 От Создателя:  {s['user']}\n"
            f"🤖 От Сильфиетты: {s['ai']}\n"
            f"🔤 Токенов (≈):   {s['tokens']:,}"
        )

    def _toggle_files(self):
        visible = self.file_panel.isVisible()
        self.file_panel.setVisible(not visible)
        if not visible:
            self._splitter.setSizes([240, 700, 350])
        else:
            self._splitter.setSizes([240, 910, 0])

    def _file_to_chat(self, fname, content):
        if not self.current_chat_id:
            return
        file_content = {"type": "text", "text": "[Файл: " + fname + "]\n```\n" + content + "\n```"}
        self.pending_files.append((fname, file_content))
        names = ", ".join(n for n, _ in self.pending_files)
        self.attach_label.setText("📎 " + names)
        self.attach_label.show()

    def _start_reminder_daemon(self):
        def on_reminder(event):
            from PyQt6.QtCore import QMetaObject, Qt
            # Вызываем в главном потоке
            QMetaObject.invokeMethod(self, "_show_reminder",
                Qt.ConnectionType.QueuedConnection,
                __import__("PyQt6.QtCore", fromlist=["Q_ARG"]).Q_ARG(str, event["title"]),
                __import__("PyQt6.QtCore", fromlist=["Q_ARG"]).Q_ARG(str, event["datetime"]))
        self._reminder_daemon = ReminderDaemon(on_reminder)
        self._reminder_daemon.start()

    def _show_reminder_notify(self, title, dt_str):
        try:
            dt = __import__("datetime").datetime.fromisoformat(dt_str)
            dt_fmt = dt.strftime("%H:%M")
        except Exception:
            dt_fmt = dt_str
        if hasattr(self, "_tray"):
            self._tray.showMessage(
                f"📅 Напоминание",
                f"{title} в {dt_fmt}",
                __import__("PyQt6.QtWidgets", fromlist=["QSystemTrayIcon"]).QSystemTrayIcon.MessageIcon.Information,
                8000
            )
        self.status_label.setText(f"📅 Напоминание: {title} в {dt_fmt}")

    def _open_calendar(self):
        w = CalendarWidget(self)
        w.exec()

    def _open_more_menu(self):
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QCursor
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#1e1f2e;color:#abb2bf;border:1px solid #2a2b3d;"
            "border-radius:8px;padding:6px;}"
            "QMenu::item{padding:8px 20px;border-radius:4px;}"
            "QMenu::item:selected{background:#2a2b3d;color:#dde3f0;}"
            "QMenu::separator{height:1px;background:#2a2b3d;margin:4px 8px;}"
        )
        menu.addAction("\u2699\ufe0f \u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438",       self._open_settings)
        menu.addAction("\U0001f4ca \u0414\u0430\u0448\u0431\u043e\u0440\u0434",         self._open_dashboard)
        menu.addAction("\U0001f9e9 \u041f\u043b\u0430\u0433\u0438\u043d\u044b",         self._open_plugins)
        menu.addSeparator()
        menu.addAction("\U0001f5d1 \u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0447\u0430\u0442",     self._delete_current_chat)
        menu.addSeparator()
        menu.addAction("\U0001f4c4 \u042d\u043a\u0441\u043f\u043e\u0440\u0442 MD",    lambda: self._export_md(self.current_chat_id) if self.current_chat_id else None)
        menu.addAction("\U0001f4cb \u042d\u043a\u0441\u043f\u043e\u0440\u0442 PDF",   lambda: self._export_pdf(self.current_chat_id) if self.current_chat_id else None)
        menu.addAction("\U0001f4ca \u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430", lambda: self._show_stats(self.current_chat_id) if self.current_chat_id else None)
        menu.exec(QCursor.pos())

    def _open_profiles(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QTextEdit, QInputDialog
        profiles = load_profiles()
        active   = get_active_profile()
        dlg = QDialog(self)
        dlg.setWindowTitle("🎯 Профили задач")
        dlg.resize(500, 400)
        s = self._current_settings
        bg = s.get("bg", "#1a1b26")
        dlg.setStyleSheet(f"QDialog{{background:{bg};color:#abb2bf;}}QListWidget{{background:#1e1f2e;color:#abb2bf;border:1px solid #2a2b3d;border-radius:6px;}}QListWidget::item{{padding:8px;}}QListWidget::item:selected{{background:#2a2b3d;color:#dde3f0;}}QTextEdit{{background:#1e1f2e;color:#abb2bf;border:1px solid #2a2b3d;border-radius:6px;padding:8px;}}QPushButton{{background:#2a2b3d;color:#abb2bf;border:none;border-radius:6px;padding:8px 16px;}}QPushButton:hover{{background:#61afef;color:white;}}")
        l = QVBoxLayout(dlg)
        lbl = QLabel("Выберите профиль — он изменит стиль ответов Сильфиетты:")
        lbl.setStyleSheet("color:#dde3f0;font-size:13px;margin-bottom:4px;")
        l.addWidget(lbl)
        lst = QListWidget()
        desc_box = QTextEdit(); desc_box.setReadOnly(True); desc_box.setMaximumHeight(80)
        for name, data in profiles.items():
            item = QListWidgetItem(("✓ " if name == active else "  ") + name)
            item.setData(32, name)
            lst.addItem(item)
        def on_select(item):
            name = item.data(32)
            desc_box.setPlainText(profiles[name]["description"] + "\n\n" + profiles[name].get("extra_prompt", "")[:200])

        lst.itemClicked.connect(on_select)
        l.addWidget(lst)
        l.addWidget(QLabel("Описание:"))
        l.addWidget(desc_box)
        btns = QHBoxLayout()
        apply_btn = QPushButton("✓ Применить")
        new_btn_p = QPushButton("+ Новый профиль")
        del_btn_p = QPushButton("🗑 Удалить")
        for b in [apply_btn, new_btn_p, del_btn_p]: btns.addWidget(b)
        l.addLayout(btns)
        def apply():
            item = lst.currentItem()
            if not item: return
            name = item.data(32)
            set_active_profile(name)
            self.profile_btn.setText(f"🎯 {name}")
            self.status_label.setText(f"Профиль: {name}")
            dlg.accept()
        def new_profile():
            name, ok = QInputDialog.getText(dlg, "Новый профиль", "Название:")
            if not ok or not name: return
            prompt, ok2 = QInputDialog.getMultiLineText(dlg, "Промпт", "Инструкция для Сильфиетты:")
            if not ok2: return
            save_custom_profile(name, "Пользовательский профиль", prompt)
            dlg.accept(); self._open_profiles()
        def del_profile():
            item = lst.currentItem()
            if not item: return
            name = item.data(32)
            if delete_custom_profile(name):
                dlg.accept(); self._open_profiles()
            else:
                self.status_label.setText("Нельзя удалить стандартный профиль")
        apply_btn.clicked.connect(apply)
        new_btn_p.clicked.connect(new_profile)
        del_btn_p.clicked.connect(del_profile)
        dlg.exec()

    def _open_plugins(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QCheckBox
        plugins = list_plugins()
        dlg = QDialog(self)
        dlg.setWindowTitle("🧩 Плагины")
        dlg.resize(480, 380)
        s = self._current_settings
        bg = s.get("bg", "#1a1b26")
        dlg.setStyleSheet(f"QDialog{{background:{bg};color:#abb2bf;}}QCheckBox{{color:#abb2bf;spacing:8px;font-size:13px;padding:6px;}}QCheckBox::indicator{{width:16px;height:16px;border-radius:3px;border:1px solid #2a2b3d;background:#252636;}}QCheckBox::indicator:checked{{background:#61afef;border-color:#61afef;}}QLabel{{color:#abb2bf;}}QPushButton{{background:#2a2b3d;color:#abb2bf;border:none;border-radius:6px;padding:8px 16px;}}QPushButton:hover{{background:#61afef;color:white;}}")
        l = QVBoxLayout(dlg)
        lbl = QLabel("Управление плагинами:")
        lbl.setStyleSheet("color:#dde3f0;font-size:13px;margin-bottom:8px;")
        l.addWidget(lbl)
        if not plugins:
            l.addWidget(QLabel("Плагины не найдены в папке plugins/"))
        for p in plugins:
            cb = QCheckBox(f"{p['name']}  —  {p['description']}")
            cb.setChecked(p["enabled"])
            cb.stateChanged.connect(lambda v, pid=p["id"]: toggle_plugin(pid, bool(v)))
            l.addWidget(cb)
        l.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(dlg.accept)
        l.addWidget(close_btn)
        dlg.exec()

    def _open_dashboard(self):
        w = DashboardWindow(self.chat_mgr, self)
        w.exec()

    def _open_settings(self):
        w = SettingsWindow(self)
        w.settings_changed.connect(self._apply_settings)
        w.exec()

    def _apply_settings(self, s):
        self._current_settings = s
        self.setStyleSheet(build_stylesheet(s))
        if self.current_chat_id:
            self._rebuild_display()
