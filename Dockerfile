FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HSA_OVERRIDE_GFX_VERSION=11.0.0
ENV PYTORCH_ROCM_ARCH=gfx1100
ENV TZ=Europe/Madrid

# Sistema base
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-pip python3.12-dev \
    ffmpeg \
    git curl wget \
    build-essential \
    libssl-dev libffi-dev \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Alias python
RUN ln -sf /usr/bin/python3.12 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.12 /usr/bin/python

WORKDIR /app

# Venv
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# PyTorch 2.5+ CPU (necesario para RMSNorm y diffusers modernos)
RUN pip install --no-cache-dir \
    torch>=2.5.0 torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Asegurar numpy está disponible
RUN pip install --no-cache-dir numpy>=1.26.0

# Código
COPY . .

# Directorios de datos (se montan como volúmenes)
RUN mkdir -p /app/output/{pending,published,tmp} /app/logs /app/db /app/credentials /app/models /app/assets/music

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

ENTRYPOINT ["python3", "main.py"]
