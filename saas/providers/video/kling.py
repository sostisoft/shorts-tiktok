"""
saas/providers/video/kling.py
Video generation via Kling API (Image-to-Video).
"""
import logging
import os
import tempfile
import time
from pathlib import Path

import httpx

from saas.config import get_settings
from saas.storage.s3 import download_file, generate_presigned_url, upload_file

logger = logging.getLogger("saas.providers.video.kling")

KLING_API_BASE = "https://api.klingai.com/v1"


class KlingVideoProvider:
    """Generates video clips from images using Kling API."""

    async def generate(self, image_path: str, motion_prompt: str, duration: int = 5) -> str:
        settings = get_settings()

        # Get presigned URL for the source image (Kling needs a URL)
        image_url = generate_presigned_url(image_path, expires_in=3600)

        async with httpx.AsyncClient(timeout=300) as client:
            # Submit I2V generation request
            response = await client.post(
                f"{KLING_API_BASE}/images/generations",
                headers={
                    "Authorization": f"Bearer {settings.kling_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "image_url": image_url,
                    "prompt": motion_prompt,
                    "duration": str(duration),
                    "aspect_ratio": "9:16",
                },
            )
            response.raise_for_status()
            task_id = response.json()["data"]["task_id"]

            # Poll for completion
            video_url = await self._poll_result(client, task_id, settings)

            # Download and upload to S3
            video_response = await client.get(video_url)
            video_response.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_response.content)
                tmp_path = tmp.name

            s3_key = f"tmp/clips/{os.urandom(8).hex()}/clip.mp4"
            upload_file(tmp_path, s3_key)
            Path(tmp_path).unlink(missing_ok=True)

        logger.info(f"Kling I2V clip generated -> {s3_key}")
        return s3_key

    @staticmethod
    async def _poll_result(client: httpx.AsyncClient, task_id: str, settings) -> str:
        """Poll Kling API until task completes. Returns video URL."""
        for _ in range(120):  # Max 10 minutes
            await _async_sleep(5)
            resp = await client.get(
                f"{KLING_API_BASE}/images/generations/{task_id}",
                headers={"Authorization": f"Bearer {settings.kling_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data.get("status")

            if status == "completed":
                return data["output"]["video_url"]
            elif status == "failed":
                raise RuntimeError(f"Kling generation failed: {data.get('error', 'unknown')}")

        raise TimeoutError("Kling generation timed out after 10 minutes")


async def _async_sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)
