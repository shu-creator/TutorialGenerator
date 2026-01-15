"""Web UI views for ManualStudio."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import Job, JobStatus, get_db
from app.schemas.theme import (
    ALLOWED_LOGO_EXTENSIONS,
    MAX_LOGO_SIZE_BYTES,
    merge_theme_with_defaults,
)
from app.services.storage import get_storage_service

logger = get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="templates")
settings = get_settings()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home page with upload form."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "max_video_minutes": settings.max_video_minutes,
            "max_video_size_mb": settings.max_video_size_mb,
        },
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str, db: Session = Depends(get_db)):
    """Job detail page."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get steps data if available
    steps_data = None
    if job.steps_json_uri:
        try:
            storage = get_storage_service()
            key = storage.key_from_uri(job.steps_json_uri)
            import json

            content = storage.download_bytes(key)
            steps_data = json.loads(content)
        except Exception as e:
            logger.warning(f"Failed to load steps: {e}")

    return templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "job": job,
            "steps_data": steps_data,
            "JobStatus": JobStatus,
        },
    )


@router.get("/jobs/{job_id}/steps", response_class=HTMLResponse)
async def steps_preview(request: Request, job_id: str, db: Session = Depends(get_db)):
    """Steps preview page."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.steps_json_uri:
        raise HTTPException(status_code=404, detail="Steps not yet generated")

    # Load steps data
    try:
        storage = get_storage_service()
        key = storage.key_from_uri(job.steps_json_uri)
        import json

        content = storage.download_bytes(key)
        steps_data = json.loads(content)
    except Exception as e:
        logger.error(f"Failed to load steps: {e}")
        raise HTTPException(status_code=500, detail="Failed to load steps")

    # Load theme settings
    theme = merge_theme_with_defaults(job.theme_json)

    return templates.TemplateResponse(
        "steps_preview.html",
        {
            "request": request,
            "job": job,
            "steps_data": steps_data,
            "theme": theme.model_dump(),
            "max_logo_size_kb": MAX_LOGO_SIZE_BYTES // 1024,
            "allowed_logo_extensions": ", ".join(ALLOWED_LOGO_EXTENSIONS),
        },
    )
