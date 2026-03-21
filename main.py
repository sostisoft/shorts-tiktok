import json
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from db.models import init_db
from scheduler.runner import (
    generate_only, publish_only, night_generation_loop, run_job,
    resume_job, list_jobs_status,
)

load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/videobot.log")
    ]
)
logger = logging.getLogger("videobot")

TIMEZONE = "Europe/Madrid"


def main():
    os.makedirs("logs", exist_ok=True)
    os.makedirs("output/pending", exist_ok=True)
    os.makedirs("output/jobs", exist_ok=True)
    init_db()

    # ── Entrada manual: python main.py generate ──
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ("generate", "generate-stock"):
            video_source = "stock" if cmd == "generate-stock" else None
            mode_label = "STOCK footage" if video_source == "stock" else "IA"
            logger.info(f"Generacion manual iniciada (modo: {mode_label})")
            # Si existe un script JSON pendiente, usarlo en lugar del LLM
            script_file = Path("output/.pending_script.json")
            script = None
            if script_file.exists():
                try:
                    script = json.loads(script_file.read_text())
                    script_file.unlink()
                    logger.info(f"Usando guion manual: {script.get('title', '?')}")
                except Exception as e:
                    logger.error(f"Error leyendo script manual: {e}")
            job_id = generate_only(script=script, video_source=video_source)
            if job_id:
                logger.info(f"Generado: {job_id}")
            else:
                logger.warning("No se pudo generar")
            return
        elif cmd == "publish":
            logger.info("Publicación manual iniciada")
            job_id = publish_only()
            if job_id:
                logger.info(f"Publicado: {job_id}")
            else:
                logger.warning("No hay vídeos para publicar")
            return
        elif cmd == "run":
            logger.info("Ejecución completa manual (generar + publicar)")
            run_job()
            return
        elif cmd == "resume":
            target_id = sys.argv[2] if len(sys.argv) > 2 else None
            if target_id:
                logger.info(f"Resumiendo job: {target_id}")
            else:
                logger.info("Resumiendo ultimo job incompleto...")
            job_id = resume_job(target_id)
            if job_id:
                logger.info(f"Job resumido y completado: {job_id}")
            else:
                logger.warning("No se pudo resumir ningun job")
            return
        elif cmd == "status":
            jobs = list_jobs_status()
            if not jobs:
                print("No hay jobs en output/jobs/")
                return
            print(f"{'JOB ID':<12} {'STATUS':<10} {'TITLE':<40} {'PHASE':<8} {'UPDATED'}")
            print("-" * 90)
            for j in jobs:
                phases_done = sum(
                    1 for p in j.get("phases", {}).values()
                    if p.get("status") == "done"
                )
                failed = j.get("failed_phase") or "-"
                updated = (j.get("updated_at") or "")[:19]
                title = (j.get("title") or "")[:38]
                print(f"{j['job_id']:<12} {j['status']:<10} {title:<40} {phases_done}/6 F:{failed!s:<3} {updated}")
            return
        else:
            logger.error(f"Comando desconocido: {cmd}")
            print("Uso: python main.py [generate|generate-stock|publish|run|resume [job_id]|status]")
            print("")
            print("  generate        Genera 1 video con IA (FLUX + Ken Burns/Wan2.1)")
            print("  generate-stock  Genera 1 video con stock footage (Pexels/Pixabay)")
            print("  publish         Publica el siguiente video pendiente")
            print("  run             Genera + publica inmediatamente")
            print("  resume [id]     Reanuda un job fallido/interrumpido")
            print("  status          Lista todos los jobs y su estado")
            return

    # ── Scheduler automático ──
    scheduler = BlockingScheduler(timezone=TIMEZONE)

    # Generación nocturna: 00:00-06:00 Madrid
    # Se lanza a medianoche y genera vídeos en bucle hasta las 06:00
    scheduler.add_job(
        night_generation_loop, "cron",
        hour=0, minute=0,
        id="generate_night",
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Publicación 3x/día: 9:00, 14:00, 19:00 Madrid
    scheduler.add_job(
        publish_only, "cron",
        hour=9, minute=0,
        id="publish_morning",
        max_instances=1,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        publish_only, "cron",
        hour=14, minute=0,
        id="publish_midday",
        max_instances=1,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        publish_only, "cron",
        hour=19, minute=0,
        id="publish_evening",
        max_instances=1,
        misfire_grace_time=1800,
    )

    logger.info("VideoBot Finanzas Claras arrancado")
    logger.info("Generación nocturna: 00:00-06:00 (Madrid)")
    logger.info("Publicaciones: 09:00, 14:00, 19:00 (Madrid)")
    logger.info("Canal: @finanzasjpg")
    logger.info("Entrada manual: python main.py [generate|generate-stock|publish|run|resume|status]")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")


if __name__ == "__main__":
    main()
