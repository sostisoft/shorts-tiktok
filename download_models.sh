#!/bin/bash
set -e
source venv/bin/activate

echo "=== Descargando modelos IA ==="

pip install huggingface-hub -q

# 1. FLUX.1 schnell — se descarga automáticamente via diffusers al primer uso

# 2. Wan2.1 I2V 14B
echo "Descargando Wan2.1 I2V 14B (~27GB)..."
huggingface-cli download \
    Wan-Video/Wan2.1-I2V-14B-480P \
    --local-dir models/wan21 \
    --include "*.safetensors" "*.json" "*.txt"

# 3. Kokoro TTS
echo "Descargando Kokoro TTS..."
pip install kokoro-onnx -q

echo "Modelos descargados"
echo "Espacio usado:"
du -sh models/
