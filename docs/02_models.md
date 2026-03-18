# 02 — Modelos IA: descarga e instalación

## Modelos necesarios

| Modelo | Uso | Tamaño | RAM |
|---|---|---|---|
| FLUX.1 schnell | Genera imágenes desde texto | ~24GB | 24GB |
| Wan2.1 I2V 14B | Anima imágenes → vídeo | ~27GB | 27GB |
| Kokoro TTS | Voz en castellano | ~350MB | 1GB |

Total en disco: ~51GB
Total en RAM al ejecutar: ~52GB (de 128GB disponibles)

---

## Script de descarga

Claude Code debe crear `download_models.sh`:

```bash
#!/bin/bash
set -e
source venv/bin/activate

echo "=== Descargando modelos IA ==="

# Instalar huggingface-hub CLI
pip install huggingface-hub -q

# 1. FLUX.1 schnell (imágenes)
# Se descarga automáticamente via diffusers al primer uso
# No hace falta descarga manual — diffusers lo cachea en ~/.cache/huggingface/

# 2. Wan2.1 I2V 14B (vídeo)
echo "Descargando Wan2.1 I2V 14B (~27GB)..."
huggingface-cli download \
    Wan-Video/Wan2.1-I2V-14B-480P \
    --local-dir models/wan21 \
    --include "*.safetensors" "*.json" "*.txt"

# 3. Kokoro TTS
echo "Descargando Kokoro TTS..."
pip install kokoro-onnx -q
# El modelo se descarga automáticamente al primer uso

echo "✅ Modelos descargados"
echo "Espacio usado:"
du -sh models/
```

---

## Verificación de modelos

Claude Code debe crear `verify_models.py`:

```python
import torch
import os
from pathlib import Path

def verify():
    print("=== Verificando modelos ===\n")

    # GPU
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
        mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"   VRAM/RAM compartida: {mem:.1f} GB")
    else:
        print("⚠️  GPU no detectada — corriendo en CPU (lento)")

    # FLUX (via diffusers cache)
    flux_cache = Path.home() / ".cache/huggingface/hub"
    flux_exists = any(flux_cache.glob("*flux*")) if flux_cache.exists() else False
    print(f"\n{'✅' if flux_exists else '⏳'} FLUX.1 schnell: {'en caché' if flux_exists else 'se descarga al primer uso'}")

    # Wan2.1
    wan_path = Path("models/wan21")
    wan_files = list(wan_path.glob("*.safetensors")) if wan_path.exists() else []
    print(f"{'✅' if wan_files else '❌'} Wan2.1 I2V: {len(wan_files)} ficheros safetensors")

    # Kokoro
    try:
        from kokoro_onnx import Kokoro
        print("✅ Kokoro TTS: instalado")
    except ImportError:
        print("❌ Kokoro TTS: pip install kokoro-onnx")

    # ffmpeg
    import subprocess
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    ok = result.returncode == 0
    print(f"{'✅' if ok else '❌'} ffmpeg: {'instalado' if ok else 'no encontrado'}")

if __name__ == "__main__":
    verify()
```

---

## Tiempos estimados en GMKtec (AMD iGPU + 128GB RAM)

| Tarea | Tiempo estimado |
|---|---|
| Generar 10 imágenes con FLUX | ~3-5 min total |
| Animar 1 imagen con Wan2.1 (5s clip) | ~10-15 min |
| Generar narración Kokoro (60s audio) | ~15 segundos |
| Edición ffmpeg completa | ~2 min |
| **Total por vídeo** | **~15-25 min** |
