import logging
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from bwf.config import settings
from bwf.scrapers.matches import run_pending_jobs
from bwf.scrapers.tournaments import discover_tournaments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log"),
    ],
)

logger = logging.getLogger(__name__)


def job_discover() -> None:
    """Job de découverte : trouve les nouveaux tournois et crée les jobs."""
    logger.info("=== Début découverte des tournois ===")
    try:
        discover_tournaments()
    except Exception as e:
        logger.error(f"Échec de la découverte : {e}", exc_info=True)
    logger.info("=== Fin découverte des tournois ===")


def job_scrape_matches() -> None:
    """Job de collecte : scrape les matchs des tournois en attente."""
    logger.info("=== Début collecte des matchs ===")
    try:
        run_pending_jobs()
    except Exception as e:
        logger.error(f"Échec de la collecte : {e}", exc_info=True)
    logger.info("=== Fin collecte des matchs ===")


def parse_cron(cron_str: str) -> dict:
    """Convertit '0 8 * * 1' en kwargs pour CronTrigger."""
    minute, hour, day, month, day_of_week = cron_str.split()
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")

    # Découverte chaque lundi à 8h UTC
    scheduler.add_job(
        job_discover,
        trigger=CronTrigger(**parse_cron(settings.discovery_cron)),
        id="discover_tournaments",
        name="Découverte des tournois BWF",
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Collecte des matchs chaque lundi à 10h UTC
    # (après la découverte, laisse 2h pour que les jobs soient créés)
    scheduler.add_job(
        job_scrape_matches,
        trigger=CronTrigger(**parse_cron(settings.matches_cron)),
        id="scrape_matches",
        name="Collecte des matchs BWF",
        max_instances=1,
        misfire_grace_time=3600,
    )

    logger.info("Scheduler démarré")
    logger.info(f"  Découverte  : {settings.discovery_cron} (UTC)")
    logger.info(f"  Collecte    : {settings.matches_cron} (UTC)")
    logger.info("En attente des prochains jobs...")

    # Au premier démarrage : lance immédiatement la découverte + collecte
    # pour récupérer l'historique sans attendre lundi
    logger.info("Premier démarrage — lancement immédiat de la découverte")
    job_discover()
    job_scrape_matches()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler arrêté proprement")


if __name__ == "__main__":
    main()