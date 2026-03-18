import soundfile as sf
from pathlib import Path
import re


class TTSEngine:
    def __init__(self):
        self.kokoro = None

    def _load(self):
        if self.kokoro is not None:
            return
        from kokoro_onnx import Kokoro
        # Voces españolas disponibles: 'ef_dora' (femenina), 'em_alex' (masculina)
        # Kokoro descarga el modelo automáticamente al primer uso
        self.kokoro = Kokoro("kokoro-v1.0.onnx", "voices.bin")

    def generate(self, text: str, output_path: Path, voice: str = "ef_dora") -> Path:
        """
        Genera audio WAV desde texto en castellano.
        voice: ef_dora (femenina natural) o em_alex (masculino)
        """
        self._load()

        # Limpiar texto
        text = self._clean(text)

        # Generar audio
        # Kokoro-onnx: lang_code 'e' = español
        samples, sample_rate = self.kokoro.create(
            text,
            voice=voice,
            speed=1.1,       # Ligeramente más rápido que normal
            lang="es"
        )

        sf.write(str(output_path), samples, sample_rate)
        return output_path

    def _clean(self, text: str) -> str:
        text = re.sub(r'[^\w\s\.,;:!?¡¿\-]', '', text)
        text = re.sub(r'\.{3,}', '.', text)
        text = text.strip()
        return text
