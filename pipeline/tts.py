"""
pipeline/tts.py
Text-to-Speech multi-engine: Edge TTS (default) y ElevenLabs con fallback automatico.
"""
import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import requests
import soundfile as sf

logger = logging.getLogger("videobot.tts")

# ── Edge TTS defaults ──────────────────────────────────────────────────
DEFAULT_VOICE = "es-ES-AlvaroNeural"
DEFAULT_RATE = "+0%"
DEFAULT_PITCH = "-7Hz"

# ── ElevenLabs defaults ────────────────────────────────────────────────
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
ELEVENLABS_DEFAULT_VOICE_ID = "ThT5KcBeYPX3keUQqHPh"  # Spanish voice
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
}


class TTSGenerator:
    """Genera audio de voz en off con Edge TTS o ElevenLabs."""

    def __init__(self):
        self._engine = os.environ.get("TTS_ENGINE", "edge").lower()
        self._elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        self._elevenlabs_voice_id = os.environ.get(
            "ELEVENLABS_VOICE_ID", ELEVENLABS_DEFAULT_VOICE_ID
        )

    # ── Public API ──────────────────────────────────────────────────────

    def generate(
        self,
        text: str,
        output_path: str | Path | None = None,
        voice: str = DEFAULT_VOICE,
        rate: str = DEFAULT_RATE,
        pitch: str = DEFAULT_PITCH,
        engine: str | None = None,
        **kwargs,
    ) -> Path:
        """Genera audio de voz en off.

        Args:
            text: Texto a sintetizar.
            output_path: Ruta del fichero WAV de salida (auto-generada si None).
            voice: Voz Edge TTS (ignorada si engine=elevenlabs).
            rate: Velocidad Edge TTS.
            pitch: Tono Edge TTS.
            engine: "edge" o "elevenlabs". Si None, usa TTS_ENGINE del entorno.
        """
        if output_path is None:
            out_dir = Path("output/tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"tts_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        chosen_engine = (engine or self._engine).lower()

        if chosen_engine == "elevenlabs":
            result = self._try_elevenlabs(text, output_path)
            if result is not None:
                return result
            # Fallback to Edge TTS
            logger.warning(
                "ElevenLabs fallo, usando Edge TTS como fallback"
            )

        # Edge TTS (default or fallback)
        return self._run_edge(text, output_path, voice, rate, pitch)

    @staticmethod
    def get_duration(audio_path: str | Path) -> float:
        """Devuelve la duracion en segundos de un fichero de audio."""
        data, samplerate = sf.read(str(audio_path))
        return len(data) / samplerate

    # ── ElevenLabs helpers ──────────────────────────────────────────────

    def get_elevenlabs_voices(self) -> list[dict]:
        """Devuelve la lista de voces disponibles en ElevenLabs.

        Returns:
            Lista de dicts con info de cada voz (voice_id, name, labels, etc.).
            Lista vacia si hay error o no hay API key.
        """
        if not self._elevenlabs_api_key:
            logger.warning("ELEVENLABS_API_KEY no configurada")
            return []
        try:
            resp = requests.get(
                f"{ELEVENLABS_BASE_URL}/voices",
                headers={"xi-api-key": self._elevenlabs_api_key},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("voices", [])
        except Exception as e:
            logger.error(f"Error obteniendo voces ElevenLabs: {e}")
            return []

    def get_elevenlabs_quota(self) -> dict:
        """Devuelve info de suscripcion y caracteres restantes de ElevenLabs.

        Returns:
            Dict con claves relevantes (character_count, character_limit,
            remaining_chars, tier, etc.). Dict vacio si hay error.
        """
        if not self._elevenlabs_api_key:
            logger.warning("ELEVENLABS_API_KEY no configurada")
            return {}
        try:
            resp = requests.get(
                f"{ELEVENLABS_BASE_URL}/user/subscription",
                headers={"xi-api-key": self._elevenlabs_api_key},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            used = data.get("character_count", 0)
            limit = data.get("character_limit", 0)
            return {
                "character_count": used,
                "character_limit": limit,
                "remaining_chars": limit - used,
                "tier": data.get("tier", "unknown"),
                "next_reset": data.get("next_character_count_reset_unix"),
            }
        except Exception as e:
            logger.error(f"Error obteniendo cuota ElevenLabs: {e}")
            return {}

    # ── ElevenLabs generation ───────────────────────────────────────────

    def _try_elevenlabs(self, text: str, output_path: Path) -> Path | None:
        """Intenta generar audio con ElevenLabs. Devuelve Path o None si falla."""
        if not self._elevenlabs_api_key:
            logger.warning("ELEVENLABS_API_KEY no configurada, saltando ElevenLabs")
            return None

        t0 = time.time()
        voice_id = self._elevenlabs_voice_id
        url = f"{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}"

        payload = {
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": ELEVENLABS_VOICE_SETTINGS,
        }
        headers = {
            "xi-api-key": self._elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        params = {"output_format": "mp3_44100_128"}

        try:
            resp = requests.post(
                url, headers=headers, json=payload, params=params, timeout=60
            )
            resp.raise_for_status()

            mp3_path = output_path.with_suffix(".mp3")
            mp3_path.write_bytes(resp.content)

            # Convertir mp3 -> wav para compatibilidad con el pipeline
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path), str(output_path)],
                capture_output=True,
                check=True,
            )
            mp3_path.unlink(missing_ok=True)

            logger.info(
                f"TTS ElevenLabs generado en {time.time()-t0:.1f}s -> "
                f"{output_path} ({len(text)} chars)"
            )
            return output_path

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            body = ""
            if e.response is not None:
                try:
                    body = e.response.json().get("detail", {}).get("message", "")
                except Exception:
                    body = e.response.text[:200]
            logger.warning(
                f"ElevenLabs HTTP {status}: {body or e}"
            )
            return None
        except Exception as e:
            logger.warning(f"ElevenLabs error: {e}")
            return None

    # ── Edge TTS generation ─────────────────────────────────────────────

    def _run_edge(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
        pitch: str,
    ) -> Path:
        """Genera audio con Edge TTS (Microsoft Neural)."""
        t0 = time.time()
        mp3_path = output_path.with_suffix(".mp3")

        try:
            asyncio.run(self._generate_edge(text, str(mp3_path), voice, rate, pitch))
            # Convertir mp3 -> wav para compatibilidad con el pipeline
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path), str(output_path)],
                capture_output=True,
                check=True,
            )
            mp3_path.unlink(missing_ok=True)
            logger.info(
                f"TTS Edge generado en {time.time()-t0:.1f}s -> "
                f"{output_path} ({len(text)} chars)"
            )
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            mp3_path.unlink(missing_ok=True)
            self._generate_silence(output_path, duration_secs=len(text) / 12)

        return output_path

    @staticmethod
    async def _generate_edge(
        text: str, output_path: str, voice: str, rate: str, pitch: str
    ):
        import edge_tts

        comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await comm.save(output_path)

    @staticmethod
    def _generate_silence(output_path: Path, duration_secs: float = 20.0):
        """Genera silencio como ultimo recurso."""
        logger.warning(f"Generando silencio ({duration_secs:.1f}s) como fallback TTS")
        silence = np.zeros(int(24000 * duration_secs), dtype=np.float32)
        sf.write(str(output_path), silence, samplerate=24000)
