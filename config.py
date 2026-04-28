import os

# ─── Пути ─────────────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_TAGS  = "http://localhost:11434/api/tags"
HISTORY_FILE = os.path.expanduser("~/.ai-assistant/chats.json")
ICON_PATH    = os.path.expanduser("~/.local/share/icons/ai-assistant.png")

os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

# ─── Цвета ────────────────────────────────────────────────────────────────────
COLORS = {
    "bg":          "#1a1b26",
    "sidebar":     "#13141f",
    "panel":       "#1e1f2e",
    "border":      "#2a2b3d",
    "accent":      "#e06c75",
    "accent2":     "#61afef",
    "purple":      "#c678dd",
    "text":        "#abb2bf",
    "text_dim":    "#565c7a",
    "text_bright": "#dde3f0",
    "input_bg":    "#252636",
    "user_msg":    "#1e2a3a",
    "ai_msg":      "#1e1f2e",
}

# ─── Стили ────────────────────────────────────────────────────────────────────
STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: 'Noto Sans', sans-serif;
    font-size: 14px;
}}
#sidebar {{
    background-color: {COLORS['sidebar']};
    border-right: 1px solid {COLORS['border']};
    min-width: 220px;
    max-width: 280px;
}}
#app_title {{
    color: {COLORS['text_bright']};
    font-size: 15px;
    font-weight: bold;
    padding: 18px 16px 4px 16px;
    letter-spacing: 1px;
}}
#app_subtitle {{
    color: {COLORS['text_dim']};
    font-size: 11px;
    padding: 0 16px 14px 16px;
    letter-spacing: 2px;
}}
QPushButton#new_chat_btn {{
    background-color: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: bold;
    margin: 8px 12px;
    text-align: left;
}}
QPushButton#new_chat_btn:hover {{ background-color: #eb7a82; }}
QPushButton#new_chat_btn:pressed {{ background-color: #c85c64; }}
QListWidget#chat_list {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px 8px;
}}
QListWidget#chat_list::item {{
    background-color: transparent;
    color: {COLORS['text']};
    border-radius: 6px;
    padding: 8px 10px;
    margin: 2px 0;
}}
QListWidget#chat_list::item:hover {{
    background-color: {COLORS['panel']};
    color: {COLORS['text_bright']};
}}
QListWidget#chat_list::item:selected {{
    background-color: {COLORS['border']};
    color: {COLORS['text_bright']};
}}
QPushButton#delete_btn {{
    background-color: transparent;
    color: {COLORS['text_dim']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    margin: 4px 12px;
}}
QPushButton#delete_btn:hover {{
    background-color: {COLORS['accent']};
    color: white;
    border-color: {COLORS['accent']};
}}
QPushButton#attach_btn {{
    background-color: transparent;
    color: {COLORS['text_dim']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    font-size: 16px;
    min-width: 46px; max-width: 46px;
    min-height: 46px; max-height: 46px;
}}
QPushButton#attach_btn:hover {{
    background-color: {COLORS['panel']};
    color: {COLORS['text_bright']};
}}
QComboBox#model_selector {{
    background-color: {COLORS['input_bg']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    margin: 4px 12px;
    font-size: 12px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['panel']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['border']};
}}
QTextEdit#chat_display {{
    background-color: transparent;
    color: {COLORS['text']};
    border: none;
    padding: 16px;
    font-size: 14px;
    selection-background-color: {COLORS['border']};
}}
#input_panel {{
    background-color: {COLORS['sidebar']};
    border-top: 1px solid {COLORS['border']};
    padding: 12px 16px;
}}
QTextEdit#input_box {{
    background-color: {COLORS['input_bg']};
    color: {COLORS['text_bright']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
    min-height: 46px;
    max-height: 120px;
}}
QTextEdit#input_box:focus {{ border-color: {COLORS['accent2']}; }}
QPushButton#send_btn {{
    background-color: {COLORS['accent2']};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 70px;
    min-height: 46px;
}}
QPushButton#send_btn:hover {{ background-color: #72bcf5; }}
QPushButton#send_btn:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_dim']};
}}
#status_bar {{
    color: {COLORS['text_dim']};
    font-size: 11px;
    padding: 2px 0;
}}
#attach_label {{
    color: {COLORS['purple']};
    font-size: 11px;
    padding: 2px 4px;
}}
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {COLORS['text_dim']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QSplitter::handle {{ background-color: {COLORS['border']}; width: 1px; }}
"""
