# 01 — Setup: Ubuntu 24.04 + ROCm 7.2 + TheRock gfx1151

## Hardware
- GMKtec EVO-X2 con AMD Ryzen AI MAX+ 395 (gfx1151, Strix Halo)
- 128 GB LPDDR5X memoria unificada
- GPU: Radeon 8060S (RDNA 3.5)

## Requisitos previos
- Ubuntu 24.04 LTS (x86_64)
- Kernel 6.18.4+ (actualmente 6.19.6-zabbly+)
- BIOS: VRAM ~512 MB (mínimo), el resto como GTT dinámico
- Al menos 100 GB libres en disco

---

## 1. Sistema base

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    python3.12 python3.12-venv python3-pip python3.12-dev \
    ffmpeg \
    git curl wget \
    build-essential \
    libssl-dev libffi-dev \
    fonts-liberation fonts-montserrat \
    htop
```

## 2. ROCm 7.2

```bash
# Instalar desde repositorio oficial AMD
wget https://repo.radeon.com/amdgpu-install/7.2/ubuntu/noble/amdgpu-install_7.2.70200-1_all.deb
sudo apt install -y ./amdgpu-install_7.2.70200-1_all.deb
sudo apt update
sudo amdgpu-install -y --usecase=rocm --no-dkms  # sin DKMS — kernel zabbly ya trae driver
sudo usermod -aG render,video $USER
```

## 3. Kernel y memoria (GRUB)

```bash
# /etc/default/grub — GRUB_CMDLINE_LINUX_DEFAULT:
quiet splash iommu=pt ttm.pages_limit=32505856 ttm.page_pool_size=32505856

sudo update-grub && sudo reboot
```

## 4. Python venv + TheRock PyTorch

```bash
cd ~/shorts
python3.12 -m venv venv
source venv/bin/activate

# PyTorch con TheRock nightlies — gfx1151 nativo, sin HSA_OVERRIDE
pip install --pre torch torchaudio torchvision \
    --index-url https://rocm.nightlies.amd.com/v2/gfx1151/

# Dependencias del proyecto
pip install -r requirements.txt
```

## 5. Ollama

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:14b
```

## 6. Verificación

```bash
# ROCm
cat /opt/rocm/.info/version        # 7.2.0
rocminfo | grep gfx                # gfx1151

# PyTorch + GPU
source venv/bin/activate
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
x = torch.randn(100, 100, device='cuda', dtype=torch.bfloat16)
print(f'Tensor GPU OK: {(x @ x.T).shape}')
"

# Ollama
ollama list | grep qwen2.5

# FFmpeg + Montserrat
ffmpeg -version | head -1
fc-list | grep -i montserrat
```

## Variables de entorno ROCm (en run.sh)

```bash
HSA_ENABLE_SDMA=0                    # Obligatorio en APU
GPU_MAX_ALLOC_PERCENT=100
GPU_SINGLE_ALLOC_PERCENT=100
GPU_MAX_HEAP_SIZE=100
PYTORCH_HIP_ALLOC_CONF="backend:native,expandable_segments:True,garbage_collection_threshold:0.9"
```

**NO necesita HSA_OVERRIDE_GFX_VERSION** — TheRock tiene soporte nativo gfx1151.
