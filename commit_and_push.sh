#!/bin/bash
# commit_and_push.sh — коммитит макросы + README и пушит на GitHub
# Запуск: bash commit_and_push.sh

set -e
cd ~/ai-assistant

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Sylviette AI — коммит в GitHub ✦    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Проверяем что git инициализирован ────────────────────────
if [ ! -d ".git" ]; then
    echo "  Git ещё не инициализирован — инициализирую…"
    git init
    git remote add origin https://github.com/liceriusminar-lab/AI.git
    echo "  ✓ Git инициализирован"
fi

# ── Проверяем remote ─────────────────────────────────────────
REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
if [ -z "$REMOTE" ]; then
    git remote add origin https://github.com/liceriusminar-lab/AI.git
    echo "  ✓ Remote добавлен"
fi

# ── Добавляем файлы в коммит ─────────────────────────────────
echo "[1/4] Добавляем файлы…"

# Новые файлы макросов
git add macros.py          2>/dev/null || echo "  ⚠ macros.py не найден"
git add macros_engine.py   2>/dev/null || echo "  ⚠ macros_engine.py не найден"
git add patch_ollama.sh    2>/dev/null || true

# Пропатченный ollama_worker (если был изменён)
git add ollama_worker.py   2>/dev/null || true

# README
git add README.md          2>/dev/null || echo "  ⚠ README.md не найден"

# Остальные файлы проекта (всё кроме исключений в .gitignore)
git add -A

echo "  ✓ Файлы добавлены"

# ── Показываем что войдёт в коммит ───────────────────────────
echo ""
echo "[2/4] Что будет закоммичено:"
git status --short
echo ""

# ── Коммит ───────────────────────────────────────────────────
echo "[3/4] Создаём коммит…"

COMMIT_MSG="✦ feat: macro system + README

- macros.py: configurable phrase-triggered action macros
  (\"я дома\" → Spotify + Steam account switch + War Thunder)
- macros_engine.py: macro execution engine with Steam account
  switching via loginusers.vdf parsing
- ollama_worker.py: integrated macro detection before LLM call
- README.md: full project documentation (ru)
  covers structure, what to edit, what to avoid, quick start"

git commit -m "$COMMIT_MSG"
echo "  ✓ Коммит создан"

# ── Пуш ──────────────────────────────────────────────────────
echo ""
echo "[4/4] Пушим на GitHub…"
echo "  (может попросить логин/пароль или токен)"
echo ""

# Пробуем main, потом master
BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
if [ -z "$BRANCH" ]; then
    BRANCH="main"
fi

git push -u origin "$BRANCH" || {
    echo ""
    echo "  ⚠ Пуш не удался. Возможные причины:"
    echo "     1. Нужен Personal Access Token вместо пароля"
    echo "        → github.com → Settings → Developer settings"
    echo "          → Personal access tokens → Generate new token"
    echo "          → Права: repo (все)"
    echo ""
    echo "     2. Ветка не совпадает — попробуй вручную:"
    echo "        git push -u origin main"
    echo "        или"
    echo "        git push -u origin master"
    echo ""
    exit 1
}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          ✦ Всё на GitHub!               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Репозиторий: https://github.com/liceriusminar-lab/AI"
echo ""
