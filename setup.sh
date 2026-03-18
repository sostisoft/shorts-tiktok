#!/bin/bash
set -e
echo "=== VideoBot Finanzas Claras — Setup ==="

# 1. Sistema base
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    ffmpeg \
    git curl wget \
    build-essential \
    libssl-dev libffi-dev \
    pkg-config \
    htop nvtop

# 2. ROCm 6.1 para AMD Ryzen AI MAX+ 395
wget https://repo.radeon.com/amdgpu-install/6.1/ubuntu/noble/amdgpu-install_6.1.60100-1_all.deb
sudo dpkg -i amdgpu-install_6.1.60100-1_all.deb
sudo apt update

sudo amdgpu-install --usecase=rocm --no-dkms -y

sudo usermod -aG render,video $USER

echo 'export PATH=$PATH:/opt/rocm/bin' >> ~/.bashrc
echo 'export HSA_OVERRIDE_GFX_VERSION=11.0.0' >> ~/.bashrc
echo 'export PYTORCH_ROCM_ARCH=gfx1100' >> ~/.bashrc
source ~/.bashrc

rocm-smi || echo "Reiniciar el sistema si rocm-smi falla"

# 4. Entorno virtual Python
python3.11 -m venv venv
source venv/bin/activate

# 5. PyTorch con ROCm
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm6.1

# 6. Dependencias del bot
pip install \
    anthropic>=0.40.0 \
    apscheduler>=3.10.0 \
    sqlalchemy>=2.0.0 \
    pyyaml>=6.0 \
    python-dotenv>=1.0.0 \
    requests>=2.31.0 \
    diffusers>=0.30.0 \
    transformers>=4.44.0 \
    accelerate>=0.33.0 \
    sentencepiece \
    protobuf \
    opencv-python \
    Pillow>=10.0.0 \
    imagehash>=4.3.0 \
    google-api-python-client>=2.100.0 \
    google-auth-httplib2>=0.2.0 \
    google-auth-oauthlib>=1.1.0 \
    kokoro>=0.9.4 \
    soundfile \
    numpy

# 7. Crear estructura de directorios
mkdir -p {credentials,models/{flux,wan21,kokoro},output/{pending,published,tmp},logs,db,config}

# 8. Copiar .env.example
cat > .env.example << 'EOF'
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google / YouTube
GOOGLE_CLIENT_ID=449567324847-ki02nto6eu211qb8g45euool9jqettss.apps.googleusercontent.com
GOOGLE_PROJECT_ID=finanzas-oc-yt
YT_CHANNEL_ID=UC...
YT_CREDENTIALS_FILE=credentials/yt_finanzas.json

# Rutas modelos
FLUX_MODEL=black-forest-labs/FLUX.1-schnell
WAN21_MODEL=models/wan21
KOKORO_VOICE=af_sarah

# Config bot
VIDEOS_PER_DAY=2
TMP_DIR=output/tmp
OUTPUT_DIR=output/published
PENDING_DIR=output/pending
DB_PATH=db/videobot.db
EOF

cp .env.example .env
echo ""
echo "Setup completo."
echo "Edita .env con tus valores reales"
echo "Reinicia el sistema para activar ROCm: sudo reboot"
