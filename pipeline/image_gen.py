"""
pipeline/image_gen.py
Generador de imágenes con FLUX.1-schnell via diffusers.
- pipe.to("cuda") siempre — memoria UMA, nunca cpu_offload
- Descarga el modelo tras cada uso para liberar GTT a Wan2GP
"""
import gc
import logging
import os
from pathlib import Path

import torch
from diffusers import FluxPipeline
from PIL import Image

logger = logging.getLogger("videobot.image_gen")

# Ruta local del modelo (si ya descargado) o HF hub id
FLUX_MODEL_ID = os.getenv("FLUX_MODEL_ID", "black-forest-labs/FLUX.1-schnell")
FLUX_LOCAL_PATH = Path(os.getenv("FLUX_LOCAL_PATH", "/app/models/flux-schnell"))


class ImageGenerator:
    def __init__(self, model: str = "schnell"):
        self.model_id = FLUX_MODEL_ID
        self.pipe = None

    # ── Carga / descarga ──────────────────────────────────────────────────────

    def _load(self):
        if self.pipe is not None:
            return
        logger.info("Cargando FLUX.1-schnell...")
        local = FLUX_LOCAL_PATH if FLUX_LOCAL_PATH.exists() else self.model_id
        self.pipe = FluxPipeline.from_pretrained(
            str(local),
            torch_dtype=torch.bfloat16,
        )
        # pipe.to("cuda") — NUNCA enable_model_cpu_offload() en UMA
        self.pipe = self.pipe.to("cuda")
        logger.info("FLUX listo en GPU")

    def _unload(self):
        if self.pipe is None:
            return
        logger.info("Descargando FLUX de GPU...")
        del self.pipe
        self.pipe = None
        gc.collect()
        torch.cuda.empty_cache()
        logger.info("GPU liberada")

    # ── Generación ────────────────────────────────────────────────────────────

    def generate_single(
        self,
        prompt: str,
        output_path: str | None = None,
        width: int = 1080,
        height: int = 1920,
        steps: int = 4,          # schnell funciona bien con 4 steps
        guidance: float = 0.0,   # schnell no usa guidance
    ) -> Path:
        """Genera una imagen y la guarda. Devuelve la ruta."""
        self._load()
        try:
            logger.info(f"Generando imagen {width}×{height}, {steps} steps...")
            result = self.pipe(
                prompt=prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance,
                output_type="pil",
            )
            image: Image.Image = result.images[0]

            if output_path is None:
                out_dir = Path("output/tmp")
                out_dir.mkdir(parents=True, exist_ok=True)
                output_path = out_dir / f"frame_{os.urandom(4).hex()}.png"
            else:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)

            image.save(str(output_path), format="PNG")
            logger.info(f"Imagen guardada: {output_path}")
            return output_path

        finally:
            self._unload()

    def generate_batch(
        self,
        prompts: list[str],
        output_dir: str | Path = "output/tmp",
        width: int = 1080,
        height: int = 1920,
        steps: int = 4,
    ) -> list[Path]:
        """Genera varias imágenes en una sola carga del modelo."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        paths = []
        try:
            for i, prompt in enumerate(prompts):
                logger.info(f"Imagen {i+1}/{len(prompts)}: {prompt[:60]}...")
                result = self.pipe(
                    prompt=prompt,
                    width=width,
                    height=height,
                    num_inference_steps=steps,
                    guidance_scale=0.0,
                    output_type="pil",
                )
                path = output_dir / f"frame_{i:02d}_{os.urandom(3).hex()}.png"
                result.images[0].save(str(path), format="PNG")
                paths.append(path)
                logger.info(f"  → {path}")
        finally:
            self._unload()
        return paths
