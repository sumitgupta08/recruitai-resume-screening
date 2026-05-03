"""
Celery async task definitions.

Tasks run in background workers so the API stays responsive
during heavy NLP parsing and scoring operations.
"""
import logging
from uuid import UUID

from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Application, JobDescription, Resume
from app.services.nlp.parser import parse_resume
from app.services.scoring.scorer import score_resume_against_job
from app.services.dedup.detector import DuplicateDetector

logger = logging.getLogger(__name__)

celery_app = Celery(
    "recruitai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,              # re-queue on worker crash
    worker_prefetch_multiplier=1,     # one task at a time per worker (ML is heavy)
    task_routes={
        "app.tasks.parse_resume_task": {"queue": "parsing"},
        "app.tasks.score_application_task": {"queue": "scoring"},
        "app.tasks.batch_score_job_task": {"queue": "scoring"},
    },
)

# Sync engine for Celery workers (Celery doesn't support async)
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
    return _sync_engine


# ─────────────────────────────────────────────────────────────
# Tasks
# ─────────────────────────────────────────────────────────────

@celery_app.task(
    name="app.tasks.parse_resume_task",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def parse_resume_task(self, resume_id: str, file_bytes_b64: str, mime_type: str, file_name: str):
    """
    Parse a resume file and update the database record.
    File bytes are base64-encoded for JSON serialisation.
    """
    import base64
    try:
        file_bytes = base64.b64decode(file_bytes_b64)
        parsed = parse_resume(file_bytes, mime_type, file_name)

        engine = _get_sync_engine()
        with Session(engine) as session:
            resume = session.get(Resume, UUID(resume_id))
            if not resume:
                logger.error(f"Resume {resume_id} not found in DB")
                return

            for key, value in parsed.items():
                if hasattr(resume, key):
                    setattr(resume, key, value)
            resume.parse_status = "done"
            session.commit()
            logger.info(f"Resume {resume_id} parsed successfully")

        # Trigger duplicate check
        check_duplicate_task.delay(resume_id)

    except Exception as exc:
        logger.exception(f"Parsing failed for resume {resume_id}: {exc}")
        engine = _get_sync_engine()
        with Session(engine) as session:
            resume = session.get(Resume, UUID(resume_id))
            if resume:
                resume.parse_status = "failed"
                resume.parse_error = str(exc)
                session.commit()
        self.retry(exc=exc)


@celery_app.task(name="app.tasks.check_duplicate_task", bind=True)
def check_duplicate_task(self, resume_id: str):
    """Compare a newly parsed resume against all existing ones for duplicates."""
    try:
        engine = _get_sync_engine()
        with Session(engine) as session:
            target = session.get(Resume, UUID(resume_id))
            if not target or not target.minhash_signature:
                return

            # Load all other resume signatures (in production: use Redis LSH index)
            others = session.execute(
                select(Resume.id, Resume.minhash_signature)
                .where(Resume.id != UUID(resume_id))
                .where(Resume.minhash_signature.isnot(None))
                .where(Resume.is_duplicate == False)  # noqa
            ).all()

            detector = DuplicateDetector()
            for other_id, other_sig in others:
                detector.add(str(other_id), other_sig)

            dups = detector.add(resume_id, target.minhash_signature)
            if dups:
                target.is_duplicate = True
                target.duplicate_of = UUID(dups[0])
                logger.info(f"Resume {resume_id} is duplicate of {dups[0]}")
                session.commit()

    except Exception as exc:
        logger.exception(f"Duplicate check failed for {resume_id}: {exc}")
        self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.tasks.score_application_task", bind=True, max_retries=3)
def score_application_task(self, application_id: str):
    """Score a single application (resume × job)."""
    try:
        engine = _get_sync_engine()
        with Session(engine) as session:
            app = session.get(Application, UUID(application_id))
            if not app:
                return

            resume = app.resume
            job = app.job

            if resume.parse_status != "done":
                # Re-queue after delay if parsing not complete
                self.retry(countdown=15, max_retries=10)
                return

            resume_dict = {
                "skills": resume.skills or [],
                "experience": resume.experience or [],
                "education": resume.education or [],
                "total_experience_years": resume.total_experience_years,
                "raw_text": resume.raw_text or "",
                "embedding": resume.embedding,
                "candidate_name": resume.candidate_name,
            }
            job_dict = {
                "required_skills": job.required_skills or [],
                "preferred_skills": job.preferred_skills or [],
                "required_experience_years": job.required_experience_years,
                "required_education": job.required_education,
                "description": job.description,
                "embedding": job.embedding,
            }

            result = score_resume_against_job(resume_dict, job_dict)

            app.score = result["score"]
            app.skill_score = result["skill_score"]
            app.experience_score = result["experience_score"]
            app.education_score = result["education_score"]
            app.semantic_score = result["semantic_score"]
            app.matched_skills = result["matched_skills"]
            app.missing_skills = result["missing_skills"]
            app.skill_gap_analysis = result["skill_gap_analysis"]
            app.explanation = result["explanation"]
            app.shap_values = result["shap_values"]
            app.status = "scored"
            session.commit()

            # Update ranks for the whole job after scoring
            _update_job_ranks(session, str(job.id))
            logger.info(f"Application {application_id} scored: {result['score']:.1f}")

    except Exception as exc:
        logger.exception(f"Scoring failed for application {application_id}: {exc}")
        self.retry(exc=exc, countdown=20)


@celery_app.task(name="app.tasks.batch_score_job_task")
def batch_score_job_task(job_id: str):
    """Score ALL applications for a given job (batch re-score)."""
    engine = _get_sync_engine()
    with Session(engine) as session:
        apps = session.execute(
            select(Application.id).where(Application.job_id == UUID(job_id))
        ).scalars().all()

    group = celery_app.group(
        score_application_task.s(str(app_id)) for app_id in apps
    )
    group.apply_async()
    logger.info(f"Queued {len(apps)} scoring tasks for job {job_id}")


def _update_job_ranks(session: Session, job_id: str):
    """Recompute integer ranks for all scored applications of a job."""
    apps = session.execute(
        select(Application)
        .where(Application.job_id == UUID(job_id))
        .where(Application.score.isnot(None))
        .order_by(Application.score.desc())
    ).scalars().all()
    for rank, app in enumerate(apps, start=1):
        app.rank = rank
    session.commit()
