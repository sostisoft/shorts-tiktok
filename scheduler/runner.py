import uuid
import logging
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import decide
from agents.metadata_gen import generate as gen_metadata
from pipeline.runner import generate_video
from publishers.youtube import publish
from db.models import get_recent_topics, save_video, update_status

logger = logging.getLogger("videobot")


def run_job():
    """
    Ciclo completo: decide → genera → publica → registra.
    Se llama automáticamente por el scheduler.
    """
    job_id = str(uuid.uuid4())[:8]
    logger.info(f"{'='*50}")
    logger.info(f"[{job_id}] Iniciando nuevo job")

    try:
        # 1. Claude decide qué vídeo hacer
        recent = get_recent_topics(limit=20)
        decision = decide(recent)
        logger.info(f"[{job_id}] Tema: {decision.topic}")
        logger.info(f"[{job_id}] Hook: {decision.hook}")

        # 2. Guardar en DB (estado pending)
        save_video(
            job_id=job_id,
            topic=decision.topic,
            hook=decision.hook,
            narration=decision.narration,
            title="",   # Se rellena después
            tags=[]
        )

        # 3. Generar vídeo completo
        video_path = generate_video(decision, job_id)

        # 4. Generar metadata
        metadata = gen_metadata(decision.topic, decision.hook, decision.narration)
        logger.info(f"[{job_id}] Título: {metadata.title}")

        # 5. Publicar en YouTube
        result = publish(
            video_path=video_path,
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
        )

        # 6. Actualizar DB
        if result.success:
            update_status(job_id, "success", result.video_id, result.url)
            # Mover a published
            published_path = Path(f"output/published/{job_id}.mp4")
            shutil.move(str(video_path), published_path)
            logger.info(f"[{job_id}] Completado: {result.url}")
        else:
            update_status(job_id, "failed", error=result.error)
            logger.error(f"[{job_id}] Falló la publicación: {result.error}")

    except Exception as e:
        logger.exception(f"[{job_id}] Error inesperado: {e}")
        update_status(job_id, "failed", error=str(e))
