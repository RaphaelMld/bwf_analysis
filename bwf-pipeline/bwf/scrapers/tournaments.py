import logging
import time
from datetime import datetime

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bwf.config import settings
from bwf.database import get_session
from bwf.models import ScrapingJob, Tournament

logger = logging.getLogger(__name__)


def fetch_tournaments_for_year(year: int, client: httpx.Client) -> list[dict]:
    """Appelle l'API BWF et retourne la liste des tournois World Tour pour une année."""
    response = client.post(
        f"{settings.bwf_base_url}/vue-grouped-year-tournaments",
        json={
            "year": year,
            "category": settings.world_tour_category_ids,
            "state": "all",
        },
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()

    tournaments = []
    for month in data.get("results", []):
        for t in month.get("tournaments", []):
            tournaments.append(t)

    logger.info(f"{year} — {len(tournaments)} tournois trouvés")
    return tournaments


def parse_prize_money(raw: str | None) -> int | None:
    """Convertit '1,450,000' en 1450000."""
    if not raw:
        return None
    try:
        return int(raw.replace(",", "").replace(".", "").strip())
    except ValueError:
        return None


def upsert_tournament(session: Session, data: dict) -> Tournament:
    """Insère ou met à jour un tournoi. Retourne l'objet Tournament."""
    stmt = (
        insert(Tournament)
        .values(
            bwf_id=data["id"],
            bwf_code=data["code"],
            name=data["name"],
            category=data.get("category", ""),
            category_id=data.get("category_id") or _infer_category_id(data.get("category", "")),
            start_date=datetime.fromisoformat(data["start_date"]).date(),
            end_date=datetime.fromisoformat(data["end_date"]).date(),
            location=data.get("location"),
            country=data.get("country"),
            prize_money=parse_prize_money(data.get("prize_money")),
        )
        .on_conflict_do_update(
            index_elements=["bwf_code"],
            set_={
                "name": data["name"],
                "start_date": datetime.fromisoformat(data["start_date"]).date(),
                "end_date": datetime.fromisoformat(data["end_date"]).date(),
                "prize_money": parse_prize_money(data.get("prize_money")),
            },
        )
        .returning(Tournament)
    )
    result = session.execute(stmt)
    session.commit()
    return result.scalar_one()


def ensure_scraping_job(session: Session, tournament: Tournament) -> None:
    """Crée un scraping_job 'pending' si le tournoi n'en a pas encore."""
    existing = (
        session.query(ScrapingJob)
        .filter_by(tournament_id=tournament.id)
        .first()
    )
    if not existing:
        job = ScrapingJob(tournament_id=tournament.id, status="pending")
        session.add(job)
        session.commit()
        logger.info(f"Job créé pour : {tournament.name}")


def _infer_category_id(category: str) -> int:
    """Infère le category_id depuis le nom de la catégorie."""
    if "Finals" in category:
        return 22
    if "1000" in category:
        return 23
    if "750" in category:
        return 24
    if "500" in category:
        return 25
    return 26  # Super 300 par défaut


def discover_tournaments(from_year: int | None = None) -> None:
    """
    Point d'entrée principal.
    Collecte tous les tournois de from_year à aujourd'hui
    et crée les scraping_jobs correspondants.
    """
    start_year = from_year or settings.scrape_from_year
    current_year = datetime.now().year

    logger.info(f"Découverte des tournois {start_year} → {current_year}")

    with httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (research project — contact: ton@email.com)"},
        follow_redirects=True,
    ) as client:
        with get_session() as session:
            for year in range(start_year, current_year + 1):
                try:
                    tournaments = fetch_tournaments_for_year(year, client)
                    for t_data in tournaments:
                        tournament = upsert_tournament(session, t_data)
                        ensure_scraping_job(session, tournament)
                    # Délai respectueux entre chaque année
                    time.sleep(settings.request_delay_seconds)
                except httpx.HTTPError as e:
                    logger.error(f"Erreur HTTP pour {year} : {e}")
                except Exception as e:
                    logger.error(f"Erreur inattendue pour {year} : {e}", exc_info=True)

    logger.info("Découverte terminée")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    discover_tournaments()