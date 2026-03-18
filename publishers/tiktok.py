import os
import logging
import requests
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("videobot")

BASE_URL = "https://open.tiktokapis.com/v2"
TOKEN_FILE = "credentials/tiktok_token.json"


@dataclass
class TikTokResult:
    success: bool
    publish_id: str | None
    error: str | None


def _get_access_token() -> str:
    """Lee el access token de TikTok desde fichero o variable de entorno."""
    token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if token:
        return token

    import json
    token_path = Path(TOKEN_FILE)
    if token_path.exists():
        data = json.loads(token_path.read_text())
        return data["access_token"]

    raise RuntimeError("No se encontró token de TikTok. Ejecuta auth_tiktok.py primero.")


def publish(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
) -> TikTokResult:
    """
    Sube un vídeo a TikTok usando Content Posting API.
    Upload chunked con FILE_UPLOAD.
    """
    try:
        access_token = _get_access_token()
        video_size = video_path.stat().st_size
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        total_chunks = max(1, (video_size + chunk_size - 1) // chunk_size)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Construir caption con hashtags
        hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:10])
        caption = f"{title}\n\n{description}\n\n{hashtags}"

        # 1. Inicializar upload
        init_payload = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
            "post_info": {
                "title": title[:150],
                "description": caption[:2200],
                "privacy_level": "PUBLIC_TO_EVERYONE",
            },
        }

        logger.info(f"TikTok: inicializando upload ({video_size} bytes, {total_chunks} chunks)")
        resp = requests.post(
            f"{BASE_URL}/post/publish/video/init/",
            json=init_payload,
            headers=headers,
        )
        resp.raise_for_status()
        init_data = resp.json()

        if init_data.get("error", {}).get("code") != "ok":
            error_msg = init_data.get("error", {}).get("message", str(init_data))
            return TikTokResult(success=False, publish_id=None, error=error_msg)

        upload_url = init_data["data"]["upload_url"]
        publish_id = init_data["data"]["publish_id"]

        # 2. Subir chunks
        with open(video_path, "rb") as f:
            for chunk_num in range(total_chunks):
                chunk_data = f.read(chunk_size)
                current_size = len(chunk_data)
                start_byte = chunk_num * chunk_size
                end_byte = start_byte + current_size - 1

                chunk_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(current_size),
                    "Content-Range": f"bytes {start_byte}-{end_byte}/{video_size}",
                }

                logger.info(f"TikTok: chunk {chunk_num + 1}/{total_chunks}")
                resp = requests.put(upload_url, data=chunk_data, headers=chunk_headers)
                if resp.status_code not in [200, 201, 206]:
                    resp.raise_for_status()

        logger.info(f"TikTok: publicado (publish_id={publish_id})")
        return TikTokResult(success=True, publish_id=publish_id, error=None)

    except Exception as e:
        logger.error(f"TikTok: error - {e}")
        return TikTokResult(success=False, publish_id=None, error=str(e))
