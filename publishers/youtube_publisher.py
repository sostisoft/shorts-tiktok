"""
publishers/youtube_publisher.py
Sube vídeos a YouTube Shorts usando la Data API v3 con OAuth.
Credenciales del proyecto GCloud: finanzas-oc-yt
Canal: @finanzasjpg
"""
import logging
import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger("videobot.youtube")

# Scopes necesarios
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Rutas de credenciales
CREDENTIALS_DIR = Path(os.getenv("CREDENTIALS_DIR", "credentials"))
CLIENT_SECRETS = CREDENTIALS_DIR / "yt_finanzas.json"
TOKEN_PICKLE = CREDENTIALS_DIR / "yt_token.pkl"

# Categoría "Science & Technology" (28) — buena para finanzas/educación
# También: "Education" (27) o "People & Blogs" (22)
CATEGORY_ID = os.getenv("YT_CATEGORY_ID", "28")


class YouTubePublisher:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service

        creds = None
        if TOKEN_PICKLE.exists():
            with open(TOKEN_PICKLE, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refrescando token YouTube...")
                creds.refresh(Request())
            else:
                if not CLIENT_SECRETS.exists():
                    raise FileNotFoundError(
                        f"Credenciales OAuth no encontradas: {CLIENT_SECRETS}\n"
                        "Descárgate el archivo desde Google Cloud Console > "
                        "APIs & Services > Credentials > OAuth 2.0 Client IDs\n"
                        "Luego ejecuta: python auth_youtube.py"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CLIENT_SECRETS), SCOPES
                )
                creds = flow.run_local_server(port=0)

            CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_PICKLE, "wb") as f:
                pickle.dump(creds, f)
            logger.info("Token YouTube guardado")

        self._service = build("youtube", "v3", credentials=creds)
        return self._service

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str] | None = None,
        privacy: str = "public",
    ) -> str:
        """
        Sube un vídeo a YouTube.

        Args:
            video_path: Ruta al .mp4
            title:      Título del vídeo (max 100 chars)
            description: Descripción (max 5000 chars)
            tags:       Lista de etiquetas
            privacy:    "public", "private" o "unlisted"

        Returns:
            YouTube video ID (ej: "dQw4w9WgXcQ")
        """
        service = self._get_service()

        # Truncar título si excede 100 chars
        title = title[:97] + "..." if len(title) > 100 else title

        # Añadir hashtag #Shorts para activar el formato Short
        if "#Shorts" not in description:
            description = f"{description}\n\n#Shorts #FinanzasPersonales"

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": (tags or []) + ["Shorts", "FinanzasPersonales", "FinanzasClaras"],
                "categoryId": CATEGORY_ID,
                "defaultLanguage": "es",
                "defaultAudioLanguage": "es",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                "madeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,  # 5 MB chunks
        )

        logger.info(f"Subiendo a YouTube: '{title}' ({video_path.stat().st_size / 1e6:.1f} MB)...")
        request = service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logger.info(f"  Subida: {pct}%")

        video_id = response["id"]
        logger.info(f"Vídeo publicado: https://youtube.com/watch?v={video_id}")
        return video_id
