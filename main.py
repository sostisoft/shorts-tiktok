import logging
import os
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from db.models import init_db
from scheduler.runner import run_job

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


def main():
    os.makedirs("logs", exist_ok=True)
    init_db()

    scheduler = BlockingScheduler(timezone="Europe/Madrid")

    # 2 vídeos al día: 10:00 y 18:00
    scheduler.add_job(run_job, "cron", hour=10, minute=0,
                      id="job_manana", max_instances=1)
    scheduler.add_job(run_job, "cron", hour=18, minute=0,
                      id="job_tarde", max_instances=1)

    logger.info("VideoBot Finanzas Claras arrancado")
    logger.info("Publicaciones: 10:00 y 18:00 (Madrid)")
    logger.info("Canal: @finanzasjpg")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")


if __name__ == "__main__":
    main()
