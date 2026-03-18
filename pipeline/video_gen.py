import os
import torch
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
        self.pipe = self.pipe.to(device)

        # Optimizaciones
        try:
            self.pipe.enable_attention_slicing(slice_size="auto")
        except Exception:
            pass
        try:
            self.pipe.enable_vae_slicing()
        except Exception:
            pass

    def animate(self, image_path: Path, prompt: str, output_path: Path, duration_seconds: int = 5) -> Path:
        self._load()

        image = Image.open(image_path).convert("RGB")
        num_frames = duration_seconds * 16 + 1

        motion_prompt = (
            f"smooth cinematic camera movement, subtle motion, "
            f"professional documentary style, {prompt}"
        )

        print(f"  Animando {image_path.name} → {output_path.name}...")
        with torch.inference_mode():
            output = self.pipe(
                image=image,
                prompt=motion_prompt,
                num_frames=num_frames,
                guidance_scale=5.0,
                num_inference_steps=14,  # Reducido de 20 a 14 — buen balance calidad/velocidad
                height=1920,
                width=1080,
            )

        frames = output.frames[0]
        _export_frames_to_video(frames, output_path, fps=16)
        return output_path


def _export_frames_to_video(frames, output_path: Path, fps: int = 16):
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp())

    for i, frame in enumerate(frames):
        frame.save(tmp_dir / f"frame_{i:04d}.png")

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(tmp_dir / "frame_%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "fast",  # Más rápido que default
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    for f in tmp_dir.glob("*.png"):
        f.unlink()
    tmp_dir.rmdir()
