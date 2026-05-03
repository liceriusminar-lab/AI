import json
import numpy as np
import torch
from pathlib import Path
from torch.utils.data import Dataset


class TextDataset(Dataset):
    def __init__(self, data_dir, tokenizer=None, context_length=1024, split=None, val_fraction=0.005):
        self.context_length = context_length
        self.chunks = []

        data_path = Path(data_dir)
        bin_files = sorted(data_path.glob("**/*.bin"))

        if not bin_files:
            print(f"  ⚠ .bin файлы не найдены в {data_dir}", flush=True)
            return

        all_tokens = []
        for fp in bin_files:
            print(f"  📄 {fp.name}...", end=" ", flush=True)
            tokens = np.fromfile(fp, dtype=np.uint32).tolist()
            print(f"{len(tokens):,} токенов", flush=True)
            all_tokens.extend(tokens)
            if len(all_tokens) > 15_000_000:
                all_tokens = all_tokens[:15_000_000]
                print(f"  ✂ Ограничено до 5M токенов", flush=True)
                break

        print(f"  Нарезаем на чанки...", end=" ", flush=True)
        for i in range(0, len(all_tokens) - context_length - 1, context_length):
            self.chunks.append(all_tokens[i:i + context_length + 1])
        print(f"{len(self.chunks):,} чанков", flush=True)

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, idx):
        chunk = self.chunks[idx]
        return torch.tensor(chunk[:-1], dtype=torch.long), torch.tensor(chunk[1:], dtype=torch.long)


class ChatDataset(Dataset):
    def __init__(self, data_path, tokenizer, context_length=1024, split="train", val_fraction=0.05):
        self.context_length = context_length
        self.items = []

        fp    = Path(data_path)
        files = list(fp.glob("*.jsonl")) if fp.is_dir() else ([fp] if fp.exists() else [])

        dialogs = []
        for f in files:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try: dialogs.append(json.loads(line))
                        except: pass

        if not dialogs:
            print(f"  ⚠ Диалоги не найдены в {data_path}", flush=True)
            return

        split_idx = int(len(dialogs) * (1 - val_fraction))
        dialogs   = dialogs[:split_idx] if split == "train" else dialogs[split_idx:]

        for d in dialogs:
            tokens, labels = [], []
            for msg in d.get("messages", []):
                role    = msg["role"]
                content = msg["content"]
                role_map = {"system": tokenizer.system_id, "user": tokenizer.user_id, "assistant": tokenizer.assistant_id}
                role_tok = role_map.get(role, tokenizer.user_id)
                tok = [role_tok] + tokenizer.encode(content) + [tokenizer.end_id]
                tokens.extend(tok)
                if role == "assistant":
                    labels.extend(tok)
                else:
                    # Для не-ассистента игнорируем, но токен роли ассистента включаем
                    labels.extend([-1] * len(tok))

            tokens = tokens[:context_length] + [tokenizer.pad_id] * max(0, context_length - len(tokens))
            labels = labels[:context_length] + [-1]               * max(0, context_length - len(labels))
            self.items.append((torch.tensor(tokens, dtype=torch.long), torch.tensor(labels, dtype=torch.long)))

        print(f"  ChatDataset {split}: {len(self.items)} диалогов", flush=True)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        return self.items[idx]
