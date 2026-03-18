"""Descarga modelos IA necesarios para el pipeline."""
import logging
from pathlib import Path
from huggingface_hub import snapshot_download

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("download")


def main():
    # 1. FLUX.1 schnell — se descarga automáticamente via diffusers al primer uso
    logger.info("FLUX.1 schnell se descargará al primer uso (vía diffusers cache)")

    # 2. Wan2.1 I2V 14B 480P
    wan_path = Path("models/wan21")
    if list(wan_path.glob("*.safetensors")) if wan_path.exists() else []:
        logger.info("Wan2.1 ya descargado, saltando")
    else:
        logger.info("Descargando Wan2.1 I2V 14B 480P Diffusers (~27GB)...")
        snapshot_download(
            "Wan-AI/Wan2.1-I2V-14B-480P-Diffusers",
            local_dir=str(wan_path),
            allow_patterns=["*.safetensors", "*.json", "*.txt", "*.model"],
        )
        logger.info("Wan2.1 descargado")

    # 3. Kokoro TTS — se descarga al primer uso
    logger.info("Kokoro TTS se descargará al primer uso")

    logger.info("Descarga de modelos completada")


if __name__ == "__main__":
    main()
