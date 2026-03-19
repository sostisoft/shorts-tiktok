"""
pipeline/kenburns.py
Genera clips de vídeo con efecto Ken Burns (zoom/pan suave) sobre imágenes estáticas.
Alternativa a Wan2.1 I2V: sin artefactos, sin GPU, instantáneo.
"""
import logging
import os
import random
import subprocess
from pathlib import Path

logger = logging.getLogger("videobot.kenburns")

# Efectos disponibles — cada uno es un filtro FFmpeg zoompan
EFFECTS = [
    # Zoom in lento al centro
    "zoompan=z='min(zoom+0.0015,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Zoom in a la parte superior
    "zoompan=z='min(zoom+0.0015,1.3)':x='iw/2-(iw/zoom/2)':y='if(eq(on,0),0,y)':d={frames}:s={w}x{h}:fps={fps}",
    # Zoom out desde el centro
    "zoompan=z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Pan izquierda a derecha
    "zoompan=z='1.15':x='if(lte(on,1),0,x+1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Pan derecha a izquierda
    "zoompan=z='1.15':x='if(lte(on,1),iw,x-1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Zoom in a esquina inferior derecha
    "zoompan=z='min(zoom+0.0015,1.3)':x='iw-(iw/zoom)':y='ih-(ih/zoom)':d={frames}:s={w}x{h}:fps={fps}",
]


class KenBurnsGenerator:
    """Genera clips de vídeo con efecto Ken Burns sobre imágenes estáticas."""

    def __init__(self, fps: int = 24, width: int = 1080, height: int = 1920):
        self.fps = fps
        self.width = width
        self.height = height

    def animate(
        self,
        image_path: Path,
        prompt: str,
        output_path: Path,
        duration_seconds: int = 5,
    ) -> Path:
        """
        Genera un clip con efecto Ken Burns sobre una imagen.
        El prompt se ignora (solo se usa para logging).
        """
        image_path = Path(image_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        frames = duration_seconds * self.fps
        effect = random.choice(EFFECTS).format(
            frames=frames, w=self.width, h=self.height, fps=self.fps
        )

        logger.info(f"  Ken Burns: {image_path.name} → {output_path.name} "
                     f"({self.width}x{self.height}, {duration_seconds}s)")

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-vf", effect,
            "-t", str(duration_seconds),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            "-preset", "fast",
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg Ken Burns error: {result.stderr[-500:]}")
            raise RuntimeError(f"Ken Burns falló: {result.stderr[-200:]}")

        logger.info(f"  Clip generado → {output_path}")
        return output_path

    def unload(self):
        """No-op — Ken Burns no usa GPU ni modelos."""
        pass
