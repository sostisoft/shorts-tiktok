"""
saas/providers/tts/edge_tts.py
TTS provider using Microsoft Edge TTS (free).
Wraps existing pipeline/tts.py logic.
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from saas.storage.s3 import upload_file

logger = logging.getLogger("saas.providers.tts.edge")


class EdgeTTSProvider:
    """Text-to-speech using Edge TTS (free, no API key needed)."""

    async def generate(self, text: str, voice: str = "es-ES-AlvaroNeural") -> str:
        import edge_tts

        with tempfile.TemporaryDirectory(prefix="sf_tts_") as tmp_dir:
            tmp = Path(tmp_dir)
            mp3_path = tmp / "voice.mp3"
            wav_path = tmp / "voice.wav"

            # Generate MP3 with edge-tts
            comm = edge_tts.Communicate(text, voice, rate="+0%", pitch="-7Hz")
            await comm.save(str(mp3_path))

            # Convert to WAV for pipeline compatibility
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path), str(wav_path)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg mp3->wav failed: {result.stderr[-200:]}")

            # Upload to S3
            s3_key = f"tmp/tts/{os.urandom(8).hex()}/voice.wav"
            upload_file(wav_path, s3_key)

        logger.info(f"Edge TTS generated ({len(text)} chars) -> {s3_key}")
        return s3_key
