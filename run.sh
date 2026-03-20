#!/bin/bash
# run.sh — Ejecutar VideoBot nativamente (sin Docker)
# Uso: ./run.sh [generate|publish|run|resume [job_id]|status]
# Sin args: arranca el scheduler automático
set -e

# ── Directorio de trabajo ──
cd "$(dirname "$0")"

# ── ROCm env vars para gfx1151 (Strix Halo) ──
# NO necesita HSA_OVERRIDE_GFX_VERSION — TheRock tiene soporte nativo gfx1151
export HSA_ENABLE_SDMA=0
export TQDM_DISABLE=1
export HF_HUB_DISABLE_PROGRESS_BARS=1
export GPU_MAX_ALLOC_PERCENT=100
export GPU_SINGLE_ALLOC_PERCENT=100
export GPU_MAX_HEAP_SIZE=100
export PYTORCH_HIP_ALLOC_CONF="backend:native,expandable_segments:True,garbage_collection_threshold:0.9"
export AMD_LOG_LEVEL=0
export MIOPEN_FIND_MODE=FAST
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export OMP_NUM_THREADS=16
export MKL_NUM_THREADS=16

# ── Ollama ──
export OLLAMA_HOST="http://localhost:11434"

# ── Python ──
export PYTHONUNBUFFERED=1
export TZ=Europe/Madrid

# ── Activar venv (usar python del venv directamente por portabilidad) ──
PYTHON="$(dirname "$0")/venv/bin/python3"

echo "=== VideoBot Finanzas Claras ==="
echo "ROCm: gfx1151 | Ollama: $OLLAMA_HOST"
echo "Python: $($PYTHON --version) | PyTorch: $($PYTHON -c 'import torch; print(torch.__version__)')"
echo "GPU: $($PYTHON -c 'import torch; print("disponible" if torch.cuda.is_available() else "NO disponible")')"
echo ""

# ── Ejecutar ──
exec $PYTHON main.py "$@"
