"""
pipeline/tts.py
Text-to-Speech con Chatterbox (23 idiomas, clonación de voz).
Corre 100% en CPU — no compite con GPU durante la generación de video.
"""
import logging
import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger("videobot.tts")

# Voz por defecto: español de España (neutro, profesional)
DEFAULT_VOICE = os.getenv("TTS_VOICE", "es")
VOICE_SAMPLE = os.getenv("TTS_VOICE_SAMPLE", "")  # Ruta a audio de muestra para clonación


class TTSGenerator:
    """
    Genera audio de voz en off a partir de texto.
    Usa Chatterbox TTS con soporte multiidioma.
    """

    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        logger.info("Cargando Chatterbox TTS (CPU)...")
        try:
            from chatterbox.tts import ChatterboxTTS
            # Forzar CPU — la GPU debe estar libre para Wan2GP/Flux
            self._model = ChatterboxTTS.from_pretrained(device="cpu")
            logger.info("Chatterbox TTS listo")
        except ImportError:
            # Fallback a Kokoro si Chatterbox no está instalado
            logger.warning("Chatterbox no disponible, usando Kokoro como fallback")
            self._model = "kokoro"

    def generate(
        self,
        text: str,
        output_path: str | Path | None = None,
        voice_sample: str | None = None,
        exaggeration: float = 0.3,   # 0=neutro, 1=muy expresivo
        speed: float = 1.0,
    ) -> Path:
        """
        Genera audio de voz en off.

        Args:
            text:          Texto a leer
            output_path:   Dónde guardar el .wav (None = auto)
            voice_sample:  Ruta a audio de muestra para clonación de voz
            exaggeration:  Expresividad (0.3 = profesional neutro para finanzas)
            speed:         Velocidad (1.0 = normal)

        Returns:
            Path al .wav generado
        """
        self._load()

        if output_path is None:
            out_dir = Path("output/tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"tts_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sample = voice_sample or VOICE_SAMPLE or None
        t0 = time.time()

        if self._model == "kokoro":
            self._generate_kokoro(text, output_path)
        else:
            self._generate_chatterbox(text, output_path, sample, exaggeration, speed)

        logger.info(f"TTS generado en {time.time()-t0:.1f}s → {output_path} ({len(text)} chars)")
        return output_path

    def _generate_chatterbox(
        self, text: str, output_path: Path,
        voice_sample: str | None, exaggeration: float, speed: float
    ):
        try:
            wav = self._model.generate(
                text,
                audio_prompt_path=voice_sample,
                exaggeration=exaggeration,
                speed=speed,
            )
            # Chatterbox devuelve tensor — convertir a numpy
            if hasattr(wav, 'numpy'):
                wav = wav.squeeze().numpy()
            elif hasattr(wav, 'cpu'):
                wav = wav.cpu().squeeze().numpy()

            sf.write(str(output_path), wav, samplerate=24000)
        except Exception as e:
            logger.error(f"Error Chatterbox: {e}")
            # Fallback a silencio de la duración estimada
            self._generate_silence(output_path, duration_secs=len(text) / 15)

    def _generate_kokoro(self, text: str, output_path: Path):
        """Fallback con Kokoro si Chatterbox no está disponible."""
        try:
            # Forzar CPU — ocultar GPU via HIP/ROCR (no CUDA) para que
            # Kokoro no intente usar MIOpen que falla en gfx1151
            old_hip = os.environ.get("HIP_VISIBLE_DEVICES", "")
            old_rocr = os.environ.get("ROCR_VISIBLE_DEVICES", "")
            os.environ["HIP_VISIBLE_DEVICES"] = "-1"
            os.environ["ROCR_VISIBLE_DEVICES"] = "-1"
            try:
                from kokoro import KPipeline
                pipeline = KPipeline(lang_code="e")  # español
            finally:
                os.environ["HIP_VISIBLE_DEVICES"] = old_hip
                os.environ["ROCR_VISIBLE_DEVICES"] = old_rocr
            voice = "ef_dora"
            generator = pipeline(text, voice=voice, speed=1.0)
            samples = []
            sample_rate = 24000
            for _, _, audio in generator:
                if hasattr(audio, 'numpy'):
                    audio = audio.numpy()
                samples.append(audio)
            if samples:
                combined = np.concatenate(samples)
                sf.write(str(output_path), combined, samplerate=sample_rate)
            else:
                self._generate_silence(output_path)
        except Exception as e:
            logger.error(f"Error Kokoro: {e}")
            self._generate_silence(output_path, duration_secs=len(text) / 15)

    def _generate_silence(self, output_path: Path, duration_secs: float = 30.0):
        """Genera silencio como último recurso."""
        logger.warning(f"Generando silencio ({duration_secs:.1f}s) como fallback TTS")
        silence = np.zeros(int(24000 * duration_secs), dtype=np.float32)
        sf.write(str(output_path), silence, samplerate=24000)

    def get_duration(self, audio_path: str | Path) -> float:
        """Devuelve la duración en segundos de un fichero de audio."""
        data, samplerate = sf.read(str(audio_path))
        return len(data) / samplerate
