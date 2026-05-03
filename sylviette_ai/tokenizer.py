"""
my_ai/model/tokenizer.py
────────────────────────
BPE токенизатор на базе tiktoken (как в GPT-4).
Добавлены специальные токены для Сильфиетты.
"""

import tiktoken
from typing import List, Union


# Специальные токены модели
SPECIAL_TOKENS = {
    "<|system|>":    "<|system|>",
    "<|user|>":      "<|user|>",
    "<|assistant|>": "<|assistant|>",
    "<|image|>":     "<|image|>",     # для vision
    "<|end|>":       "<|end|>",
    "<|pad|>":       "<|pad|>",
}


class SylvietteTokenizer:
    """
    Токенизатор для SylvietteGPT.
    Использует cl100k_base (GPT-4 токенизация) + наши спец-токены.
    """

    def __init__(self):
        self._enc = tiktoken.get_encoding("cl100k_base")
        self._special = list(SPECIAL_TOKENS.values())

        # Переопределяем с доп. токенами
        self.enc = tiktoken.Encoding(
            name="sylviette",
            pat_str=self._enc._pat_str,
            mergeable_ranks=self._enc._mergeable_ranks,
            special_tokens={
                **self._enc._special_tokens,
                **{tok: self._enc.n_vocab + i for i, tok in enumerate(self._special)}
            }
        )

        self.vocab_size  = self.enc.n_vocab + len(self._special)
        self.pad_id      = self.enc.encode_single_token("<|pad|>")
        self.end_id      = self.enc.encode_single_token("<|end|>")
        self.system_id   = self.enc.encode_single_token("<|system|>")
        self.user_id     = self.enc.encode_single_token("<|user|>")
        self.assistant_id = self.enc.encode_single_token("<|assistant|>")
        self.image_id    = self.enc.encode_single_token("<|image|>")

    def encode(self, text: str, add_special: bool = False) -> List[int]:
        """Кодирует текст в список токенов."""
        allowed = set(self._special)
        return self.enc.encode(text, allowed_special=allowed)

    def decode(self, tokens: List[int]) -> str:
        """Декодирует список токенов в текст."""
        return self.enc.decode(tokens)

    def encode_chat(self, messages: List[dict]) -> List[int]:
        """
        Кодирует список сообщений в формате:
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, ...]
        
        Результат: <|system|>контент<|end|><|user|>контент<|end|><|assistant|>
        """
        tokens = []
        role_map = {
            "system":    self.system_id,
            "user":      self.user_id,
            "assistant": self.assistant_id,
        }
        for msg in messages:
            role_tok = role_map.get(msg["role"], self.user_id)
            tokens += [role_tok] + self.encode(msg["content"]) + [self.end_id]

        # Добавляем токен ассистента в конец (модель будет продолжать отсюда)
        tokens += [self.assistant_id]
        return tokens

    def __len__(self):
        return self.vocab_size


if __name__ == "__main__":
    tok = SylvietteTokenizer()
    print(f"Размер словаря: {tok.vocab_size}")

    test = "Привет, Хозяин-сан! Чем могу помочь?"
    ids  = tok.encode(test)
    back = tok.decode(ids)
    print(f"Оригинал:   {test}")
    print(f"Токены:     {ids[:10]}...")
    print(f"Декодировано: {back}")

    # Тест chat формата
    msgs = [
        {"role": "system",    "content": "Ты Сильфиетта, личный ИИ-ассистент."},
        {"role": "user",      "content": "Привет!"},
        {"role": "assistant", "content": "Привет, Хозяин-сан!"},
    ]
    chat_tokens = tok.encode_chat(msgs)
    print(f"\nChat токены ({len(chat_tokens)}): {chat_tokens[:15]}...")
    print("✓ Токенизатор работает!")