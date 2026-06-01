#!/usr/bin/env python3
"""
download_datasets.py — загрузка датасетов для Сильфиетты 8B
Запуск: python3 download_datasets.py
Фоном:  nohup python3 download_datasets.py > logs/download.log 2>&1 &
"""
import os
import sys
from pathlib import Path

# ── Установка зависимостей ────────────────────────────────────
os.system(f"{sys.executable} -m pip install huggingface_hub datasets -q")

from datasets import load_dataset

DATA = Path("data/raw")
DATA.mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(exist_ok=True)

print("=" * 54)
print("   Загрузка датасетов для Сильфиетты 8B")
print("=" * 54)

datasets = [
    # (название,         hf_path,                                  subset,       split,          размер)
    ("ru_language",      "uonlp/CulturaX",                         "ru",         "train",        "~2B tok"),
    ("rp_chat",          "Norquinal/claude_multiround_chat_30k",   None,         "train",        "~200M tok"),
    ("erp",              "cgato/SubtleErotic",                     None,         "train",        "~150M tok"),
    ("coding_python",    "codeparrot/github-code",                 None,         "train[:5%]",   "~1B tok"),
    ("function_call",    "glaiveai/glaive-function-calling-v2",    None,         "train",        "~100M tok"),
    ("logic_math",       "microsoft/orca-math-word-problems-200k", None,         "train",        "~50M tok"),
    ("logic_meta",       "meta-math/MetaMathQA",                   None,         "train",        "~150M tok"),
    ("instructions",     "tatsu-lab/alpaca_cleaned",               None,         "train",        "~50M tok"),
    ("long_context",     "tau/scrolls",                            "gov_report", "train",        "~100M tok"),
    ("emotions",         "facebook/empathetic_dialogues",          None,         "train",        "~20M tok"),
    ("personality",      "proj-persona/PersonaChat",               None,         "train",        "~30M tok"),
    ("ru_instruct",      "IlyaGusev/ru_turbo_alpaca",              None,         "train",        "~30M tok"),
    ("vision_captions",  "laion/220k-GPT4Vision-captions-from-LIVIS", None,     "train",        "~50M tok"),
]

total   = len(datasets)
success = 0
failed  = []

for i, (name, path, subset, split, size) in enumerate(datasets, 1):
    out = DATA / name
    if out.exists():
        print(f"[{i}/{total}] skip  {name} — уже скачан")
        success += 1
        continue

    print(f"[{i}/{total}] down  {name} ({size})...", flush=True)
    try:
        kwargs = {"split": split, "trust_remote_code": True}
        if subset:
            kwargs["name"] = subset
        ds = load_dataset(path, **kwargs, streaming=False)
        ds.save_to_disk(str(out))
        print(f"           ok    {name} -> {out}", flush=True)
        success += 1
    except Exception as e:
        print(f"           fail  {name}: {e}", flush=True)
        failed.append(name)
        continue

# ── Итог ─────────────────────────────────────────────────────
print("")
print(f"Готово: {success}/{total} датасетов скачано")

if failed:
    print(f"Не скачались: {', '.join(failed)}")

total_size = sum(
    f.stat().st_size
    for f in DATA.rglob("*")
    if f.is_file()
)
print(f"Размер на диске: {total_size/1e9:.1f} GB")
print("")
print("Следующий шаг:")
print("  python3 tokenize_datasets.py")
