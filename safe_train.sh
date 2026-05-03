#!/bin/bash
cd ~/ai-assistant
source venv/bin/activate
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "Выбери режим:"
echo "1) pretrain"
echo "2) finetune"
read -p "Введи 1 или 2: " choice

MODE="pretrain"
[ "$choice" = "2" ] && MODE="finetune"

echo "Запускаем обучение в режиме: $MODE"
echo "Авто-остановка при температуре > 85°C"

python -m sylviette_ai.train --mode $MODE 2>&1 | tee ${MODE}.log &
TRAIN_PID=$!

while kill -0 $TRAIN_PID 2>/dev/null; do
    TEMP=$(sensors | grep "Core 0" | awk '{print $3}' | tr -d '+°C' | cut -d'.' -f1)
    if [ "$TEMP" -gt 92 ]; then
        echo ""
        echo "ТЕМПЕРАТУРА $TEMP°C > 85°C — ОСТАНАВЛИВАЕМ!"
        kill $TRAIN_PID
        break
    fi
    sleep 30
done

echo "Готово. Последняя температура: ${TEMP}°C"
