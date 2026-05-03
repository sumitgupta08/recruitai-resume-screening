"""
Admin-only endpoints.

GET  /admin/stats           – Pipeline-wide statistics
GET  /admin/users           – List all users
PUT  /admin/users/{id}      – Activate/deactivate user
GET  /admin/duplicates      – List flagged duplicate resumes
POST /admin/rescore-all     – Requeue all scoring tasks for a job
GET  /admin/system-health   – Service health snapshot
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_admin
from app.db.session import get_db
from app.models.models import Application, JobDescription, Resume, User
from app.tasks.tasks import batch_score_job_task

router = APIRouter()


@router.get("/stats")
async def pipeline_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Aggregate statistics for the admin dashboard."""
    total_resumes = (await db.execute(select(func.count(Resume.id)))).scalar_one()
    parsed_resumes = (
        await db.execute(select(func.count(Resume.id)).where(Resume.parse_status == "done"))
    ).scalar_one()
    total_jobs = (await db.execute(select(func.count(JobDescription.id)))).scalar_one()
    total_apps = (await db.execute(select(func.count(Application.id)))).scalar_one()
    shortlisted = (
        await db.execute(select(func.count(Application.id)).where(Application.status == "shortlisted"))
    ).scalar_one()
    avg_score = (
        await db.execute(select(func.avg(Application.score)).where(Application.score.isnot(None)))
    ).scalar_one()
    duplicates = (
        await db.execute(select(func.count(Resume.id)).where(Resume.is_duplicate == True))  # noqa
    ).scalar_one()

    return {
        "resumes": {"total": total_resumes, "parsed": parsed_resumes, "duplicates": duplicates},
        "jobs": {"total": total_jobs},
        "applications": {
            "total": total_apps,
            "shortlisted": shortlisted,
            "avg_score": round(float(avg_score or 0), 2),
        },
    }


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    users = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return [
        {"id": str(u.id), "email": u.email, "full_name": u.full_name,
         "role": u.role, "is_active": u.is_active, "created_at": u.created_at}
        for u in users
    ]


@router.put("/users/{user_id}/toggle-active")
async def toggle_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = not user.is_active
    await db.commit()
    return {"id": str(user.id), "is_active": user.is_active}


@router.get("/duplicates")
async def list_duplicates(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    dups = (
        await db.execute(
            select(Resume)
            .where(Resume.is_duplicate == True)  # noqa
            .order_by(Resume.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "file_name": r.file_name,
            "candidate_name": r.candidate_name,
            "duplicate_of": str(r.duplicate_of),
            "created_at": r.created_at,
        }
        for r in dups
    ]


@router.post("/rescore-all/{job_id}")
async def rescore_all(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    job = await db.get(JobDescription, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    batch_score_job_task.delay(str(job_id))
    return {"message": f"Re-scoring all applications for job {job_id} queued."}


@router.get("/system-health")
async def system_health():
    """Quick health check of all downstream services."""
    import redis.asyncio as aioredis
    results = {}

    # Redis
    try:
        from app.core.config import settings
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        results["redis"] = "ok"
    except Exception as e:
        results["redis"] = f"error: {e}"

    results["api"] = "ok"
    return results
