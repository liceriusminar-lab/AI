"""
plugin_manager.py — менеджер плагинов Сильфиетты
Плагин = папка в ~/ai-assistant/plugins/ с файлами:
  plugin.json  — метаданные
  main.py      — код (функция run(query, context) -> str)

Поля plugin.json:
  name        — название
  description — описание
  version     — версия
  enabled     — включён ли
  triggers    — список триггерных фраз
  requires    — список pip пакетов (устанавливаются автоматически)
"""
import json
import importlib.util
import subprocess
import sys
from pathlib import Path

PLUGINS_DIR = Path(__file__).parent / "plugins"


def _load_meta(plugin_dir: Path) -> dict:
    meta_file = plugin_dir / "plugin.json"
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ensure_requirements(requires: list):
    """Устанавливает недостающие зависимости плагина."""
    if not requires:
        return
    pkg_map = {
        "beautifulsoup4": "bs4",
        "youtube-transcript-api": "youtube_transcript_api",
        "markdownify": "markdownify",
        "icalendar": "icalendar",
        "requests": "requests",
    }
    for pkg in requires:
        import_name = pkg_map.get(pkg, pkg.replace("-", "_"))
        try:
            __import__(import_name)
        except ImportError:
            print(f"  📦 Плагин: устанавливаю {pkg}…", flush=True)
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg,
                     "--break-system-packages", "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"  ✓ {pkg} установлен", flush=True)
            except Exception as e:
                print(f"  ⚠ Не удалось установить {pkg}: {e}", flush=True)


def list_plugins() -> list:
    """Возвращает список всех плагинов."""
    plugins = []
    if not PLUGINS_DIR.exists():
        return plugins
    for d in sorted(PLUGINS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        meta = _load_meta(d)
        if not meta:
            continue
        plugins.append({
            "id":          d.name,
            "name":        meta.get("name", d.name),
            "description": meta.get("description", ""),
            "version":     meta.get("version", "1.0"),
            "enabled":     meta.get("enabled", True),
            "triggers":    meta.get("triggers", []),
            "requires":    meta.get("requires", []),
            "path":        str(d),
        })
    return plugins


def load_plugin(plugin_id: str):
    """Загружает модуль плагина (с установкой зависимостей)."""
    plugin_dir = PLUGINS_DIR / plugin_id
    main_file  = plugin_dir / "main.py"
    if not main_file.exists():
        return None

    # Устанавливаем зависимости если нужно
    meta = _load_meta(plugin_dir)
    _ensure_requirements(meta.get("requires", []))

    spec   = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", main_file)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"Plugin {plugin_id} error: {e}")
        return None


def run_plugin(plugin_id: str, query: str, context: dict = None) -> str:
    """Запускает плагин и возвращает результат."""
    module = load_plugin(plugin_id)
    if not module or not hasattr(module, "run"):
        return f"[Плагин {plugin_id} не найден или не имеет функции run]"
    try:
        return module.run(query, context or {})
    except Exception as e:
        return f"[Ошибка плагина {plugin_id}: {e}]"


def find_plugin_for_query(query: str) -> str | None:
    """Находит плагин по триггерам в запросе."""
    q = query.lower()
    for p in list_plugins():
        if not p["enabled"]:
            continue
        for trigger in p["triggers"]:
            if trigger.lower() in q:
                return p["id"]
    return None


def toggle_plugin(plugin_id: str, enabled: bool):
    """Включает/выключает плагин."""
    meta_file = PLUGINS_DIR / plugin_id / "plugin.json"
    if not meta_file.exists():
        return
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["enabled"] = enabled
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
