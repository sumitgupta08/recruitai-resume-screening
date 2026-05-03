"""
Core application configuration.
All secrets are read from environment variables — never hardcoded.
"""
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "RecruitAI Resume Screening API"
    APP_VERSION: str = "1.0.0"
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-secrets-manager"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ── CORS ─────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[AnyHttpUrl] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/recruitai"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis / Celery ────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ── Object Storage (MinIO / S3) ───────────────────────────────
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_RESUMES: str = "resumes"
    S3_REGION: str = "us-east-1"

    # ── ML Models ────────────────────────────────────────────────
    SPACY_MODEL: str = "en_core_web_lg"
    SENTENCE_TRANSFORMER_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    SIMILARITY_THRESHOLD: float = 0.75  # for duplicate detection

    # ── Scoring weights ───────────────────────────────────────────
    WEIGHT_SKILLS: float = 0.40
    WEIGHT_EXPERIENCE: float = 0.30
    WEIGHT_EDUCATION: float = 0.15
    WEIGHT_SEMANTIC: float = 0.15

    # ── Pagination ────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # ── File upload limits ────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_MIME_TYPES: list[str] = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]

    # ── Observability ─────────────────────────────────────────────
    SENTRY_DSN: str | None = None
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
