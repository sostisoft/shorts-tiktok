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
        logger.info("Cargando Kokoro TTS (CPU)...")
        self._model = "kokoro"

    def generate(
        self,
        text: str,
        output_path: str | Path | None = None,
        voice: str = None,
        speed: float = 0.85,
    ) -> Path:
        """Genera audio de voz en off con Kokoro TTS."""
        self._load()

        if output_path is None:
            out_dir = Path("output/tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"tts_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.time()

        kokoro_voice = voice or "em_alex"
        self._generate_kokoro(text, output_path, kokoro_voice, speed)

        logger.info(f"TTS generado en {time.time()-t0:.1f}s → {output_path} ({len(text)} chars)")
        return output_path

    def _generate_kokoro(self, text: str, output_path: Path, voice: str = "ef_dora", speed: float = 0.9):
        """Genera TTS con Kokoro en un subproceso para aislar GPU/MIOpen."""
        import subprocess, sys, json as _json
        try:
            # Ejecutar en subproceso con GPU oculta — evita conflictos MIOpen
            script = f'''
import os
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["ROCR_VISIBLE_DEVICES"] = "-1"
import numpy as np
import soundfile as sf
from kokoro import KPipeline
lang = "e" if "{voice}".startswith("e") else "a"
pipeline = KPipeline(lang_code=lang)
generator = pipeline("""{text.replace('"', '\\"')}""", voice="{voice}", speed={speed})
samples = []
for _, _, audio in generator:
    if hasattr(audio, "numpy"):
        audio = audio.numpy()
    samples.append(audio)
if samples:
    combined = np.concatenate(samples)
    sf.write("{output_path}", combined, samplerate=24000)
    print(f"OK {{len(combined)/24000:.1f}}s")
else:
    print("EMPTY")
'''
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, timeout=120,
                env={**os.environ, "HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1"},
            )
            if result.returncode != 0:
                logger.error(f"Kokoro subprocess error: {result.stderr[-500:]}")
                self._generate_silence(output_path, duration_secs=len(text) / 15)
            elif "EMPTY" in result.stdout:
                self._generate_silence(output_path)
            else:
                logger.info(f"Kokoro: {result.stdout.strip()}")
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
