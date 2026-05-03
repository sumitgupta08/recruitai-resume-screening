# RecruitAI — AI-Powered Resume Screening System

> Production-grade resume screening with NLP parsing, semantic matching, explainable AI, and a modern React dashboard.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Features](#features)
3. [Quick Start](#quick-start)
4. [Manual Setup](#manual-setup)
5. [API Documentation](#api-documentation)
6. [Project Structure](#project-structure)
7. [AI/ML Pipeline](#aiml-pipeline)
8. [Configuration](#configuration)
9. [Testing](#testing)
10. [Deployment](#deployment)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React Frontend (Vite + TypeScript)                         │
│  Dashboard · Upload · Rankings · Admin · XAI Insights       │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/REST
┌───────────────────────▼─────────────────────────────────────┐
│  FastAPI Backend                                             │
│  Auth · Resume API · Jobs API · Applications API · Admin    │
└──────┬─────────────────────┬───────────────────────────────┘
       │                     │ Celery tasks
┌──────▼──────┐    ┌─────────▼──────────────────────────────┐
│  PostgreSQL  │    │  Celery Workers                        │
│  + pgvector │    │  parse_resume · score · dedup · rank   │
└─────────────┘    └────────────────────────────────────────┘
┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐
│    Redis     │    │   MinIO/S3  │    │  NLP/ML Models      │
│  Queue/Cache │    │  File Store  │    │  spaCy · BERT · LSH │
└─────────────┘    └─────────────┘    └─────────────────────┘
```

---

## Features

### Core
- **Resume Upload** — PDF and DOCX, single or batch (up to 50 files)
- **NLP Parsing** — Extracts name, email, phone, skills, experience, education, projects
- **Skill Ontology** — 80+ tech skills with aliases, categories, and implication rules
- **Semantic Matching** — BERT-based cosine similarity between resume and job description
- **Composite Scoring** — Weighted score (skills 40% + experience 30% + education 15% + semantic 15%)
- **Candidate Ranking** — Sorted ranked list per job with real-time updates

### AI/ML
- **NER** via spaCy `en_core_web_lg`
- **Embeddings** via `sentence-transformers/all-MiniLM-L6-v2`
- **TF-IDF + ontology expansion** for skill extraction
- **Cosine similarity** for semantic matching
- **MinHash LSH** for duplicate detection (O(1) amortised lookup)
- **SHAP-style contribution breakdown** for explainability

### Advanced
- **XAI Explanations** — Human-readable justification per candidate
- **Skill Gap Analysis** — Exact missing skills vs requirements
- **Duplicate Detection** — Near-duplicate resumes flagged automatically
- **Bias Reduction** — Gender pronoun detection, name anonymisation options
- **Multi-language Support** — Language detection via `langdetect`
- **Admin Panel** — User management, scoring weight tuning, system health

### Infrastructure
- **Async** FastAPI with SQLAlchemy async + asyncpg
- **pgvector** extension for fast vector similarity search
- **Celery** distributed task queue (separate parse and score workers)
- **MinIO** (S3-compatible) file storage
- **Prometheus + Grafana** observability
- **Docker Compose** single-command deployment

---

## Quick Start

### Prerequisites
- Docker ≥ 24 and Docker Compose ≥ 2
- 8GB RAM recommended (ML models are loaded per worker)

### One command

```bash
git clone https://github.com/yourorg/recruitai.git
cd recruitai
bash scripts/setup.sh
```

The script will:
1. Create `.env` with a random secret key
2. Build all Docker images
3. Start PostgreSQL, Redis, MinIO
4. Run database migrations
5. Generate 15 sample resumes
6. Create default admin user
7. Start all services

**Access:**

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | admin@recruitai.com / admin123 |
| API Docs (Swagger) | http://localhost:8000/api/docs | — |
| Celery Flower | http://localhost:5555 | — |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| Grafana | http://localhost:3001 | admin / admin |

---

## Manual Setup

### Backend (local dev without Docker)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download NLP models
python -m spacy download en_core_web_lg

# Copy and edit environment
cp ../.env.example .env
# Edit DATABASE_URL, REDIS_URL, S3_ENDPOINT_URL to point to local services

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A app.tasks.tasks.celery_app worker -Q parsing,scoring -c 2 --loglevel=info
```

### Frontend (local dev)

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

---

## API Documentation

Full interactive docs at **http://localhost:8000/api/docs** (Swagger UI).

### Key Endpoints

#### Authentication
```
POST /api/v1/auth/register    Register new recruiter
POST /api/v1/auth/login       Login → JWT token
GET  /api/v1/auth/me          Current user
```

#### Resumes
```
POST /api/v1/resumes/upload              Upload single resume (async)
POST /api/v1/resumes/batch-upload        Batch upload (up to 50 files)
GET  /api/v1/resumes/                    List resumes (paginated)
GET  /api/v1/resumes/{id}               Get parsed resume data
GET  /api/v1/resumes/{id}/status        Poll parse status
DELETE /api/v1/resumes/{id}             Delete resume
```

#### Job Descriptions
```
POST /api/v1/jobs/            Create job (auto-embeds description)
GET  /api/v1/jobs/            List all jobs
GET  /api/v1/jobs/{id}        Get job details
PUT  /api/v1/jobs/{id}        Update job
DELETE /api/v1/jobs/{id}      Soft delete job
```

#### Applications / Rankings
```
POST /api/v1/applications/                    Submit resume for job
POST /api/v1/applications/batch               Batch apply multiple resumes
GET  /api/v1/applications/job/{id}/rankings   Ranked candidates (scored)
GET  /api/v1/applications/{id}               Full application with XAI
POST /api/v1/applications/{id}/score         Force re-score
PATCH /api/v1/applications/{id}/status       Update status (shortlist/reject)
```

#### Admin
```
GET  /api/v1/admin/stats           Pipeline statistics
GET  /api/v1/admin/users           All users
GET  /api/v1/admin/duplicates      Flagged duplicate resumes
POST /api/v1/admin/rescore-all/{job_id}  Requeue all scoring
GET  /api/v1/admin/system-health   Service status
```

### Example: Upload and Score

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin@recruitai.com&password=admin123" | jq -r .access_token)

# 2. Create a job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senior Python Engineer",
    "description": "Build scalable Python backend services...",
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "required_experience_years": 4
  }' | jq -r .id)

# 3. Upload resume
RESUME_ID=$(curl -s -X POST http://localhost:8000/api/v1/resumes/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@resume.pdf" | jq -r .id)

# 4. Poll until parsed
until [ "$(curl -s http://localhost:8000/api/v1/resumes/$RESUME_ID/status \
  -H "Authorization: Bearer $TOKEN" | jq -r .parse_status)" = "done" ]; do
  sleep 3; echo "Parsing..."
done

# 5. Submit for scoring
APP_ID=$(curl -s -X POST http://localhost:8000/api/v1/applications/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"resume_id\": \"$RESUME_ID\", \"job_id\": \"$JOB_ID\"}" | jq -r .id)

# 6. Get rankings with explanation
curl -s http://localhost:8000/api/v1/applications/job/$JOB_ID/rankings \
  -H "Authorization: Bearer $TOKEN" | jq '.[0] | {score, rank, explanation, missing_skills}'
```

---

## Project Structure

```
resume-screening/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── deps.py              # Auth dependencies
│   │   │   └── endpoints/
│   │   │       ├── auth.py          # Login, register
│   │   │       ├── resumes.py       # Upload, parse, list
│   │   │       ├── jobs.py          # Job CRUD
│   │   │       ├── applications.py  # Score, rank, status
│   │   │       └── admin.py         # Admin-only
│   │   ├── core/
│   │   │   └── config.py            # Settings from env
│   │   ├── db/
│   │   │   └── session.py           # Async SQLAlchemy
│   │   ├── models/
│   │   │   └── models.py            # ORM models + pgvector
│   │   ├── schemas/
│   │   │   └── resume.py            # Pydantic v2 schemas
│   │   ├── services/
│   │   │   ├── nlp/
│   │   │   │   ├── parser.py        # PDF/DOCX extraction + NER
│   │   │   │   └── skill_ontology.py # 80+ skills, expansion rules
│   │   │   ├── scoring/
│   │   │   │   └── scorer.py        # Composite scoring + XAI
│   │   │   ├── dedup/
│   │   │   │   └── detector.py      # MinHash LSH deduplication
│   │   │   └── storage.py           # S3/MinIO operations
│   │   ├── tasks/
│   │   │   └── tasks.py             # Celery async tasks
│   │   └── main.py                  # FastAPI app factory
│   ├── alembic/                     # Database migrations
│   ├── tests/
│   │   └── test_main.py             # 25+ unit + integration tests
│   ├── Dockerfile
│   ├── requirements.txt
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── services/api.ts          # Typed API client
│   │   └── App.html                 # Full dashboard UI
│   ├── Dockerfile
│   └── package.json
├── nginx/
│   ├── nginx.conf                   # Reverse proxy + SSL
│   └── prometheus.yml               # Metrics scrape config
├── scripts/
│   ├── setup.sh                     # One-command setup
│   ├── init_db.sql                  # pgvector + extensions
│   └── generate_sample_data.py      # Test data generator
├── .github/workflows/
│   └── ci-cd.yml                    # GitHub Actions CI/CD
├── docker-compose.yml
└── .env.example
```

---

## AI/ML Pipeline

### Resume Parsing Flow

```
PDF/DOCX File
     │
     ▼
Text Extraction (pdfminer → PyMuPDF fallback)
     │
     ▼
Language Detection (langdetect)
     │
     ▼
spaCy NER (name, email, location entities)
     │
     ├── Section Splitter (regex header detection)
     │        ├── Experience → structured entries + year extraction
     │        ├── Education  → degree normalisation + rank scoring
     │        ├── Projects   → block extraction
     │        └── Skills     → ontology lookup + alias expansion
     │
     ├── Sentence Embedding (all-MiniLM-L6-v2)
     │
     └── MinHash Signature (128 permutations, 3-shingles)
```

### Scoring Formula

```
score = 0.40 × skill_score
       + 0.30 × experience_score
       + 0.15 × education_score
       + 0.15 × semantic_score

skill_score      = (matched_required/total_required × 0.80)
                 + (matched_preferred/total_preferred × 0.20)
experience_score = min(candidate_years/required_years, 1.0) × 90
                 + bonus up to 10 pts for over-qualification
education_score  = degree_rank >= required_rank → 100
                   degree_rank == required_rank - 1 → 70
                   else → max(30 - gap*10, 0)
semantic_score   = cosine_similarity(resume_emb, jd_emb)^0.8 × 100
```

### Duplicate Detection

MinHash LSH with Jaccard similarity threshold of 0.80. Three-gram shingles over normalised resume text. O(1) amortised lookup per new resume against the full index.

---

## Configuration

All configuration is via environment variables. See `.env.example` for full list.

### Scoring Weights

Weights must sum to 1.0:

```env
WEIGHT_SKILLS=0.40
WEIGHT_EXPERIENCE=0.30
WEIGHT_EDUCATION=0.15
WEIGHT_SEMANTIC=0.15
```

These can also be adjusted at runtime via the Admin Panel UI.

### Model Selection

```env
# Smaller/faster for development:
SPACY_MODEL=en_core_web_sm
SENTENCE_TRANSFORMER_MODEL=sentence-transformers/paraphrase-MiniLM-L3-v2

# Higher accuracy for production:
SPACY_MODEL=en_core_web_lg
SENTENCE_TRANSFORMER_MODEL=sentence-transformers/all-mpnet-base-v2
```

---

## Testing

```bash
cd backend

# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=app --cov-report=html
open htmlcov/index.html

# Run specific test class
pytest tests/test_main.py::TestSkillOntology -v

# Run with live DB (integration tests)
DATABASE_URL=postgresql+asyncpg://... pytest tests/ -v
```

Test coverage includes:
- Auth: register, login, JWT validation, access control
- Skill Ontology: extraction, expansion, gap analysis
- Scoring Engine: all sub-scores, composite, explanation generation
- Resume API: upload validation, pagination, 404 handling
- Health endpoint

---

## Deployment

### Production Checklist

- [ ] Set `ENV=production` in `.env`
- [ ] Set strong random `SECRET_KEY` (32+ hex bytes)
- [ ] Configure real AWS S3 (remove `S3_ENDPOINT_URL`)
- [ ] Set `SENTRY_DSN` for error tracking
- [ ] Add SSL certs to `nginx/ssl/`
- [ ] Update `ALLOWED_ORIGINS` to production domain
- [ ] Set `DEBUG=false`
- [ ] Configure external PostgreSQL with daily backups
- [ ] Scale Celery workers: `docker compose up -d --scale worker-parse=2 --scale worker-score=4`

### Scaling Celery Workers

```bash
# More parse workers for high upload volume
docker compose up -d --scale worker-parse=3

# More score workers for large batches
docker compose up -d --scale worker-score=6
```

### Resource Requirements

| Service | Min RAM | Recommended |
|---------|---------|-------------|
| API | 512MB | 1GB |
| Parse Worker | 2GB | 4GB (NLP models) |
| Score Worker | 1GB | 2GB |
| PostgreSQL | 512MB | 2GB |
| Redis | 256MB | 512MB |

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run tests: `pytest tests/ -v`
4. Commit and push
5. Open a Pull Request

---

## License

MIT License — see `LICENSE` file.
