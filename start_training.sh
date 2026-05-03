#!/bin/bash
cd ~/ai-assistant
source venv/bin/activate
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "Выбери режим:"
echo "1) pretrain - продолжить предобучение"
echo "2) finetune - файнтюнинг характера Сильфиетты"
read -p "Введи 1 или 2: " choice

if [ "$choice" = "1" ]; then
    python -m sylviette_ai.train --mode pretrain 2>&1 | tee training.log
else
    python -m sylviette_ai.train --mode finetune 2>&1 | tee finetune.log
fi
