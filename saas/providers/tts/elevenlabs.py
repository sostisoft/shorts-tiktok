"""
saas/providers/tts/elevenlabs.py
TTS provider using ElevenLabs API (premium).
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import requests

from saas.config import get_settings
from saas.storage.s3 import upload_file

logger = logging.getLogger("saas.providers.tts.elevenlabs")

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "ThT5KcBeYPX3keUQqHPh"
MODEL_ID = "eleven_multilingual_v2"


class ElevenLabsTTSProvider:
    """Text-to-speech using ElevenLabs API."""

    async def generate(self, text: str, voice: str = DEFAULT_VOICE_ID) -> str:
        settings = get_settings()
        if not settings.elevenlabs_api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not configured")

        with tempfile.TemporaryDirectory(prefix="sf_tts_") as tmp_dir:
            tmp = Path(tmp_dir)
            mp3_path = tmp / "voice.mp3"
            wav_path = tmp / "voice.wav"

            # Call ElevenLabs API
            resp = requests.post(
                f"{ELEVENLABS_BASE_URL}/text-to-speech/{voice}",
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": MODEL_ID,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.3,
                    },
                },
                params={"output_format": "mp3_44100_128"},
                timeout=60,
            )
            resp.raise_for_status()
            mp3_path.write_bytes(resp.content)

            # Convert to WAV
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path), str(wav_path)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg mp3->wav failed: {result.stderr[-200:]}")

            # Upload to S3
            s3_key = f"tmp/tts/{os.urandom(8).hex()}/voice.wav"
            upload_file(wav_path, s3_key)

        logger.info(f"ElevenLabs TTS generated ({len(text)} chars) -> {s3_key}")
        return s3_key
