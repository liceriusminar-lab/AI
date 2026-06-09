import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QIcon

from config import COLORS, ICON_PATH
from ui.main_window import MainWindow
import os


def start_backend():
    """Запускает Ollama и inference сервер в фоне."""
    import subprocess, time, os, requests

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Проверяем не запущена ли уже Ollama на 11435
    try:
        requests.get("http://localhost:11435/api/tags", timeout=2)
        print("Ollama уже запущена")
    except Exception:
        # Запускаем Ollama с Qwen на порту 11435
        env = os.environ.copy()
        env["OLLAMA_HOST"] = "127.0.0.1:11435"
        subprocess.Popen(["ollama", "serve"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Ollama запускается...")
        time.sleep(5)

    # Проверяем не запущен ли уже inference сервер
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        print("Inference сервер уже запущен")
    except Exception:
        # Запускаем inference сервер
        checkpoint = os.path.join(base_dir, "checkpoints/sylviette-pretrain/latest.pt")
        env2 = os.environ.copy()
        env2["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        subprocess.Popen(
            [sys.executable, "-m", "sylviette_ai.inference",
             "--checkpoint", checkpoint, "--no-vision"],
            env=env2, cwd=base_dir,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("Inference сервер запускается...")


def start_voice_process():
    import subprocess, sys, os
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_daemon.py")
    if not os.path.exists(script):
        return
    try:
        r = subprocess.run(["pgrep", "-f", "voice_daemon.py"], capture_output=True)
        if r.returncode == 0:
            print("Голосовой демон уже запущен")
            return
    except Exception:
        pass
    proc = subprocess.Popen(
        [sys.executable, script, "--run"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Голосовой демон запущен (pid={proc.pid})")

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
    # Выбор микрофона
    from mic_selector import show_mic_selector
    chosen_mic = show_mic_selector(app)
    if chosen_mic is not None:
        os.environ["SYLVIETTE_MIC_INDEX"] = str(chosen_mic)
    start_voice_process()

    win = MainWindow()
    win.show()
    # Перезагружаем модели через 10 секунд
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(10000, win._load_models)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
