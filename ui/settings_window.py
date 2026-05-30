from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QColorDialog, QSpinBox, QTabWidget, QWidget, QComboBox,
    QCheckBox, QSlider, QGroupBox, QScrollArea, QFontComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import json, os

SETTINGS_FILE = os.path.expanduser("~/.ai-assistant/settings.json")

DEFAULT = {
    "bg":             "#1a1b26",
    "sidebar":        "#13141f",
    "accent":         "#e06c75",
    "accent2":        "#61afef",
    "font_size":      14,
    "bubble_radius":  10,
    "sidebar_width":  240,
    "font_family":    "Noto Sans",
    "mono_font":      "JetBrains Mono",
    "avatar_ai":      "✦",
    "avatar_user":    "👤",
    "avatar_ai_bg":   "#e06c75",
    "avatar_user_bg": "#61afef",
    "show_avatars":   True,
    "bubble_animation": True,
    "typing_dots":    True,
    "bubble_shadow":  True,
    "compact_mode":   False,
    "show_timestamp": False,
    "animation_speed": 200,
}


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return {**DEFAULT, **json.load(f)}
    except Exception:
        return DEFAULT.copy()


def save_settings(s):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def _is_light(hex_color: str) -> bool:
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r * 0.299 + g * 0.587 + b * 0.114) > 140
    except Exception:
        return False


def _lighten(hex_color: str, amount: int = 20) -> str:
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"#{min(255,r+amount):02x}{min(255,g+amount):02x}{min(255,b+amount):02x}"
    except Exception:
        return hex_color


def build_stylesheet(s):
    bg      = s.get("bg",            DEFAULT["bg"])
    sidebar = s.get("sidebar",       DEFAULT["sidebar"])
    accent  = s.get("accent",        DEFAULT["accent"])
    accent2 = s.get("accent2",       DEFAULT["accent2"])
    fs      = s.get("font_size",     DEFAULT["font_size"])
    br      = s.get("bubble_radius", DEFAULT["bubble_radius"])
    sw      = s.get("sidebar_width", DEFAULT["sidebar_width"])
    ff      = s.get("font_family",   DEFAULT["font_family"])

    is_light    = _is_light(bg)
    text        = "#1a1b26" if is_light else "#abb2bf"
    text_bright = "#0d0e16" if is_light else "#dde3f0"
    text_dim    = "#6b7280" if is_light else "#565c7a"
    border      = "#d1d5db" if is_light else "#2a2b3d"
    panel       = "#e5e7eb" if is_light else "#1e1f2e"
    input_bg    = "#f3f4f6" if is_light else "#252636"

    font_rule = f"'System Default'" if ff == "System Default" else f"'{ff}', 'Noto Sans', sans-serif"

    return f"""
QMainWindow, QWidget {{
    background-color: {bg};
    color: {text};
    font-family: {font_rule};
    font-size: {fs}px;
}}
#sidebar {{
    background-color: {sidebar};
    border-right: 1px solid {border};
    min-width: {sw}px;
    max-width: {sw + 60}px;
}}
#app_title {{
    color: {text_bright};
    font-size: 15px; font-weight: bold;
    padding: 18px 16px 4px 16px; letter-spacing: 1px;
}}
#app_subtitle {{
    color: {text_dim};
    font-size: 11px;
    padding: 0 16px 14px 16px; letter-spacing: 2px;
}}
QLineEdit#search_box {{
    background-color: {input_bg};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 10px;
    margin: 4px 12px;
    font-size: 12px;
}}
QLineEdit#search_box:focus {{ border-color: {accent2}; }}
QPushButton#new_chat_btn {{
    background-color: {accent}; color: white; border: none;
    border-radius: {br}px; padding: 10px 14px;
    font-size: 13px; font-weight: bold; margin: 8px 12px;
}}
QPushButton#new_chat_btn:hover {{ background-color: {_lighten(accent)}; }}
QListWidget#chat_list {{
    background-color: transparent; border: none; outline: none; padding: 4px 8px;
}}
QListWidget#chat_list::item {{
    color: {text}; border-radius: 6px; padding: 8px 10px; margin: 2px 0;
}}
QListWidget#chat_list::item:hover {{ background-color: {panel}; color: {text_bright}; }}
QListWidget#chat_list::item:selected {{ background-color: {border}; color: {text_bright}; }}
QPushButton#delete_btn {{
    background-color: transparent; color: {text_dim};
    border: 1px solid {border}; border-radius: 6px;
    padding: 6px 10px; font-size: 12px; margin: 4px 12px;
}}
QPushButton#delete_btn:hover {{ background-color: {accent}; color: white; }}
QPushButton#attach_btn {{
    background-color: transparent; color: {text_dim};
    border: 1px solid {border}; border-radius: 10px;
    font-size: 16px; min-width: 46px; max-width: 46px; max-height: 46px;
}}
QComboBox#model_selector {{
    background-color: {input_bg}; color: {text};
    border: 1px solid {border}; border-radius: 6px;
    padding: 6px 10px; margin: 4px 12px; font-size: 12px;
}}
QComboBox QAbstractItemView {{
    background-color: {panel}; color: {text};
    border: 1px solid {border}; selection-background-color: {border};
}}
#chat_header {{
    background-color: {bg};
    border-bottom: 1px solid {border};
}}
#chat_title_label {{
    color: {text_bright};
    font-size: 14px;
    font-weight: bold;
}}
QTextEdit#chat_display {{
    background-color: transparent; color: {text};
    border: none; padding: 16px; font-size: {fs}px;
}}
#input_panel {{
    background-color: {sidebar};
    border-top: 1px solid {border};
    padding: 8px 12px;
}}
#input_outer {{
    background-color: {input_bg};
    border: 1px solid {border};
    border-radius: 16px;
}}
#input_outer:focus-within {{
    border-color: {accent2};
}}
QTextEdit#input_box {{
    background-color: transparent;
    color: {text_bright};
    border: none;
    padding: 2px 4px;
    font-size: {fs}px;
}}
QPushButton#send_btn {{
    background-color: {accent2};
    color: white; border: none;
    border-radius: 18px;
    font-size: 16px; font-weight: bold;
    min-width: 36px; max-width: 36px;
    min-height: 36px; max-height: 36px;
}}
QPushButton#send_btn:hover {{ background-color: {_lighten(accent2)}; }}
QPushButton#send_btn:disabled {{ background-color: {border}; color: {text_dim}; }}
QPushButton#md_toggle_btn {{
    background-color: {border};
    color: {text_dim};
    border: none; border-radius: 6px;
    font-size: 10px; font-weight: bold;
}}
QPushButton#md_toggle_btn:checked {{
    background-color: {accent2}; color: white;
}}
QPushButton#mic_btn {{
    background-color: {border};
    color: {text_dim};
    border: none; border-radius: 18px;
    font-size: 16px;
}}
QPushButton#mic_btn:hover {{ background-color: {accent}; color: white; }}
QPushButton#mic_btn:checked {{ background-color: {accent}; color: white; }}
QPushButton#continue_btn {{
    background-color: {panel};
    color: {accent2};
    border: 1px solid {accent2};
    border-radius: 6px;
    padding: 6px 20px;
    font-size: 12px;
    margin: 4px 16px;
}}
QPushButton#continue_btn:hover {{ background-color: {accent2}; color: white; }}
QTextEdit#md_preview {{
    background-color: {input_bg};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: {fs}px;
}}
#status_bar {{ color: {text_dim}; font-size: 11px; padding: 2px 0; }}
#attach_label {{ color: #c678dd; font-size: 11px; padding: 2px 4px; }}
QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 3px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {text_dim}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QSplitter::handle {{ background-color: {border}; width: 1px; }}
"""


def get_bubble_style(s, role):
    bg      = s.get("bg",            DEFAULT["bg"])
    accent  = s.get("accent",        DEFAULT["accent"])
    accent2 = s.get("accent2",       DEFAULT["accent2"])
    br      = s.get("bubble_radius", DEFAULT["bubble_radius"])
    is_light = _is_light(bg)
    text_bright = "#0d0e16" if is_light else "#dde3f0"
    user_msg    = "#dbeafe" if is_light else "#1e2a3a"
    ai_msg      = "#f0fdf4" if is_light else "#1e1f2e"

    padding = "6px 10px"  if s.get("compact_mode", False) else "10px 14px"
    shadow  = "box-shadow:0 1px 4px rgba(0,0,0,0.20);" if s.get("bubble_shadow", True) else ""

    if role == "user":
        # Пузырёк справа, скруглён как у claude.ai
        style = (
            f"display:block;max-width:72%;margin:4px 0 4px auto;"
            f"padding:{padding};background-color:{user_msg};"
            f"border-radius:{br}px {br}px 4px {br}px;"
            f"{shadow}"
        )
        color = accent2
    else:
        # Пузырёк слева, без фона — как ответ Claude
        style = (
            f"display:block;max-width:82%;margin:4px auto 4px 0;"
            f"padding:{padding};background-color:{ai_msg};"
            f"border-radius:4px {br}px {br}px {br}px;"
            f"{shadow}"
        )
        color = accent

    return style, color, text_bright


class ColorButton(QPushButton):
    color_changed = pyqtSignal(str)

    def __init__(self, color: str, label: str = ""):
        super().__init__(label or color)
        self.color = color
        self._update_style()
        self.clicked.connect(self._pick)

    def _update_style(self):
        text = "#000" if _is_light(self.color) else "#fff"
        self.setStyleSheet(
            f"background-color:{self.color};color:{text};"
            f"border-radius:6px;padding:6px 12px;"
            f"border:1px solid rgba(255,255,255,0.1);font-size:13px;"
        )

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self, "Выберите цвет")
        if c.isValid():
            self.color = c.name()
            self.setText(self.color)
            self._update_style()
            self.color_changed.emit(self.color)


class SettingsWindow(QDialog):
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки — Sylviette AI")
        self.setMinimumWidth(520)
        self.setMinimumHeight(520)
        self.settings = load_settings()
        self._apply_dialog_style()
        self._build()

    def _apply_dialog_style(self):
        bg      = self.settings.get("bg",      DEFAULT["bg"])
        accent2 = self.settings.get("accent2", DEFAULT["accent2"])
        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: #abb2bf; }}
            QTabWidget::pane {{ border:1px solid #2a2b3d; border-radius:6px; background:{bg}; }}
            QTabBar::tab {{ background:#13141f; color:#abb2bf; padding:8px 14px; margin-right:4px; border-radius:4px; }}
            QTabBar::tab:selected {{ background:#2a2b3d; color:#dde3f0; }}
            QLabel {{ color:#abb2bf; }}
            QGroupBox {{ color:#565c7a; border:1px solid #2a2b3d; border-radius:6px;
                         margin-top:8px; padding-top:8px; font-size:11px; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; }}
            QSpinBox {{ background:#252636; color:#dde3f0; border:1px solid #2a2b3d;
                        border-radius:4px; padding:4px 8px; }}
            QComboBox {{ background:#252636; color:#dde3f0; border:1px solid #2a2b3d;
                         border-radius:4px; padding:4px 8px; }}
            QComboBox QAbstractItemView {{ background:#1e1f2e; color:#dde3f0;
                border:1px solid #2a2b3d; selection-background-color:#2a2b3d; }}
            QCheckBox {{ color:#abb2bf; spacing:8px; }}
            QCheckBox::indicator {{ width:16px; height:16px; border-radius:3px;
                border:1px solid #2a2b3d; background:#252636; }}
            QCheckBox::indicator:checked {{ background:{accent2}; border-color:{accent2}; }}
            QSlider::groove:horizontal {{ height:4px; background:#2a2b3d; border-radius:2px; }}
            QSlider::handle:horizontal {{ background:{accent2}; width:14px; height:14px;
                margin:-5px 0; border-radius:7px; }}
            QSlider::sub-page:horizontal {{ background:{accent2}; border-radius:2px; }}
            QFontComboBox {{ background:#252636; color:#dde3f0; border:1px solid #2a2b3d;
                             border-radius:4px; padding:4px 8px; }}
        """)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        tabs = QTabWidget()
        tabs.addTab(self._themes_tab(),  "🎨 Темы")
        tabs.addTab(self._colors_tab(),  "🖌 Цвета")
        tabs.addTab(self._fonts_tab(),   "✏️ Шрифты")
        tabs.addTab(self._avatars_tab(), "👤 Аватарки")
        tabs.addTab(self._effects_tab(), "✨ Эффекты")
        tabs.addTab(self._layout_tab(),  "📐 Размеры")
        layout.addWidget(tabs)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        reset_btn = QPushButton("↺ Сброс")
        apply_btn = QPushButton("▶ Применить")
        save_btn  = QPushButton("💾 Сохранить")
        for btn, style in [
            (reset_btn, "background:#2a2b3d;color:#abb2bf;border:none;border-radius:6px;padding:8px 16px;"),
            (apply_btn, "background:#565c7a;color:white;border:none;border-radius:6px;padding:8px 16px;"),
            (save_btn,  "background:#61afef;color:white;border:none;border-radius:6px;padding:8px 20px;font-weight:bold;"),
        ]:
            btn.setStyleSheet(style)
            btns.addWidget(btn)

        reset_btn.clicked.connect(self._reset)
        apply_btn.clicked.connect(self._apply_only)
        save_btn.clicked.connect(self._save)
        layout.addLayout(btns)

    def _themes_tab(self):
        from ui.theme_presets import THEMES
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(8)
        l.setContentsMargins(12, 12, 12, 12)
        lbl = QLabel("Нажми на тему — она сразу применится:")
        lbl.setStyleSheet("color:#dde3f0;font-size:13px;margin-bottom:4px;")
        l.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        grid  = QVBoxLayout(inner)
        grid.setSpacing(6)

        for name, theme in THEMES.items():
            bg_t = theme["bg"]; sb_t = theme["sidebar"]
            ac_t = theme["accent"]; ac2_t = theme["accent2"]
            tc   = "#1a1b26" if _is_light(bg_t) else "#dde3f0"
            btn  = QPushButton(f"  {name}   ● ●")
            btn.setFixedHeight(48)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {sb_t}, stop:0.3 {bg_t}, stop:1 {bg_t});
                    border: 1px solid rgba(255,255,255,0.05);
                    border-radius: 8px; text-align: left;
                    padding: 0 16px; color: {tc}; font-size: 13px;
                }}
                QPushButton:hover {{ border: 1px solid {ac_t}; }}
            """)
            def apply_theme(checked=False, t=theme):
                for k, v in t.items():
                    self.settings[k] = v
                self._apply_only()
            btn.clicked.connect(apply_theme)
            grid.addWidget(btn)

        grid.addStretch()
        scroll.setWidget(inner)
        l.addWidget(scroll)
        return w

    def _colors_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)
        l.setContentsMargins(12, 12, 12, 12)
        for key, label in [
            ("bg",      "Фон приложения"),
            ("sidebar", "Боковая панель"),
            ("accent",  "Акцент Сильфиетты"),
            ("accent2", "Акцент Создателя / кнопки"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label); lbl.setFixedWidth(240)
            btn = ColorButton(self.settings.get(key, DEFAULT[key]))
            btn.color_changed.connect(lambda c, k=key: self.settings.update({k: c}))
            row.addWidget(lbl); row.addWidget(btn)
            l.addLayout(row)
        l.addStretch()
        return w

    def _fonts_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(14)
        l.setContentsMargins(12, 12, 12, 12)

        grp1 = QGroupBox("Основной шрифт")
        g1   = QVBoxLayout(grp1)
        fc1  = QFontComboBox()
        fc1.setCurrentFont(QFont(self.settings.get("font_family", DEFAULT["font_family"])))
        self._font_preview = QLabel("Привет, Создатель! Сильфиетта готова помочь…")
        self._font_preview.setWordWrap(True)
        self._font_preview.setStyleSheet("color:#dde3f0;padding:8px;background:#252636;border-radius:4px;")
        def on_font(font):
            self.settings["font_family"] = font.family()
            self._font_preview.setFont(QFont(font.family(), self.settings.get("font_size", 14)))
        fc1.currentFontChanged.connect(on_font)
        g1.addWidget(fc1)
        g1.addWidget(QLabel("Предпросмотр:"))
        g1.addWidget(self._font_preview)
        l.addWidget(grp1)

        grp2 = QGroupBox("Шрифт кода (блоки ```)")
        g2   = QVBoxLayout(grp2)
        fc2  = QFontComboBox()
        fc2.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        fc2.setCurrentFont(QFont(self.settings.get("mono_font", DEFAULT["mono_font"])))
        self._mono_preview = QLabel("def sylviette(): return '✦'")
        self._mono_preview.setStyleSheet("color:#abb2bf;padding:8px;background:#1a1f2e;border-radius:4px;")
        def on_mono(font):
            self.settings["mono_font"] = font.family()
            self._mono_preview.setFont(QFont(font.family(), 13))
        fc2.currentFontChanged.connect(on_mono)
        g2.addWidget(fc2)
        g2.addWidget(self._mono_preview)
        l.addWidget(grp2)

        l.addStretch()
        return w

    def _avatars_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(14)
        l.setContentsMargins(12, 12, 12, 12)

        show_cb = QCheckBox("Показывать аватарки в чате")
        show_cb.setChecked(self.settings.get("show_avatars", True))
        show_cb.stateChanged.connect(lambda v: self.settings.update({"show_avatars": bool(v)}))
        l.addWidget(show_cb)

        EMOJI_AI   = ["✦", "🌙", "⭐", "🌸", "🤖", "👾", "🦋", "💫", "🔮", "🌺", "🐱", "🌟"]
        EMOJI_USER = ["👤", "👑", "⚡", "🎮", "🔥", "🐉", "🎯", "💎", "🦊", "🧙", "🌊", "🦁"]

        for group_label, emoji_key, bg_key, emoji_list in [
            ("Аватарка Сильфиетты", "avatar_ai",   "avatar_ai_bg",   EMOJI_AI),
            ("Аватарка Создателя",  "avatar_user",  "avatar_user_bg", EMOJI_USER),
        ]:
            grp = QGroupBox(group_label)
            g   = QVBoxLayout(grp)
            row = QHBoxLayout()

            preview = QLabel(self.settings.get(emoji_key, emoji_list[0]))
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setFixedSize(48, 48)
            cur_bg = self.settings.get(bg_key, DEFAULT[bg_key])
            preview.setStyleSheet(f"background:{cur_bg};border-radius:24px;font-size:22px;")
            row.addWidget(preview)

            combo = QComboBox()
            combo.addItems(emoji_list)
            cur_emoji = self.settings.get(emoji_key, emoji_list[0])
            idx = combo.findText(cur_emoji)
            if idx >= 0: combo.setCurrentIndex(idx)
            def on_emoji(text, k=emoji_key, p=preview):
                self.settings[k] = text
                p.setText(text)
            combo.currentTextChanged.connect(on_emoji)
            row.addWidget(combo)

            color_btn = ColorButton(cur_bg, "Фон")
            def on_bg(c, k=bg_key, p=preview):
                self.settings[k] = c
                p.setStyleSheet(f"background:{c};border-radius:24px;font-size:22px;")
            color_btn.color_changed.connect(on_bg)
            row.addWidget(color_btn)

            g.addLayout(row)
            l.addWidget(grp)

        l.addStretch()
        return w

    def _effects_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)
        l.setContentsMargins(12, 12, 12, 12)

        for key, label in [
            ("bubble_animation", "✨ Анимация появления пузырьков"),
            ("typing_dots",      "💬 Курсор ▌ при стриминге"),
            ("bubble_shadow",    "🌑 Тень у пузырьков"),
            ("compact_mode",     "📦 Компактный режим"),
            ("show_timestamp",   "🕐 Показывать время сообщений"),
        ]:
            cb = QCheckBox(label)
            cb.setChecked(self.settings.get(key, DEFAULT.get(key, False)))
            cb.stateChanged.connect(lambda v, k=key: self.settings.update({k: bool(v)}))
            l.addWidget(cb)

        l.addSpacing(8)
        self._speed_lbl = QLabel(f"Скорость анимации: {self.settings.get('animation_speed', 200)} мс")
        self._speed_lbl.setStyleSheet("color:#dde3f0;")
        l.addWidget(self._speed_lbl)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(80, 600)
        slider.setValue(self.settings.get("animation_speed", 200))
        def on_speed(v):
            self.settings["animation_speed"] = v
            self._speed_lbl.setText(f"Скорость анимации: {v} мс")
        slider.valueChanged.connect(on_speed)
        l.addWidget(slider)
        hint = QLabel("← Быстрее                                   Медленнее →")
        hint.setStyleSheet("color:#565c7a;font-size:11px;")
        l.addWidget(hint)

        l.addStretch()
        return w

    def _layout_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(14)
        l.setContentsMargins(12, 12, 12, 12)
        for label, key, mn, mx in [
            ("Размер шрифта (px)",        "font_size",      10, 22),
            ("Скругление углов (px)",      "bubble_radius",   0, 24),
            ("Ширина боковой панели (px)", "sidebar_width", 180, 420),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:"); lbl.setFixedWidth(230)
            spin = QSpinBox()
            spin.setRange(mn, mx)
            spin.setValue(self.settings.get(key, DEFAULT[key]))
            spin.valueChanged.connect(lambda v, k=key: self.settings.update({k: v}))
            row.addWidget(lbl); row.addWidget(spin)
            l.addLayout(row)
        l.addStretch()
        return w

    def _apply_only(self):
        self.settings_changed.emit(self.settings)

    def _save(self):
        save_settings(self.settings)
        self.settings_changed.emit(self.settings)
        self.accept()

    def _reset(self):
        save_settings(DEFAULT.copy())
        self.settings_changed.emit(DEFAULT.copy())
        self.accept()
