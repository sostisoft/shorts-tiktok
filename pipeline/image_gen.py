import gc
import os
import torch
from diffusers import FluxPipeline
from pathlib import Path


class ImageGenerator:
    def __init__(self, model="schnell"):
        self.pipe = None
        self.model = model

    def _load(self):
        if self.pipe is not None:
            return

        n_threads = min(os.cpu_count() or 16, 16)
        torch.set_num_threads(n_threads)
        try:
            torch.set_num_interop_threads(max(1, n_threads // 2))
        except RuntimeError:
            pass

        hf_token = os.environ.get("HF_TOKEN")
        if hf_token:
            try:
                from huggingface_hub import login
                login(token=hf_token, add_to_git_credential=False)
            except Exception:
                pass

        use_gpu = torch.cuda.is_available()
        device = "cuda" if use_gpu else "cpu"
        dtype = torch.bfloat16

        model_id = {
            "dev": "black-forest-labs/FLUX.1-dev",
            "schnell": "black-forest-labs/FLUX.1-schnell",
        }[self.model]

        self.steps = 25 if self.model == "dev" else 4
        self.guidance = 3.5 if self.model == "dev" else 0.0

        print(f"Cargando {model_id} ({device}, {dtype}, {n_threads} threads)...")
        self.pipe = FluxPipeline.from_pretrained(
            model_id,
            torch_dtype=dtype,
        )

        # UMA (Strix Halo): cargar directo a GPU — cpu_offload causa SVM thrashing
        # La memoria es físicamente compartida, las copias CPU↔GPU son redundantes
        self.pipe.to(device)

        # VAE tiling (helps with large images, minimal overhead)
        try:
            self.pipe.vae.enable_slicing()
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
            print("FLUX descargado de VRAM")

    def generate(self, prompts: list[str], job_id: str, output_dir: Path) -> list[Path]:
        self._load()
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for i, prompt in enumerate(prompts):
            full_prompt = (
                f"cinematic photography, ultra realistic, 4K, professional lighting, "
                f"shallow depth of field, {prompt}, "
                f"financial content, modern aesthetic, Spain"
            )

            print(f"  Generando imagen {i+1}/{len(prompts)}...", flush=True)
            with torch.inference_mode():
                image = self.pipe(
                    prompt=full_prompt,
                    num_inference_steps=self.steps,
                    guidance_scale=self.guidance,
                    height=1344,
                    width=768,
                ).images[0]

            path = output_dir / f"img_{i:02d}.png"
            image.save(path)
            paths.append(path)

        return paths

    def generate_single(self, prompt: str, output_path: str = None,
                        width: int = 768, height: int = 1344,
                        steps: int = None, guidance: float = None) -> str:
        self._load()
        steps = steps or self.steps
        guidance = guidance if guidance is not None else self.guidance

        if output_path is None:
            output_path = f"/home/gmktec/shorts/output/ondemand/img_{id(prompt) % 100000:05d}.png"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        print(f"Generando: {prompt[:80]}...")
        with torch.inference_mode():
            image = self.pipe(
                prompt=prompt,
                num_inference_steps=steps,
                guidance_scale=guidance,
                height=height,
                width=width,
            ).images[0]

        image.save(output_path)
        print(f"Guardada en: {output_path}")
        return output_path
