"""
pipeline/image_gen.py
Generador de imágenes con FLUX.1-schnell via diffusers.
- pipe.to("cuda") siempre — memoria UMA, nunca cpu_offload
- Descarga el modelo tras cada uso para liberar GTT a Wan2GP
"""
import gc
import logging
import os
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
from pathlib import Path

import torch
from diffusers import FluxPipeline
from PIL import Image

logger = logging.getLogger("videobot.image_gen")

# Ruta local del modelo (si ya descargado) o HF hub id
FLUX_MODEL_ID = os.getenv("FLUX_MODEL_ID", "black-forest-labs/FLUX.1-schnell")
FLUX_LOCAL_PATH = Path(os.getenv("FLUX_LOCAL_PATH", "models/flux-schnell"))


class ImageGenerator:
    def __init__(self, model: str = "schnell"):
        self.model_id = FLUX_MODEL_ID
        self.pipe = None

    # ── Carga / descarga ──────────────────────────────────────────────────────

    def _load(self):
        if self.pipe is not None:
            return
        logger.info("Cargando FLUX.1-schnell...")
        if FLUX_LOCAL_PATH.exists():
            logger.info(f"  Ruta local: {FLUX_LOCAL_PATH}")
            self.pipe = FluxPipeline.from_pretrained(
                str(FLUX_LOCAL_PATH),
                torch_dtype=torch.bfloat16,
                local_files_only=True,
            )
        else:
            logger.info(f"  Descargando desde HuggingFace: {self.model_id}")
            self.pipe = FluxPipeline.from_pretrained(
                self.model_id,
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

    def _decode_latents_cpu(self, latents, height, width):
        """Decodifica latents con el VAE en CPU — ROCm gfx1151 cuelga en GPU."""
        import numpy as np
        logger.info("  VAE decode en CPU...")
        vae_scale = self.pipe.vae_scale_factor
        # Unpack latents (FLUX empaqueta en formato especial)
        latents = self.pipe._unpack_latents(latents, height, width, vae_scale)
        latents = (latents / self.pipe.vae.config.scaling_factor) + self.pipe.vae.config.shift_factor
        # Mover VAE a CPU para decode
        vae = self.pipe.vae.to("cpu", dtype=torch.float32)
        latents_cpu = latents.to("cpu", dtype=torch.float32)
        with torch.no_grad():
            decoded = vae.decode(latents_cpu, return_dict=False)[0]
        # Volver VAE a GPU para la siguiente imagen
        self.pipe.vae = vae.to("cuda", dtype=torch.bfloat16)
        # Convertir a PIL
        decoded = decoded.squeeze(0).permute(1, 2, 0).numpy()
        decoded = ((decoded + 1) / 2 * 255).clip(0, 255).astype(np.uint8)
        return Image.fromarray(decoded)

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
                output_type="latent",
            )
            # VAE decode en CPU — cuelga en ROCm gfx1151
            image = self._decode_latents_cpu(result.images, height, width)

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
                    output_type="latent",
                )
                image = self._decode_latents_cpu(result.images, height, width)
                path = output_dir / f"frame_{i:02d}_{os.urandom(3).hex()}.png"
                image.save(str(path), format="PNG")
                paths.append(path)
                logger.info(f"  → {path}")
        finally:
            self._unload()
        return paths
