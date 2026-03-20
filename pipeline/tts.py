"""
pipeline/tts.py
Text-to-Speech con Edge TTS (Microsoft Neural, AlvaroNeural castellano).
"""
import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger("videobot.tts")

# Voz por defecto: Alvaro (castellano España, masculino, neural)
DEFAULT_VOICE = "es-ES-AlvaroNeural"
DEFAULT_RATE = "+0%"
DEFAULT_PITCH = "-7Hz"


class TTSGenerator:
    """Genera audio de voz en off con Edge TTS (Microsoft Neural)."""

    def generate(
        self,
        text: str,
        output_path: str | Path | None = None,
        voice: str = DEFAULT_VOICE,
        rate: str = DEFAULT_RATE,
        pitch: str = DEFAULT_PITCH,
        **kwargs,
    ) -> Path:
        """Genera audio de voz en off."""
        if output_path is None:
            out_dir = Path("output/tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"tts_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.time()
        mp3_path = output_path.with_suffix(".mp3")

        try:
            asyncio.run(self._generate_edge(text, str(mp3_path), voice, rate, pitch))
            # Convertir mp3 -> wav para compatibilidad con el pipeline
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path), str(output_path)],
                capture_output=True, check=True,
            )
            mp3_path.unlink(missing_ok=True)
            logger.info(f"TTS generado en {time.time()-t0:.1f}s -> {output_path} ({len(text)} chars)")
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            mp3_path.unlink(missing_ok=True)
            self._generate_silence(output_path, duration_secs=len(text) / 12)

        return output_path

    @staticmethod
    async def _generate_edge(text: str, output_path: str, voice: str, rate: str, pitch: str):
        import edge_tts
        comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await comm.save(output_path)

    @staticmethod
    def _generate_silence(output_path: Path, duration_secs: float = 20.0):
        """Genera silencio como ultimo recurso."""
        logger.warning(f"Generando silencio ({duration_secs:.1f}s) como fallback TTS")
        silence = np.zeros(int(24000 * duration_secs), dtype=np.float32)
        sf.write(str(output_path), silence, samplerate=24000)

    @staticmethod
    def get_duration(audio_path: str | Path) -> float:
        """Devuelve la duracion en segundos de un fichero de audio."""
        data, samplerate = sf.read(str(audio_path))
        return len(data) / samplerate
