import logging
from pathlib import Path
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logger = logging.getLogger("videobot")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "credentials/yt_token.json"
CREDENTIALS_FILE = "credentials/yt_finanzas.json"


@dataclass
class PublishResult:
    success: bool
    video_id: str | None
    url: str | None
    error: str | None


def _get_service():
    """Obtiene el servicio YouTube autenticado."""
    creds = None

    # Intentar cargar token guardado
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Si no hay token válido, hacer flujo OAuth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Primera vez: abre navegador para autorizar
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=8080)

        # Guardar token para próximas veces
        Path(TOKEN_FILE).parent.mkdir(exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def _upload(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = "public",
) -> PublishResult:
    """
    Sube un vídeo a YouTube.
    privacy: "public", "unlisted", "private"

    CUOTA: cada upload cuesta 1.600 unidades.
    Con 10.000 unidades/día → máximo 6 vídeos/día.
    El bot usa 4/día (2 shorts + 2 backups) → sin problema.
    """
    try:
        service = _get_service()

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:20],
                "categoryId": "22",           # People & Blogs
                "defaultLanguage": "es",
                "defaultAudioLanguage": "es",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                "madeForKids": False,
            }
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=5 * 1024 * 1024  # 5MB chunks
        )

        label = "Short" if privacy == "public" else "backup"
        logger.info(f"YouTube ({label}): subiendo '{title}'")
        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"  YouTube ({label}): {progress}%")

        video_id = response["id"]
        url = f"https://youtube.com/shorts/{video_id}" if privacy == "public" else f"https://youtube.com/watch?v={video_id}"
        logger.info(f"YouTube ({label}): publicado {url}")

        return PublishResult(
            success=True,
            video_id=video_id,
            url=url,
            error=None
        )

    except Exception as e:
        logger.error(f"YouTube ({privacy}): error - {e}")
        return PublishResult(
            success=False,
            video_id=None,
            url=None,
            error=str(e)
        )


def publish(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
) -> PublishResult:
    """Sube un vídeo a YouTube Shorts (público, con #shorts)."""
    if "#shorts" not in description.lower():
        description += "\n\n#shorts"
    return _upload(video_path, title, description, tags, privacy="public")


def publish_backup(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
) -> PublishResult:
    """Sube el vídeo a YouTube normal como privado (almacén/backup)."""
    backup_title = f"[BACKUP] {title}"
    return _upload(video_path, backup_title, description, tags, privacy="private")
