import os
import torch
from diffusers import FluxPipeline
from pathlib import Path


class ImageGenerator:
    def __init__(self, model="dev"):
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
            pass  # Already set or parallel work started

        # Login to HuggingFace for gated models (FLUX)
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

        # dev: 20-30 steps, guidance 3.5 | schnell: 4 steps, guidance 0
        self.steps = 25 if self.model == "dev" else 4
        self.guidance = 3.5 if self.model == "dev" else 0.0

        print(f"Cargando {model_id} ({device}, {dtype}, {n_threads} threads)...")
        self.pipe = FluxPipeline.from_pretrained(
            model_id,
            torch_dtype=dtype,
        )
        self.pipe = self.pipe.to(device)

        try:
            self.pipe.enable_attention_slicing(slice_size="auto")
        except Exception:
            pass
        try:
            self.pipe.enable_vae_slicing()
        except Exception:
            pass

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

            print(f"  Generando imagen {i+1}/{len(prompts)}...")
            with torch.inference_mode():
                image = self.pipe(
                    prompt=full_prompt,
                    num_inference_steps=self.steps,
                    guidance_scale=self.guidance,
                    height=1920,
                    width=1080,
                ).images[0]

            path = output_dir / f"img_{i:02d}.png"
            image.save(path)
            paths.append(path)

        return paths


    def generate_single(self, prompt: str, output_path: str = None,
                        width: int = 1080, height: int = 1920,
                        steps: int = None, guidance: float = None) -> str:
        """Genera una sola imagen bajo demanda."""
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
