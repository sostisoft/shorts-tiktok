"""
saas/providers/compose/ffmpeg.py
Video compositor using FFmpeg — wraps existing pipeline/composer.py.
Downloads all S3 inputs, composes locally, uploads result to S3.
"""
import logging
import os
import sys
import tempfile
from pathlib import Path

from saas.storage.s3 import download_file, upload_file

logger = logging.getLogger("saas.providers.compose.ffmpeg")


class FFmpegComposeProvider:
    """Composites final video using FFmpeg (CPU-only)."""

    async def compose(
        self,
        clips: list[str],
        voice: str,
        music: str,
        subtitles: list[dict],
        target_duration: float,
    ) -> str:
        # Import existing composer
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from pipeline.composer import VideoComposer

        with tempfile.TemporaryDirectory(prefix="sf_compose_") as tmp_dir:
            tmp = Path(tmp_dir)

            # Download all inputs from S3
            local_clips = []
            for i, clip_key in enumerate(clips):
                local_clip = tmp / f"clip_{i:02d}.mp4"
                download_file(clip_key, local_clip)
                local_clips.append(local_clip)

            local_voice = tmp / "voice.wav"
            download_file(voice, local_voice)

            local_music = tmp / "music.mp3"
            download_file(music, local_music)

            output = tmp / "final.mp4"

            # Run composer
            composer = VideoComposer()
            composer.compose(
                clips=local_clips,
                audio_voice=local_voice,
                audio_music=local_music,
                subtitles=subtitles,
                output_path=output,
                target_duration=target_duration,
            )

            # Upload result to S3
            s3_key = f"tmp/composed/{os.urandom(8).hex()}/final.mp4"
            upload_file(output, s3_key)

        logger.info(f"Composed video -> {s3_key}")
        return s3_key
