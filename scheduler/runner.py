import uuid
import logging
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import decide
from agents.metadata_gen import generate as gen_metadata
from pipeline.runner import generate_video
from publishers.youtube import publish as yt_publish, publish_backup as yt_backup
from publishers.instagram import publish as ig_publish
from publishers.tiktok import publish as tt_publish
from db.models import get_recent_topics, save_video, update_status

logger = logging.getLogger("videobot")


def _publish_all(video_path: Path, title: str, description: str, tags: list[str]) -> dict:
    """
    Publica en las 4 plataformas en paralelo:
    1. YouTube privado (backup/almacén)
    2. YouTube Shorts (público)
    3. Instagram Reels
    4. TikTok

    Devuelve dict con resultados de cada plataforma.
    """
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


def run_job():
    """
    Ciclo completo: decide → genera → publica (4 plataformas en paralelo) → borra local.
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
            title="",
            tags=[]
        )

        # 3. Generar vídeo completo
        video_path = generate_video(decision, job_id)

        # 4. Generar metadata
        metadata = gen_metadata(decision.topic, decision.hook, decision.narration)
        logger.info(f"[{job_id}] Título: {metadata.title}")

        # 5. Publicar en las 4 plataformas en paralelo
        logger.info(f"[{job_id}] Publicando en 4 plataformas en paralelo...")
        results = _publish_all(
            video_path=video_path,
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
        )

        # 6. Evaluar resultados
        yt_shorts = results.get("yt_shorts")
        yt_bk = results.get("yt_backup")

        # Considerar éxito si al menos YouTube Shorts o backup funcionó
        any_success = any(r.success for r in results.values())

        if any_success:
            yt_id = yt_shorts.video_id if yt_shorts and yt_shorts.success else None
            yt_url = yt_shorts.url if yt_shorts and yt_shorts.success else None
            update_status(job_id, "success", yt_id, yt_url)

            # Log resumen
            for platform, result in results.items():
                status = "OK" if result.success else f"FAIL: {result.error}"
                logger.info(f"[{job_id}]   {platform}: {status}")

            # 7. Borrar vídeo local — ya está en YouTube privado como backup
            if yt_bk and yt_bk.success:
                video_path.unlink(missing_ok=True)
                logger.info(f"[{job_id}] Vídeo local borrado (backup en YouTube: {yt_bk.url})")
            else:
                # No borrar si el backup falló — mantener en pending
                logger.warning(f"[{job_id}] Backup YouTube falló — vídeo local conservado en {video_path}")

            logger.info(f"[{job_id}] Job completado")
        else:
            # Todo falló
            errors = "; ".join(f"{p}: {r.error}" for p, r in results.items())
            update_status(job_id, "failed", error=errors)
            logger.error(f"[{job_id}] Todas las plataformas fallaron: {errors}")

    except Exception as e:
        logger.exception(f"[{job_id}] Error inesperado: {e}")
        update_status(job_id, "failed", error=str(e))
