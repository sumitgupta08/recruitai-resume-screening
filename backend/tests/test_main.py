"""
Test suite for RecruitAI backend.
Run: pytest tests/ -v --cov=app
"""
import base64
import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import patch, MagicMock

from app.main import app
from app.db.session import get_db
from app.models.models import Base
from app.services.nlp.skill_ontology import SkillOntology
from app.services.scoring.scorer import (
    compute_skill_score,
    compute_experience_score,
    compute_education_score,
    compute_composite_score,
    generate_explanation,
)

# ── Test database ────────────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Helper to get auth token ─────────────────────────────────
async def get_token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com", "password": "testpass123", "full_name": "Test User"
    })
    resp = await client.post("/api/v1/auth/login", data={
        "username": "test@example.com", "password": "testpass123"
    })
    return resp.json()["access_token"]


# ════════════════════════════════════════════════════════════
# Auth tests
# ════════════════════════════════════════════════════════════

class TestAuth:
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com", "password": "password123", "full_name": "New User"
        })
        assert resp.status_code == 201
        assert resp.json()["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        data = {"email": "dup@example.com", "password": "pass1234", "full_name": "Dup"}
        await client.post("/api/v1/auth/register", json=data)
        resp = await client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "login@example.com", "password": "pass1234", "full_name": "Login User"
        })
        resp = await client.post("/api/v1/auth/login", data={
            "username": "login@example.com", "password": "pass1234"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "wp@example.com", "password": "correct", "full_name": "User"
        })
        resp = await client.post("/api/v1/auth/login", data={
            "username": "wp@example.com", "password": "wrong"
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_endpoint(self, client):
        token = await get_token(client)
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_unauthenticated_access(self, client):
        resp = await client.get("/api/v1/resumes/")
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════
# Skill Ontology tests
# ════════════════════════════════════════════════════════════

class TestSkillOntology:
    def setup_method(self):
        self.ontology = SkillOntology()

    def test_extract_canonical_name(self):
        skills = self.ontology.extract_skills("I have 3 years of python3 experience")
        assert "Python" in skills

    def test_extract_alias(self):
        skills = self.ontology.extract_skills("Used pytorch and sklearn for ML pipelines")
        assert "PyTorch" in skills
        assert "scikit-learn" in skills

    def test_extract_multiple(self):
        text = "Built with React, FastAPI, PostgreSQL, Docker, Redis"
        skills = self.ontology.extract_skills(text)
        assert "React" in skills
        assert "FastAPI" in skills
        assert "PostgreSQL" in skills
        assert "Docker" in skills

    def test_skill_expansion(self):
        expanded = self.ontology.expand_skills(["React"])
        assert "JavaScript" in expanded  # React implies JavaScript

    def test_skill_expansion_chain(self):
        expanded = self.ontology.expand_skills(["TypeScript"])
        assert "JavaScript" in expanded  # TypeScript → JavaScript

    def test_skill_gap_all_matched(self):
        gap = self.ontology.compute_skill_gap(
            ["Python", "Docker", "PostgreSQL"],
            ["Python", "Docker", "PostgreSQL"],
        )
        assert gap["match_rate"] == 1.0
        assert gap["missing"] == []

    def test_skill_gap_partial(self):
        gap = self.ontology.compute_skill_gap(
            ["Python", "Docker"],
            ["Python", "Docker", "Kubernetes", "AWS"],
        )
        assert "Kubernetes" in gap["missing"]
        assert "AWS" in gap["missing"]
        assert gap["match_rate"] == 0.5

    def test_skill_gap_empty_resume(self):
        gap = self.ontology.compute_skill_gap([], ["Python", "FastAPI"])
        assert gap["match_rate"] == 0.0
        assert gap["matched"] == []


# ════════════════════════════════════════════════════════════
# Scoring Engine tests
# ════════════════════════════════════════════════════════════

class TestScoringEngine:
    def test_skill_score_perfect_match(self):
        score, gap = compute_skill_score(["Python", "Docker"], ["Python", "Docker"])
        assert score >= 80.0

    def test_skill_score_no_match(self):
        score, gap = compute_skill_score(["Java", "Spring"], ["Python", "FastAPI", "Docker"])
        assert score < 30.0

    def test_experience_meets_requirement(self):
        score = compute_experience_score(candidate_years=6, required_years=5)
        assert score >= 90.0

    def test_experience_under_requirement(self):
        score = compute_experience_score(candidate_years=2, required_years=5)
        assert score < 50.0

    def test_experience_no_requirement(self):
        score = compute_experience_score(candidate_years=3, required_years=None)
        assert score == 80.0

    def test_education_exact_match(self):
        edu = [{"degree": "Bachelor's", "degree_rank": 3}]
        score = compute_education_score(edu, "Bachelor's")
        assert score == 100.0

    def test_education_over_qualified(self):
        edu = [{"degree": "PhD", "degree_rank": 5}]
        score = compute_education_score(edu, "Bachelor's")
        assert score == 100.0

    def test_education_under_qualified(self):
        edu = [{"degree": "Diploma", "degree_rank": 1}]
        score = compute_education_score(edu, "Master's")
        assert score < 70.0

    def test_composite_score_weights(self):
        score = compute_composite_score(
            skill_score=100, experience_score=100,
            education_score=100, semantic_score=100,
        )
        assert score == 100.0

    def test_composite_score_all_zero(self):
        score = compute_composite_score(0, 0, 0, 0)
        assert score == 0.0

    def test_explanation_shortlisted(self):
        explanation = generate_explanation(
            "Alice Smith", 80, 85, 75, 90, 70,
            ["Python", "Docker"], ["Kubernetes"], 5, 5
        )
        assert "SHORTLISTED" in explanation
        assert "Python" in explanation

    def test_explanation_rejected(self):
        explanation = generate_explanation(
            "Bob Jones", 35, 20, 30, 40, 45,
            [], ["Python", "FastAPI", "Docker"], 1, 5
        )
        assert "REJECTED" in explanation


# ════════════════════════════════════════════════════════════
# Resume API tests
# ════════════════════════════════════════════════════════════

class TestResumeAPI:
    @pytest.mark.asyncio
    async def test_upload_invalid_type(self, client):
        token = await get_token(client)
        resp = await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("test.txt", b"some text", "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 415

    @pytest.mark.asyncio
    async def test_list_resumes_empty(self, client):
        token = await get_token(client)
        resp = await client.get("/api/v1/resumes/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_resume(self, client):
        token = await get_token(client)
        resp = await client.get(
            "/api/v1/resumes/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════
# Health check
# ════════════════════════════════════════════════════════════

class TestHealth:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
