"""
Generador de música de fondo por vídeo usando MusicGen (Meta).
Genera ~17s de música adecuada al tema del vídeo.
Modelo: facebook/musicgen-small (~300MB, funciona en CPU).
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

    def _load(self):
        if self.model is not None:
            return

        n_threads = min(os.cpu_count() or 16, 16)
        torch.set_num_threads(n_threads)

        logger.info(f"Cargando MusicGen small (CPU, {n_threads} threads)...")
        from transformers import AutoProcessor, MusicgenForConditionalGeneration

        self.processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
        self.model = MusicgenForConditionalGeneration.from_pretrained(
            "facebook/musicgen-small",
            torch_dtype=torch.float32,
        )
        self.model.eval()

    def generate(self, topic: str, style: str, output_path: Path, duration_seconds: int = 17) -> Path:
        """
        Genera música de fondo que encaje con el tema del vídeo.
        Siempre genera música que engancha: ritmo, energía, dopamina.
        """
        self._load()

        # Prompt diseñado para generar música que engancha
        music_prompt = (
            f"upbeat energetic background music for short video about {topic}, "
            f"{style} style, catchy beat, modern production, "
            f"corporate pop, motivational, dopamine-inducing rhythm, "
            f"no vocals, clean mix, 120 bpm"
        )

        logger.info(f"Generando música: {music_prompt[:80]}...")

        inputs = self.processor(
            text=[music_prompt],
            padding=True,
            return_tensors="pt",
        )

        # MusicGen genera a 32kHz, calcular tokens necesarios
        # ~50 tokens por segundo de audio
        max_tokens = duration_seconds * 50

        with torch.inference_mode():
            audio_values = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
            )

        # Guardar como WAV
        import soundfile as sf
        sampling_rate = self.model.config.audio_encoder.sampling_rate
        audio = audio_values[0, 0].cpu().numpy()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, sampling_rate)

        logger.info(f"Música generada: {output_path} ({duration_seconds}s)")
        return output_path
