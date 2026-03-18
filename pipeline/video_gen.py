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
        print("Cargando Wan2.1 I2V...")
        from diffusers import WanImageToVideoPipeline
        self.pipe = WanImageToVideoPipeline.from_pretrained(
            "models/wan21",
            torch_dtype=torch.bfloat16,
        )
        if torch.cuda.is_available():
            self.pipe = self.pipe.to("cuda")
        else:
            self.pipe.enable_model_cpu_offload()

    def animate(self, image_path: Path, prompt: str, output_path: Path, duration_seconds: int = 5) -> Path:
        """
        Anima una imagen estática → clip de vídeo.
        duration_seconds: 3-5 segundos por clip.
        """
        self._load()

        image = Image.open(image_path).convert("RGB")
        num_frames = duration_seconds * 16 + 1  # 16fps + 1

        # Prompt de movimiento: sutil, cinematográfico
        motion_prompt = (
            f"smooth cinematic camera movement, subtle motion, "
            f"professional documentary style, {prompt}"
        )

        print(f"  Animando {image_path.name} → {output_path.name}...")
        output = self.pipe(
            image=image,
            prompt=motion_prompt,
            num_frames=num_frames,
            guidance_scale=5.0,
            num_inference_steps=20,
            height=1920,
            width=1080,
        )

        # Exportar frames como vídeo
        frames = output.frames[0]
        _export_frames_to_video(frames, output_path, fps=16)
        return output_path


def _export_frames_to_video(frames, output_path: Path, fps: int = 16):
    """Exporta lista de PIL Images a MP4 via ffmpeg."""
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
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    # Limpiar frames temporales
    for f in tmp_dir.glob("*.png"):
        f.unlink()
    tmp_dir.rmdir()
