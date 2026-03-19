"""
pipeline/music_gen.py
Genera música de fondo con MusicGen (Meta) local.
Modelo "small" (~300 MB) corre en CPU/GPU — se descarga el modelo tras usarlo.
"""
import gc
import logging
import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

logger = logging.getLogger("videobot.music_gen")

# Usar CPU para no competir con GPU durante video; cambiar a "cuda" si se usa después
MUSIC_DEVICE = os.getenv("MUSIC_DEVICE", "cpu")
MUSIC_MODEL = os.getenv("MUSIC_MODEL", "facebook/musicgen-small")

# Prompts temáticos para finanzas personales
FINANCE_MUSIC_PROMPTS = [
    "corporate upbeat electronic background music, professional, positive energy, no vocals",
    "motivational piano loop, modern finance, uplifting, instrumental, clean",
    "ambient electronic beat, money mindset, focus, subtle bass, no lyrics",
    "inspiring orchestral corporate background, wealth growth, cinematic light",
    "smooth lofi hip hop, productivity, finance focus, calm, no vocals",
]


class MusicGenerator:
    def __init__(self, model: str = MUSIC_MODEL, device: str = MUSIC_DEVICE):
        self.model_id = model
        self.device = device
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is not None:
            return
        logger.info(f"Cargando MusicGen ({self.model_id}) en {self.device}...")
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        self._processor = AutoProcessor.from_pretrained(self.model_id)
        self._model = MusicgenForConditionalGeneration.from_pretrained(self.model_id)
        self._model = self._model.to(self.device)
        logger.info("MusicGen listo")

    def _unload(self):
        if self._model is None:
            return
        del self._model, self._processor
        self._model = self._processor = None
        gc.collect()
        if self.device == "cuda":
            torch.cuda.empty_cache()
        logger.info("MusicGen descargado")

    def generate(
        self,
        prompt: str | None = None,
        duration_seconds: float = 35.0,
        output_path: str | Path | None = None,
    ) -> Path:
        """
        Genera música de fondo.

        Args:
            prompt:           Descripción del estilo musical. None = prompt de finanzas aleatorio
            duration_seconds: Duración en segundos (idealmente = duración del video + 2s)
            output_path:      Dónde guardar el .wav

        Returns:
            Path al .wav generado
        """
        if prompt is None:
            import random
            prompt = random.choice(FINANCE_MUSIC_PROMPTS)

        if output_path is None:
            out_dir = Path("output/tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"music_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self._load()
        t0 = time.time()
        try:
            # MusicGen genera ~256 tokens/segundo de audio a 32 kHz
            # max_new_tokens = duration * 50 (aprox para musicgen-small)
            max_tokens = int(duration_seconds * 50)

            inputs = self._processor(
                text=[prompt],
                padding=True,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                audio_values = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    do_sample=True,
                    guidance_scale=3.0,
                )

            # Convertir a numpy y guardar
            audio = audio_values[0, 0].cpu().numpy()
            sample_rate = self._model.config.audio_encoder.sampling_rate
            sf.write(str(output_path), audio, samplerate=sample_rate)

            logger.info(
                f"Música generada en {time.time()-t0:.0f}s "
                f"({len(audio)/sample_rate:.1f}s de audio) → {output_path}"
            )
            return output_path

        finally:
            self._unload()
