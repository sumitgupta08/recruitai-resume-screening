"""
Job Description endpoints.

POST /jobs/          – Create job description
GET  /jobs/          – List all jobs (paginated)
GET  /jobs/{id}      – Get single job
PUT  /jobs/{id}      – Update job
DELETE /jobs/{id}    – Delete job
POST /jobs/{id}/embed – Recompute embedding for semantic search
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import JobDescription
from app.schemas.resume import JobCreate, JobOut
from app.api.v1.deps import get_current_user
from app.services.nlp.parser import compute_embedding

router = APIRouter()


@router.post("/", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a job description and compute its semantic embedding."""
    embedding = compute_embedding(payload.description[:2000])
    job = JobDescription(
        **payload.model_dump(),
        embedding=embedding,
        created_by=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/", response_model=dict)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(JobDescription)
    if active_only:
        q = q.where(JobDescription.is_active == True)  # noqa

    total = (await db.execute(select(func.count()).select_from(JobDescription))).scalar_one()
    jobs = (
        await db.execute(q.order_by(JobDescription.created_at.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    return {"total": total, "page": page, "page_size": page_size, "items": jobs}


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    job = await db.get(JobDescription, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.put("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: UUID,
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    job = await db.get(JobDescription, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    for key, value in payload.model_dump().items():
        setattr(job, key, value)
    # Recompute embedding if description changed
    job.embedding = compute_embedding(payload.description[:2000])
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    job = await db.get(JobDescription, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.is_active = False   # soft delete
    await db.commit()


@router.post("/{job_id}/embed", status_code=200)
async def recompute_embedding(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Force recompute semantic embedding (use after model updates)."""
    job = await db.get(JobDescription, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.embedding = compute_embedding(job.description[:2000])
    await db.commit()
    return {"message": "Embedding recomputed", "job_id": str(job_id)}
