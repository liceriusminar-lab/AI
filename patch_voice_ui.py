"""
patch_voice_ui.py — патч ui/main_window.py
Добавляет в сайдбар кнопку паузы/возобновления голосового демона
и индикатор состояния (слушает / пауза / не установлен).

Запуск: python3 patch_voice_ui.py
"""

import re

path = "ui/main_window.py"

with open(path, encoding="utf-8") as f:
    src = f.read()

# ── 1. Импорт ──────────────────────────────────────────────────────────────

import_block = "from voice_daemon import start_voice_daemon, stop_voice_daemon, get_daemon"
if import_block in src:
    print("✓ Импорт уже есть")
else:
    src = src.replace(
        "from encryption import get_encryption_status",
        "from encryption import get_encryption_status\ntry:\n"
        "    from voice_daemon import start_voice_daemon, stop_voice_daemon, get_daemon\n"
        "    _VOICE_AVAILABLE = True\nexcept ImportError:\n"
        "    _VOICE_AVAILABLE = False",
        1
    )
    print("✓ Импорт добавлен")

# ── 2. Кнопка в сайдбар ────────────────────────────────────────────────────

voice_btn_code = '''
        # Голосовая активация
        self._voice_btn = QPushButton("🎙 Голос: слушаю")
        self._voice_btn.setObjectName("delete_btn")
        self._voice_btn.setCheckable(True)
        self._voice_btn.setChecked(True)
        self._voice_btn.clicked.connect(self._toggle_voice)
        if not _VOICE_AVAILABLE:
            self._voice_btn.setText("🎙 Голос: не установлен")
            self._voice_btn.setEnabled(False)
'''

if "_voice_btn" in src:
    print("✓ Кнопка уже добавлена")
else:
    # Вставляем перед files_btn
    src = src.replace(
        '        files_btn = QPushButton("📁 Файлы")',
        voice_btn_code + '\n        files_btn = QPushButton("📁 Файлы")',
        1
    )
    # Добавляем кнопку в layout
    src = src.replace(
        '        for w in [title, self.server_indicator, subtitle, new_btn, self.profile_btn,\n'
        '                  self.search_box, self.chat_list, self.model_selector,\n'
        '                  files_btn, more_btn, self._sysmon]:',
        '        for w in [title, self.server_indicator, subtitle, new_btn, self.profile_btn,\n'
        '                  self.search_box, self.chat_list, self.model_selector,\n'
        '                  self._voice_btn, files_btn, more_btn, self._sysmon]:',
        1
    )
    print("✓ Кнопка добавлена в сайдбар")

# ── 3. Метод _toggle_voice ─────────────────────────────────────────────────

toggle_method = '''
    def _toggle_voice(self, checked):
        """Пауза/возобновление голосового демона."""
        if not _VOICE_AVAILABLE:
            return
        daemon = get_daemon()
        if checked:
            daemon.start()
            self._voice_btn.setText("🎙 Голос: слушаю")
            self.status_label.setText("✦ Голосовая активация включена")
        else:
            daemon.stop()
            self._voice_btn.setText("🎙 Голос: пауза")
            self.status_label.setText("🎙 Голосовая активация на паузе")
        QTimer.singleShot(3000, lambda: self.status_label.setText("Готово ✦"))

'''

if "_toggle_voice" in src:
    print("✓ Метод _toggle_voice уже есть")
else:
    # Вставляем перед _toggle_stt
    src = src.replace(
        "    def _toggle_stt(self, checked):",
        toggle_method + "    def _toggle_stt(self, checked):",
        1
    )
    print("✓ Метод _toggle_voice добавлен")

# ── Сохраняем ──────────────────────────────────────────────────────────────

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

print("\n✓ ui/main_window.py сохранён")
print("  Кнопка «🎙 Голос» появится в сайдбаре при следующем запуске")
