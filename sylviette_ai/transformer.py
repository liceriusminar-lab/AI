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
            loss = chunked_cross_entropy(logits, targets)
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


def chunked_cross_entropy(logits, targets, chunk_size=512, ignore_index=-1):
    """Cross entropy по чанкам — не выделяет весь vocab тензор разом."""
    B, T, V = logits.shape
    logits  = logits.view(-1, V)
    targets = targets.view(-1)
    total_loss = torch.zeros(1, device=logits.device)
    valid      = 0
    for i in range(0, logits.shape[0], chunk_size):
        lg = logits[i:i+chunk_size]
        tg = targets[i:i+chunk_size]
        mask = tg != ignore_index
        if mask.sum() == 0:
            continue
        total_loss += F.cross_entropy(lg[mask], tg[mask], reduction="sum")
        valid      += mask.sum()
    return total_loss / valid.clamp(min=1)
