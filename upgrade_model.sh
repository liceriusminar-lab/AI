#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  upgrade_model.sh — апгрейд Сильфиетты до 350M параметров
#  Запуск: bash upgrade_model.sh
# ═══════════════════════════════════════════════════════════════

set -e  # останавливаемся при любой ошибке
cd ~/ai-assistant

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Сильфиетта — апгрейд до 350M params   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Бэкап старых файлов ────────────────────────────────────
echo "📦 [1/4] Бэкап старых файлов..."
cp sylviette_ai/config.py      sylviette_ai/config.py.bak
cp sylviette_ai/transformer.py sylviette_ai/transformer.py.bak
echo "  ✓ Бэкапы: config.py.bak, transformer.py.bak"

# ── 2. Новый config.py ────────────────────────────────────────
echo ""
echo "⚙  [2/4] Пишем новый config.py (350M, ctx=2048, CPU offload)..."

cat > sylviette_ai/config.py << 'ENDOFCONFIG'
from dataclasses import dataclass
from typing import Optional

# ──────────────────────────────────────────────────────────────
# Конфигурация Сильфиетты 350M
# Железо: RTX 4050 6 GB VRAM + 64 GB RAM
#
# Стратегия экономии VRAM:
#   • Gradient Checkpointing  → пересчёт активаций, -40% VRAM
#   • CPU Offload Embedding   → ~200 MB в RAM вместо VRAM
#   • Flash Attention         → O(n) памяти вместо O(n²)
#   • bf16                    → вдвое меньше VRAM чем fp32
# ──────────────────────────────────────────────────────────────

@dataclass
class TrainConfig:
    data_dir:       str   = "data/text/pretrain"
    out_dir:        str   = "checkpoints"
    run_name:       str   = "sylviette-pretrain"
    mode:           str   = "pretrain"

    # Архитектура 350M
    vocab_size:     int   = 50310
    context_length: int   = 2048
    n_embd:         int   = 1024      # было 768
    n_heads:        int   = 16        # было 12
    n_layers:       int   = 24        # было 12
    dropout:        float = 0.05

    # Обучение
    max_iters:      int   = 50_000
    batch_size:     int   = 2
    grad_accum:     int   = 8          # эффективный batch = 16
    learning_rate:  float = 2e-4
    min_lr:         float = 2e-5
    warmup_iters:   int   = 2_000
    weight_decay:   float = 0.1
    grad_clip:      float = 1.0
    beta1:          float = 0.9
    beta2:          float = 0.95
    eps:            float = 1e-8
    dtype:          str   = "bfloat16"
    device:         str   = "cuda"
    seed:           int   = 42

    # Оптимизации памяти
    gradient_checkpointing: bool = True
    cpu_offload_embed:      bool = True
    pin_memory:             bool = True
    num_workers:            int  = 4
    compile:                bool = False

    # Логирование
    log_interval:   int   = 10
    eval_interval:  int   = 1_000
    eval_iters:     int   = 50
    save_interval:  int   = 2_000
    resume:         Optional[str] = None


PRETRAIN_CONFIG = TrainConfig(
    mode          = "pretrain",
    run_name      = "sylviette-350m-pretrain",
    data_dir      = "data/text/pretrain",
    max_iters     = 50_000,
    batch_size    = 2,
    grad_accum    = 8,
    learning_rate = 2e-4,
    resume        = "checkpoints/sylviette-350m-pretrain/latest.pt",
)

FINETUNE_CONFIG = TrainConfig(
    mode          = "finetune",
    run_name      = "sylviette-350m-chat",
    data_dir      = "data/chat",
    max_iters     = 1_000,
    batch_size    = 2,
    grad_accum    = 4,
    learning_rate = 3e-5,
    min_lr        = 5e-6,
    warmup_iters  = 200,
    eval_interval = 500,
    save_interval = 500,
    resume        = "checkpoints/sylviette-350m-pretrain/latest.pt",
)

SMOKE_CONFIG = TrainConfig(
    mode          = "pretrain",
    run_name      = "sylviette-smoke",
    data_dir      = "data/text/pretrain",
    max_iters     = 100,
    batch_size    = 1,
    grad_accum    = 2,
    eval_interval = 50,
    save_interval = 100,
    resume        = None,
    gradient_checkpointing = True,
    cpu_offload_embed      = True,
)
ENDOFCONFIG

echo "  ✓ config.py записан"

# ── 3. Новый transformer.py ───────────────────────────────────
echo ""
echo "🧠 [3/4] Пишем новый transformer.py (350M + CPU offload)..."

cat > sylviette_ai/transformer.py << 'ENDOFTRANSFORMER'
"""
sylviette_ai/transformer.py — SylvietteGPT 350M
Оптимизации: Gradient Checkpointing, CPU Offload Embedding, Flash Attention
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Optional
from torch.utils.checkpoint import checkpoint


@dataclass
class ModelConfig:
    vocab_size:     int   = 50310
    context_length: int   = 2048
    n_embd:         int   = 1024
    n_heads:        int   = 16
    n_layers:       int   = 24
    dropout:        float = 0.05
    bias:           bool  = False
    vision_enabled: bool  = False
    vision_dim:     int   = 512
    gradient_checkpointing: bool = True
    cpu_offload_embed:      bool = True


class RotaryEmbedding(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        inv_freq = 1.0 / (10000 ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)
        self._cache_len = 0
        self._cos_cache = None
        self._sin_cache = None

    def _build_cache(self, seq_len: int, device):
        if seq_len <= self._cache_len:
            return
        t = torch.arange(seq_len, device=device, dtype=self.inv_freq.dtype)
        freqs = torch.outer(t, self.inv_freq)
        emb = torch.cat([freqs, freqs], dim=-1)
        self._cos_cache = emb.cos()
        self._sin_cache = emb.sin()
        self._cache_len = seq_len

    def forward(self, seq_len: int, device):
        self._build_cache(seq_len, device)
        return self._cos_cache[:seq_len], self._sin_cache[:seq_len]


def rotate_half(x):
    x1, x2 = x.chunk(2, dim=-1)
    return torch.cat([-x2, x1], dim=-1)


def apply_rotary_emb(q, k, cos, sin):
    cos = cos[:q.shape[-2]].unsqueeze(0).unsqueeze(0)
    sin = sin[:q.shape[-2]].unsqueeze(0).unsqueeze(0)
    return (q * cos) + (rotate_half(q) * sin), (k * cos) + (rotate_half(k) * sin)


class CausalSelfAttention(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        assert config.n_embd % config.n_heads == 0
        self.n_heads  = config.n_heads
        self.n_embd   = config.n_embd
        self.head_dim = config.n_embd // config.n_heads
        self.dropout  = config.dropout
        self.qkv_proj  = nn.Linear(config.n_embd, 3 * config.n_embd, bias=config.bias)
        self.out_proj  = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        self.resid_drop = nn.Dropout(config.dropout)
        self.rotary = RotaryEmbedding(self.head_dim)
        self.use_flash = hasattr(F, "scaled_dot_product_attention")

    def forward(self, x):
        B, T, C = x.shape
        qkv = self.qkv_proj(x)
        q, k, v = qkv.split(self.n_embd, dim=2)
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        cos, sin = self.rotary(T, x.device)
        q, k = apply_rotary_emb(q, k, cos, sin)
        if self.use_flash:
            y = F.scaled_dot_product_attention(
                q, k, v,
                dropout_p=self.dropout if self.training else 0.0,
                is_causal=True,
            )
        else:
            scale = 1.0 / math.sqrt(self.head_dim)
            attn  = (q @ k.transpose(-2, -1)) * scale
            attn  = attn.masked_fill(
                ~torch.tril(torch.ones(T, T, device=x.device, dtype=torch.bool)),
                float("-inf")
            )
            attn = F.dropout(F.softmax(attn, dim=-1), p=self.dropout, training=self.training)
            y    = attn @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.resid_drop(self.out_proj(y))


class SwiGLU(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        hidden = (int(config.n_embd * 8 / 3) + 63) // 64 * 64
        self.gate = nn.Linear(config.n_embd, hidden, bias=config.bias)
        self.up   = nn.Linear(config.n_embd, hidden, bias=config.bias)
        self.down = nn.Linear(hidden, config.n_embd, bias=config.bias)
        self.drop = nn.Dropout(config.dropout)

    def forward(self, x):
        return self.drop(self.down(F.silu(self.gate(x)) * self.up(x)))


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps    = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps) * self.weight


class TransformerBlock(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.norm1 = RMSNorm(config.n_embd)
        self.attn  = CausalSelfAttention(config)
        self.norm2 = RMSNorm(config.n_embd)
        self.ffn   = SwiGLU(config)

    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        x = x + self.ffn(self.norm2(x))
        return x


class OffloadedEmbedding(nn.Module):
    """Embedding таблица в CPU RAM — экономит ~200 MB VRAM."""
    def __init__(self, num_embeddings: int, embedding_dim: int):
        super().__init__()
        self.weight = nn.Parameter(
            torch.empty(num_embeddings, embedding_dim).cpu(),
            requires_grad=True
        )
        nn.init.normal_(self.weight, mean=0.0, std=0.02)

    def forward(self, input_ids):
        return F.embedding(input_ids, self.weight.to(input_ids.device))


class SylvietteGPT(nn.Module):
    """SylvietteGPT 350M — RTX 4050 6GB + 64GB RAM."""

    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config

        if config.cpu_offload_embed:
            self.token_emb = OffloadedEmbedding(config.vocab_size, config.n_embd)
            print("  💾 Embedding → CPU RAM (~200 MB VRAM saved)")
        else:
            self.token_emb = nn.Embedding(config.vocab_size, config.n_embd)

        self.emb_drop = nn.Dropout(config.dropout)
        self.blocks   = nn.ModuleList([TransformerBlock(config) for _ in range(config.n_layers)])
        self.norm_f   = RMSNorm(config.n_embd)
        self.lm_head  = nn.Linear(config.n_embd, config.vocab_size, bias=False)

        if config.vision_enabled:
            self.vision_proj = nn.Sequential(
                nn.Linear(config.vision_dim, config.n_embd),
                nn.GELU(),
                nn.Linear(config.n_embd, config.n_embd),
            )

        self.apply(self._init_weights)
        for name, p in self.named_parameters():
            if name.endswith("out_proj.weight") or name.endswith("down.weight"):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * config.n_layers))

        total = sum(p.numel() for p in self.parameters()) / 1e6
        print(f"✦ SylvietteGPT: {total:.1f}M параметров | ctx={config.context_length}")

    def _init_weights(self, module):
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if hasattr(module, "bias") and module.bias is not None:
                nn.init.zeros_(module.bias)

    def count_params(self):
        return sum(p.numel() for p in self.parameters()) / 1e6

    def forward(self, input_ids, targets=None, image_features=None):
        B, T = input_ids.shape
        assert T <= self.config.context_length

        x = self.emb_drop(self.token_emb(input_ids))

        if image_features is not None and self.config.vision_enabled:
            img_emb = self.vision_proj(image_features).unsqueeze(1)
            x = torch.cat([img_emb, x], dim=1)

        for block in self.blocks:
            if self.config.gradient_checkpointing and self.training:
                x = checkpoint(block, x, use_reentrant=False)
            else:
                x = block(x)

        x = self.norm_f(x)

        if targets is not None:
            logits = self.lm_head(x)
            if image_features is not None and self.config.vision_enabled:
                logits = logits[:, 1:, :]
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=-1,
            )
            return logits, loss

        return self.lm_head(x[:, [-1], :]), None

    @torch.no_grad()
    def generate(self, input_ids, max_new_tokens=512, temperature=0.8,
                 top_k=50, top_p=0.9, image_features=None):
        self.eval()
        for _ in range(max_new_tokens):
            idx_cond = input_ids[:, -self.config.context_length:]
            logits, _ = self(idx_cond, image_features=image_features)
            logits = logits[:, -1, :] / max(temperature, 1e-6)
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float("-inf")
            if top_p < 1.0:
                sorted_logits, sorted_idx = torch.sort(logits, descending=True)
                cum_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                remove = cum_probs - F.softmax(sorted_logits, dim=-1) > top_p
                sorted_logits[remove] = float("-inf")
                logits = torch.scatter(logits, 1, sorted_idx, sorted_logits)
            next_token = torch.multinomial(F.softmax(logits, dim=-1), num_samples=1)
            input_ids  = torch.cat([input_ids, next_token], dim=1)
        return input_ids


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg    = ModelConfig()
    model  = SylvietteGPT(cfg).to(device)
    if torch.cuda.is_available():
        print(f"  VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")
    x = torch.randint(0, cfg.vocab_size, (1, 64)).to(device)
    logits, loss = model(x, targets=x)
    print(f"✓ Logits: {logits.shape} | Loss: {loss.item():.4f}")
ENDOFTRANSFORMER

echo "  ✓ transformer.py записан"

# ── 4. Smoke-тест ─────────────────────────────────────────────
echo ""
echo "🧪 [4/4] Smoke-тест — проверяем что модель запускается..."

source venv/bin/activate
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python - << 'ENDOFTEST'
import sys
sys.path.insert(0, '.')
import torch
from sylviette_ai.transformer import SylvietteGPT, ModelConfig
from sylviette_ai.config import PRETRAIN_CONFIG

print("  Создаём модель 350M...")
cfg = ModelConfig(
    vocab_size     = PRETRAIN_CONFIG.vocab_size,
    context_length = PRETRAIN_CONFIG.context_length,
    n_embd         = PRETRAIN_CONFIG.n_embd,
    n_heads        = PRETRAIN_CONFIG.n_heads,
    n_layers       = PRETRAIN_CONFIG.n_layers,
    dropout        = PRETRAIN_CONFIG.dropout,
    gradient_checkpointing = PRETRAIN_CONFIG.gradient_checkpointing,
    cpu_offload_embed      = PRETRAIN_CONFIG.cpu_offload_embed,
)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model  = SylvietteGPT(cfg).to(device)

if torch.cuda.is_available():
    vram = torch.cuda.memory_allocated() / 1e9
    print(f"  VRAM после загрузки: {vram:.2f} GB / 6.00 GB")

# Тест forward
x = torch.randint(0, cfg.vocab_size, (2, 128)).to(device)
logits, loss = model(x, targets=x)
print(f"  Forward OK — loss: {loss.item():.4f}")

if torch.cuda.is_available():
    vram2 = torch.cuda.memory_allocated() / 1e9
    print(f"  VRAM после forward: {vram2:.2f} GB")

total_mb = sum(p.numel() * 4 for p in model.parameters()) / 1e6
print(f"  Размер весов: ~{total_mb:.0f} MB")
print("")
print("  ✅ Всё работает! Запускай обучение:")
print("     bash start_training.sh")
ENDOFTEST

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           ✦ Апгрейд завершён!           ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Модель:   350M параметров (было ~125M)"
echo "  Контекст: 2048 токенов (было 512)"
echo "  Embedding: в RAM, не VRAM"
echo "  Grad checkpoint: активен"
echo ""
echo "  Следующий шаг — обучение:"
echo "  bash safe_train.sh"
echo ""
