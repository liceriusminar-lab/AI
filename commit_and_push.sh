#!/bin/bash
# commit_and_push.sh — интерактивный коммит с диалогом
cd ~/ai-assistant

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Sylviette AI — коммит в GitHub ✦    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Проверяем git ─────────────────────────────────────────────
if [ ! -d ".git" ]; then
    git init
    git remote add origin https://github.com/liceriusminar-lab/AI.git
fi

REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
if [ -z "$REMOTE" ]; then
    git remote add origin https://github.com/liceriusminar-lab/AI.git
fi

# ── Показываем что изменилось ─────────────────────────────────
echo "📋 Изменённые файлы:"
git status --short
echo ""

# ── Диалог: репозиторий ───────────────────────────────────────
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "https://github.com/liceriusminar-lab/AI.git")
echo "🔗 Текущий репозиторий: $CURRENT_REMOTE"
read -p "   Оставить? [Enter = да / вставь новый URL]: " NEW_REMOTE
if [ -n "$NEW_REMOTE" ]; then
    git remote set-url origin "$NEW_REMOTE"
    echo "   ✓ Репозиторий изменён: $NEW_REMOTE"
fi
echo ""

# ── Диалог: ветка ─────────────────────────────────────────────
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
read -p "🌿 Ветка [$CURRENT_BRANCH]: " BRANCH
BRANCH=${BRANCH:-$CURRENT_BRANCH}
echo ""

# ── Диалог: сообщение коммита ─────────────────────────────────
echo "✏️  Сообщение коммита (Enter = открыть редактор):"
read -p "   > " COMMIT_MSG

if [ -z "$COMMIT_MSG" ]; then
    # Открываем nano для многострочного сообщения
    TMPFILE=$(mktemp /tmp/commit_msg_XXXXXX.txt)
    echo "# Введи сообщение коммита. Строки с # игнорируются." > "$TMPFILE"
    echo "# Сохрани (Ctrl+O) и выйди (Ctrl+X)" >> "$TMPFILE"
    nano "$TMPFILE"
    COMMIT_MSG=$(grep -v "^#" "$TMPFILE" | sed '/^$/d' | head -20 | tr '\n' ' ')
    rm -f "$TMPFILE"
fi

if [ -z "$COMMIT_MSG" ]; then
    echo "⚠ Сообщение пустое — отмена"
    exit 1
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  Репозиторий: $(git remote get-url origin)"
echo "  Ветка:       $BRANCH"
echo "  Коммит:      $COMMIT_MSG"
echo "══════════════════════════════════════════════"
read -p "Всё верно? [Enter = да / n = отмена]: " CONFIRM
if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
    echo "Отменено."
    exit 0
fi

# ── Коммит и пуш ─────────────────────────────────────────────
echo ""
git add -A
git commit -m "$COMMIT_MSG"
git push -u origin "$BRANCH" || {
    echo ""
    echo "⚠ Пуш не удался."
    echo "  Проверь токен: github.com → Settings → Developer settings"
    echo "  → Personal access tokens → repo"
    exit 1
}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          ✦ Готово! Всё на GitHub        ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  $(git remote get-url origin)"
echo ""
