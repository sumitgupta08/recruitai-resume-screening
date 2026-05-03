"""
SQLAlchemy ORM models.
pgvector extension enables efficient semantic similarity search.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ─────────────────────────────────────────────────────────────
# Users / Recruiters
# ─────────────────────────────────────────────────────────────

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="recruiter")  # admin | recruiter
    is_active = Column(Boolean, default=True, nullable=False)

    job_descriptions = relationship("JobDescription", back_populates="created_by_user")


# ─────────────────────────────────────────────────────────────
# Job Descriptions
# ─────────────────────────────────────────────────────────────

class JobDescription(Base, TimestampMixin):
    __tablename__ = "job_descriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    required_skills = Column(JSON, default=list)       # ["Python", "FastAPI", ...]
    preferred_skills = Column(JSON, default=list)
    required_experience_years = Column(Integer, nullable=True)
    required_education = Column(String(100), nullable=True)  # "Bachelor's", "Master's"
    location = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    embedding = Column(Vector(384), nullable=True)    # semantic embedding for JD

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_by_user = relationship("User", back_populates="job_descriptions")
    applications = relationship("Application", back_populates="job")


# ─────────────────────────────────────────────────────────────
# Resumes / Candidates
# ─────────────────────────────────────────────────────────────

class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String(500), nullable=False)
    file_key = Column(String(500), nullable=False)       # S3/MinIO object key
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=False)
    language = Column(String(10), default="en")
    raw_text = Column(Text, nullable=True)               # extracted text
    parse_status = Column(String(50), default="pending") # pending|processing|done|failed
    parse_error = Column(Text, nullable=True)

    # Structured parsed data
    candidate_name = Column(String(255), nullable=True)
    candidate_email = Column(String(255), nullable=True)
    candidate_phone = Column(String(50), nullable=True)
    candidate_location = Column(String(255), nullable=True)
    skills = Column(JSON, default=list)                  # ["Python", "Docker", ...]
    experience = Column(JSON, default=list)              # [{title, company, years, ...}]
    education = Column(JSON, default=list)               # [{degree, institution, year}]
    projects = Column(JSON, default=list)                # [{name, description, skills}]
    certifications = Column(JSON, default=list)
    total_experience_years = Column(Float, nullable=True)

    # AI features
    embedding = Column(Vector(384), nullable=True)       # semantic embedding
    minhash_signature = Column(JSON, nullable=True)      # for duplicate detection (LSH)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True)

    applications = relationship("Application", back_populates="resume")


# ─────────────────────────────────────────────────────────────
# Applications (Resume × Job)
# ─────────────────────────────────────────────────────────────

class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("resume_id", "job_id", name="uq_resume_job"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id"), nullable=False)
    score = Column(Float, nullable=True)                 # 0-100 composite score
    rank = Column(Integer, nullable=True)
    status = Column(String(50), default="pending")       # pending|scored|shortlisted|rejected

    # Score components
    skill_score = Column(Float, nullable=True)
    experience_score = Column(Float, nullable=True)
    education_score = Column(Float, nullable=True)
    semantic_score = Column(Float, nullable=True)

    # Explainability
    matched_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)          # skill gaps
    skill_gap_analysis = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)            # human-readable XAI
    shap_values = Column(JSON, nullable=True)            # SHAP contribution values

    # Bias flags
    bias_flags = Column(JSON, default=list)              # e.g. ["gender_pronoun_detected"]

    resume = relationship("Resume", back_populates="applications")
    job = relationship("JobDescription", back_populates="applications")
