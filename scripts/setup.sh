#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
# RecruitAI — One-command setup script
# Usage: bash scripts/setup.sh
# ══════════════════════════════════════════════════════════════
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${BLUE}[RecruitAI]${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

log "Starting RecruitAI setup..."

# ── Check prerequisites ───────────────────────────────────────
command -v docker >/dev/null 2>&1 || { echo "Docker is required. Install: https://docs.docker.com/get-docker/"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1 || { echo "Docker Compose is required"; exit 1; }
ok "Docker found"

# ── Environment file ──────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    # Generate a random secret key
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    sed -i.bak "s/change-me-to-a-random-256-bit-secret/$SECRET/" .env && rm -f .env.bak
    ok ".env created with random SECRET_KEY"
else
    warn ".env already exists — skipping"
fi

# ── Pull / build images ───────────────────────────────────────
log "Building Docker images (this may take 5-10 min on first run)..."
docker compose build --parallel
ok "Images built"

# ── Start infrastructure ──────────────────────────────────────
log "Starting infrastructure services..."
docker compose up -d db redis minio
log "Waiting for PostgreSQL to be ready..."
until docker compose exec -T db pg_isready -U postgres >/dev/null 2>&1; do
    sleep 2; echo -n "."
done
echo ""
ok "PostgreSQL ready"

# ── Run migrations ─────────────────────────────────────────────
log "Running database migrations..."
docker compose run --rm api alembic upgrade head
ok "Migrations applied"

# ── Start all services ────────────────────────────────────────
log "Starting all services..."
docker compose up -d
ok "All services started"

# ── Generate sample data ──────────────────────────────────────
log "Generating sample data..."
docker compose exec api python scripts/generate_sample_data.py --count 15 --output /tmp/sample_data
ok "Sample data generated"

# ── Create default admin user ─────────────────────────────────
log "Creating default admin user..."
docker compose exec -T api python - <<'EOF'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models.models import User
from app.api.v1.endpoints.auth import hash_password

async def create_admin():
    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, class_=AsyncSession)
    async with Session() as session:
        from sqlalchemy import select
        existing = await session.execute(select(User).where(User.email == "admin@recruitai.com"))
        if not existing.scalar_one_or_none():
            admin = User(email="admin@recruitai.com", hashed_password=hash_password("admin123"),
                        full_name="Admin User", role="admin")
            session.add(admin)
            await session.commit()
            print("Admin created: admin@recruitai.com / admin123")
        else:
            print("Admin already exists")

asyncio.run(create_admin())
EOF
ok "Admin user ready"

echo ""
echo "══════════════════════════════════════════════════════"
echo -e "${GREEN}RecruitAI is running!${NC}"
echo "══════════════════════════════════════════════════════"
echo ""
echo "  🌐 Frontend:     http://localhost:3000"
echo "  🔌 API:          http://localhost:8000"
echo "  📚 API Docs:     http://localhost:8000/api/docs"
echo "  🌸 Celery UI:    http://localhost:5555"
echo "  🗄  MinIO:        http://localhost:9001  (minioadmin/minioadmin)"
echo "  📊 Grafana:      http://localhost:3001  (admin/admin)"
echo ""
echo "  👤 Default login: admin@recruitai.com / admin123"
echo ""
echo "  Stop:  docker compose down"
echo "  Logs:  docker compose logs -f api"
echo ""
