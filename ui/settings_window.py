from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QColorDialog, QSpinBox, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
import json, os

SETTINGS_FILE = os.path.expanduser("~/.ai-assistant/settings.json")

DEFAULT = {
    "bg":            "#1a1b26",
    "sidebar":       "#13141f",
    "accent":        "#e06c75",
    "accent2":       "#61afef",
    "font_size":     14,
    "bubble_radius": 10,
    "sidebar_width": 240,
}

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return {**DEFAULT, **json.load(f)}
    except:
        return DEFAULT.copy()

def save_settings(s):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)

def build_stylesheet(s):
    return f"""
QMainWindow, QWidget {{
    background-color: {s['bg']};
    color: #abb2bf;
    font-family: 'Noto Sans', sans-serif;
    font-size: {s['font_size']}px;
}}
#sidebar {{
    background-color: {s['sidebar']};
    border-right: 1px solid #2a2b3d;
    min-width: {s['sidebar_width']}px;
    max-width: {s['sidebar_width']+60}px;
}}
#app_title {{
    color: #dde3f0;
    font-size: 15px;
    font-weight: bold;
    padding: 18px 16px 4px 16px;
    letter-spacing: 1px;
}}
#app_subtitle {{
    color: #565c7a;
    font-size: 11px;
    padding: 0 16px 14px 16px;
    letter-spacing: 2px;
}}
QPushButton#new_chat_btn {{
    background-color: {s['accent']};
    color: white; border: none;
    border-radius: {s['bubble_radius']}px;
    padding: 10px 14px; font-size: 13px;
    font-weight: bold; margin: 8px 12px;
}}
QPushButton#new_chat_btn:hover {{ background-color: #eb7a82; }}
QListWidget#chat_list {{
    background-color: transparent;
    border: none; outline: none; padding: 4px 8px;
}}
QListWidget#chat_list::item {{
    color: #abb2bf; border-radius: 6px;
    padding: 8px 10px; margin: 2px 0;
}}
QListWidget#chat_list::item:hover {{ background-color: #1e1f2e; color: #dde3f0; }}
QListWidget#chat_list::item:selected {{ background-color: #2a2b3d; color: #dde3f0; }}
QPushButton#delete_btn {{
    background-color: transparent;
    color: #565c7a;
    border: 1px solid #2a2b3d;
    border-radius: 6px; padding: 6px 10px;
    font-size: 12px; margin: 4px 12px;
}}
QPushButton#delete_btn:hover {{ background-color: {s['accent']}; color: white; }}
QPushButton#attach_btn {{
    background-color: transparent; color: #565c7a;
    border: 1px solid #2a2b3d; border-radius: 10px;
    font-size: 16px; min-width: 46px; max-width: 46px;
    max-height: 46px;
}}
QComboBox#model_selector {{
    background-color: #252636; color: #abb2bf;
    border: 1px solid #2a2b3d; border-radius: 6px;
    padding: 6px 10px; margin: 4px 12px; font-size: 12px;
}}
QComboBox QAbstractItemView {{
    background-color: #1e1f2e; color: #abb2bf;
    border: 1px solid #2a2b3d;
    selection-background-color: #2a2b3d;
}}
QTextEdit#chat_display {{
    background-color: transparent; color: #abb2bf;
    border: none; padding: 16px;
    font-size: {s['font_size']}px;
}}
#input_panel {{
    background-color: {s['sidebar']};
    border-top: 1px solid #2a2b3d; padding: 12px 16px;
}}
QTextEdit#input_box {{
    background-color: #252636; color: #dde3f0;
    border: 1px solid #2a2b3d;
    border-radius: {s['bubble_radius']}px;
    padding: 4px 10px; font-size: {s['font_size']}px;
}}
QTextEdit#input_box:focus {{ border-color: {s['accent2']}; }}
QPushButton#send_btn {{
    background-color: {s['accent2']};
    color: white; border: none;
    border-radius: {s['bubble_radius']}px;
    padding: 10px 20px; font-size: 14px;
    font-weight: bold; min-width: 70px;
}}
QPushButton#send_btn:hover {{ background-color: #72bcf5; }}
QPushButton#send_btn:disabled {{ background-color: #2a2b3d; color: #565c7a; }}
#status_bar {{ color: #565c7a; font-size: 11px; padding: 2px 0; }}
#attach_label {{ color: #c678dd; font-size: 11px; padding: 2px 4px; }}
QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #2a2b3d; border-radius: 3px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: #565c7a; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QSplitter::handle {{ background-color: #2a2b3d; width: 1px; }}
"""


class ColorButton(QPushButton):
    color_changed = pyqtSignal(str)

    def __init__(self, color, label):
        super().__init__(label)
        self.color = color
        self._update_style()
        self.clicked.connect(self._pick)

    def _update_style(self):
        self.setStyleSheet(
            f"background-color:{self.color};color:white;border-radius:6px;"
            f"padding:6px 12px;border:none;font-size:13px;")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self)
        if c.isValid():
            self.color = c.name()
            self._update_style()
            self.color_changed.emit(self.color)


class SettingsWindow(QDialog):
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки — Sylfiette AI")
        self.setMinimumWidth(440)
        self.setStyleSheet("""
            QDialog { background-color: #1a1b26; color: #abb2bf; }
            QTabWidget::pane { border: 1px solid #2a2b3d; border-radius: 6px; }
            QTabBar::tab { background: #13141f; color: #abb2bf; padding: 8px 16px; margin-right: 4px; border-radius: 4px; }
            QTabBar::tab:selected { background: #2a2b3d; color: #dde3f0; }
            QLabel { color: #abb2bf; }
            QSpinBox { background: #252636; color: #dde3f0; border: 1px solid #2a2b3d; border-radius: 4px; padding: 4px 8px; }
        """)
        self.settings = load_settings()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        tabs = QTabWidget()
        tabs.addTab(self._colors_tab(), "🎨 Цвета")
        tabs.addTab(self._layout_tab(), "📐 Размеры")
        layout.addWidget(tabs)

        btns = QHBoxLayout()
        reset_btn = QPushButton("↺ Сброс")
        save_btn  = QPushButton("✓ Сохранить и применить")
        reset_btn.setStyleSheet("background:#2a2b3d;color:#abb2bf;border:none;border-radius:6px;padding:8px 20px;")
        save_btn.setStyleSheet("background:#61afef;color:white;border:none;border-radius:6px;padding:8px 20px;font-weight:bold;")
        reset_btn.clicked.connect(self._reset)
        save_btn.clicked.connect(self._save)
        btns.addWidget(reset_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _colors_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(10)
        colors = [
            ("bg",      "Фон приложения"),
            ("sidebar", "Фон боковой панели"),
            ("accent",  "Акцент Сильфиетты"),
            ("accent2", "Акцент кнопок / вас"),
        ]
        for key, label in colors:
            row = QHBoxLayout()
            lbl = QLabel(label); lbl.setFixedWidth(200)
            btn = ColorButton(self.settings[key], self.settings[key])
            btn.color_changed.connect(lambda c, k=key: self.settings.update({k: c}))
            row.addWidget(lbl); row.addWidget(btn)
            l.addLayout(row)
        l.addStretch()
        return w

    def _layout_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(14)
        rows = [
            ("Размер шрифта (px)",       "font_size",     10, 22),
            ("Скругление углов (px)",    "bubble_radius",  0, 20),
            ("Ширина боковой панели",    "sidebar_width", 180, 400),
        ]
        for label, key, mn, mx in rows:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:"); lbl.setFixedWidth(200)
            spin = QSpinBox()
            spin.setRange(mn, mx)
            spin.setValue(self.settings[key])
            spin.valueChanged.connect(lambda v, k=key: self.settings.update({k: v}))
            row.addWidget(lbl); row.addWidget(spin)
            l.addLayout(row)
        l.addStretch()
        return w

    def _save(self):
        save_settings(self.settings)
        self.settings_changed.emit(self.settings)
        self.accept()

    def _reset(self):
        from ui.settings_window import DEFAULT
        save_settings(DEFAULT.copy())
        self.settings_changed.emit(DEFAULT.copy())
        self.accept()
