"""
ui/calendar_widget.py — виджет календаря Сильфиетты
"""
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QListWidget, QListWidgetItem,
    QLineEdit, QDateTimeEdit, QSpinBox, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QDateTime, QTimer
from PyQt6.QtGui import QColor
from calendar_manager import (
    load_calendar, add_event, delete_event,
    get_upcoming, format_events, parse_datetime
)


class CalendarWidget(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📅 Календарь — Sylviette AI")
        self.resize(560, 520)
        self.setStyleSheet("""
            QDialog { background:#1a1b26; color:#abb2bf; }
            QLabel  { color:#abb2bf; }
            QListWidget {
                background:#1e1f2e; color:#abb2bf;
                border:1px solid #2a2b3d; border-radius:6px;
            }
            QListWidget::item { padding:8px 12px; border-bottom:1px solid #2a2b3d; }
            QListWidget::item:selected { background:#2a2b3d; color:#dde3f0; }
            QLineEdit, QTextEdit {
                background:#252636; color:#dde3f0;
                border:1px solid #2a2b3d; border-radius:6px; padding:6px 10px;
            }
            QDateTimeEdit {
                background:#252636; color:#dde3f0;
                border:1px solid #2a2b3d; border-radius:6px; padding:6px 10px;
            }
            QSpinBox {
                background:#252636; color:#dde3f0;
                border:1px solid #2a2b3d; border-radius:6px; padding:4px 8px;
            }
            QPushButton {
                background:#2a2b3d; color:#abb2bf;
                border:none; border-radius:6px; padding:8px 16px;
            }
            QPushButton:hover { background:#61afef; color:white; }
            QPushButton#add_btn { background:#4ade80; color:#0d1b14; font-weight:bold; }
            QPushButton#add_btn:hover { background:#86efac; }
            QPushButton#del_btn { background:#e06c75; color:white; }
            QPushButton#del_btn:hover { background:#eb7a82; }
        """)
        self._build()
        self._refresh()

    def _build(self):
        l = QVBoxLayout(self)
        l.setSpacing(12)
        l.setContentsMargins(16, 16, 16, 16)

        # Заголовок
        header = QHBoxLayout()
        title  = QLabel("📅 Календарь")
        title.setStyleSheet("font-size:18px;font-weight:bold;color:#dde3f0;")
        self._today_lbl = QLabel("")
        self._today_lbl.setStyleSheet("color:#565c7a;font-size:12px;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._today_lbl)
        l.addLayout(header)

        # Список событий
        self._list = QListWidget()
        self._list.setMinimumHeight(180)
        l.addWidget(QLabel("Предстоящие события:"))
        l.addWidget(self._list)

        # Кнопки управления
        btn_row = QHBoxLayout()
        del_btn = QPushButton("🗑 Удалить выбранное"); del_btn.setObjectName("del_btn")
        del_btn.clicked.connect(self._delete_selected)
        open_btn = QPushButton("📂 Открыть в KOrganizer")
        open_btn.clicked.connect(self._open_korganizer)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        l.addLayout(btn_row)

        # Форма добавления
        sep = QLabel("── Добавить событие ──")
        sep.setStyleSheet("color:#565c7a;font-size:11px;margin-top:4px;")
        l.addWidget(sep)

        # Название
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Название события…")
        l.addWidget(self._title_input)

        # Описание
        self._desc_input = QLineEdit()
        self._desc_input.setPlaceholderText("Описание (необязательно)…")
        l.addWidget(self._desc_input)

        # Дата/время + напоминание
        dt_row = QHBoxLayout()
        self._dt_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self._dt_edit.setDisplayFormat("dd.MM.yyyy HH:mm")
        self._dt_edit.setCalendarPopup(True)
        remind_lbl = QLabel("Напомнить за:")
        self._remind_spin = QSpinBox()
        self._remind_spin.setRange(0, 1440)
        self._remind_spin.setValue(15)
        self._remind_spin.setSuffix(" мин")
        dt_row.addWidget(QLabel("Дата/время:"))
        dt_row.addWidget(self._dt_edit)
        dt_row.addStretch()
        dt_row.addWidget(remind_lbl)
        dt_row.addWidget(self._remind_spin)
        l.addLayout(dt_row)

        # Быстрый ввод
        quick_row = QHBoxLayout()
        self._quick_input = QLineEdit()
        self._quick_input.setPlaceholderText("Быстрый ввод: 'встреча завтра в 15:00'")
        self._quick_input.returnPressed.connect(self._add_quick)
        quick_btn = QPushButton("⚡ Быстро")
        quick_btn.clicked.connect(self._add_quick)
        quick_row.addWidget(self._quick_input)
        quick_row.addWidget(quick_btn)
        l.addLayout(quick_row)

        # Кнопка добавить
        add_btn = QPushButton("+ Добавить событие"); add_btn.setObjectName("add_btn")
        add_btn.clicked.connect(self._add_event)
        l.addWidget(add_btn)

    def _refresh(self):
        self._list.clear()
        now = datetime.now()
        self._today_lbl.setText(now.strftime("%d.%m.%Y, %A"))
        events = get_upcoming(days=30)
        if not events:
            item = QListWidgetItem("Нет запланированных событий")
            item.setForeground(QColor("#565c7a"))
            self._list.addItem(item)
            return
        for e in events:
            try:
                dt = datetime.fromisoformat(e["datetime"])
                delta = dt - now
                if delta.days == 0:
                    when = f"сегодня в {dt.strftime('%H:%M')}"
                elif delta.days == 1:
                    when = f"завтра в {dt.strftime('%H:%M')}"
                else:
                    when = dt.strftime("%d.%m в %H:%M")
                text = f"📅 {when}  —  {e['title']}"
                if e.get("description"):
                    text += f"\n   {e['description']}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, e["id"])
                # Цвет по срочности
                if delta.total_seconds() < 3600:
                    item.setForeground(QColor("#e06c75"))
                elif delta.days == 0:
                    item.setForeground(QColor("#f97316"))
                else:
                    item.setForeground(QColor("#dde3f0"))
                self._list.addItem(item)
            except Exception:
                pass

    def _add_event(self):
        title = self._title_input.text().strip()
        if not title:
            self._title_input.setPlaceholderText("Введите название!")
            return
        qt_dt = self._dt_edit.dateTime().toPyDateTime()
        add_event(title, qt_dt, self._desc_input.text().strip(), self._remind_spin.value())
        self._title_input.clear()
        self._desc_input.clear()
        self._refresh()

    def _add_quick(self):
        text = self._quick_input.text().strip()
        if not text: return
        dt = parse_datetime(text)
        if dt:
            import re
            title = re.sub(r'(завтра|сегодня|послезавтра|через\s+\d+\s*\w+|\d{1,2}[.:]\d{2}|в\s+\d+[.:]\d+|\d{1,2}\.\d{1,2})', '', text, flags=re.IGNORECASE).strip(" ,.-")
            if not title: title = "Событие"
            add_event(title, dt)
            self._quick_input.clear()
            self._refresh()
        else:
            self._quick_input.setPlaceholderText("Не понял дату — попробуй 'встреча завтра в 15:00'")

    def _delete_selected(self):
        item = self._list.currentItem()
        if not item: return
        eid = item.data(Qt.ItemDataRole.UserRole)
        if not eid: return
        if delete_event(eid):
            self._refresh()

    def _open_korganizer(self):
        import subprocess
        try:
            subprocess.Popen(["korganizer"], start_new_session=True)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))
