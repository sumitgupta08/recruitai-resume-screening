"""
Resume API endpoints.

POST /resumes/upload           – Upload single resume (async parse)
POST /resumes/batch-upload     – Upload multiple resumes
GET  /resumes/                 – List all resumes (paginated)
GET  /resumes/{id}             – Get single resume with parsed data
DELETE /resumes/{id}           – Delete resume
GET  /resumes/{id}/status      – Poll parse status (for async UI)
"""
import base64
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.models import Resume
from app.schemas.resume import ResumeOut, ResumeListOut, ResumeStatus
from app.services.storage import upload_file_to_s3
from app.tasks.tasks import parse_resume_task
from app.api.v1.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


async def _validate_upload(file: UploadFile) -> bytes:
    """Validate file size and MIME type, return raw bytes."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Only PDF and DOCX allowed.",
        )
    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.",
        )
    return file_bytes


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Upload a single resume file.
    Parsing happens asynchronously — poll `/resumes/{id}/status` for completion.
    """
    file_bytes = await _validate_upload(file)
    file_key = f"resumes/{uuid4()}/{file.filename}"

    # Store file in S3/MinIO
    await upload_file_to_s3(file_bytes, file_key, file.content_type)

    # Create DB record (status = pending)
    resume = Resume(
        file_name=file.filename,
        file_key=file_key,
        file_size_bytes=len(file_bytes),
        mime_type=file.content_type,
        parse_status="pending",
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    # Dispatch async parse task
    parse_resume_task.delay(
        str(resume.id),
        base64.b64encode(file_bytes).decode(),
        file.content_type,
        file.filename,
    )

    logger.info(f"Resume uploaded: {resume.id}, queued for parsing")
    return resume


@router.post("/batch-upload", status_code=status.HTTP_202_ACCEPTED)
async def batch_upload_resumes(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Upload multiple resumes in one request.
    Returns list of created resume IDs for status polling.
    """
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per batch.")

    results = []
    for file in files:
        try:
            file_bytes = await _validate_upload(file)
            file_key = f"resumes/{uuid4()}/{file.filename}"
            await upload_file_to_s3(file_bytes, file_key, file.content_type)

            resume = Resume(
                file_name=file.filename,
                file_key=file_key,
                file_size_bytes=len(file_bytes),
                mime_type=file.content_type,
                parse_status="pending",
            )
            db.add(resume)
            await db.flush()  # get ID before commit

            parse_resume_task.delay(
                str(resume.id),
                base64.b64encode(file_bytes).decode(),
                file.content_type,
                file.filename,
            )
            results.append({"id": str(resume.id), "file_name": file.filename, "status": "queued"})
        except HTTPException as e:
            results.append({"file_name": file.filename, "error": e.detail})

    await db.commit()
    return {"uploaded": len([r for r in results if "id" in r]), "results": results}


@router.get("/", response_model=ResumeListOut)
async def list_resumes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List resumes with optional status filtering and pagination."""
    query = select(Resume).where(Resume.is_duplicate == False)  # noqa
    if status_filter:
        query = query.where(Resume.parse_status == status_filter)

    total_q = select(func.count()).select_from(Resume).where(Resume.is_duplicate == False)  # noqa
    total = (await db.execute(total_q)).scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Resume.created_at.desc())
    resumes = (await db.execute(query)).scalars().all()

    return {"total": total, "page": page, "page_size": page_size, "items": resumes}


@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.get("/{resume_id}/status", response_model=ResumeStatus)
async def get_resume_status(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Lightweight endpoint for polling parse status."""
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"id": resume.id, "parse_status": resume.parse_status, "parse_error": resume.parse_error}


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    await db.delete(resume)
    await db.commit()
