import json, torch
from pathlib import Path
from datetime import datetime


class OnlineLearner:
    def __init__(self, model, tokenizer, device, examples_file="data/online_examples.jsonl"):
        self.model     = model
        self.tokenizer = tokenizer
        self.device    = device
        self.examples_file = Path(examples_file)
        self.examples_file.parent.mkdir(parents=True, exist_ok=True)
        self.pending   = []
        self.learn_every = 10
        print(f"✦ OnlineLearner готов!")

    def add_example(self, question, answer):
        example = {"question": question.strip(), "answer": answer.strip(), "time": datetime.now().isoformat()}
        self.pending.append(example)
        with open(self.examples_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")
        print(f"  ✦ Пример добавлен ({len(self.pending)}/{self.learn_every})")
        if len(self.pending) >= self.learn_every:
            self.train_on_pending()

    def train_on_pending(self, steps=50, lr=1e-4):
        if not self.pending:
            return
        print(f"\n✦ Дообучаемся на {len(self.pending)} примерах...")
        all_tokens = []
        for ex in self.pending:
            text = f"Вопрос: {ex['question']}\nОтвет: {ex['answer']}\n"
            all_tokens.extend(self.tokenizer.encode(text))
        if len(all_tokens) < 10:
            return
        max_len = min(len(all_tokens) - 1, self.model.config.context_length)
        x = torch.tensor(all_tokens[:max_len],    dtype=torch.long).unsqueeze(0).to(self.device)
        y = torch.tensor(all_tokens[1:max_len+1], dtype=torch.long).unsqueeze(0).to(self.device)
        self.model.train()
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr)
        losses = []
        for _ in range(steps):
            optimizer.zero_grad()
            _, loss = self.model(x, targets=y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            optimizer.step()
            losses.append(loss.item())
        self.model.eval()
        print(f"  ✓ Loss: {losses[0]:.4f} → {losses[-1]:.4f}")
        self.pending.clear()

    def learn_now(self, question, answer, steps=100):
        print(f"\n✦ Немедленное обучение...")
        self.pending = [{"question": question, "answer": answer}]
        self.train_on_pending(steps=steps, lr=5e-5)

    def save_model(self, path):
        raw = self.model._orig_mod if hasattr(self.model, "_orig_mod") else self.model
        torch.save({"model": raw.state_dict(), "model_cfg": vars(raw.config)}, path)
        print(f"  ✦ Модель сохранена: {path}")

    def load_all_examples(self):
        if not self.examples_file.exists():
            return []
        examples = []
        with open(self.examples_file, encoding="utf-8") as f:
            for line in f:
                try: examples.append(json.loads(line))
                except: pass
        return examples
