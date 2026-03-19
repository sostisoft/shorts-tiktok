"""
pipeline/video_generator.py
Anima imágenes con Wan2GP I2V + Self-Forcing LoRA (2 steps).
- Llama a Wan2GP como subprocess con los env vars correctos para gfx1151
- ~90-120 segundos por clip de 5s a 480p en Strix Halo
- NO usa diffusers — Wan2GP tiene su propio stack ROCm
"""
import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("videobot.video_gen")

# Ruta donde está clonado Wan2GP
WAN2GP_DIR = Path(os.getenv("WAN2GP_DIR", str(Path.home() / "Wan2GP")))
WAN2GP_VENV = WAN2GP_DIR / "wan2gp-env" / "bin" / "python"

# Variables de entorno para gfx1151 — críticas
_ENV = {
    **os.environ,
    "HSA_OVERRIDE_GFX_VERSION": "11.5.1",
    "HSA_ENABLE_SDMA": "0",
    "GPU_MAX_ALLOC_PERCENT": "100",
    "GPU_MAX_HEAP_SIZE": "100",
    "HSA_XNACK": "1",
    "PYTORCH_HIP_ALLOC_CONF": "backend:native,expandable_segments:True,max_split_size_mb:512",
    "TORCH_BLAS_PREFER_HIPBLASLT": "1",
    "FLASH_ATTENTION_TRITON_AMD_ENABLE": "TRUE",
    "FLASH_ATTENTION_BACKEND": "flash_attn_triton_amd",
}


class VideoGenerator:
    """
    Anima una imagen de entrada con Wan2.1 I2V usando Self-Forcing LoRA.

    Self-Forcing permite solo 2 steps de denoising (sin CFG), lo que da:
    - ~90-120s por clip de 5s (480p) en gfx1151
    - Calidad comparable a 20+ steps normales
    """

    def __init__(
        self,
        model: str = "wan_i2v_1.3B",   # modelo ligero, cabe en ~8 GB GTT
        lora: str = "self_forcing",      # Self-Forcing = 2 steps, máxima velocidad
        steps: int = 2,
        fps: int = 16,
        width: int = 480,
        height: int = 832,               # vertical 9:16 a 480p
        duration_seconds: float = 5.0,
    ):
        self.model = model
        self.lora = lora
        self.steps = steps
        self.fps = fps
        self.width = width
        self.height = height
        self.num_frames = int(duration_seconds * fps)
        self._verify_wan2gp()

    def _verify_wan2gp(self):
        if not WAN2GP_DIR.exists():
            raise RuntimeError(
                f"Wan2GP no encontrado en {WAN2GP_DIR}. "
                "Clona con: git clone https://github.com/deepbeepmeep/Wan2GP.git ~/Wan2GP"
            )
        if not WAN2GP_VENV.exists():
            raise RuntimeError(
                f"Venv de Wan2GP no encontrado en {WAN2GP_VENV}. "
                "Crea con: cd ~/Wan2GP && python -m venv wan2gp-env && source wan2gp-env/bin/activate && "
                "pip install --pre torch torchaudio torchvision rocm[devel] "
                "--index-url https://rocm.nightlies.amd.com/v2/gfx1151/ && pip install -r requirements.txt"
            )

    def animate(
        self,
        image_path: str | Path,
        prompt: str,
        output_path: str | Path | None = None,
    ) -> Path:
        """
        Anima una imagen con Wan2GP I2V.

        Args:
            image_path: Imagen de entrada (PNG/JPG)
            prompt:     Descripción del movimiento deseado
            output_path: Dónde guardar el .mp4 (None = auto en output/tmp/)

        Returns:
            Path al .mp4 generado
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {image_path}")

        if output_path is None:
            out_dir = Path("output/tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"clip_{os.urandom(4).hex()}.mp4"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Script Python inline que Wan2GP ejecutará
        # Usamos la API de Wan2GP si está disponible, o wgp.py como fallback
        script = self._build_script(image_path, prompt, output_path)

        logger.info(f"Iniciando Wan2GP I2V: {image_path.name} → {output_path.name}")
        logger.info(f"  modelo={self.model}, lora={self.lora}, steps={self.steps}, "
                    f"{self.width}×{self.height}, {self.num_frames} frames")

        t0 = time.time()
        result = subprocess.run(
            [str(WAN2GP_VENV), "-c", script],
            cwd=str(WAN2GP_DIR),
            env=_ENV,
            capture_output=False,   # dejar que los logs fluyan al terminal
            timeout=900,            # 15 min máximo por clip
        )

        elapsed = time.time() - t0
        if result.returncode != 0:
            raise RuntimeError(
                f"Wan2GP falló con código {result.returncode} tras {elapsed:.0f}s"
            )

        if not output_path.exists():
            raise RuntimeError(
                f"Wan2GP terminó sin error pero no se encontró el vídeo: {output_path}"
            )

        logger.info(f"Clip generado en {elapsed:.0f}s → {output_path}")
        return output_path

    def animate_batch(
        self,
        images: list[Path],
        prompts: list[str],
        output_dir: str | Path = "output/tmp",
    ) -> list[Path]:
        """
        Anima una lista de imágenes secuencialmente.
        Wan2GP mantiene el modelo en GPU entre clips — más eficiente que llamadas separadas.
        """
        assert len(images) == len(prompts), "Debe haber un prompt por imagen"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Script que procesa todos los clips en una sola carga del modelo
        outputs = [output_dir / f"clip_{i:02d}_{os.urandom(3).hex()}.mp4" for i in range(len(images))]
        script = self._build_batch_script(images, prompts, outputs)

        logger.info(f"Iniciando batch Wan2GP: {len(images)} clips...")
        t0 = time.time()
        result = subprocess.run(
            [str(WAN2GP_VENV), "-c", script],
            cwd=str(WAN2GP_DIR),
            env=_ENV,
            timeout=900 * len(images),
        )
        elapsed = time.time() - t0

        if result.returncode != 0:
            raise RuntimeError(f"Wan2GP batch falló con código {result.returncode}")

        generated = [p for p in outputs if p.exists()]
        logger.info(f"Batch completo: {len(generated)}/{len(images)} clips en {elapsed:.0f}s")
        return generated

    # ── Construcción de scripts ───────────────────────────────────────────────

    def _build_script(self, image_path: Path, prompt: str, output_path: Path) -> str:
        """Genera el script Python para un solo clip."""
        return f"""
import sys
sys.path.insert(0, '.')

# Intentar usar la API interna de Wan2GP (disponible desde v9+)
try:
    from wgp import generate_video
    generate_video(
        model='{self.model}',
        lora='{self.lora}',
        input_image=r'{image_path}',
        prompt={repr(prompt)},
        output_path=r'{output_path}',
        num_steps={self.steps},
        width={self.width},
        height={self.height},
        num_frames={self.num_frames},
        fps={self.fps},
    )
except (ImportError, AttributeError):
    # Fallback: llamada directa al pipeline de diffusión de Wan2GP
    import torch
    from wan.pipeline_wan_i2v import WanI2VPipeline
    from wan.utils.lora_utils import load_lora
    from diffusers.utils import load_image
    import imageio

    print("Cargando modelo Wan2.1 I2V 1.3B...")
    pipe = WanI2VPipeline.from_pretrained(
        'Wan-AI/Wan2.1-I2V-14B-480P',
        torch_dtype=torch.bfloat16,
    ).to('cuda')

    load_lora(pipe, '{self.lora}', strength=1.0)

    image = load_image(r'{image_path}').resize(({self.width}, {self.height}))

    with torch.no_grad():
        output = pipe(
            image=image,
            prompt={repr(prompt)},
            num_frames={self.num_frames},
            num_inference_steps={self.steps},
            height={self.height},
            width={self.width},
            guidance_scale=1.0,  # Self-Forcing no necesita CFG
        )

    frames = output.frames[0]
    imageio.mimwrite(r'{output_path}', frames, fps={self.fps}, quality=8)
    del pipe
    import gc
    gc.collect()
    import torch as t
    t.cuda.empty_cache()
    print(f"Clip guardado: {output_path}")
"""

    def _build_batch_script(
        self, images: list[Path], prompts: list[str], outputs: list[Path]
    ) -> str:
        """Genera el script Python para un batch de clips (una sola carga del modelo)."""
        items = list(zip(images, prompts, outputs))
        items_repr = repr([(str(img), pmt, str(out)) for img, pmt, out in items])

        return f"""
import sys, gc, torch
sys.path.insert(0, '.')

items = {items_repr}

try:
    from wgp import generate_video
    for img_path, prompt, out_path in items:
        generate_video(
            model='{self.model}',
            lora='{self.lora}',
            input_image=img_path,
            prompt=prompt,
            output_path=out_path,
            num_steps={self.steps},
            width={self.width},
            height={self.height},
            num_frames={self.num_frames},
            fps={self.fps},
        )
        print(f"Clip generado: {{out_path}}")
except (ImportError, AttributeError):
    from wan.pipeline_wan_i2v import WanI2VPipeline
    from wan.utils.lora_utils import load_lora
    from diffusers.utils import load_image
    import imageio

    pipe = WanI2VPipeline.from_pretrained(
        'Wan-AI/Wan2.1-I2V-14B-480P',
        torch_dtype=torch.bfloat16,
    ).to('cuda')
    load_lora(pipe, '{self.lora}', strength=1.0)

    for img_path, prompt, out_path in items:
        image = load_image(img_path).resize(({self.width}, {self.height}))
        with torch.no_grad():
            output = pipe(
                image=image,
                prompt=prompt,
                num_frames={self.num_frames},
                num_inference_steps={self.steps},
                height={self.height},
                width={self.width},
                guidance_scale=1.0,
            )
        imageio.mimwrite(out_path, output.frames[0], fps={self.fps}, quality=8)
        print(f"Clip generado: {{out_path}}")

    del pipe
    gc.collect()
    torch.cuda.empty_cache()
"""
