"""
saas/providers/video/kenburns.py
Ken Burns video provider — wraps existing pipeline/kenburns.py.
CPU-only, runs on VPS via FFmpeg.
"""
import logging
import os
import tempfile
from pathlib import Path

from saas.storage.s3 import download_file, upload_file

logger = logging.getLogger("saas.providers.video.kenburns")


class KenBurnsVideoProvider:
    """Generates video clips with Ken Burns effect (zoom/pan) over images."""

    async def generate(self, image_path: str, motion_prompt: str, duration: int = 5) -> str:
        # Import the existing kenburns module
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from pipeline.kenburns import KenBurnsGenerator

        with tempfile.TemporaryDirectory(prefix="sf_kenburns_") as tmp_dir:
            tmp = Path(tmp_dir)

            # Download image from S3
            local_image = tmp / "input.png"
            download_file(image_path, local_image)

            # Generate Ken Burns clip
            output_clip = tmp / "clip.mp4"
            gen = KenBurnsGenerator()
            gen.animate(local_image, motion_prompt, output_clip, duration)

            # Upload to S3
            s3_key = f"tmp/clips/{os.urandom(8).hex()}/clip.mp4"
            upload_file(output_clip, s3_key)

        logger.info(f"Ken Burns clip generated -> {s3_key}")
        return s3_key
