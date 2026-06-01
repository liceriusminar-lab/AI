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

# Патч под реальный токенизатор (vocab=100289) и 6GB VRAM
PRETRAIN_CONFIG.vocab_size  = 100289
PRETRAIN_CONFIG.n_embd      = 768    # уменьшаем: 509M → ~280M
PRETRAIN_CONFIG.n_heads     = 12
PRETRAIN_CONFIG.n_layers    = 18
PRETRAIN_CONFIG.batch_size  = 1      # batch 1 пока не проверим VRAM
PRETRAIN_CONFIG.grad_accum  = 16     # эффективный batch остаётся 16
