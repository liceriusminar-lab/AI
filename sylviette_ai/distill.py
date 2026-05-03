"""
sylviette_ai/distill.py
────────────────────────
Дистилляция знаний от Qwen2.5-VL (учитель) к Сильфиетте (ученик).

Запуск:
    python -m sylviette_ai.distill --generate   # генерируем данные от учителя
    python -m sylviette_ai.distill --train      # обучаем Сильфиетту на данных
    python -m sylviette_ai.distill --all        # всё сразу
"""

import json
import numpy as np
import requests
import argparse
from pathlib import Path
from tqdm import tqdm


OLLAMA_URL   = "http://localhost:11434/api/chat"
TEACHER_MODEL = "qwen2.5vl:7b"
DISTILL_DIR  = Path("data/distill")
DISTILL_DIR.mkdir(parents=True, exist_ok=True)

# ── Темы для генерации диалогов ───────────────────────────────────────────────

TOPICS = [
    # Общение и личность
    "Представься и расскажи о себе",
    "Что ты умеешь делать?",
    "Как ты можешь мне помочь?",
    "Ты умная?",
    "Тебе нравится помогать людям?",
    "Что ты думаешь о программировании?",
    "Какой твой любимый язык программирования?",

    # Программирование
    "Напиши функцию сортировки пузырьком на Python",
    "Объясни что такое рекурсия",
    "Напиши класс для работы со стеком на Python",
    "Что такое декоратор в Python?",
    "Объясни разницу между list и tuple в Python",
    "Напиши функцию для поиска простых чисел",
    "Что такое генераторы в Python?",
    "Напиши парсер JSON на Python",
    "Объясни что такое ООП",
    "Напиши singleton паттерн на Python",
    "Что такое async/await?",
    "Напиши HTTP сервер на Python",
    "Объясни что такое git rebase",
    "Что такое Docker?",
    "Напиши Dockerfile для Python приложения",
    "Объясни CI/CD",
    "Что такое REST API?",
    "Напиши CRUD операции для SQLite",
    "Объясни индексы в базах данных",
    "Что такое нормализация БД?",

    # Математика и наука
    "Объясни теорему Пифагора",
    "Что такое производная?",
    "Объясни интеграл простыми словами",
    "Что такое матрица?",
    "Объясни метод наименьших квадратов",
    "Что такое вероятность?",
    "Объясни теорему Байеса",

    # Нейросети и ИИ
    "Что такое нейронная сеть?",
    "Объясни градиентный спуск",
    "Что такое backpropagation?",
    "Объясни трансформер архитектуру",
    "Что такое attention механизм?",
    "Объясни что такое overfitting",
    "Что такое regularization?",
    "Объясни разницу между CNN и RNN",
    "Что такое reinforcement learning?",
    "Объясни что такое RAG",
    "Что такое дистилляция знаний?",
    "Объясни квантизацию моделей",

    # Linux и системное
    "Как найти файл в Linux?",
    "Объясни разницу между process и thread",
    "Что такое systemd?",
    "Как настроить cron job?",
    "Объясни chmod и chown",
    "Что такое swap в Linux?",
    "Как мониторить производительность системы?",
    "Объясни как работает DNS",
    "Что такое SSH туннель?",
    "Как настроить firewall в Linux?",

    # История и культура
    "Кто такой Лев Толстой?",
    "Расскажи о Второй мировой войне",
    "Кто такой Никола Тесла?",
    "Расскажи об истории интернета",
    "Кто такой Алан Тьюринг?",
    "Расскажи о Холодной войне",
    "Кто такой Эйнштейн?",

    # Повседневные вопросы
    "Как правильно питаться?",
    "Как улучшить продуктивность?",
    "Как научиться программированию с нуля?",
    "Как работать с большими объёмами данных?",
    "Как защитить свои данные в интернете?",
]

SYSTEM_PROMPT = """Ты — Сильфиетта, личный ИИ-ассистент Создателя.
Говоришь мягко, заботливо, иногда немного застенчиво.
Обращаешься к пользователю ТОЛЬКО «Создатель».
Отвечаешь ТОЛЬКО на русском языке.
Даёшь точные, полезные ответы. В коде максимально точна."""


def ask_teacher(question: str) -> str:
    """Спрашивает учителя (Qwen2.5-VL) и получает ответ."""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model":    TEACHER_MODEL,
            "messages": [
                {"role": "system",  "content": SYSTEM_PROMPT},
                {"role": "user",    "content": question},
            ],
            "stream": False,
        }, timeout=120)

        if resp.status_code == 200:
            return resp.json()["message"]["content"]
        else:
            return ""
    except Exception as e:
        print(f"  ⚠ Ошибка учителя: {e}")
        return ""


def generate_distill_data(n_repeats: int = 3):
    """
    Генерирует обучающие данные от учителя.
    n_repeats — сколько раз задать каждый вопрос (разнообразие ответов).
    """
    out_file = DISTILL_DIR / "teacher_dialogs.jsonl"
    print(f"✦ Генерируем данные от {TEACHER_MODEL}...")
    print(f"  Вопросов: {len(TOPICS)} × {n_repeats} = {len(TOPICS) * n_repeats}")
    print(f"  Сохраняем в: {out_file}\n")

    count = 0
    with open(out_file, "w", encoding="utf-8") as f:
        for repeat in range(n_repeats):
            print(f"  Раунд {repeat + 1}/{n_repeats}")
            for topic in tqdm(TOPICS, desc="  Генерация"):
                answer = ask_teacher(topic)
                if len(answer) > 20:
                    record = {
                        "question": topic,
                        "answer":   answer,
                        "model":    TEACHER_MODEL,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1

    print(f"\n✓ Сгенерировано {count} диалогов → {out_file}")
    return count


def convert_to_bin():
    """Конвертирует JSONL в бинарный формат для обучения."""
    from sylviette_ai.tokenizer import SylvietteTokenizer

    tok      = SylvietteTokenizer()
    in_file  = DISTILL_DIR / "teacher_dialogs.jsonl"
    out_file = DISTILL_DIR / "distill.bin"

    if not in_file.exists():
        print(f"⚠ Файл не найден: {in_file}")
        return

    print(f"✦ Конвертируем в бинарный формат...")
    all_tokens = []

    with open(in_file, encoding="utf-8") as f:
        for line in f:
            try:
                d    = json.loads(line)
                text = f"Вопрос: {d['question']}\nОтвет: {d['answer']}\n\n"
                all_tokens.extend(tok.encode(text))
            except:
                pass

    arr = np.array(all_tokens, dtype=np.uint32)
    arr.tofile(out_file)
    print(f"✓ {len(all_tokens):,} токенов → {out_file} ({out_file.stat().st_size/1e6:.1f} MB)")


def train_on_distill():
    """Запускает обучение Сильфиетты на данных от учителя."""
    import subprocess
    import sys

    bin_file = DISTILL_DIR / "distill.bin"
    if not bin_file.exists():
        print("⚠ Сначала запусти: python -m sylviette_ai.distill --generate")
        return

    print("✦ Запускаем обучение на дистиллированных данных...")
    subprocess.run([
        sys.executable, "-m", "sylviette_ai.train",
        "--mode", "finetune"
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="Генерировать данные от учителя")
    parser.add_argument("--convert",  action="store_true", help="Конвертировать в бинарный формат")
    parser.add_argument("--train",    action="store_true", help="Обучить Сильфиетту")
    parser.add_argument("--all",      action="store_true", help="Всё сразу")
    parser.add_argument("--repeats",  type=int, default=3, help="Повторений каждого вопроса")
    args = parser.parse_args()

    if args.all or args.generate:
        generate_distill_data(args.repeats)

    if args.all or args.convert:
        convert_to_bin()

    if args.all or args.train:
        train_on_distill()

    if not any([args.generate, args.convert, args.train, args.all]):
        print("Использование:")
        print("  python -m sylviette_ai.distill --generate   # генерируем данные")
        print("  python -m sylviette_ai.distill --convert    # конвертируем в .bin")
        print("  python -m sylviette_ai.distill --train      # обучаем")
        print("  python -m sylviette_ai.distill --all        # всё сразу")
        print("  python -m sylviette_ai.distill --all --repeats 5  # 5 повторений")
