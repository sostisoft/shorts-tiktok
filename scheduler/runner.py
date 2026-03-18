import uuid
import logging
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import decide, decide_from_topic
from agents.metadata_gen import generate as gen_metadata
from pipeline.runner import generate_video
from publishers.youtube import publish as yt_publish, publish_backup as yt_backup
from publishers.instagram import publish as ig_publish
from publishers.tiktok import publish as tt_publish
from db.models import (
    init_db, get_recent_topics, get_pending_topics,
    mark_topic_used, save_video, update_status,
)

logger = logging.getLogger("videobot")


def _publish_all(video_path: Path, title: str, description: str, tags: list[str]) -> dict:
    """Publica en 4 plataformas en paralelo."""
    results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(yt_backup, video_path, title, description, tags): "yt_backup",
            executor.submit(yt_publish, video_path, title, description, tags): "yt_shorts",
            executor.submit(ig_publish, video_path, title, description, tags): "instagram",
            executor.submit(tt_publish, video_path, title, description, tags): "tiktok",
        }

        for future in as_completed(futures):
            platform = futures[future]
            try:
                result = future.result()
                results[platform] = result
                if result.success:
                    logger.info(f"  {platform}: OK")
                else:
                    logger.warning(f"  {platform}: FALLÓ - {result.error}")
            except Exception as e:
                logger.error(f"  {platform}: EXCEPCIÓN - {e}")
                results[platform] = type("Result", (), {
                    "success": False, "error": str(e),
                    "video_id": None, "url": None,
                    "publish_id": None, "media_id": None,
                })()

    return results


def _decide_topic(job_id: str) -> tuple:
    """
    Decide el tema del vídeo. Prioridad:
    1. Temas manuales pendientes en la DB (puestos por el usuario)
    2. Claude elige automáticamente

    Devuelve (decision, topic_id_or_none)
    """
    recent = get_recent_topics(limit=50)

    # 1. Buscar temas manuales pendientes
    pending = get_pending_topics()
    if pending:
        topic_entry = pending[0]
        logger.info(f"[{job_id}] Tema manual: '{topic_entry['tema']}' (prioridad: {topic_entry['prioridad']})")
        decision = decide_from_topic(
            topic=topic_entry["tema"],
            enfoque=topic_entry.get("enfoque"),
            recent_topics=recent,
        )
        return decision, topic_entry["id"]

    # 2. Claude elige libremente
    logger.info(f"[{job_id}] Sin temas manuales — Claude decide")
    decision = decide(recent)
    return decision, None


def run_job():
    """
    Ciclo completo:
    1. Tema manual (si hay) o Claude decide
    2. Genera vídeo (con cache de imágenes)
    3. Publica en 4 plataformas en paralelo
    4. Borra local si backup YouTube OK
    """
    init_db()
    job_id = str(uuid.uuid4())[:8]
    logger.info(f"{'='*50}")
    logger.info(f"[{job_id}] Iniciando nuevo job")

    try:
        # 1. Decidir tema
        decision, topic_id = _decide_topic(job_id)
        logger.info(f"[{job_id}] Tema: {decision.topic}")
        logger.info(f"[{job_id}] Hook: {decision.hook}")

        # Marcar tema manual como usado
        if topic_id:
            mark_topic_used(topic_id, job_id)

        # 2. Guardar en DB
        save_video(
            job_id=job_id,
            topic=decision.topic,
            hook=decision.hook,
            narration=decision.narration,
            title="",
            tags=[]
        )

        # 3. Generar vídeo (usa cache de imágenes)
        video_path = generate_video(decision, job_id)

        # 4. Generar metadata
        metadata = gen_metadata(decision.topic, decision.hook, decision.narration)
        logger.info(f"[{job_id}] Título: {metadata.title}")

        # 5. Publicar en 4 plataformas en paralelo
        logger.info(f"[{job_id}] Publicando en 4 plataformas...")
        results = _publish_all(
            video_path=video_path,
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
        )

        # 6. Evaluar resultados
        yt_shorts = results.get("yt_shorts")
        yt_bk = results.get("yt_backup")
        ig_result = results.get("instagram")
        tt_result = results.get("tiktok")

        any_success = any(r.success for r in results.values())

        if any_success:
            yt_id = yt_shorts.video_id if yt_shorts and yt_shorts.success else None
            yt_url = yt_shorts.url if yt_shorts and yt_shorts.success else None

            ig_url = None
            if ig_result and ig_result.success and hasattr(ig_result, 'media_id') and ig_result.media_id:
                ig_url = f"https://www.instagram.com/reel/{ig_result.media_id}/"

            tiktok_url = None
            if tt_result and tt_result.success:
                publish_id = getattr(tt_result, 'publish_id', None)
                if publish_id:
                    tiktok_url = f"https://www.tiktok.com/@finanzasjpg/video/{publish_id}"

            update_status(
                job_id, "success", yt_id, yt_url,
                ig_url=ig_url,
                tiktok_url=tiktok_url,
                description=metadata.description,
            )

            for platform, result in results.items():
                st = "OK" if result.success else f"FAIL: {result.error}"
                logger.info(f"[{job_id}]   {platform}: {st}")

            # 7. Borrar local si backup OK
            if yt_bk and yt_bk.success:
                video_path.unlink(missing_ok=True)
                logger.info(f"[{job_id}] Local borrado (backup: {yt_bk.url})")
            else:
                logger.warning(f"[{job_id}] Backup falló — conservado en {video_path}")

            logger.info(f"[{job_id}] Job completado")
        else:
            errors = "; ".join(f"{p}: {r.error}" for p, r in results.items())
            update_status(job_id, "failed", error=errors)
            logger.error(f"[{job_id}] Todas las plataformas fallaron: {errors}")

    except Exception as e:
        logger.exception(f"[{job_id}] Error inesperado: {e}")
        update_status(job_id, "failed", error=str(e))
