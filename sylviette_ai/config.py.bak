from dataclasses import dataclass
from typing import Optional

@dataclass
class TrainConfig:
    data_dir:       str   = "data/text/pretrain"
    out_dir:        str   = "checkpoints"
    run_name:       str   = "sylviette-pretrain"
    mode:           str   = "pretrain"
    vocab_size:     int   = 50304
    context_length: int   = 512
    n_embd:         int   = 768
    n_heads:        int   = 12
    n_layers:       int   = 12
    dropout:        float = 0.05
    max_iters:      int   = 50000
    batch_size:     int   = 1
    grad_accum:     int   = 4
    learning_rate:  float = 3e-4
    min_lr:         float = 3e-5
    warmup_iters:   int   = 1000
    weight_decay:   float = 0.1
    grad_clip:      float = 0.5
    beta1:          float = 0.9
    beta2:          float = 0.95
    eps:            float = 1e-8
    dtype:          str   = "bfloat16"
    compile:        bool  = False
    device:         str   = "cuda"
    seed:           int   = 42
    log_interval:   int   = 10
    eval_interval:  int   = 1000
    eval_iters:     int   = 50
    save_interval:  int   = 2000
    resume:         Optional[str] = None

PRETRAIN_CONFIG = TrainConfig(
    mode          = "pretrain",
    run_name      = "sylviette-pretrain",
    data_dir      = "data/text/pretrain",
    max_iters     = 50000,
    batch_size    = 1,
    grad_accum    = 4,
    learning_rate = 3e-4,
    eval_interval = 1000,
    save_interval = 2000,
    resume        = "checkpoints/sylviette-pretrain/latest.pt",
)

FINETUNE_CONFIG = TrainConfig(
    mode          = "pretrain",
    run_name      = "sylviette-chat",
    data_dir      = "data/chat",
    max_iters     = 500,
    batch_size    = 1,
    grad_accum    = 4,
    learning_rate = 5e-6,
    min_lr        = 1e-5,
    warmup_iters  = 200,
    eval_interval = 500,
    save_interval = 1000,
    resume        = "checkpoints/sylviette-pretrain/latest.pt",
)
