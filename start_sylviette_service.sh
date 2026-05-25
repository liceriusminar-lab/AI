#!/bin/bash
# Убиваем старые процессы
pkill -f "sylviette_ai.inference" 2>/dev/null || true
sleep 2

# Запускаем Ollama
export OLLAMA_HOST=127.0.0.1:11435
/usr/local/bin/ollama serve &
sleep 8

# Запускаем Сильфиетту
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/licerius/ai-assistant
source venv/bin/activate
exec python -m sylviette_ai.inference \
    --checkpoint checkpoints/sylviette-pretrain/latest.pt \
    --no-vision
