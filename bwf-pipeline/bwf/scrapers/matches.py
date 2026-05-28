import logging
import time
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bwf.config import settings
from bwf.scrapers.http import BWF_HEADERS
from bwf.database import get_session
from bwf.models import Match, Player, ScrapingJob, SetScore, Tournament

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Joueurs
# ---------------------------------------------------------------------------

def upsert_player(session: Session, player_data: dict) -> int:
    """Insère ou met à jour un joueur. Retourne l'id interne (PK)."""
    stmt = (
        insert(Player)
        .values(
            bwf_id=str(player_data["id"]),
            first_name=player_data.get("firstName"),
            last_name=player_data.get("lastName"),
            display_name=player_data.get("nameDisplay", ""),
            country_code=player_data.get("countryCode"),
        )
        .on_conflict_do_update(
            index_elements=["bwf_id"],
            set_={
                "display_name": player_data.get("nameDisplay", ""),
                "country_code": player_data.get("countryCode"),
            },
        )
        .returning(Player.id)
    )
    result = session.execute(stmt)
    session.flush()
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Fetch API
# ---------------------------------------------------------------------------

def fetch_day_matches(
    tournament_code: str,
    day: date,
    client: httpx.Client,
) -> list[dict]:
    """Récupère les matchs d'un tournoi pour un jour donné."""
    response = client.get(
        f"{settings.bwf_base_url}/tournaments/day-matches",
        params={
            "tournamentCode": tournament_code,
            "date": day.isoformat(),
            "order": 2,
            "court": 0,
        },
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_seed(raw: str | None) -> int | None:
    """Convertit '1' ou None en int."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def is_singles(match: dict) -> bool:
    """Filtre uniquement MS et WS."""
    return match.get("eventName") in settings.singles_disciplines


def is_valid_score(match: dict) -> bool:
    """Exclut les walkovers et matchs sans score."""
    return match.get("scoreStatus") == 0 and bool(match.get("score"))


def parse_match_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Upsert match + set scores
# ---------------------------------------------------------------------------

def upsert_match(
    session: Session,
    match_data: dict,
    tournament_id: int,
    player1_id: int,
    player2_id: int,
) -> int | None:
    """
    Insère le match s'il n'existe pas encore.
    Retourne l'id interne ou None si déjà présent.
    """
    stmt = (
        insert(Match)
        .values(
            bwf_match_id=match_data["id"],
            tournament_id=tournament_id,
            discipline=match_data["eventName"],
            round_name=match_data.get("roundName"),
            match_time_utc=parse_match_time(match_data.get("matchTimeUtc")),
            player1_id=player1_id,
            player2_id=player2_id,
            player1_seed=parse_seed(match_data.get("team1seed")),
            player2_seed=parse_seed(match_data.get("team2seed")),
            winner=match_data.get("winner"),
            score_status=match_data.get("scoreStatus", 0),
            duration_minutes=match_data.get("duration"),
        )
        .on_conflict_do_nothing(constraint="uq_matches_bwf_id")
        .returning(Match.id)
    )
    result = session.execute(stmt)
    session.flush()
    row = result.fetchone()
    return row[0] if row else None


def insert_set_scores(session: Session, match_id: int, scores: list[dict]) -> None:
    """Insère les scores par set pour un match."""
    for s in scores:
        session.execute(
            insert(SetScore).values(
                match_id=match_id,
                set_number=s["set"],
                score_player1=s["home"],
                score_player2=s["away"],
            ).on_conflict_do_nothing()
        )
    session.flush()


# ---------------------------------------------------------------------------
# Scraping d'un tournoi
# ---------------------------------------------------------------------------

def scrape_tournament(tournament: Tournament, client: httpx.Client) -> tuple[int, int]:
    """
    Collecte tous les matchs d'un tournoi jour par jour.
    Retourne (matchs_insérés, matchs_ignorés).
    """
    inserted = 0
    skipped = 0

    # Itère sur chaque jour du tournoi
    current_day = tournament.start_date
    while current_day <= tournament.end_date:
        try:
            raw_matches = fetch_day_matches(tournament.bwf_code, current_day, client)
            logger.debug(f"{tournament.name} — {current_day} : {len(raw_matches)} matchs bruts")

            with get_session() as session:
                for m in raw_matches:
                    # Filtre : simples uniquement + score valide
                    if not is_singles(m) or not is_valid_score(m):
                        continue

                    # Upsert des joueurs
                    p1_data = m["team1"]["players"][0]
                    p2_data = m["team2"]["players"][0]
                    p1_id = upsert_player(session, p1_data)
                    p2_id = upsert_player(session, p2_data)

                    # Upsert du match
                    match_id = upsert_match(session, m, tournament.id, p1_id, p2_id)

                    if match_id:
                        insert_set_scores(session, match_id, m["score"])
                        inserted += 1
                    else:
                        skipped += 1

                session.commit()

            time.sleep(settings.request_delay_seconds)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Pas de matchs ce jour-là — normal
                logger.debug(f"{current_day} : pas de matchs (404)")
            else:
                logger.error(f"HTTP {e.response.status_code} pour {current_day}")
        except Exception as e:
            logger.error(f"Erreur pour {current_day} : {e}", exc_info=True)

        current_day += timedelta(days=1)

    return inserted, skipped


# ---------------------------------------------------------------------------
# Gestion des jobs
# ---------------------------------------------------------------------------

def mark_job(session: Session, job: ScrapingJob, status: str, error: str | None = None) -> None:
    job.status = status
    job.error_message = error
    if status == "in_progress":
        job.started_at = datetime.utcnow()
    elif status in ("completed", "failed"):
        job.completed_at = datetime.utcnow()
    session.commit()


def run_pending_jobs() -> None:
    """
    Point d'entrée principal.
    Traite tous les scraping_jobs en statut 'pending'.
    """
    with get_session() as session:
        pending = (
            session.query(ScrapingJob)
            .filter_by(status="pending")
            .join(Tournament)
            .filter(Tournament.end_date <= date.today())  # tournoi terminé uniquement
            .order_by(Tournament.end_date.asc())           # du plus ancien au plus récent
            .all()
        )

    if not pending:
        logger.info("Aucun job en attente")
        return

    logger.info(f"{len(pending)} jobs en attente")

    with httpx.Client(
        headers=BWF_HEADERS,
        follow_redirects=True,
    ) as client:
        for job in pending:
            tournament = job.tournament
            logger.info(f"Scraping : {tournament.name} ({tournament.start_date})")

            with get_session() as session:
                job = session.merge(job)
                mark_job(session, job, "in_progress")

            try:
                inserted, skipped = scrape_tournament(tournament, client)
                logger.info(
                    f"{tournament.name} — {inserted} matchs insérés, {skipped} ignorés"
                )
                with get_session() as session:
                    job = session.merge(job)
                    mark_job(session, job, "completed")

            except Exception as e:
                logger.error(f"Échec : {tournament.name} — {e}", exc_info=True)
                with get_session() as session:
                    job = session.merge(job)
                    job.retry_count += 1
                    mark_job(session, job, "failed", error=str(e))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_pending_jobs()