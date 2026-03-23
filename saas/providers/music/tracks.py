"""
saas/providers/music/tracks.py
Music provider using royalty-free local tracks.
"""
import logging
import os
import random
from pathlib import Path

from saas.storage.s3 import upload_file

logger = logging.getLogger("saas.providers.music.tracks")

TRACKS_DIR = Path(__file__).resolve().parents[3] / "assets" / "music" / "tracks"


class TracksProvider:
    """Selects a random royalty-free track from local assets."""

    async def generate(self, duration_seconds: float, style: str | None = None) -> str:
        tracks = list(TRACKS_DIR.glob("*.mp3")) + list(TRACKS_DIR.glob("*.wav"))
        if not tracks:
            raise RuntimeError(f"No music tracks found in {TRACKS_DIR}")

        track = random.choice(tracks)

        s3_key = f"tmp/music/{os.urandom(8).hex()}/{track.name}"
        upload_file(track, s3_key)

        logger.info(f"Selected track: {track.name} -> {s3_key}")
        return s3_key
