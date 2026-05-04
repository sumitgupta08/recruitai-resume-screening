"""
RecruitAI — FastAPI Application Entry Point.

Configures:
  - CORS, GZip, Trusted hosts middleware
  - Prometheus metrics instrumentation
  - Structured logging
  - Sentry error tracking
  - API router registration
  - Startup/shutdown lifespan events
"""
import logging

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.api.v1.endpoints import (
    auth,
    resumes,
    jobs,
    applications,
    admin,
)
from app.db.session import engine
from app.models.models import Base

# ── Structured logging setup ──────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: setup on startup, cleanup on shutdown."""
    logger.info("startup", version=settings.APP_VERSION, env=settings.ENV)
    # Create DB tables (use Alembic for production migrations)
    if settings.ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Optionally: warm-up ML models in main process
    # from app.services.nlp.parser import _get_nlp, _get_embedder
    # _get_nlp(); _get_embedder()

    yield

    logger.info("shutdown")
    await engine.dispose()


# ── App factory ───────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.ALLOWED_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if settings.ENV == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )

    # ── Prometheus metrics ────────────────────────────────────
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # ── Sentry ────────────────────────────────────────────────
    if settings.SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        sentry_sdk.init(dsn=settings.SENTRY_DSN, integrations=[FastApiIntegration()])

    # ── Routes ────────────────────────────────────────────────
    prefix = "/api/v1"
    app.include_router(auth.router,         prefix=f"{prefix}/auth",         tags=["Authentication"])
    app.include_router(resumes.router,      prefix=f"{prefix}/resumes",      tags=["Resumes"])
    app.include_router(jobs.router,         prefix=f"{prefix}/jobs",         tags=["Job Descriptions"])
    app.include_router(applications.router, prefix=f"{prefix}/applications", tags=["Applications"])
    app.include_router(admin.router,        prefix=f"{prefix}/admin",        tags=["Admin"])

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION, "env": settings.ENV}

    return app


app = create_app()
