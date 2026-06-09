"""
mic_selector.py — выбор микрофона при старте Сильфиетты
"""
import json
from pathlib import Path
import pyaudio
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QCheckBox
)
from PyQt6.QtCore import Qt

SETTINGS_FILE = Path.home() / ".ai-assistant" / "mic_settings.json"


def get_devices():
    pa    = pyaudio.PyAudio()
    count = pa.get_device_count()
    devs  = []
    for i in range(count):
        try:
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] < 1:
                continue
            name = info["name"]
            # Скрываем мусорные ALSA устройства
            if any(x in name.lower() for x in ["rear","center_lfe","side",
                                                "hdmi","spdif","iec958"]):
                continue
            devs.append({"index": i, "name": name,
                         "channels": int(info["maxInputChannels"])})
        except Exception:
            continue
    pa.terminate()
    return devs


def load_saved() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return {}


def save_choice(index: int, name: str, skip: bool):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(
        {"index": index, "name": name, "skip": skip}, ensure_ascii=False
    ))


def get_mic_index() -> int | None:
    """Возвращает сохранённый индекс микрофона или None."""
    saved = load_saved()
    if saved.get("skip"):
        return saved.get("index")
    return None


class MicSelectorDialog(QDialog):
    def __init__(self, devices, saved):
        super().__init__()
        self.setWindowTitle("✦ Сильфиетта — выбор микрофона")
        self.setMinimumWidth(480)
        self.setMinimumHeight(340)
        self.chosen_index = saved.get("index")
        self.setStyleSheet("""
            QDialog { background:#1a1b26; color:#abb2bf; font-size:13px; }
            QLabel  { color:#dde3f0; }
            QListWidget {
                background:#1e1f2e; color:#abb2bf;
                border:1px solid #2a2b3d; border-radius:8px;
                padding:4px;
            }
            QListWidget::item { padding:10px 12px; border-radius:4px; }
            QListWidget::item:hover    { background:#2a2b3d; color:#dde3f0; }
            QListWidget::item:selected { background:#61afef; color:#1a1b26; font-weight:bold; }
            QPushButton {
                background:#61afef; color:#1a1b26; border:none;
                border-radius:8px; padding:10px 24px; font-size:13px; font-weight:bold;
            }
            QPushButton:hover   { background:#72bcf5; }
            QPushButton#skip_btn {
                background:#2a2b3d; color:#abb2bf;
            }
            QPushButton#skip_btn:hover { background:#3a3b4d; }
            QCheckBox { color:#565c7a; font-size:11px; spacing:8px; }
            QCheckBox::indicator {
                width:14px; height:14px; border-radius:3px;
                border:1px solid #2a2b3d; background:#252636;
            }
            QCheckBox::indicator:checked { background:#61afef; border-color:#61afef; }
        """)

        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(14)

        title = QLabel("✦ Выбери микрофон")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#e06c75;")
        l.addWidget(title)

        hint = QLabel("Сильфиетта будет слушать тебя через выбранное устройство.")
        hint.setStyleSheet("color:#565c7a; font-size:11px;")
        l.addWidget(hint)

        self.lst = QListWidget()
        saved_idx = saved.get("index")
        for d in devices:
            label = d["name"]
            if "pipewire" in label.lower():
                label = "🔊 PipeWire (рекомендуется)"
            elif "pulse" in label.lower():
                label = "🔈 PulseAudio"
            else:
                label = f"🎙 {label}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, d["index"])
            self.lst.addItem(item)
            if d["index"] == saved_idx:
                self.lst.setCurrentItem(item)

        if self.lst.currentItem() is None and self.lst.count() > 0:
            self.lst.setCurrentRow(0)

        self.lst.itemClicked.connect(self._on_select)
        l.addWidget(self.lst)

        self.remember_cb = QCheckBox("Запомнить выбор и не спрашивать при следующем запуске")
        self.remember_cb.setChecked(saved.get("skip", False))
        l.addWidget(self.remember_cb)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        skip_btn = QPushButton("Пропустить")
        skip_btn.setObjectName("skip_btn")
        ok_btn   = QPushButton("✓ Выбрать")
        skip_btn.clicked.connect(self._skip)
        ok_btn.clicked.connect(self._ok)
        btns.addWidget(skip_btn)
        btns.addStretch()
        btns.addWidget(ok_btn)
        l.addLayout(btns)

    def _on_select(self, item):
        self.chosen_index = item.data(Qt.ItemDataRole.UserRole)

    def _ok(self):
        item = self.lst.currentItem()
        if item:
            self.chosen_index = item.data(Qt.ItemDataRole.UserRole)
            save_choice(self.chosen_index, item.text(), self.remember_cb.isChecked())
        self.accept()

    def _skip(self):
        self.chosen_index = None
        self.accept()


def show_mic_selector(app) -> int | None:
    """
    Показывает диалог выбора микрофона.
    Если пользователь выбрал "запомнить" — не показывает снова.
    Возвращает выбранный индекс или None.
    """
    saved = load_saved()

    # Если пользователь сохранил выбор — пропускаем диалог
    if saved.get("skip") and "index" in saved:
        return saved["index"]

    devices = get_devices()
    if not devices:
        return None

    dlg = MicSelectorDialog(devices, saved)
    dlg.exec()
    return dlg.chosen_index
