import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QIcon

from config import COLORS, ICON_PATH
from ui.main_window import MainWindow
import os


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    # Тёмная палитра
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,     QColor(COLORS['bg']))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(COLORS['text']))
    pal.setColor(QPalette.ColorRole.Base,       QColor(COLORS['input_bg']))
    pal.setColor(QPalette.ColorRole.Text,       QColor(COLORS['text_bright']))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
