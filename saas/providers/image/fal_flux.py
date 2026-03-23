"""
saas/providers/image/fal_flux.py
Image generation via fal.ai FLUX API.
"""
import logging
import os
import tempfile
from pathlib import Path

import httpx

from saas.config import get_settings
from saas.storage.s3 import upload_file

logger = logging.getLogger("saas.providers.image.fal")

FAL_FLUX_URL = "https://queue.fal.run/fal-ai/flux/schnell"


class FalFluxImageProvider:
    """Generates images using fal.ai FLUX Schnell API."""

    async def generate(self, prompts: list[str], size: tuple[int, int]) -> list[str]:
        settings = get_settings()
        s3_keys = []

        async with httpx.AsyncClient(timeout=120) as client:
            for i, prompt in enumerate(prompts):
                try:
                    s3_key = await self._generate_one(client, prompt, size, i, settings)
                    s3_keys.append(s3_key)
                except Exception as e:
                    logger.error(f"fal.ai FLUX failed for prompt {i}: {e}")
                    raise

        return s3_keys

    async def _generate_one(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        size: tuple[int, int],
        index: int,
        settings,
    ) -> str:
        # Submit request to fal.ai
        response = await client.post(
            FAL_FLUX_URL,
            headers={
                "Authorization": f"Key {settings.fal_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "image_size": {"width": size[0], "height": size[1]},
                "num_images": 1,
                "enable_safety_checker": True,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Download the image from fal.ai CDN
        image_url = data["images"][0]["url"]
        img_response = await client.get(image_url)
        img_response.raise_for_status()

        # Save to temp file and upload to S3
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_response.content)
            tmp_path = tmp.name

        s3_key = f"tmp/images/{os.urandom(8).hex()}/image_{index:02d}.png"
        upload_file(tmp_path, s3_key)
        Path(tmp_path).unlink(missing_ok=True)

        logger.info(f"fal.ai FLUX generated image {index} -> {s3_key}")
        return s3_key
