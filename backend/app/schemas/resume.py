"""
Pydantic v2 schemas for API request/response validation.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ─────────────────────────────────────────────────────────────
# Resume schemas
# ─────────────────────────────────────────────────────────────

class ResumeOut(BaseModel):
    id: UUID
    file_name: str
    mime_type: str
    language: str
    parse_status: str
    candidate_name: str | None = None
    candidate_email: str | None = None
    candidate_phone: str | None = None
    candidate_location: str | None = None
    skills: list[str] = []
    experience: list[dict] = []
    education: list[dict] = []
    projects: list[dict] = []
    total_experience_years: float | None = None
    is_duplicate: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ResumeOut]


class ResumeStatus(BaseModel):
    id: UUID
    parse_status: str
    parse_error: str | None = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# Job Description schemas
# ─────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    company: str | None = Field(None, max_length=255)
    description: str = Field(..., min_length=50)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    required_experience_years: int | None = Field(None, ge=0, le=50)
    required_education: str | None = None
    location: str | None = None


class JobOut(BaseModel):
    id: UUID
    title: str
    company: str | None = None
    description: str
    required_skills: list[str]
    preferred_skills: list[str]
    required_experience_years: int | None = None
    required_education: str | None = None
    location: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# Application schemas
# ─────────────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    resume_id: UUID
    job_id: UUID


class ShapValues(BaseModel):
    baseline: float
    skills_contribution: float
    experience_contribution: float
    education_contribution: float
    semantic_contribution: float


class ApplicationOut(BaseModel):
    id: UUID
    resume_id: UUID
    job_id: UUID
    score: float | None = None
    rank: int | None = None
    status: str
    skill_score: float | None = None
    experience_score: float | None = None
    education_score: float | None = None
    semantic_score: float | None = None
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    skill_gap_analysis: dict | None = None
    explanation: str | None = None
    shap_values: dict | None = None
    bias_flags: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class RankingOut(BaseModel):
    """Compact ranking view for the leaderboard."""
    id: UUID
    resume_id: UUID
    score: float | None = None
    rank: int | None = None
    status: str
    skill_score: float | None = None
    experience_score: float | None = None
    education_score: float | None = None
    semantic_score: float | None = None
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    explanation: str | None = None
    shap_values: dict | None = None

    # Denormalised from Resume for convenience
    candidate_name: str | None = None
    candidate_email: str | None = None
    candidate_location: str | None = None
    skills: list[str] = []
    total_experience_years: float | None = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# Auth schemas
# ─────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: UUID | None = None
