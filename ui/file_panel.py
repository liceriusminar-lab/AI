import os
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeView, QTextEdit, QLabel,
    QSplitter, QMessageBox, QInputDialog, QMenu
)
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import Qt, pyqtSignal


class FilePanel(QWidget):
    send_to_chat = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Файлы")
        header.setStyleSheet("color:#dde3f0;font-size:13px;font-weight:bold;padding:8px 12px;background:#13141f;border-bottom:1px solid #2a2b3d;")
        layout.addWidget(header)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(6, 6, 6, 6)
        btn_row.setSpacing(4)
        for text, slot in [("Новый", self._new_file), ("Папка", self._new_dir),
                           ("Удалить", self._delete), ("В чат", self._send_to_chat)]:
            btn_row.addWidget(self._btn(text, slot))
        btn_widget = QWidget()
        btn_widget.setStyleSheet("background:#1a1b26;border-bottom:1px solid #2a2b3d;")
        btn_widget.setLayout(btn_row)
        layout.addWidget(btn_widget)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.model = QFileSystemModel()
        self.model.setRootPath(str(Path.home()))
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(Path.home())))
        self.tree.setColumnWidth(0, 200)
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.setStyleSheet("QTreeView{background:#1a1b26;color:#abb2bf;border:none;font-size:12px;}QTreeView::item:hover{background:#1e2a3a;}QTreeView::item:selected{background:#2a2b3d;color:#dde3f0;}")
        self.tree.clicked.connect(self._on_item_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        splitter.addWidget(self.tree)

        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        self.file_label = QLabel("Выберите файл")
        self.file_label.setStyleSheet("color:#565c7a;font-size:11px;padding:4px 8px;background:#13141f;border-bottom:1px solid #2a2b3d;")
        editor_layout.addWidget(self.file_label)

        self.editor = QTextEdit()
        self.editor.setStyleSheet("QTextEdit{background:#1a1b26;color:#abb2bf;border:none;font-family:monospace;font-size:12px;padding:8px;}")
        self.editor.setPlaceholderText("Содержимое файла появится здесь...")
        editor_layout.addWidget(self.editor)

        save_btn = QPushButton("Сохранить файл")
        save_btn.setStyleSheet("QPushButton{background:#2a2b3d;color:#abb2bf;border:none;padding:6px;font-size:12px;}QPushButton:hover{background:#61afef;color:white;}")
        save_btn.clicked.connect(self._save_file)
        editor_layout.addWidget(save_btn)

        splitter.addWidget(editor_widget)
        splitter.setSizes([300, 200])
        layout.addWidget(splitter)

    def _btn(self, text, slot):
        btn = QPushButton(text)
        btn.setStyleSheet("QPushButton{background:#2a2b3d;color:#abb2bf;border:none;border-radius:4px;padding:4px 8px;font-size:11px;}QPushButton:hover{background:#61afef;color:white;}")
        btn.clicked.connect(slot)
        return btn

    def _read_docx(self, path):
        try:
            from docx import Document
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            return "Ошибка docx: " + str(e)

    def _read_pdf(self, path):
        try:
            result = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout:
                return result.stdout
            return "[PDF без текста — установите pdftotext]"
        except Exception as e:
            return "Ошибка pdf: " + str(e)

    def _read_hex(self, path):
        size = os.path.getsize(path)
        lines = []
        lines.append("Бинарный файл: " + os.path.basename(path))
        lines.append("Размер: " + str(round(size / 1024, 1)) + " KB")
        lines.append("")
        lines.append("HEX (первые 4KB):")
        try:
            with open(path, "rb") as f:
                data = f.read(4096)
            for i in range(0, min(len(data), 512), 16):
                chunk = data[i:i+16]
                hex_part = " ".join(format(b, "02x") for b in chunk)
                asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(format(i, "04x") + "  " + hex_part.ljust(48) + "  " + asc_part)
        except Exception as e:
            lines.append("Ошибка: " + str(e))
        return "\n".join(lines)

    def _on_item_clicked(self, index):
        path = self.model.filePath(index)
        if not os.path.isfile(path):
            return
        self.current_file = path
        ext = os.path.splitext(path)[1].lower()
        self.file_label.setText(path)

        if ext == ".docx":
            self.editor.setPlainText(self._read_docx(path))
            return

        if ext == ".pdf":
            self.editor.setPlainText(self._read_pdf(path))
            return

        try:
            with open(path, "r", encoding="utf-8", errors="strict") as f:
                self.editor.setPlainText(f.read())
            return
        except UnicodeDecodeError:
            pass

        try:
            with open(path, "r", encoding="latin-1") as f:
                self.editor.setPlainText(f.read())
            return
        except Exception:
            pass

        self.editor.setPlainText(self._read_hex(path))

    def _save_file(self):
        if not self.current_file:
            return
        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.file_label.setText("Сохранено: " + self.current_file)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def _new_file(self):
        name, ok = QInputDialog.getText(self, "Новый файл", "Имя файла:")
        if not ok or not name:
            return
        idx = self.tree.currentIndex()
        base = self.model.filePath(idx) if idx.isValid() else str(Path.home())
        if os.path.isfile(base):
            base = os.path.dirname(base)
        try:
            open(os.path.join(base, name), "w").close()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def _new_dir(self):
        name, ok = QInputDialog.getText(self, "Новая папка", "Имя папки:")
        if not ok or not name:
            return
        idx = self.tree.currentIndex()
        base = self.model.filePath(idx) if idx.isValid() else str(Path.home())
        if os.path.isfile(base):
            base = os.path.dirname(base)
        try:
            os.makedirs(os.path.join(base, name), exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def _delete(self):
        idx = self.tree.currentIndex()
        if not idx.isValid():
            return
        path = self.model.filePath(idx)
        reply = QMessageBox.question(self, "Удалить?", "Удалить " + path + "?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    import shutil
                    shutil.rmtree(path)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def _send_to_chat(self):
        if not self.current_file:
            return
        self.send_to_chat.emit(os.path.basename(self.current_file), self.editor.toPlainText())

    def _context_menu(self, pos):
        idx = self.tree.indexAt(pos)
        if not idx.isValid():
            return
        path = self.model.filePath(idx)
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#1e1f2e;color:#abb2bf;border:1px solid #2a2b3d;}QMenu::item:selected{background:#2a2b3d;}")
        open_act = menu.addAction("Открыть в Dolphin")
        term_act = menu.addAction("Открыть терминал здесь")
        chat_act = menu.addAction("Отправить в чат")
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == open_act:
            subprocess.Popen(["dolphin", path], start_new_session=True)
        elif action == term_act:
            d = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.Popen(["konsole", "--workdir", d], start_new_session=True)
        elif action == chat_act:
            self._send_to_chat()
