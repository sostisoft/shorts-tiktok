import logging
import os
import sys
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from db.models import init_db
from scheduler.runner import (
    generate_only, publish_only, night_generation_loop, run_job,
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
    init_db()

    # ── Entrada manual: python main.py generate ──
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "generate":
            logger.info("Generación manual iniciada")
            job_id = generate_only()
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
        else:
            logger.error(f"Comando desconocido: {cmd}")
            print("Uso: python main.py [generate|publish|run]")
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
    logger.info("Entrada manual: python main.py [generate|publish|run]")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")


if __name__ == "__main__":
    main()
