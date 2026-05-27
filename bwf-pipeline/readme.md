# BWF Pipeline

Pipeline de collecte et d'analyse des données de badminton BWF World Tour.

## Stack
- Python 3.11 / SQLAlchemy 2.0 / PostgreSQL 16
- httpx (scraping) / APScheduler (scheduler) / Alembic (migrations)
- Docker Compose

## Démarrage rapide

```bash
cp .env.example .env
docker compose up -d
python -m alembic upgrade head
python -m bwf.scrapers.tournaments   # collecte historique
```

## Structure

```
bwf/
├── config.py          # settings via .env
├── database.py        # engine SQLAlchemy
├── models.py          # ORM — 7 tables
├── scheduler.py       # APScheduler jobs
└── scrapers/
    ├── tournaments.py # découverte des tournois
    └── matches.py     # collecte des matchs
```

## Endpoints BWF utilisés

```
POST /api/vue-grouped-year-tournaments
     {"year": 2018, "category": [22,23,24,25,26], "state": "all"}

GET  /api/tournaments/day-matches
     ?tournamentCode={GUID}&date={YYYY-MM-DD}&order=2&court=0

GET  /api/match-center/vue-current-live
     ?category[]=22&...&category[]=26
```