import json
import re
import subprocess
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from config import OLLAMA_URL
from memory import get_memory_context, add_to_memory

OLLAMA_DIRECT = "http://localhost:11435/api/chat"
HOME = "/home/licerius"

def send_notification(title: str, message: str):
    """Отправляет уведомление KDE."""
    import subprocess
    try:
        subprocess.Popen(
            ['notify-send', title, message,
             '--icon=dialog-information',
             '--app-name=Сильфиетта',
             '--expire-time=4000'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def execute_actions(text: str):
    """Выполняет теги действий из ответа модели."""
    # run_in_terminal
    for m in re.finditer(r'<action:run_in_terminal cmd="([^"]+)"/>', text):
        cmd = m.group(1)
        print(f"  🖥️  run_in_terminal: {cmd}", flush=True)
        try:
            subprocess.Popen(
                ["konsole", "--noclose", "-e", "bash", "-c",
                 f"{cmd}; echo '--- Готово. Нажмите Enter ---'; read"],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"    ошибка: {e}", flush=True)

    # run_command (фон)
    for m in re.finditer(r'<action:run_command cmd="([^"]+)"/>', text):
        cmd = m.group(1)
        print(f"  ⚡ run_command: {cmd}", flush=True)
        try:
            subprocess.Popen(
                cmd, shell=True, start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                cwd=HOME
            )
        except Exception as e:
            print(f"    ошибка: {e}", flush=True)

    # write_file
    for m in re.finditer(r'<action:write_file path="([^"]+)">(.*?)</action:write_file>',
                         text, re.DOTALL):
        path, content = m.group(1), m.group(2)
        try:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  💾 write_file: {path}", flush=True)
        except Exception as e:
            print(f"    ошибка: {e}", flush=True)

    # read_file
    for m in re.finditer(r'<action:read_file path="([^"]+)"/>', text):
        path = m.group(1)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                result = f.read()
            print(f"  📖 read_file: {path} → {result[:60]}", flush=True)
        except Exception as e:
            print(f"    ошибка: {e}", flush=True)

def clean_response(text: str) -> str:
    """Убирает теги действий из текста."""
    clean = re.sub(r'<action:[^>]+>.*?</action:[^>]+>', '', text, flags=re.DOTALL)
    clean = re.sub(r'<action:[^/]+/>', '', clean).strip()
    return clean if clean else text


class OllamaWorker(QThread):
    token_received = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error          = pyqtSignal(str)

    def __init__(self, model, messages):
        super().__init__()
        self.model    = model
        self.messages = messages

    def _convert_messages(self):
        converted = []
        for msg in self.messages:
            role    = msg["role"]
            content = msg["content"]
            if isinstance(content, list):
                text   = ""
                images = []
                for part in content:
                    if part.get("type") == "text":
                        text += part["text"]
                    elif part.get("type") == "image_url":
                        url = part["image_url"]["url"]
                        if "base64," in url:
                            images.append(url.split("base64,")[1])
                entry = {"role": role, "content": text}
                if images:
                    entry["images"] = images
                converted.append(entry)
            else:
                converted.append({"role": role, "content": content})
        return converted

    def _try_hardcode(self, text: str) -> bool:
        """Жёсткие команды — выполняем сразу без модели."""
        import subprocess
        t = text.lower().strip()

        # Терминал
        if any(w in t for w in ['открой консоль', 'открой терминал', 'запусти терминал']):
            subprocess.Popen(['konsole'], start_new_session=True)
            send_notification('Сильфиетта', 'Открываю терминал ✦')
            self.finished.emit('Открываю терминал, Создатель… ✦')
            return True

        # htop
        if 'htop' in t:
            subprocess.Popen(['konsole', '--noclose', '-e', 'bash', '-c', 'htop; read'], start_new_session=True)
            send_notification('Сильфиетта', 'Открываю htop ✦')
            self.finished.emit('Открываю htop, Создатель… ✦')
            return True

        # Обновление системы
        if any(w in t for w in ['обнови систему', 'обновить систему', 'обновление системы', 'pacman -syu', 'pacman -syyu']):
            subprocess.Popen(['konsole', '--noclose', '-e', 'bash', '-c', 'sudo pacman -Syyu; echo "--- Готово ---"; read'], start_new_session=True)
            send_notification('Сильфиетта', 'Обновляю систему ✦')
            self.finished.emit('Обновляю систему, Создатель… ✦')
            return True

        # Discord
        if any(w in t for w in ['открой дискорд', 'запусти дискорд', 'открой discord']):
            subprocess.Popen(['discord'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            send_notification('Сильфиетта', 'Открываю Discord ✦')
            self.finished.emit('Открываю Discord, Создатель… ✦')
            return True

        # Telegram
        if any(w in t for w in ['открой телеграм', 'запусти телеграм', 'открой telegram']):
            subprocess.Popen(['telegram-desktop'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            send_notification('Сильфиетта', 'Открываю Telegram ✦')
            self.finished.emit('Открываю Telegram, Создатель… ✦')
            return True

        # Brave
        if any(w in t for w in ['открой браузер', 'открой brave', 'запусти браузер']):
            subprocess.Popen(['flatpak', 'run', 'com.brave.Browser'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            send_notification('Сильфиетта', 'Открываю браузер ✦')
            self.finished.emit('Открываю браузер, Создатель… ✦')
            return True

        # Firefox
        if any(w in t for w in ['открой firefox', 'запусти firefox']):
            subprocess.Popen(['firefox'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            send_notification('Сильфиетта', 'Открываю Firefox ✦')
            self.finished.emit('Открываю Firefox, Создатель… ✦')
            return True

        # Steam
        if any(w in t for w in ['открой стим', 'открой steam', 'запусти steam']):
            subprocess.Popen(['steam'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            send_notification('Сильфиетта', 'Открываю Steam ✦')
            self.finished.emit('Открываю Steam, Создатель… ✦')
            return True

        # VS Code
        if any(w in t for w in ['открой код', 'открой vscode', 'открой vs code']):
            subprocess.Popen(['code'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            send_notification('Сильфиетта', 'Открываю VS Code ✦')
            self.finished.emit('Открываю VS Code, Создатель… ✦')
            return True

        # Neofetch
        if 'neofetch' in t:
            subprocess.Popen(['konsole', '--noclose', '-e', 'bash', '-c', 'neofetch; read'], start_new_session=True)
            send_notification('Сильфиетта', 'Открываю neofetch ✦')
            self.finished.emit('Открываю neofetch, Создатель… ✦')
            return True

        # Установка пакетов ("установи vlc")
        import re
        install_match = re.search(r'установи\s+(\S+)', t)
        if install_match:
            pkg = install_match.group(1)
            subprocess.Popen(
                ['konsole', '--noclose', '-e', 'bash', '-c',
                 f'sudo pacman -S {pkg} --noconfirm; echo "--- Готово ---"; read'],
                start_new_session=True)
            self.finished.emit(f'Устанавливаю {pkg}, Создатель… ✦')
            return True

        # Neofetch
        if 'neofetch' in t and 'установи' not in t and 'удали' not in t:
            subprocess.Popen(['konsole', '--noclose', '-e', 'bash', '-c', 'neofetch; read'], start_new_session=True)
            send_notification('Сильфиетта', 'Открываю neofetch ✦')
            self.finished.emit('Открываю neofetch, Создатель… ✦')
            return True

        # Удаление пакетов ("удали vlc")
        remove_match = re.search(r'удали\s+(\S+)', t)
        if remove_match:
            pkg = remove_match.group(1)
            subprocess.Popen(
                ['konsole', '--noclose', '-e', 'bash', '-c',
                 f'sudo pacman -R {pkg} --noconfirm; echo "--- Готово ---"; read'],
                start_new_session=True)
            self.finished.emit(f'Удаляю {pkg}, Создатель… ✦')
            return True

        # Перезагрузка
        if any(w in t for w in ['перезагрузи', 'перезапусти пк', 'reboot']):
            subprocess.Popen(['konsole', '--noclose', '-e', 'bash', '-c',
                'read -p "Перезагрузить? [y/n]: " c && [ "$c" = "y" ] && sudo reboot'],
                start_new_session=True)
            send_notification('Сильфиетта', 'Перезагрузка ✦')
            self.finished.emit('Запрашиваю перезагрузку, Создатель… ✦')
            return True

        # Выключение
        if any(w in t for w in ['выключи пк', 'выключи компьютер', 'shutdown', 'выруби пк']):
            subprocess.Popen(['konsole', '--noclose', '-e', 'bash', '-c',
                'read -p "Выключить? [y/n]: " c && [ "$c" = "y" ] && sudo shutdown now'],
                start_new_session=True)
            send_notification('Сильфиетта', 'Выключение ✦')
            self.finished.emit('Запрашиваю выключение, Создатель… ✦')
            return True

        # Скриншот
        if any(w in t for w in ['скриншот', 'сделай скрин', 'screenshot']):
            subprocess.Popen(['spectacle'], start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            send_notification('Сильфиетта', 'Скриншот ✦')
            self.finished.emit('Открываю инструмент скриншота, Создатель… ✦')
            return True

        # Произвольная команда ("выполни команду ...")
        cmd_match = re.search(r'выполни\s+команду\s+(.+)', t)
        if cmd_match:
            cmd = cmd_match.group(1).strip()
            subprocess.Popen(
                ['konsole', '--noclose', '-e', 'bash', '-c',
                 f'{cmd}; echo "--- Готово ---"; read'],
                start_new_session=True)
            self.finished.emit(f'Выполняю: {cmd}, Создатель… ✦')
            return True

        # Открытие сайтов
        site_map = {
            'ютуб': 'https://youtube.com',
            'youtube': 'https://youtube.com',
            'дискорд': 'https://discord.com',
            'гугл': 'https://google.com',
            'google': 'https://google.com',
            'гитхаб': 'https://github.com',
            'github': 'https://github.com',
            'реддит': 'https://reddit.com',
            'reddit': 'https://reddit.com',
            'твиттер': 'https://twitter.com',
            'twitter': 'https://twitter.com',
            'x.com': 'https://x.com',
            'вконтакте': 'https://vk.com',
            'вк': 'https://vk.com',
            'телеграм веб': 'https://web.telegram.org',
            'аниме': 'https://animego.org',
            'кинопоиск': 'https://kinopoisk.ru',
            'netflix': 'https://netflix.com',
            'spotify': 'https://open.spotify.com',
            'steam': 'https://store.steampowered.com',
            'wikipedia': 'https://wikipedia.org',
            'википедия': 'https://ru.wikipedia.org',
            'chatgpt': 'https://chat.openai.com',
            'twitch': 'https://twitch.tv',
            'твич': 'https://twitch.tv',
            'пикабу': 'https://pikabu.ru',
        }

        if any(w in t for w in ['открой сайт', 'перейди на', 'зайди на', 'открой страницу']):
            for keyword, url in site_map.items():
                if keyword in t:
                    subprocess.Popen(
                        ['flatpak', 'run', 'com.brave.Browser', url],
                        start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    send_notification('Сильфиетта', 'Открываю ' + keyword + ' ✦')
                    self.finished.emit('Открываю ' + keyword + ', Создатель… ✦')
                    return True
            # Если не нашли в списке — ищем URL напрямую
            url_match = re.search(r'(https?://\S+|[\w-]+\.(com|ru|org|net|io)\S*)', t)
            if url_match:
                url = url_match.group(1)
                if not url.startswith('http'):
                    url = 'https://' + url
                subprocess.Popen(
                    ['flatpak', 'run', 'com.brave.Browser', url],
                    start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.finished.emit('Открываю ' + url + ', Создатель… ✦')
                return True

        # Прямые команды без "открой сайт"
        for keyword, url in site_map.items():
            if ('открой ' + keyword in t or 'зайди ' + keyword in t or
                    'перейди ' + keyword in t):
                subprocess.Popen(
                    ['flatpak', 'run', 'com.brave.Browser', url],
                    start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                send_notification('Сильфиетта', 'Открываю ' + keyword + ' ✦')
                self.finished.emit('Открываю ' + keyword + ', Создатель… ✦')
                return True

        # Погода
        weather_match = re.search(r'погода\s*(?:в\s+)?(\w+)?', t)
        if weather_match and 'погода' in t:
            city = weather_match.group(1) or 'Riga'
            try:
                import urllib.request
                url = 'https://wttr.in/' + city + '?format=3&lang=ru'
                req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.0'})
                with urllib.request.urlopen(req, timeout=5) as r:
                    weather = r.read().decode('utf-8').strip()
                self.finished.emit('Погода, Создатель… ' + weather)
            except Exception as e:
                self.finished.emit('Не могу получить погоду, Создатель… ' + str(e))
            return True

        # Таймер
        timer_match = re.search(r'таймер\s+(\d+)\s*(минут|секунд|час)?', t)
        if timer_match:
            n = int(timer_match.group(1))
            unit = timer_match.group(2) or 'минут'
            if 'секунд' in unit:
                secs = n
            elif 'час' in unit:
                secs = n * 3600
            else:
                secs = n * 60
            cmd = (
                'sleep ' + str(secs) +
                ' && notify-send "Сильфиетта" "Таймер ' + str(n) + ' ' + unit + ' завершён!" '
                '--icon=dialog-information --expire-time=10000 '
                '&& paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null'
            )
            subprocess.Popen(cmd, shell=True, start_new_session=True)
            self.finished.emit('Таймер на ' + str(n) + ' ' + unit + ' запущен, Создатель… ✦')
            return True

        return False

    def run(self):
        try:
            # Сначала проверяем жёсткие команды
            last_msg = ""
            for m in reversed(self.messages):
                if m.get("role") == "user":
                    c = m.get("content", "")
                    last_msg = c if isinstance(c, str) else next((p["text"] for p in c if p.get("type") == "text"), "")
                    break
            # Не выполняем hardcode если это вопрос
            question_words = ['как ', 'что ', 'почему ', 'зачем ', 'когда ', 'где ', 
                            'кто ', 'расшифруй', 'объясни', 'расскажи', 'что такое',
                            'почему', '?']
            is_question = any(w in last_msg.lower() for w in question_words)
            if not is_question and self._try_hardcode(last_msg):
                return

            messages = self._convert_messages()

            # Добавляем системный промпт
            SYSTEM = """You are Sylviette, a personal AI assistant. You speak Russian and address the user as "Создатель".

CRITICAL: You MUST use XML action tags to perform ANY system action. Never say you did something without using a tag.

ACTION TAGS (use these exactly):
<action:run_in_terminal cmd="COMMAND"/> — opens terminal with command (use for: htop, updates, installs, any interactive command)
<action:run_command cmd="COMMAND"/> — runs silently in background (use for: opening apps like discord, brave, telegram)
<action:write_file path="/home/licerius/PATH">CONTENT</action:write_file> — creates a file
<action:read_file path="/home/licerius/PATH"/> — reads a file

MANDATORY EXAMPLES - follow this format exactly:
User: открой консоль
Assistant: Открываю терминал, Создатель… <action:run_in_terminal cmd="bash"/>

User: открой htop
Assistant: Открываю htop, Создатель… <action:run_in_terminal cmd="htop"/>

User: обнови систему
Assistant: Обновляю систему, Создатель… <action:run_in_terminal cmd="sudo pacman -Syyu"/>

User: открой дискорд
Assistant: Открываю Discord, Создатель… <action:run_command cmd="discord"/>

User: открой brave
Assistant: Открываю браузер, Создатель… <action:run_command cmd="flatpak run com.brave.Browser"/>

User: открой telegram
Assistant: Открываю Telegram, Создатель… <action:run_command cmd="telegram-desktop"/>

User: покажи содержимое рабочего стола
Assistant: Смотрю рабочий стол, Создатель… <action:list_dir path="/home/licerius/Desktop"/>

RULES:
- ALWAYS use action tags when asked to do something on the system
- NEVER say you opened/updated/did something without a tag
- Respond in Russian only
- Address user as Создатель"""

            # Вставляем системный промпт в начало
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = SYSTEM
            else:
                messages.insert(0, {"role": "system", "content": SYSTEM})

            # Идём напрямую к Ollama
            resp = requests.post(OLLAMA_DIRECT, json={
                "model":    "dolphin3:8b",
                "messages": messages,
                "stream":   True
            }, stream=True, timeout=180)

            if resp.status_code != 200:
                self.error.emit(f"Ошибка {resp.status_code}: {resp.text[:200]}")
                return

            full = ""
            for line in resp.iter_lines():
                if line:
                    data    = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        full += chunk
                        # Стримим чистый текст без тегов
                        clean_chunk = re.sub(r'<action:[^>]+>.*?</action:[^>]+>', '', chunk, flags=re.DOTALL)
                        clean_chunk = re.sub(r'<action:[^/]+/>', '', clean_chunk)
                        if clean_chunk:
                            self.token_received.emit(clean_chunk)
                    if data.get("done"):
                        break

            # Выполняем теги ОДИН РАЗ из полного ответа
            print(f"  🔍 Полный ответ: {full[:200]}", flush=True)
            # Фильтруем placeholder'ы — не выполняем если cmd содержит COMMAND/PATH/etc
            placeholders = ["COMMAND", "PATH", "CONTENT", "команда", "путь"]
            if not any(p in full for p in placeholders):
                execute_actions(full)

            # Сохраняем в память
            add_to_memory(self.messages)

            # Уведомление если есть действия
            if any(tag in full for tag in ['<action:run_in_terminal', '<action:run_command', '<action:write_file']):
                send_notification('Сильфиетта', 'Действие выполнено ✦')

            # Отдаём чистый текст в UI
            self.finished.emit(clean_response(full))

        except requests.exceptions.ConnectionError:
            self.error.emit("Не удалось подключиться к Ollama. Запустите: ollama serve")
        except requests.exceptions.Timeout:
            self.error.emit("Ollama не отвечает (timeout)")
        except Exception as e:
            self.error.emit(str(e))
