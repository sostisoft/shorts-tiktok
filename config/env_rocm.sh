#!/bin/bash
# ─── ROCm / Strix Halo gfx1151 ──────────────────────────────────────────────
# Source este fichero antes de lanzar el bot:
#   source config/env_rocm.sh

# Arquitectura correcta (era 11.0.0 en el Dockerfile — INCORRECTO)
export HSA_OVERRIDE_GFX_VERSION=11.5.1

# OBLIGATORIO en APUs: previene artefactos checkerboard en VAE decode
export HSA_ENABLE_SDMA=0

# Memoria UMA: permite usar todo el pool GTT
export GPU_MAX_ALLOC_PERCENT=100
export GPU_MAX_HEAP_SIZE=100
export HSA_XNACK=1

# PyTorch: allocator nativo, segmentos expandibles
export PYTORCH_HIP_ALLOC_CONF="backend:native,expandable_segments:True,max_split_size_mb:512,garbage_collection_threshold:0.9"

# hipBLASLt: diferencia entre 5 TFLOPS y 37 TFLOPS
export TORCH_BLAS_PREFER_HIPBLASLT=1
export ROCBLAS_USE_HIPBLASLT=1

# Dispositivo GPU visible
export HIP_VISIBLE_DEVICES=0
export ROCR_VISIBLE_DEVICES=0

# Flash Attention Triton AMD (para Wan2GP)
export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"
export FLASH_ATTENTION_BACKEND="flash_attn_triton_amd"

# Ollama en CPU para no competir con GPU durante la generación de video
# (descomenta si usas Ollama como servicio systemd)
# export OLLAMA_GPU_LAYERS=0
