import torch
from diffusers import FluxPipeline
from pathlib import Path


class ImageGenerator:
    def __init__(self):
        self.pipe = None

    def _load(self):
        if self.pipe is not None:
            return
        print("Cargando FLUX.1 schnell...")
        self.pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-schnell",
            torch_dtype=torch.bfloat16,
        )
        # ROCm: usar cuda (ROCm expone interfaz CUDA)
        if torch.cuda.is_available():
            self.pipe = self.pipe.to("cuda")
        else:
            self.pipe.enable_model_cpu_offload()

    def generate(self, prompts: list[str], job_id: str, output_dir: Path) -> list[Path]:
        """
        Genera una imagen por prompt.
        Devuelve lista de rutas de imágenes generadas.
        """
        self._load()
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for i, prompt in enumerate(prompts):
            # Añadir prefijo de calidad al prompt
            full_prompt = (
                f"cinematic photography, ultra realistic, 4K, professional lighting, "
                f"shallow depth of field, {prompt}, "
                f"financial content, modern aesthetic, Spain"
            )

            print(f"  Generando imagen {i+1}/{len(prompts)}...")
            image = self.pipe(
                prompt=full_prompt,
                num_inference_steps=4,   # schnell = 4 steps
                guidance_scale=0.0,      # schnell no usa CFG
                height=1920,
                width=1080,
            ).images[0]

            path = output_dir / f"img_{i:02d}.png"
            image.save(path)
            paths.append(path)

        return paths
