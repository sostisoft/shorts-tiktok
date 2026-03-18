import torch
from pathlib import Path


def verify():
    print("=== Verificando modelos ===\n")

    # GPU
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"   VRAM/RAM compartida: {mem:.1f} GB")
    else:
        print("GPU no detectada — corriendo en CPU (lento)")

    # FLUX (via diffusers cache)
    flux_cache = Path.home() / ".cache/huggingface/hub"
    flux_exists = any(flux_cache.glob("*flux*")) if flux_cache.exists() else False
    print(f"\nFLUX.1 schnell: {'en caché' if flux_exists else 'se descarga al primer uso'}")

    # Wan2.1
    wan_path = Path("models/wan21")
    wan_files = list(wan_path.glob("*.safetensors")) if wan_path.exists() else []
    print(f"Wan2.1 I2V: {len(wan_files)} ficheros safetensors")

    # Kokoro
    try:
        from kokoro_onnx import Kokoro
        print("Kokoro TTS: instalado")
    except ImportError:
        print("Kokoro TTS: pip install kokoro-onnx")

    # ffmpeg
    import subprocess
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    ok = result.returncode == 0
    print(f"ffmpeg: {'instalado' if ok else 'no encontrado'}")


if __name__ == "__main__":
    verify()
