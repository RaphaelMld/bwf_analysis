"""
Script de retry des jobs échoués.
Usage : python -m bwf.retry [--max-retries 3]
"""
import argparse
import logging
import sys

from bwf.database import get_session
from bwf.models import ScrapingJob
from bwf.scrapers.matches import run_pending_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def reset_failed_jobs(max_retries: int) -> int:
    """
    Remet en 'pending' les jobs échoués sous le seuil de retry.
    Retourne le nombre de jobs remis en attente.
    """
    with get_session() as session:
        failed = (
            session.query(ScrapingJob)
            .filter(
                ScrapingJob.status == "failed",
                ScrapingJob.retry_count < max_retries,
            )
            .all()
        )

        if not failed:
            logger.info("Aucun job échoué à relancer")
            return 0

        for job in failed:
            logger.info(
                f"Remise en attente : {job.tournament.name} "
                f"(tentative {job.retry_count + 1}/{max_retries})"
            )
            job.status = "pending"

        session.commit()
        return len(failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Relance les scraping jobs échoués")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Nombre maximum de tentatives avant abandon définitif (défaut: 3)",
    )
    args = parser.parse_args()

    logger.info(f"Retry des jobs échoués (max {args.max_retries} tentatives)")

    count = reset_failed_jobs(args.max_retries)
    if count > 0:
        logger.info(f"{count} jobs remis en attente — lancement de la collecte")
        run_pending_jobs()
    else:
        logger.info("Rien à faire")


if __name__ == "__main__":
    main()