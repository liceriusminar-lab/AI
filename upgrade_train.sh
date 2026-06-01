#!/bin/bash
set -e
cd ~/ai-assistant

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Апгрейд train.py под 350M + RAM     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

cp sylviette_ai/train.py sylviette_ai/train.py.bak
echo "📦 Бэкап → train.py.bak"

cat > sylviette_ai/train.py << 'ENDOFTRAIN'
import os, sys, math, time, json
from pathlib import Path
from contextlib import nullcontext

import torch
from torch.utils.data import DataLoader, random_split

sys.path.insert(0, str(Path(__file__).parent.parent))
from sylviette_ai.transformer import SylvietteGPT, ModelConfig
from sylviette_ai.tokenizer   import SylvietteTokenizer
from sylviette_ai.config      import TrainConfig, PRETRAIN_CONFIG, FINETUNE_CONFIG
from sylviette_ai.dataset     import TextDataset, ChatDataset


def get_lr(it, cfg):
    if it < cfg.warmup_iters:
        return cfg.learning_rate * it / cfg.warmup_iters
    if it > cfg.max_iters:
        return cfg.min_lr
    progress = (it - cfg.warmup_iters) / (cfg.max_iters - cfg.warmup_iters)
    return cfg.min_lr + 0.5 * (1.0 + math.cos(math.pi * progress)) * (cfg.learning_rate - cfg.min_lr)


def train(cfg=PRETRAIN_CONFIG):
    torch.manual_seed(cfg.seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.benchmark = True  # авто-оптимизация для фиксированных размеров

    device = torch.device(cfg.device if torch.cuda.is_available() else "cpu")
    print(f"✦ Устройство: {device}", flush=True)
    if device.type == "cuda":
        print(f"  GPU:  {torch.cuda.get_device_name(0)}", flush=True)
        total_vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"  VRAM: {total_vram:.1f} GB", flush=True)

    dtype_map = {"float32": torch.float32, "bfloat16": torch.bfloat16, "float16": torch.float16}
    pt_dtype  = dtype_map.get(cfg.dtype, torch.bfloat16)
    ctx       = torch.amp.autocast(device_type="cuda", dtype=pt_dtype) if device.type == "cuda" else nullcontext()
    scaler    = torch.amp.GradScaler(enabled=(cfg.dtype == "float16"))

    print(f"✦ Загружаем токенизатор...", flush=True)
    tokenizer = SylvietteTokenizer()
    print(f"  vocab_size={tokenizer.vocab_size}", flush=True)

    print(f"✦ Загружаем датасет из {cfg.data_dir}...", flush=True)
    if cfg.mode == "finetune":
        train_ds = ChatDataset(cfg.data_dir, tokenizer, cfg.context_length, split="train")
        val_ds   = ChatDataset(cfg.data_dir, tokenizer, cfg.context_length, split="val")
    else:
        full_ds  = TextDataset(cfg.data_dir, tokenizer, cfg.context_length)
        split_i  = int(len(full_ds) * 0.995)
        train_ds, val_ds = random_split(full_ds, [split_i, len(full_ds) - split_i])
        print(f"  train: {len(train_ds):,} | val: {len(len(full_ds) - split_i):,}", flush=True)

    # pin_memory=True — данные закреплены в RAM для быстрого DMA→VRAM
    # num_workers   — параллельная подготовка батчей в RAM пока GPU считает
    train_loader = DataLoader(
        train_ds, batch_size=cfg.batch_size, shuffle=True,
        num_workers=cfg.num_workers, pin_memory=cfg.pin_memory,
        persistent_workers=(cfg.num_workers > 0),
    )
    val_loader = DataLoader(
        val_ds, batch_size=cfg.batch_size, shuffle=False,
        num_workers=cfg.num_workers, pin_memory=cfg.pin_memory,
        persistent_workers=(cfg.num_workers > 0),
    )
    print(f"  train батчей: {len(train_loader)} | workers: {cfg.num_workers} | pin_memory: {cfg.pin_memory}", flush=True)

    print(f"✦ Создаём модель {cfg.n_embd}d × {cfg.n_layers}L × {cfg.n_heads}H...", flush=True)
    model_cfg = ModelConfig(
        vocab_size     = tokenizer.vocab_size,
        context_length = cfg.context_length,
        n_embd         = cfg.n_embd,
        n_heads        = cfg.n_heads,
        n_layers       = cfg.n_layers,
        dropout        = cfg.dropout,
        gradient_checkpointing = cfg.gradient_checkpointing,
        cpu_offload_embed      = cfg.cpu_offload_embed,
    )
    model = SylvietteGPT(model_cfg).to(device)

    if device.type == "cuda":
        vram_used = torch.cuda.memory_allocated() / 1e9
        vram_total = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"  VRAM после загрузки модели: {vram_used:.2f} / {vram_total:.1f} GB", flush=True)

    start_iter = 0
    if cfg.resume and os.path.exists(cfg.resume):
        print(f"✦ Загружаем чекпоинт: {cfg.resume}", flush=True)
        ckpt = torch.load(cfg.resume, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model"])
        start_iter = ckpt.get("iter", 0)
        print(f"  Загружен с iter={start_iter}!", flush=True)

    # Параметры с weight decay только для матриц (не bias, не norm)
    decay_params   = [p for n, p in model.named_parameters() if p.dim() >= 2]
    nodecay_params = [p for n, p in model.named_parameters() if p.dim() < 2]

    try:
        import bitsandbytes as bnb
        optimizer = bnb.optim.AdamW8bit(
            [{"params": decay_params,   "weight_decay": cfg.weight_decay},
             {"params": nodecay_params, "weight_decay": 0.0}],
            lr=cfg.learning_rate, betas=(cfg.beta1, cfg.beta2), eps=cfg.eps,
        )
        print("  ✓ 8-bit AdamW (bitsandbytes) — экономия ~500 MB VRAM", flush=True)
    except ImportError:
        optimizer = torch.optim.AdamW(
            [{"params": decay_params,   "weight_decay": cfg.weight_decay},
             {"params": nodecay_params, "weight_decay": 0.0}],
            lr=cfg.learning_rate, betas=(cfg.beta1, cfg.beta2), eps=cfg.eps,
        )
        print("  ⚠ Обычный AdamW (установи bitsandbytes для экономии VRAM)", flush=True)

    out_dir = Path(cfg.out_dir) / cfg.run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    @torch.no_grad()
    def estimate_loss():
        model.eval()
        losses = {}
        for split, loader in [("train", train_loader), ("val", val_loader)]:
            total, count = 0.0, 0
            for i, (x, y) in enumerate(loader):
                if i >= cfg.eval_iters: break
                x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
                with ctx:
                    _, loss = model(x, targets=y)
                total += loss.item(); count += 1
            losses[split] = total / max(count, 1)
        model.train()
        return losses

    def save_checkpoint(it, val_loss):
        raw = model._orig_mod if hasattr(model, "_orig_mod") else model
        ckpt = {
            "iter": it, "model": raw.state_dict(),
            "optimizer": optimizer.state_dict(),
            "val_loss": val_loss, "model_cfg": vars(model_cfg),
        }
        torch.save(ckpt, out_dir / f"ckpt_{it:07d}.pt")
        torch.save(ckpt, out_dir / "latest.pt")
        print(f"  💾 Сохранён iter={it} | val_loss={val_loss:.4f}", flush=True)

    print(f"\n{'='*52}")
    print(f"✦ Начинаем обучение!")
    print(f"  Модель:     {sum(p.numel() for p in model.parameters())/1e6:.1f}M параметров")
    print(f"  Batch:      {cfg.batch_size} × grad_accum {cfg.grad_accum} = {cfg.batch_size * cfg.grad_accum} эффективный")
    print(f"  Контекст:   {cfg.context_length} токенов")
    print(f"  Grad ckpt:  {cfg.gradient_checkpointing}")
    print(f"  CPU offload:{cfg.cpu_offload_embed}")
    print(f"  max_iters:  {cfg.max_iters}")
    print(f"{'='*52}\n", flush=True)

    train_iter    = iter(train_loader)
    best_val_loss = float("inf")
    t0            = time.time()
    model.train()
    optimizer.zero_grad()

    for it in range(start_iter, cfg.max_iters + 1):
        lr = get_lr(it, cfg)
        for pg in optimizer.param_groups:
            pg["lr"] = lr

        loss_accum = 0.0
        for _ in range(cfg.grad_accum):
            try:
                x, y = next(train_iter)
            except StopIteration:
                train_iter = iter(train_loader)
                x, y = next(train_iter)
            # non_blocking=True — перенос RAM→VRAM асинхронно
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            with ctx:
                _, loss = model(x, targets=y)
                loss    = loss / cfg.grad_accum
            loss_accum += loss.item()
            scaler.scale(loss).backward()

        if cfg.grad_clip > 0:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)

        if it % cfg.log_interval == 0:
            dt   = time.time() - t0; t0 = time.time()
            toks = cfg.batch_size * cfg.grad_accum * cfg.context_length * cfg.log_interval
            vram = torch.cuda.memory_allocated() / 1e9 if device.type == "cuda" else 0
            print(f"iter {it:6d} | loss {loss_accum:.4f} | lr {lr:.2e} | "
                  f"{toks/dt/1e3:.1f}K tok/s | VRAM {vram:.2f}GB", flush=True)

        if it % cfg.eval_interval == 0:
            losses = estimate_loss()
            print(f"\n📊 iter {it} | train {losses['train']:.4f} | val {losses['val']:.4f}", flush=True)
            if losses["val"] < best_val_loss:
                best_val_loss = losses["val"]
                save_checkpoint(it, losses["val"])
            model.train()
            print(flush=True)
        elif it % cfg.save_interval == 0 and it > 0:
            save_checkpoint(it, loss_accum)

    print(f"\n✦ Готово! Лучший val loss: {best_val_loss:.4f}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["pretrain", "finetune"], default="pretrain")
    args = parser.parse_args()
    cfg  = PRETRAIN_CONFIG if args.mode == "pretrain" else FINETUNE_CONFIG
    cfg.mode = args.mode
    train(cfg)
ENDOFTRAIN

echo "  ✓ train.py записан"

# Проверяем bitsandbytes
echo ""
echo "🔍 Проверяем bitsandbytes (8-bit AdamW)..."
source venv/bin/activate
python -c "import bitsandbytes; print('  ✓ bitsandbytes установлен')" 2>/dev/null || {
    echo "  ⚠ Не установлен — устанавливаем..."
    pip install bitsandbytes --break-system-packages -q
    echo "  ✓ bitsandbytes установлен"
}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         ✦ train.py обновлён!            ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Новые фичи:"
echo "  • pin_memory=True    — быстрый DMA RAM→VRAM"
echo "  • num_workers=4      — параллельная загрузка данных"
echo "  • non_blocking=True  — асинхронный перенос на GPU"
echo "  • 8-bit AdamW        — ~500 MB VRAM на оптимизатор"
echo "  • VRAM логирование   — виден расход на каждом шаге"
echo ""
echo "  Запуск обучения:"
echo "  bash safe_train.sh"
echo ""
