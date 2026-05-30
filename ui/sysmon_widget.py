"""
ui/sysmon_widget.py — виджет мониторинга системы
"""
import psutil
import subprocess
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor


def _bar_style(color: str) -> str:
    return f"""
        QProgressBar {{
            background:#1e1f2e; border:none; border-radius:4px; height:6px;
        }}
        QProgressBar::chunk {{
            background:{color}; border-radius:4px;
        }}
    """


class SysMonWidget(QWidget):
    """Компактный виджет мониторинга — вставляется в сайдбар."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sysmon_widget")
        self._build()
        self._timer = QTimer()
        self._timer.timeout.connect(self._update)
        self._timer.start(2000)
        self._update()

    def _build(self):
        l = QVBoxLayout(self)
        l.setContentsMargins(12, 6, 12, 6)
        l.setSpacing(4)

        title = QLabel("⚙ Система")
        title.setStyleSheet("color:#565c7a;font-size:10px;letter-spacing:1px;")
        l.addWidget(title)

        # CPU
        cpu_row = QHBoxLayout()
        self._cpu_lbl = QLabel("CPU")
        self._cpu_lbl.setStyleSheet("color:#abb2bf;font-size:11px;min-width:36px;")
        self._cpu_val = QLabel("0%")
        self._cpu_val.setStyleSheet("color:#61afef;font-size:11px;min-width:32px;text-align:right;")
        self._cpu_bar = QProgressBar()
        self._cpu_bar.setRange(0, 100)
        self._cpu_bar.setTextVisible(False)
        self._cpu_bar.setFixedHeight(6)
        self._cpu_bar.setStyleSheet(_bar_style("#61afef"))
        cpu_row.addWidget(self._cpu_lbl)
        cpu_row.addWidget(self._cpu_bar)
        cpu_row.addWidget(self._cpu_val)
        l.addLayout(cpu_row)

        # RAM
        ram_row = QHBoxLayout()
        self._ram_lbl = QLabel("RAM")
        self._ram_lbl.setStyleSheet("color:#abb2bf;font-size:11px;min-width:36px;")
        self._ram_val = QLabel("0%")
        self._ram_val.setStyleSheet("color:#c678dd;font-size:11px;min-width:32px;")
        self._ram_bar = QProgressBar()
        self._ram_bar.setRange(0, 100)
        self._ram_bar.setTextVisible(False)
        self._ram_bar.setFixedHeight(6)
        self._ram_bar.setStyleSheet(_bar_style("#c678dd"))
        ram_row.addWidget(self._ram_lbl)
        ram_row.addWidget(self._ram_bar)
        ram_row.addWidget(self._ram_val)
        l.addLayout(ram_row)

        # GPU (если есть nvidia-smi)
        self._gpu_row = QHBoxLayout()
        self._gpu_lbl = QLabel("GPU")
        self._gpu_lbl.setStyleSheet("color:#abb2bf;font-size:11px;min-width:36px;")
        self._gpu_val = QLabel("—")
        self._gpu_val.setStyleSheet("color:#4ade80;font-size:11px;min-width:32px;")
        self._gpu_bar = QProgressBar()
        self._gpu_bar.setRange(0, 100)
        self._gpu_bar.setTextVisible(False)
        self._gpu_bar.setFixedHeight(6)
        self._gpu_bar.setStyleSheet(_bar_style("#4ade80"))
        self._gpu_row.addWidget(self._gpu_lbl)
        self._gpu_row.addWidget(self._gpu_bar)
        self._gpu_row.addWidget(self._gpu_val)
        l.addLayout(self._gpu_row)

        # Temp + Disk
        info_row = QHBoxLayout()
        self._temp_lbl = QLabel("🌡 —°C")
        self._temp_lbl.setStyleSheet("color:#f97316;font-size:10px;")
        self._disk_lbl = QLabel("💾 —%")
        self._disk_lbl.setStyleSheet("color:#565c7a;font-size:10px;")
        info_row.addWidget(self._temp_lbl)
        info_row.addStretch()
        info_row.addWidget(self._disk_lbl)
        l.addLayout(info_row)

    def _update(self):
        # CPU
        cpu = psutil.cpu_percent(interval=None)
        self._cpu_bar.setValue(int(cpu))
        self._cpu_val.setText(f"{cpu:.0f}%")
        color = "#e06c75" if cpu > 80 else "#f97316" if cpu > 60 else "#61afef"
        self._cpu_val.setStyleSheet(f"color:{color};font-size:11px;min-width:32px;")

        # RAM
        ram = psutil.virtual_memory()
        ram_pct = ram.percent
        self._ram_bar.setValue(int(ram_pct))
        ram_gb = ram.used / 1e9
        self._ram_val.setText(f"{ram_gb:.1f}G")
        color = "#e06c75" if ram_pct > 85 else "#f97316" if ram_pct > 70 else "#c678dd"
        self._ram_val.setStyleSheet(f"color:{color};font-size:11px;min-width:32px;")

        # GPU
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 4:
                    gpu_pct  = int(parts[0])
                    mem_used = int(parts[1])
                    mem_tot  = int(parts[2])
                    gpu_temp = int(parts[3])
                    self._gpu_bar.setValue(gpu_pct)
                    self._gpu_val.setText(f"{mem_used}M")
                    color = "#e06c75" if gpu_pct > 90 else "#f97316" if gpu_pct > 70 else "#4ade80"
                    self._gpu_val.setStyleSheet(f"color:{color};font-size:11px;min-width:32px;")
                    self._temp_lbl.setText(f"🌡 {gpu_temp}°C")
                    tc = "#e06c75" if gpu_temp > 85 else "#f97316" if gpu_temp > 75 else "#f97316"
                    self._temp_lbl.setStyleSheet(f"color:{tc};font-size:10px;")
        except Exception:
            self._gpu_val.setText("—")

        # Disk
        try:
            disk = psutil.disk_usage("/")
            self._disk_lbl.setText(f"💾 {disk.percent:.0f}%")
        except Exception:
            pass

        # CPU temp (если нет GPU)
        try:
            temps = psutil.sensors_temperatures()
            for key in ["coretemp", "k10temp", "cpu_thermal"]:
                if key in temps and temps[key]:
                    t = temps[key][0].current
                    self._temp_lbl.setText(f"🌡 {t:.0f}°C")
                    break
        except Exception:
            pass
