#!/usr/bin/env bash
# =============================================================================
# setup.sh — initialisation complète du pipeline BWF sur un nouveau serveur
# Usage : bash setup.sh
# =============================================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# -----------------------------------------------------------------------------
# 1. Vérifications préalables
# -----------------------------------------------------------------------------
info "Vérification des prérequis..."

command -v docker   >/dev/null 2>&1 || error "Docker non trouvé. Installe-le via : curl -fsSL https://get.docker.com | sh"
command -v python3  >/dev/null 2>&1 || error "Python 3 non trouvé."

PYTHON_VERSION=$(python3 -c 'import sys; print(sys.version_info.minor)')
[ "$PYTHON_VERSION" -ge 11 ] || error "Python 3.11+ requis (trouvé : 3.$PYTHON_VERSION)"

# -----------------------------------------------------------------------------
# 2. Fichier .env
# -----------------------------------------------------------------------------
if [ ! -f .env ]; then
    warning ".env manquant — copie depuis .env.example"
    cp .env.example .env
    warning "Édite .env avec tes mots de passe avant de continuer"
    warning "Puis relance : bash setup.sh"
    exit 0
fi

info ".env trouvé"

# -----------------------------------------------------------------------------
# 3. Installation des dépendances Python
# -----------------------------------------------------------------------------
info "Installation des dépendances Python..."
pip install -e ".[dev]" --quiet || pip install httpx sqlalchemy alembic psycopg2-binary \
    pydantic pydantic-settings apscheduler tenacity python-dotenv pytest ruff --quiet

# -----------------------------------------------------------------------------
# 4. Démarrage de PostgreSQL
# -----------------------------------------------------------------------------
info "Démarrage de PostgreSQL..."
docker compose up -d db

info "Attente que PostgreSQL soit prêt..."
until docker compose exec db pg_isready -U "${POSTGRES_USER:-bwf}" >/dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo ""
info "PostgreSQL prêt"

# -----------------------------------------------------------------------------
# 5. Migrations
# -----------------------------------------------------------------------------
info "Application des migrations Alembic..."
PYTHONPATH=. alembic upgrade head

# -----------------------------------------------------------------------------
# 6. Vérification du schéma
# -----------------------------------------------------------------------------
info "Vérification des tables créées..."
TABLE_COUNT=$(docker compose exec -T db psql -U "${POSTGRES_USER:-bwf}" \
    -d "${POSTGRES_DB:-bwf_pipeline}" \
    -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" \
    | tr -d ' ')

[ "$TABLE_COUNT" -eq 7 ] || error "Attendu 7 tables, trouvé $TABLE_COUNT"
info "7 tables créées avec succès"

# -----------------------------------------------------------------------------
# 7. Test rapide des imports
# -----------------------------------------------------------------------------
info "Vérification des imports Python..."
PYTHONPATH=. python3 -c "
from bwf.config import settings
from bwf.models import Tournament, Player, Match, SetScore, RatingHistory, BwfRanking, ScrapingJob
from bwf.scrapers.tournaments import discover_tournaments
from bwf.scrapers.matches import run_pending_jobs
print('OK')
"

# -----------------------------------------------------------------------------
# 8. Lancement des tests
# -----------------------------------------------------------------------------
info "Lancement des tests unitaires..."
PYTHONPATH=. python3 -m pytest tests/ -q

# -----------------------------------------------------------------------------
# 9. Résumé
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Pipeline BWF prêt !${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Prochaines étapes :"
echo "  1. Lancer le scraping historique (quelques heures) :"
echo "     docker compose up pipeline"
echo ""
echo "  2. Ou lancer le pipeline en arrière-plan :"
echo "     docker compose up -d pipeline"
echo "     docker compose logs -f pipeline"
echo ""
echo "  3. En cas de jobs échoués :"
echo "     python -m bwf.retry --max-retries 3"
echo ""