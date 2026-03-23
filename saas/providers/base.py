"""
saas/providers/base.py
Protocol definitions for all pipeline phases.
Each provider implements one protocol; the registry maps (plan, phase) -> provider.
"""
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ScriptProvider(Protocol):
    """Generates a video script from a topic."""

    async def generate(self, topic: str, style: str, language: str) -> dict:
        """
        Returns dict with keys: title, description, narration, scenes[], tags[].
        Each scene has: text, image_prompt, stock_keywords.
        """
        ...


@runtime_checkable
class ImageProvider(Protocol):
    """Generates or downloads images for video scenes."""

    async def generate(self, prompts: list[str], size: tuple[int, int]) -> list[str]:
        """
        Returns list of S3 keys for generated/downloaded images.
        """
        ...


@runtime_checkable
class VideoProvider(Protocol):
    """Generates video clips from images (Ken Burns, I2V, etc.)."""

    async def generate(self, image_path: str, motion_prompt: str, duration: int) -> str:
        """
        Returns S3 key of generated video clip.
        """
        ...


@runtime_checkable
class TTSProvider(Protocol):
    """Generates speech audio from text."""

    async def generate(self, text: str, voice: str) -> str:
        """
        Returns S3 key of generated WAV/MP3 audio.
        """
        ...


@runtime_checkable
class MusicProvider(Protocol):
    """Generates or selects background music."""

    async def generate(self, duration_seconds: float, style: str | None) -> str:
        """
        Returns S3 key of music audio file.
        """
        ...


@runtime_checkable
class ComposeProvider(Protocol):
    """Composites final video from clips, voice, music, and subtitles."""

    async def compose(
        self,
        clips: list[str],
        voice: str,
        music: str,
        subtitles: list[dict],
        target_duration: float,
    ) -> str:
        """
        All inputs are S3 keys. Returns S3 key of final composed video.
        """
        ...


@runtime_checkable
class PublishProvider(Protocol):
    """Publishes a video to a platform."""

    async def publish(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        credentials: dict,
    ) -> dict:
        """
        Returns dict with platform-specific IDs (e.g. youtube_id, tiktok_id).
        """
        ...
