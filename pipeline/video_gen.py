"""
pipeline/video_gen.py
Wan2.1 I2V via diffusers — genera clips de vídeo a partir de imágenes.
- Modelo: Wan2.1-I2V-14B-480P (en models/wan21/)
- pipe.to("cuda") directo — 128 GB UMA es suficiente para 480x832
- ROCm gfx1151: math SDPA only, VAE float32
"""
import gc
import logging
import os
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import io
import time
import torch
import numpy as np
import subprocess
from pathlib import Path
from PIL import Image

logger = logging.getLogger("videobot.video_gen")

# Ruta al modelo — se puede override con env var
WAN21_MODEL_PATH = os.getenv("WAN21_MODEL_PATH", "models/wan21")


class VideoGenerator:
    def __init__(self):
        self.pipe = None

    def _load(self):
        if self.pipe is not None:
            return

        n_threads = min(os.cpu_count() or 16, 16)
        torch.set_num_threads(n_threads)
        try:
            torch.set_num_interop_threads(max(1, n_threads // 2))
        except RuntimeError:
            pass

        # Limpiar GPU antes de cargar
        gc.collect()
        torch.cuda.empty_cache()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16

        logger.info(f"Cargando Wan2.1 I2V ({device}, {dtype})...")

        # ROCm gfx1151: solo math SDPA (flash/efficient no tienen kernels para VAE)
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        torch.backends.cuda.enable_math_sdp(True)

        from diffusers import WanImageToVideoPipeline
        model_path = WAN21_MODEL_PATH
        self.pipe = WanImageToVideoPipeline.from_pretrained(
            model_path,
            torch_dtype=dtype,
        )

        # UMA 128 GB: pipe.to("cuda") directo — NUNCA cpu_offload (lentísimo)
        self.pipe = self.pipe.to("cuda")

        # VAE en float32 — más estable en ROCm
        self.pipe.vae = self.pipe.vae.to(dtype=torch.float32)

        # Reducir pico de memoria en attention
        self.pipe.enable_attention_slicing(1)
        try:
            self.pipe.vae.enable_tiling()
            self.pipe.vae.enable_slicing()
        except Exception:
            pass

        logger.info("Wan2.1 listo")

    def unload(self):
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Wan2.1 descargado de VRAM")

    def animate(self, image_path: Path, prompt: str, output_path: Path, duration_seconds: int = 5) -> Path:
        self._load()

        image = Image.open(image_path).convert("RGB")
        # 480x832 portrait (9:16) — resolución nativa Wan2.1
        # Wan2.1 14B: attention cuadrática en frames
        # 25 frames (~1.5s) es el sweet spot para 128GB UMA + velocidad razonable
        max_frames = 25
        num_frames = min(duration_seconds * 16 + 1, max_frames)

        motion_prompt = (
            f"smooth cinematic camera movement, subtle motion, "
            f"professional documentary style, {prompt}"
        )

        total_steps = 6  # 6 steps suficiente para calidad Shorts (vs 15)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"  Animando {image_path.name} → {output_path.name} "
                     f"(480x832, {num_frames}f, {total_steps} steps)...")

        t0 = time.time()

        def _progress(pipe, step, timestep, kwargs):
            elapsed = time.time() - t0
            per_step = elapsed / (step + 1) if step >= 0 else 0
            remaining = per_step * (total_steps - step - 1)
            logger.info(f"    Step {step+1}/{total_steps} "
                        f"({per_step:.0f}s/step, ~{remaining/60:.1f}min restantes)")
            return kwargs

        with torch.inference_mode():
            output = self.pipe(
                image=image,
                prompt=motion_prompt,
                num_frames=num_frames,
                guidance_scale=5.0,
                num_inference_steps=total_steps,
                height=832,
                width=480,
                callback_on_step_end=_progress,
            )

        elapsed = time.time() - t0
        logger.info(f"  Clip generado en {elapsed/60:.1f} min")

        frames = output.frames[0]
        _export_frames_pipe(frames, output_path, fps=16)
        return output_path


def _to_pil_frames(frames) -> list:
    if isinstance(frames, torch.Tensor):
        frames = frames.cpu().numpy()
    if isinstance(frames, np.ndarray):
        if frames.ndim == 4 and frames.shape[-1] not in (1, 3, 4):
            frames = frames.transpose(0, 2, 3, 1)
        elif frames.ndim == 3 and frames.shape[0] in (1, 3, 4) and frames.shape[0] < frames.shape[1]:
            frames = frames.transpose(1, 2, 0)
            frames = frames[np.newaxis]
        if frames.dtype in (np.float16, np.float32, np.float64):
            frames = (frames * 255).clip(0, 255).astype(np.uint8)
        elif frames.dtype != np.uint8:
            frames = frames.astype(np.uint8)
        return [Image.fromarray(f) for f in frames]
    if hasattr(frames, '__iter__'):
        frame_list = list(frames)
        if frame_list and isinstance(frame_list[0], Image.Image):
            return frame_list
    raise ValueError(f"Formato de frames no soportado: type={type(frames)}")


def _export_frames_pipe(frames, output_path: Path, fps: int = 16):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pil_frames = _to_pil_frames(frames)
    w, h = pil_frames[0].size
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "fast",
        str(output_path)
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for frame in pil_frames:
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read().decode()
        raise RuntimeError(f"ffmpeg failed: {err}")
