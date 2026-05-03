import re
from config import COLORS


def convert(text: str) -> str:
    """Конвертирует Markdown текст в HTML для отображения в QTextEdit."""

    # Экранируем HTML символы (кроме того что уже добавим сами)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ── Блоки кода ```язык\\n...``` ───────────────────────────────────────────
    def code_block(m):
        lang = m.group(1) or ""
        code = m.group(2)
        return (
            f'<div style="background:#1a1f2e;border:1px solid #2a2b3d;'
            f'border-radius:6px;padding:12px;margin:8px 0;'
            f'font-family:monospace;font-size:13px;color:#abb2bf;white-space:pre-wrap;">'
            f'<span style="color:{COLORS["text_dim"]};font-size:11px;">{lang}</span><br>'
            f'{code}</div>'
        )
    text = re.sub(r'```(\w*)\n?(.*?)```', code_block, text, flags=re.DOTALL)

    # ── Inline код `...` ──────────────────────────────────────────────────────
    text = re.sub(
        r'`([^`]+)`',
        lambda m: (
            f'<code style="background:#252636;padding:2px 6px;border-radius:4px;'
            f'font-family:monospace;color:{COLORS["accent2"]};font-size:13px;">'
            f'{m.group(1)}</code>'
        ),
        text
    )

    # ── Жирный **текст** ──────────────────────────────────────────────────────
    text = re.sub(
        r'\*\*(.+?)\*\*',
        lambda m: f'<b style="color:{COLORS["text_bright"]};">{m.group(1)}</b>',
        text
    )

    # ── Курсив *текст* ────────────────────────────────────────────────────────
    text = re.sub(r'\*(.+?)\*', lambda m: f'<i>{m.group(1)}</i>', text)

    # ── Заголовки ### ## # ────────────────────────────────────────────────────
    text = re.sub(
        r'^### (.+)$',
        lambda m: f'<h3 style="color:{COLORS["accent2"]};margin:8px 0 4px 0;">{m.group(1)}</h3>',
        text, flags=re.MULTILINE
    )
    text = re.sub(
        r'^## (.+)$',
        lambda m: f'<h2 style="color:{COLORS["accent2"]};margin:10px 0 4px 0;">{m.group(1)}</h2>',
        text, flags=re.MULTILINE
    )
    text = re.sub(
        r'^# (.+)$',
        lambda m: f'<h1 style="color:{COLORS["accent"]};margin:12px 0 6px 0;">{m.group(1)}</h1>',
        text, flags=re.MULTILINE
    )

    # ── Списки - пункт ────────────────────────────────────────────────────────
    text = re.sub(
        r'^- (.+)$',
        lambda m: f'<div style="padding:2px 0 2px 16px;">• {m.group(1)}</div>',
        text, flags=re.MULTILINE
    )

    # ── Нумерованные списки 1. пункт ─────────────────────────────────────────
    text = re.sub(
        r'^\d+\. (.+)$',
        lambda m: f'<div style="padding:2px 0 2px 16px;">{m.group(0)}</div>',
        text, flags=re.MULTILINE
    )

    # ── Переносы строк ────────────────────────────────────────────────────────
    text = text.replace('\n', '<br>')

    return text
