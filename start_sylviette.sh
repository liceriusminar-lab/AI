#!/bin/bash
sleep 5
export OLLAMA_HOST=127.0.0.1:11435
cd /home/licerius/ai-assistant
source venv/bin/activate
python3 main.py
