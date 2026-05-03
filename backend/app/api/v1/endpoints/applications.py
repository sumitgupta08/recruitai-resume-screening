"""
Applications API — the core matching/ranking endpoints.

POST /applications/                         – Create application (resume × job)
POST /applications/batch                    – Batch apply multiple resumes to a job
GET  /applications/job/{job_id}/rankings    – Ranked candidates for a job
GET  /applications/{id}                     – Get single application with full XAI
POST /applications/{id}/score              – Re-score on demand
"""
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Application, JobDescription, Resume
from app.schemas.application import ApplicationOut, ApplicationCreate, RankingOut
from app.tasks.tasks import score_application_task, batch_score_job_task
from app.api.v1.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=ApplicationOut, status_code=status.HTTP_202_ACCEPTED)
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Submit a resume for a job.
    Scoring happens asynchronously via Celery.
    """
    # Validate resume and job exist
    resume = await db.get(Resume, payload.resume_id)
    job = await db.get(JobDescription, payload.job_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    if not job:
        raise HTTPException(404, "Job description not found")

    # Check for duplicate application
    existing = await db.execute(
        select(Application).where(
            Application.resume_id == payload.resume_id,
            Application.job_id == payload.job_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Application already exists for this resume/job pair")

    application = Application(
        resume_id=payload.resume_id,
        job_id=payload.job_id,
        status="pending",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)

    score_application_task.delay(str(application.id))
    logger.info(f"Application {application.id} created, scoring queued")
    return application


@router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
async def batch_apply(
    job_id: UUID,
    resume_ids: list[UUID],
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Apply multiple resumes to a single job at once."""
    job = await db.get(JobDescription, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    created, skipped = 0, 0
    for rid in resume_ids:
        existing = await db.execute(
            select(Application).where(Application.resume_id == rid, Application.job_id == job_id)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        app = Application(resume_id=rid, job_id=job_id, status="pending")
        db.add(app)
        created += 1

    await db.commit()

    # Score all applications for this job in background
    batch_score_job_task.delay(str(job_id))

    return {"job_id": str(job_id), "created": created, "skipped_duplicates": skipped}


@router.get("/job/{job_id}/rankings", response_model=list[RankingOut])
async def get_job_rankings(
    job_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    min_score: float = Query(0.0, ge=0, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Returns ranked candidates for a job, highest score first.
    Includes score breakdown and XAI explanation per candidate.
    """
    query = (
        select(Application)
        .join(Resume)
        .where(Application.job_id == job_id)
        .where(Application.score >= min_score)
    )
    if status_filter:
        query = query.where(Application.status == status_filter)

    query = query.order_by(Application.score.desc()).offset((page - 1) * page_size).limit(page_size)
    apps = (await db.execute(query)).scalars().all()

    return apps


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app


@router.post("/{application_id}/score", status_code=status.HTTP_202_ACCEPTED)
async def rescore_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Force re-scoring of an application (e.g., after JD update)."""
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")

    app.status = "pending"
    await db.commit()
    score_application_task.delay(str(application_id))
    return {"message": "Re-scoring queued", "application_id": str(application_id)}


@router.patch("/{application_id}/status")
async def update_application_status(
    application_id: UUID,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Recruiter action: shortlist, reject, etc."""
    VALID = {"pending", "scored", "shortlisted", "rejected", "hired"}
    if new_status not in VALID:
        raise HTTPException(400, f"Invalid status. Must be one of: {VALID}")

    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")

    app.status = new_status
    await db.commit()
    return {"id": str(application_id), "status": new_status}
