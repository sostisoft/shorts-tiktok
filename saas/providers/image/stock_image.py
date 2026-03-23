"""
saas/providers/image/stock_image.py
Stock image provider using Pexels/Pixabay APIs.
Downloads images and uploads to S3.
"""
import logging
import os
import random
import tempfile
import time
from pathlib import Path

import requests

from saas.config import get_settings
from saas.storage.s3 import upload_file

logger = logging.getLogger("saas.providers.image.stock")


class StockImageProvider:
    """Downloads stock images from Pexels/Pixabay."""

    async def generate(self, prompts: list[str], size: tuple[int, int]) -> list[str]:
        settings = get_settings()
        s3_keys = []

        with tempfile.TemporaryDirectory(prefix="sf_images_") as tmp_dir:
            for i, prompt in enumerate(prompts):
                local_path = Path(tmp_dir) / f"image_{i:02d}.jpg"

                url = self._search_pexels(prompt, settings.pexels_api_key)
                if url is None and settings.pixabay_api_key:
                    url = self._search_pixabay(prompt, settings.pixabay_api_key)

                if url is None:
                    # Generate placeholder
                    self._generate_placeholder(local_path, size)
                else:
                    self._download(url, local_path)

                # Upload to S3 with a temporary key (caller provides tenant context)
                s3_key = f"tmp/images/{os.urandom(8).hex()}/image_{i:02d}.jpg"
                upload_file(local_path, s3_key)
                s3_keys.append(s3_key)

        return s3_keys

    @staticmethod
    def _search_pexels(query: str, api_key: str) -> str | None:
        if not api_key:
            return None
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": api_key},
                params={"query": query, "orientation": "portrait", "per_page": 10},
                timeout=15,
            )
            time.sleep(1.0)
            if r.status_code == 429:
                return None
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if not photos:
                return None
            photo = random.choice(photos[:5])
            return photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
        except Exception as e:
            logger.warning(f"Pexels search error: {e}")
            return None

    @staticmethod
    def _search_pixabay(query: str, api_key: str) -> str | None:
        if not api_key:
            return None
        try:
            r = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": api_key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": "vertical",
                    "per_page": 10,
                },
                timeout=15,
            )
            time.sleep(0.7)
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return None
            hit = random.choice(hits[:5])
            return hit.get("largeImageURL")
        except Exception as e:
            logger.warning(f"Pixabay search error: {e}")
            return None

    @staticmethod
    def _download(url: str, path: Path):
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        path.write_bytes(r.content)

    @staticmethod
    def _generate_placeholder(path: Path, size: tuple[int, int]):
        from PIL import Image
        img = Image.new("RGB", size, color=(30, 30, 30))
        img.save(path, "JPEG")
