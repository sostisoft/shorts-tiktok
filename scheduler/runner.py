import uuid
import time
import logging
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

from agents.orchestrator import decide, decide_from_topic
from agents.metadata_gen import generate as gen_metadata, generate_en as gen_metadata_en
from pipeline.runner import generate_video
from publishers.youtube import publish as yt_publish, publish_backup as yt_backup
from publishers.instagram import publish as ig_publish
from publishers.tiktok import publish as tt_publish
from db.models import (
    init_db, get_recent_topics, get_pending_topics,
    mark_topic_used, save_video, update_status, update_metadata,
    get_oldest_generated,
)

logger = logging.getLogger("videobot")

MADRID_TZ = ZoneInfo("Europe/Madrid")


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


# ═══════════════════════════════════════
# generate_only: genera vídeo sin publicar
# ═══════════════════════════════════════

def generate_only():
    """
    Genera un vídeo completo (ES + EN) y lo guarda en output/pending/.
    NO publica. Actualiza DB con status='generated'.

    Retorna job_id si se generó, None si no había temas.
    """
    init_db()
    job_id = str(uuid.uuid4())[:8]
    logger.info(f"{'='*50}")
    logger.info(f"[{job_id}] Iniciando generación (sin publicar)")

    try:
        # 1. Decidir tema
        decision, topic_id = _decide_topic(job_id)
        logger.info(f"[{job_id}] Tema: {decision.topic}")
        logger.info(f"[{job_id}] Hook: {decision.hook}")

        # Marcar tema manual como usado
        if topic_id:
            mark_topic_used(topic_id, job_id)

        # 2. Guardar en DB con status pending
        save_video(
            job_id=job_id,
            topic=decision.topic,
            hook=decision.hook,
            narration=decision.narration,
            title="",
            tags=[]
        )

        # Guardar narración EN en DB
        update_metadata(job_id, narration_en=decision.narration_en)

        # 3. Generar vídeo (imágenes + animación + TTS + música + ffmpeg)
        start_time = time.time()
        video_path = generate_video(decision, job_id)
        gen_seconds = int(time.time() - start_time)
        logger.info(f"[{job_id}] Generación completada en {gen_seconds}s")

        # 4. Generar metadata ES
        metadata_es = gen_metadata(decision.topic, decision.hook, decision.narration)
        logger.info(f"[{job_id}] Título ES: {metadata_es.title}")

        # 5. Generar metadata EN
        metadata_en = gen_metadata_en(decision.topic, decision.hook, decision.narration_en)
        logger.info(f"[{job_id}] Título EN: {metadata_en.title}")

        # 6. Guardar metadata en DB y marcar como generated
        update_metadata(
            job_id,
            title=metadata_es.title,
            description=metadata_es.description,
            tags=metadata_es.tags,
            title_en=metadata_en.title,
            description_en=metadata_en.description,
            tags_en=metadata_en.tags,
            generation_time_s=gen_seconds,
        )
        update_status(job_id, "generated")

        # Verificar que los ficheros existen
        es_path = Path(f"output/pending/{job_id}_es.mp4")
        en_path = Path(f"output/pending/{job_id}_en.mp4")
        if not es_path.exists() or not en_path.exists():
            raise FileNotFoundError(f"Vídeos no encontrados: {es_path}, {en_path}")

        logger.info(f"[{job_id}] Vídeo generado y listo para publicar")
        logger.info(f"[{job_id}]   ES: {es_path}")
        logger.info(f"[{job_id}]   EN: {en_path}")
        return job_id

    except Exception as e:
        logger.exception(f"[{job_id}] Error en generación: {e}")
        update_status(job_id, "failed", error=str(e))
        return None


# ═══════════════════════════════════════
# publish_only: publica vídeo pre-generado
# ═══════════════════════════════════════

def publish_only():
    """
    Publica el vídeo más antiguo con status='generated'.
    Publica versión ES y EN en 4 plataformas cada una (en paralelo).
    Actualiza DB con status='success' o 'failed'.
    Borra local si backup YouTube OK.
    """
    init_db()
    video = get_oldest_generated()
    if not video:
        logger.info("No hay vídeos generados pendientes de publicar")
        return None

    job_id = video["job_id"]
    logger.info(f"{'='*50}")
    logger.info(f"[{job_id}] Publicando vídeo pre-generado: {video['topic']}")

    es_path = Path(f"output/pending/{job_id}_es.mp4")
    en_path = Path(f"output/pending/{job_id}_en.mp4")

    if not es_path.exists():
        logger.error(f"[{job_id}] Fichero ES no encontrado: {es_path}")
        update_status(job_id, "failed", error=f"Fichero no encontrado: {es_path}")
        return None

    try:
        # ── Publicar versión ES ──
        title_es = video.get("title") or video["topic"]
        desc_es = video.get("description") or ""
        tags_es = video.get("tags") or []

        logger.info(f"[{job_id}] Publicando ES en 4 plataformas...")
        results_es = _publish_all(
            video_path=es_path,
            title=title_es,
            description=desc_es,
            tags=tags_es,
        )

        # ── Publicar versión EN ──
        results_en = {}
        if en_path.exists():
            title_en = video.get("title_en") or title_es
            desc_en = video.get("description_en") or desc_es
            tags_en = video.get("tags_en") or tags_es

            logger.info(f"[{job_id}] Publicando EN en 4 plataformas...")
            results_en = _publish_all(
                video_path=en_path,
                title=title_en,
                description=desc_en,
                tags=tags_en,
            )
        else:
            logger.warning(f"[{job_id}] Fichero EN no encontrado, solo se publica ES")

        # ── Evaluar resultados ES ──
        yt_shorts_es = results_es.get("yt_shorts")
        yt_bk_es = results_es.get("yt_backup")
        ig_es = results_es.get("instagram")
        tt_es = results_es.get("tiktok")

        # ── Evaluar resultados EN ──
        yt_shorts_en = results_en.get("yt_shorts")
        yt_bk_en = results_en.get("yt_backup")
        ig_en = results_en.get("instagram")
        tt_en = results_en.get("tiktok")

        any_success = any(r.success for r in results_es.values())
        if results_en:
            any_success = any_success or any(r.success for r in results_en.values())

        if any_success:
            # ES URLs
            yt_id = yt_shorts_es.video_id if yt_shorts_es and yt_shorts_es.success else None
            yt_url = yt_shorts_es.url if yt_shorts_es and yt_shorts_es.success else None
            yt_backup_url = yt_bk_es.url if yt_bk_es and yt_bk_es.success else None

            ig_url = None
            if ig_es and ig_es.success and hasattr(ig_es, 'media_id') and ig_es.media_id:
                ig_url = f"https://www.instagram.com/reel/{ig_es.media_id}/"

            tiktok_url = None
            if tt_es and tt_es.success:
                publish_id = getattr(tt_es, 'publish_id', None)
                if publish_id:
                    tiktok_url = f"https://www.tiktok.com/@finanzasjpg/video/{publish_id}"

            # EN URLs
            yt_url_en = yt_shorts_en.url if yt_shorts_en and yt_shorts_en.success else None

            ig_url_en = None
            if ig_en and ig_en.success and hasattr(ig_en, 'media_id') and ig_en.media_id:
                ig_url_en = f"https://www.instagram.com/reel/{ig_en.media_id}/"

            tiktok_url_en = None
            if tt_en and tt_en.success:
                publish_id_en = getattr(tt_en, 'publish_id', None)
                if publish_id_en:
                    tiktok_url_en = f"https://www.tiktok.com/@finanzasjpg/video/{publish_id_en}"

            update_status(
                job_id, "success", yt_id, yt_url,
                ig_url=ig_url,
                tiktok_url=tiktok_url,
                yt_backup_url=yt_backup_url,
                yt_url_en=yt_url_en,
                ig_url_en=ig_url_en,
                tiktok_url_en=tiktok_url_en,
                description=video.get("description"),
            )

            # Log resultados
            for platform, result in results_es.items():
                st = "OK" if result.success else f"FAIL: {result.error}"
                logger.info(f"[{job_id}]   ES {platform}: {st}")
            for platform, result in results_en.items():
                st = "OK" if result.success else f"FAIL: {result.error}"
                logger.info(f"[{job_id}]   EN {platform}: {st}")

            # Borrar locales si backup OK
            if yt_bk_es and yt_bk_es.success:
                es_path.unlink(missing_ok=True)
                logger.info(f"[{job_id}] ES local borrado (backup: {yt_bk_es.url})")

            if yt_bk_en and yt_bk_en.success:
                en_path.unlink(missing_ok=True)
                logger.info(f"[{job_id}] EN local borrado (backup: {yt_bk_en.url})")

            if not (yt_bk_es and yt_bk_es.success):
                logger.warning(f"[{job_id}] Backup ES falló — conservado en {es_path}")
            if not (yt_bk_en and yt_bk_en.success):
                logger.warning(f"[{job_id}] Backup EN falló — conservado en {en_path}")

            logger.info(f"[{job_id}] Publicación completada")
            return job_id
        else:
            errors_es = "; ".join(f"ES {p}: {r.error}" for p, r in results_es.items())
            errors_en = "; ".join(f"EN {p}: {r.error}" for p, r in results_en.items())
            all_errors = f"{errors_es}; {errors_en}".strip("; ")
            update_status(job_id, "failed", error=all_errors)
            logger.error(f"[{job_id}] Todas las plataformas fallaron: {all_errors}")
            return None

    except Exception as e:
        logger.exception(f"[{job_id}] Error en publicación: {e}")
        update_status(job_id, "failed", error=str(e))
        return None


# ═══════════════════════════════════════
# night_generation_loop: genera vídeos de 00:00 a 06:00
# ═══════════════════════════════════════

def night_generation_loop():
    """
    Genera vídeos en bucle desde medianoche hasta las 06:00 (Madrid).
    Cada vídeo tarda ~30-60 min en CPU.
    Se detiene cuando:
    - Son las 06:00 o más
    - No quedan temas pendientes y Claude no puede decidir
    """
    logger.info("=" * 50)
    logger.info("Iniciando generación nocturna (00:00-06:00)")

    count = 0
    while True:
        # Comprobar hora Madrid
        now_madrid = datetime.now(MADRID_TZ)
        if now_madrid.hour >= 6:
            logger.info(f"Son las {now_madrid.strftime('%H:%M')} — fin de generación nocturna")
            break

        logger.info(f"Hora Madrid: {now_madrid.strftime('%H:%M')} — generando vídeo #{count + 1}")

        try:
            job_id = generate_only()
            if job_id:
                count += 1
                logger.info(f"Vídeo #{count} generado: {job_id}")
            else:
                logger.info("No se pudo generar vídeo — parando generación nocturna")
                break
        except Exception as e:
            logger.exception(f"Error en generación nocturna: {e}")
            # Esperar 5 min antes de reintentar tras error
            time.sleep(300)

    logger.info(f"Generación nocturna finalizada: {count} vídeos generados")


# ═══════════════════════════════════════
# run_job: ciclo completo (legacy, para compatibilidad)
# ═══════════════════════════════════════

def run_job():
    """
    Ciclo completo legacy: genera + publica.
    Mantenido para compatibilidad con entrada manual.
    """
    job_id = generate_only()
    if job_id:
        publish_only()
