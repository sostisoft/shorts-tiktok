"""
Generador de música de fondo por vídeo usando MusicGen (Meta).
Genera ~17s de música adecuada al tema del vídeo.
Modelo: facebook/musicgen-small (~300MB). Usa GPU si disponible.
"""
import os
import torch
import logging
from pathlib import Path

logger = logging.getLogger("videobot")


class MusicGenerator:
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None

    def _load(self):
        if self.model is not None:
            return

        n_threads = min(os.cpu_count() or 16, 16)
        torch.set_num_threads(n_threads)

        use_gpu = torch.cuda.is_available()
        self.device = "cuda" if use_gpu else "cpu"
        dtype = torch.bfloat16 if use_gpu else torch.float32

        logger.info(f"Cargando MusicGen small ({self.device}, {dtype}, {n_threads} threads)...")
        from transformers import AutoProcessor, MusicgenForConditionalGeneration

        self.processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
        self.model = MusicgenForConditionalGeneration.from_pretrained(
            "facebook/musicgen-small",
            torch_dtype=dtype,
        ).to(self.device)
        self.model.eval()

    def generate(self, topic: str, style: str, output_path: Path, duration_seconds: int = 17) -> Path:
        self._load()

        music_prompt = (
            f"upbeat energetic background music for short video about {topic}, "
            f"{style} style, catchy beat, modern production, "
            f"corporate pop, motivational, dopamine-inducing rhythm, "
            f"no vocals, clean mix, 120 bpm"
        )

        logger.info(f"Generando música ({self.device}): {music_prompt[:80]}...")

        inputs = self.processor(
            text=[music_prompt],
            padding=True,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        max_tokens = duration_seconds * 50

        with torch.inference_mode():
            audio_values = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
            )

        import soundfile as sf
        sampling_rate = self.model.config.audio_encoder.sampling_rate
        audio = audio_values[0, 0].cpu().numpy()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, sampling_rate)

        logger.info(f"Música generada: {output_path} ({duration_seconds}s)")
        return output_path
