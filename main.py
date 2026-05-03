import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QIcon

from config import COLORS, ICON_PATH
from ui.main_window import MainWindow
import os


def start_backend():
    """Запускает Ollama и inference сервер в фоне."""
    import subprocess, time, os
    
    # Запускаем Ollama с Qwen
    env = os.environ.copy()
    env["OLLAMA_HOST"] = "127.0.0.1:11435"
    subprocess.Popen(["ollama", "serve"], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    
    # Запускаем inference сервер
    venv_python = os.path.join(os.path.dirname(sys.executable), "python")
    checkpoint = os.path.expanduser("~/.local/share/sylviette/pretrain/latest.pt")
    if not os.path.exists(checkpoint):
        checkpoint = os.path.join(os.path.dirname(__file__), 
                                  "checkpoints/sylviette-pretrain/latest.pt")
    env2 = os.environ.copy()
    env2["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    subprocess.Popen(
        [sys.executable, "-m", "sylviette_ai.inference",
         "--checkpoint", checkpoint, "--no-vision"],
        env=env2, cwd=os.path.dirname(__file__),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

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

    start_backend()
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
