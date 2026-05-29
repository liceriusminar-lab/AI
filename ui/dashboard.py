"""
ui/dashboard.py — дашборд статистики Sylviette AI
"""
import json
import os
from datetime import datetime, timedelta
from collections import Counter

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QWidget, QScrollArea, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False


def _dark_style():
    return {
        "bg":       "#1a1b26",
        "panel":    "#1e1f2e",
        "border":   "#2a2b3d",
        "accent":   "#e06c75",
        "accent2":  "#61afef",
        "purple":   "#c678dd",
        "green":    "#4ade80",
        "text":     "#abb2bf",
        "text_dim": "#565c7a",
    }


class StatCard(QWidget):
    def __init__(self, title, value, subtitle="", color="#61afef"):
        super().__init__()
        c = _dark_style()
        self.setStyleSheet(f"""
            QWidget {{
                background: {c['panel']};
                border: 1px solid {c['border']};
                border-radius: 10px;
            }}
        """)
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 12, 16, 12)
        l.setSpacing(4)

        val_lbl = QLabel(str(value))
        val_lbl.setStyleSheet(f"color:{color};font-size:28px;font-weight:bold;border:none;background:transparent;")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color:{c['text']};font-size:12px;border:none;background:transparent;")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(f"color:{c['text_dim']};font-size:11px;border:none;background:transparent;")

        l.addWidget(val_lbl)
        l.addWidget(title_lbl)
        if subtitle:
            l.addWidget(sub_lbl)


class MplChart(QWidget):
    def __init__(self, fig):
        super().__init__()
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        canvas = FigureCanvas(fig)
        l.addWidget(canvas)


class DashboardWindow(QDialog):
    def __init__(self, chat_manager, parent=None):
        super().__init__(parent)
        self.chat_mgr = chat_manager
        self.setWindowTitle("📊 Дашборд — Sylviette AI")
        self.resize(900, 650)
        c = _dark_style()
        self.setStyleSheet(f"""
            QDialog {{ background:{c['bg']}; color:{c['text']}; }}
            QLabel {{ color:{c['text']}; }}
            QScrollArea {{ border:none; background:transparent; }}
            QPushButton {{
                background:{c['panel']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:6px;
                padding:6px 16px; font-size:12px;
            }}
            QPushButton:hover {{ background:{c['accent2']}; color:white; border-color:{c['accent2']}; }}
        """)
        self._build()

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 16, 20, 16)
        main.setSpacing(16)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel("📊 Дашборд")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#dde3f0;")
        refresh_btn = QPushButton("↺ Обновить")
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh_btn)
        main.addLayout(header)

        # Скролл
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self._inner_layout = QVBoxLayout(inner)
        self._inner_layout.setSpacing(16)
        scroll.setWidget(inner)
        main.addWidget(scroll)

        self._populate()

    def _refresh(self):
        # Чистим и перестраиваем
        while self._inner_layout.count():
            item = self._inner_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._populate()

    def _populate(self):
        c  = _dark_style()
        l  = self._inner_layout
        cm = self.chat_mgr

        # Собираем данные
        all_ids   = cm.get_sorted_ids()
        all_msgs  = []
        daily     = Counter()
        topics    = Counter()
        ai_lens   = []

        for cid in all_ids:
            try:
                msgs = cm.get_messages(cid)
                all_msgs.extend(msgs)
                # Дата чата
                try:
                    dt = datetime.strptime(cid, "%Y%m%d_%H%M%S")
                    day = dt.strftime("%d.%m")
                    daily[day] += len([m for m in msgs if m["role"] == "user"])
                except Exception:
                    pass
                # Топ слов из заголовков
                title = cm.get_title(cid).lower()
                for word in title.split():
                    if len(word) > 3:
                        topics[word] += 1
                # Длина ответов AI
                for m in msgs:
                    if m["role"] == "assistant":
                        text = m["content"] if isinstance(m["content"], str) else ""
                        ai_lens.append(len(text))
            except Exception:
                pass

        user_msgs = [m for m in all_msgs if m["role"] == "user"]
        ai_msgs   = [m for m in all_msgs if m["role"] == "assistant"]
        total_chars = sum(len(m["content"]) if isinstance(m["content"], str) else 0 for m in all_msgs)
        avg_ai_len  = int(sum(ai_lens) / len(ai_lens)) if ai_lens else 0

        # ── Карточки статистики ──────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(12)
        cards = [
            ("Всего чатов",      len(all_ids),       "",                          c["accent2"]),
            ("Сообщений",        len(all_msgs),       f"от вас: {len(user_msgs)}", c["accent"]),
            ("Ответов Сильфиетты", len(ai_msgs),      f"≈{avg_ai_len} симв./ответ", c["purple"]),
            ("Токенов (≈)",      f"{total_chars//4:,}", "всего в истории",          c["green"]),
        ]
        for i, (title, val, sub, color) in enumerate(cards):
            grid.addWidget(StatCard(title, val, sub, color), 0, i)

        grid_w = QWidget()
        grid_w.setStyleSheet("background:transparent;")
        grid_w.setLayout(grid)
        l.addWidget(grid_w)

        if not HAS_MPL:
            lbl = QLabel("matplotlib не установлен — графики недоступны")
            lbl.setStyleSheet(f"color:{c['text_dim']};font-size:12px;")
            l.addWidget(lbl)
            l.addStretch()
            return

        mpl_style = {
            "bg":    "#1e1f2e",
            "text":  "#abb2bf",
            "grid":  "#2a2b3d",
        }

        # ── График активности по дням ────────────────────────────────────
        if daily:
            # Последние 14 дней
            today = datetime.now()
            days_range = [(today - timedelta(days=i)).strftime("%d.%m") for i in range(13, -1, -1)]
            counts = [daily.get(d, 0) for d in days_range]

            fig = Figure(figsize=(8, 2.4), facecolor=mpl_style["bg"])
            ax  = fig.add_subplot(111, facecolor=mpl_style["bg"])
            ax.bar(days_range, counts, color=c["accent2"], alpha=0.8, width=0.6)
            ax.set_title("Активность за 14 дней (сообщений от вас)", color=mpl_style["text"], fontsize=11, pad=8)
            ax.tick_params(colors=mpl_style["text"], labelsize=8)
            ax.set_facecolor(mpl_style["bg"])
            for spine in ax.spines.values():
                spine.set_color(mpl_style["grid"])
            ax.yaxis.grid(True, color=mpl_style["grid"], linewidth=0.5)
            ax.set_axisbelow(True)
            fig.tight_layout()

            sec_title = QLabel("📈 Активность по дням")
            sec_title.setStyleSheet(f"color:#dde3f0;font-size:13px;font-weight:bold;")
            l.addWidget(sec_title)
            l.addWidget(MplChart(fig))

        # ── Топ тем ──────────────────────────────────────────────────────
        if topics:
            stop_words = {"новый", "чат", "это", "как", "что", "для", "мне", "можешь", "сделай"}
            filtered   = {k: v for k, v in topics.items() if k not in stop_words}
            top10      = sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:10]

            if top10:
                words, counts = zip(*top10)
                fig2 = Figure(figsize=(8, 2.4), facecolor=mpl_style["bg"])
                ax2  = fig2.add_subplot(111, facecolor=mpl_style["bg"])
                colors_bar = [c["accent"], c["purple"], c["accent2"], c["green"]] * 3
                ax2.barh(list(words), list(counts), color=colors_bar[:len(words)], alpha=0.85)
                ax2.set_title("Топ тем чатов", color=mpl_style["text"], fontsize=11, pad=8)
                ax2.tick_params(colors=mpl_style["text"], labelsize=9)
                ax2.set_facecolor(mpl_style["bg"])
                for spine in ax2.spines.values():
                    spine.set_color(mpl_style["grid"])
                ax2.xaxis.grid(True, color=mpl_style["grid"], linewidth=0.5)
                ax2.set_axisbelow(True)
                ax2.invert_yaxis()
                fig2.tight_layout()

                sec2 = QLabel("🏷 Топ тем")
                sec2.setStyleSheet("color:#dde3f0;font-size:13px;font-weight:bold;")
                l.addWidget(sec2)
                l.addWidget(MplChart(fig2))

        # ── Соотношение сообщений ────────────────────────────────────────
        if user_msgs and ai_msgs:
            fig3 = Figure(figsize=(3.5, 3.5), facecolor=mpl_style["bg"])
            ax3  = fig3.add_subplot(111, facecolor=mpl_style["bg"])
            ax3.pie(
                [len(user_msgs), len(ai_msgs)],
                labels=["Создатель", "Сильфиетта"],
                colors=[c["accent2"], c["accent"]],
                autopct="%1.0f%%",
                textprops={"color": mpl_style["text"], "fontsize": 10},
                startangle=90,
                wedgeprops={"edgecolor": mpl_style["bg"], "linewidth": 2},
            )
            ax3.set_title("Кто пишет больше", color=mpl_style["text"], fontsize=11, pad=8)
            fig3.tight_layout()

            row = QHBoxLayout()
            pie_w = QWidget()
            pie_w.setStyleSheet("background:transparent;")
            pie_l = QVBoxLayout(pie_w)
            sec3 = QLabel("🥧 Соотношение сообщений")
            sec3.setStyleSheet("color:#dde3f0;font-size:13px;font-weight:bold;")
            pie_l.addWidget(sec3)
            pie_l.addWidget(MplChart(fig3))
            row.addWidget(pie_w)
            row.addStretch()
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_w.setLayout(row)
            l.addWidget(row_w)

        l.addStretch()
