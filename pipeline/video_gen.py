import gc
import os
import io
import torch
import numpy as np
import subprocess
from pathlib import Path
from PIL import Image


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

        use_gpu = torch.cuda.is_available()
        device = "cuda" if use_gpu else "cpu"
        dtype = torch.bfloat16

        print(f"Cargando Wan2.1 I2V ({device}, {dtype}, {n_threads} threads)...")
        from diffusers import WanImageToVideoPipeline
        self.pipe = WanImageToVideoPipeline.from_pretrained(
            "models/wan21",
            torch_dtype=dtype,
        )
        # UMA (Strix Halo): NUNCA usar cpu_offload — causa SVM thrashing
        self.pipe.to("cuda")

        # Attention slicing reduce pico de memoria en self-attention de video
        try:
            self.pipe.enable_attention_slicing(slice_size="auto")
        except Exception:
            pass

        # VAE tiling (reduce peak VRAM during decode)
        try:
            self.pipe.vae.enable_tiling()
        except Exception:
            pass

    def unload(self):
        """Libera VRAM para que otros modelos puedan usarla."""
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("Wan2.1 descargado de VRAM")

    def animate(self, image_path: Path, prompt: str, output_path: Path, duration_seconds: int = 5) -> Path:
        self._load()

        image = Image.open(image_path).convert("RGB")
        # 480x832 portrait (9:16) — resolución nativa de Wan2.1, mucho más rápido que 1080x1920
        # Se upscalea después con ffmpeg si hace falta
        num_frames = duration_seconds * 16 + 1  # 81 frames for 5s@16fps

        motion_prompt = (
            f"smooth cinematic camera movement, subtle motion, "
            f"professional documentary style, {prompt}"
        )

        total_steps = 10
        print(f"  Animando {image_path.name} → {output_path.name} (480x832, {num_frames}f, {total_steps} steps)...", flush=True)

        def _progress(pipe, step, timestep, kwargs):
            pct = int((step + 1) / total_steps * 100)
            print(f"    Step {step+1}/{total_steps} ({pct}%)", flush=True)
            return kwargs

        # Forzar flash/memory-efficient attention en ROCm — evita materializar
        # la matriz de atención completa (160GB con attention nativa)
        with torch.inference_mode(), \
             torch.backends.cuda.sdp_kernel(
                 enable_flash=True,
                 enable_mem_efficient=True,
                 enable_math=False,
             ):
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

        frames = output.frames[0]
        _export_frames_pipe(frames, output_path, fps=16)
        return output_path


def _to_pil_frames(frames) -> list:
    """Convierte frames a lista de PIL Images independientemente del formato de salida."""
    # Torch tensor → numpy primero
    if isinstance(frames, torch.Tensor):
        frames = frames.cpu().numpy()

    if isinstance(frames, np.ndarray):
        # Si es CHW (C, H, W) o (N, C, H, W) → transponer a HWC
        if frames.ndim == 4 and frames.shape[-1] not in (1, 3, 4):
            # (N, C, H, W) → (N, H, W, C)
            frames = frames.transpose(0, 2, 3, 1)
        elif frames.ndim == 3 and frames.shape[0] in (1, 3, 4) and frames.shape[0] < frames.shape[1]:
            # (C, H, W) → (H, W, C) — un solo frame
            frames = frames.transpose(1, 2, 0)
            frames = frames[np.newaxis]  # añadir dim batch

        # Normalizar a uint8
        if frames.dtype == np.float16 or frames.dtype == np.float32 or frames.dtype == np.float64:
            # diffusers output_type='np' devuelve floats 0.0-1.0
            frames = (frames * 255).clip(0, 255).astype(np.uint8)
        elif frames.dtype != np.uint8:
            frames = frames.astype(np.uint8)

        return [Image.fromarray(f) for f in frames]

    # Ya son PIL Images (output_type='pil')
    if hasattr(frames, '__iter__'):
        frame_list = list(frames)
        if frame_list and isinstance(frame_list[0], Image.Image):
            return frame_list

    raise ValueError(f"Formato de frames no soportado: type={type(frames)}")


def _export_frames_pipe(frames, output_path: Path, fps: int = 16):
    """Exporta frames directamente a ffmpeg via pipe (sin escribir PNGs a disco)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pil_frames = _to_pil_frames(frames)
    w, h = pil_frames[0].size

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{w}x{h}",
        "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "fast",
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
