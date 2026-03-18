import os
import json
import time
import logging
import requests
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("videobot")

GRAPH_API = "https://graph.facebook.com/v21.0"
RUPLOAD_URL = "https://rupload.facebook.com"
TOKEN_FILE = "credentials/instagram_token.json"


@dataclass
class InstagramResult:
    success: bool
    media_id: str | None
    error: str | None


def _get_credentials() -> tuple[str, str]:
    """Devuelve (ig_user_id, access_token)."""
    ig_user_id = os.environ.get("INSTAGRAM_USER_ID")
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")

    if ig_user_id and token:
        return ig_user_id, token

    token_path = Path(TOKEN_FILE)
    if token_path.exists():
        data = json.loads(token_path.read_text())
        return data["ig_user_id"], data["access_token"]

    raise RuntimeError("No se encontró credenciales de Instagram. Configura .env o credentials/instagram_token.json")


def _upload_video_resumable(video_path: Path, access_token: str) -> str:
    """
    Sube vídeo via Resumable Upload API de Meta.
    Devuelve el upload handle (video_id).
    """
    video_size = video_path.stat().st_size

    # 1. Iniciar sesión de upload
    headers = {
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "file_size": str(video_size),
    }

    resp = requests.post(
        f"{RUPLOAD_URL}/ig-api-upload/",
        headers=headers,
    )
    resp.raise_for_status()
    upload_id = resp.json().get("id") or resp.json().get("video_id")

    # 2. Subir el fichero
    with open(video_path, "rb") as f:
        data = f.read()

    headers = {
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "Content-Type": "video/mp4",
    }

    resp = requests.post(
        f"{RUPLOAD_URL}/ig-api-upload/{upload_id}",
        headers=headers,
        data=data,
    )
    resp.raise_for_status()
    return upload_id


def publish(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
) -> InstagramResult:
    """
    Publica un Reel en Instagram via Graph API.

    Flujo:
    1. Crear container con video_url o upload resumable
    2. Esperar a que el container esté FINISHED
    3. Publicar el container
    """
    try:
        ig_user_id, access_token = _get_credentials()

        # Construir caption con hashtags
        hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:20])
        caption = f"{title}\n\n{description}\n\n{hashtags}"

        # Opción 1: Si hay VIDEO_HOST_URL, usar URL pública
        # Opción 2: Resumable upload directo
        video_url = os.environ.get("VIDEO_HOST_URL")

        if video_url:
            # Usar URL pública (ej: después de subir a YouTube privado)
            create_payload = {
                "media_type": "REELS",
                "video_url": f"{video_url}/{video_path.name}",
                "caption": caption[:2200],
                "share_to_feed": True,
                "access_token": access_token,
            }
        else:
            # Upload directo via resumable upload
            logger.info("Instagram: subiendo vídeo via upload resumable...")
            upload_handle = _upload_video_resumable(video_path, access_token)
            create_payload = {
                "media_type": "REELS",
                "upload_handle": upload_handle,
                "caption": caption[:2200],
                "share_to_feed": True,
                "access_token": access_token,
            }

        # 1. Crear container
        logger.info("Instagram: creando media container...")
        resp = requests.post(
            f"{GRAPH_API}/{ig_user_id}/media",
            data=create_payload,
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]

        # 2. Esperar a que esté listo (polling)
        logger.info(f"Instagram: esperando procesamiento (container={container_id})...")
        for attempt in range(60):  # max 5 minutos
            resp = requests.get(
                f"{GRAPH_API}/{container_id}",
                params={"fields": "status_code", "access_token": access_token},
            )
            status = resp.json().get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                error_msg = resp.json().get("status", "Error desconocido")
                return InstagramResult(success=False, media_id=None, error=error_msg)
            time.sleep(5)
        else:
            return InstagramResult(success=False, media_id=None, error="Timeout esperando procesamiento")

        # 3. Publicar
        logger.info("Instagram: publicando Reel...")
        resp = requests.post(
            f"{GRAPH_API}/{ig_user_id}/media_publish",
            data={"creation_id": container_id, "access_token": access_token},
        )
        resp.raise_for_status()
        media_id = resp.json()["id"]

        logger.info(f"Instagram: Reel publicado (media_id={media_id})")
        return InstagramResult(success=True, media_id=media_id, error=None)

    except Exception as e:
        logger.error(f"Instagram: error - {e}")
        return InstagramResult(success=False, media_id=None, error=str(e))
