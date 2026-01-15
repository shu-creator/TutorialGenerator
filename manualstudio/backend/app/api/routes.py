"""API routes for ManualStudio."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger, set_trace_id
from app.db import Job, JobStatus, StepsVersion, get_db
from app.schemas.theme import (
    ALLOWED_LOGO_CONTENT_TYPES,
    ALLOWED_LOGO_EXTENSIONS,
    MAX_LOGO_SIZE_BYTES,
    Theme,
    ThemeUpdate,
    merge_theme_with_defaults,
)
from app.services.llm import LLMValidationError, validate_steps_json
from app.services.storage import get_storage_service
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
router = APIRouter(prefix="/api")
settings = get_settings()

# Allowed video extensions
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


class StepsUpdateRequest(BaseModel):
    """Request body for updating steps."""

    steps_json: dict
    edit_note: str | None = None


def _build_content_disposition(filename: str) -> str:
    safe_name = quote(filename, safe="")
    return f"attachment; filename*=UTF-8''{safe_name}"


@router.post("/jobs")
async def create_job(
    video_file: UploadFile = File(...),
    title: str | None = Form(None),
    goal: str | None = Form(None),
    language: str = Form("ja"),
    db: Session = Depends(get_db),
):
    """
    Create a new video processing job.

    - Upload a video file (mp4/mov)
    - Optionally provide title, goal, and language
    - Returns job_id and initial status
    """
    # Generate trace ID for this request
    trace_id = str(uuid.uuid4())[:8]
    set_trace_id(trace_id)

    logger.info(f"Creating new job, file: {video_file.filename}")

    # Validate file extension
    filename = video_file.filename or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: {ext}. Supported: mp4, mov, avi, mkv, webm",
        )

    # Check file size
    video_file.file.seek(0, 2)
    file_size = video_file.file.tell()
    video_file.file.seek(0)

    max_size = settings.max_video_size_bytes
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Video file too large ({file_size / 1024 / 1024:.1f}MB). Maximum: {max_size / 1024 / 1024:.0f}MB",
        )

    # Create job record
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        status=JobStatus.QUEUED,
        title=title,
        goal=goal,
        language=language,
        trace_id=trace_id,
    )
    db.add(job)

    # Upload video to storage
    try:
        storage = get_storage_service()
        video_key = f"jobs/{job_id}/input{ext}"
        storage.upload_file(video_file.file, video_key, video_file.content_type)
        job.input_video_uri = f"s3://{settings.s3_bucket}/{video_key}"
    except Exception as e:
        logger.error(f"Failed to upload video: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to upload video")

    db.commit()

    # Queue the processing task
    try:
        celery_app.send_task(
            "app.workers.tasks.process_video", args=[str(job_id)], task_id=str(job_id)
        )
    except Exception as e:
        logger.error(f"Failed to queue job {job_id}: {e}")
        job.status = JobStatus.FAILED
        job.error_code = "QUEUE_ERROR"
        job.error_message = str(e)
        job.updated_at = datetime.utcnow()
        db.commit()
        try:
            storage.delete_object(video_key)
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup uploaded video: {cleanup_error}")
        raise HTTPException(status_code=500, detail="Failed to queue processing task")

    logger.info(f"Job created: {job_id}")

    return JSONResponse(
        status_code=201,
        content={
            "job_id": str(job_id),
            "status": job.status.value,
            "message": "Job created and queued for processing",
        },
    )


@router.get("/jobs")
async def list_jobs(
    status: str | None = Query(
        None, description="Filter by status (QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELED)"
    ),
    q: str | None = Query(None, description="Search query for title/goal"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: Literal["created_at", "-created_at"] = Query("-created_at", description="Sort order"),
    db: Session = Depends(get_db),
):
    """
    List jobs with filtering, search, and pagination.

    - status: Filter by job status
    - q: Search in title and goal fields
    - page: Page number (1-indexed)
    - page_size: Number of items per page (max 100)
    - sort: Sort by created_at (prefix with - for descending)
    """
    query = db.query(Job)

    # Filter by status
    if status:
        status_upper = status.upper()
        try:
            job_status = JobStatus(status_upper)
            query = query.filter(Job.status == job_status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {', '.join([s.value for s in JobStatus])}",
            )

    # Search in title and goal
    if q:
        search_pattern = f"%{q}%"
        query = query.filter(
            or_(
                Job.title.ilike(search_pattern),
                Job.goal.ilike(search_pattern),
            )
        )

    # Get total count
    total = query.count()

    # Apply sorting
    if sort == "-created_at":
        query = query.order_by(Job.created_at.desc())
    else:
        query = query.order_by(Job.created_at.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    jobs = query.offset(offset).limit(page_size).all()

    return {
        "items": [job.to_dict() for job in jobs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.post("/jobs/batch")
async def create_batch_jobs(
    video_files: list[UploadFile] = File(..., description="Multiple video files"),
    title_prefix: str | None = Form(None, description="Title prefix for all jobs"),
    goal: str | None = Form(None, description="Goal for all jobs"),
    language: str = Form("ja", description="Language for all jobs"),
    db: Session = Depends(get_db),
):
    """
    Create multiple jobs from multiple video files.

    - Uploads multiple video files at once
    - Creates a job for each file
    - Returns list of created job IDs
    """
    if not video_files:
        raise HTTPException(status_code=400, detail="No video files provided")

    if len(video_files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files per batch")

    created_jobs = []
    errors = []

    for idx, video_file in enumerate(video_files):
        try:
            # Generate trace ID for this job
            trace_id = str(uuid.uuid4())[:8]

            # Validate file extension
            filename = video_file.filename or f"video_{idx}.mp4"
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_VIDEO_EXTENSIONS:
                errors.append(
                    {
                        "file": filename,
                        "error": f"Unsupported video format: {ext}",
                    }
                )
                continue

            # Check file size
            video_file.file.seek(0, 2)
            file_size = video_file.file.tell()
            video_file.file.seek(0)

            max_size = settings.max_video_size_bytes
            if file_size > max_size:
                errors.append(
                    {
                        "file": filename,
                        "error": f"File too large ({file_size / 1024 / 1024:.1f}MB)",
                    }
                )
                continue

            # Generate title from filename or prefix
            base_name = os.path.splitext(filename)[0]
            job_title = f"{title_prefix} - {base_name}" if title_prefix else base_name

            # Create job record
            job_id = uuid.uuid4()
            job = Job(
                id=job_id,
                status=JobStatus.QUEUED,
                title=job_title,
                goal=goal,
                language=language,
                trace_id=trace_id,
            )
            db.add(job)

            # Upload video to storage
            storage = get_storage_service()
            video_key = f"jobs/{job_id}/input{ext}"
            storage.upload_file(video_file.file, video_key, video_file.content_type)
            job.input_video_uri = f"s3://{settings.s3_bucket}/{video_key}"

            # Queue the processing task
            try:
                celery_app.send_task(
                    "app.workers.tasks.process_video",
                    args=[str(job_id)],
                    task_id=str(job_id),
                )
            except Exception as e:
                db.rollback()
                try:
                    storage.delete_object(video_key)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup uploaded video: {cleanup_error}")
                errors.append(
                    {
                        "file": filename,
                        "error": f"Failed to queue job: {e}",
                    }
                )
                continue

            db.commit()

            created_jobs.append(
                {
                    "job_id": str(job_id),
                    "file": filename,
                    "status": "QUEUED",
                }
            )

            logger.info(f"Batch job created: {job_id} for file {filename}")

        except Exception as e:
            logger.error(f"Failed to create job for {video_file.filename}: {e}")
            db.rollback()
            if "video_key" in locals():
                try:
                    storage.delete_object(video_key)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup uploaded video: {cleanup_error}")
            errors.append(
                {
                    "file": video_file.filename or f"file_{idx}",
                    "error": str(e),
                }
            )

    return JSONResponse(
        status_code=201 if created_jobs else 400,
        content={
            "created": created_jobs,
            "errors": errors,
            "total_created": len(created_jobs),
            "total_errors": len(errors),
        },
    )


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get job status and details.

    Returns:
        - job_id, status, stage, progress
        - error_message if failed
        - outputs info if succeeded
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": str(job.id),
        "status": job.status.value,
        "stage": job.stage,
        "progress": job.progress,
        "title": job.title,
        "goal": job.goal,
        "language": job.language,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "current_steps_version": job.current_steps_version,
    }

    if job.status == JobStatus.FAILED:
        response["error_code"] = job.error_code
        response["error_message"] = job.error_message
        response["trace_id"] = job.trace_id

    if job.status == JobStatus.SUCCEEDED:
        response["outputs"] = {
            "steps_json": job.steps_json_uri is not None,
            "pptx": job.pptx_uri is not None,
            "frames": job.frames_prefix_uri is not None,
        }
        response["video_info"] = {
            "duration_sec": job.video_duration_sec,
            "fps": job.video_fps,
            "resolution": job.video_resolution,
        }

    return response


@router.get("/jobs/{job_id}/steps")
async def get_job_steps(job_id: str, version: int | None = None, db: Session = Depends(get_db)):
    """
    Get steps.json for a job.

    Args:
        version: Optional specific version to retrieve. Defaults to current version.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Try to get from steps_versions first
    target_version = version or job.current_steps_version
    steps_version = (
        db.query(StepsVersion)
        .filter(StepsVersion.job_id == job_uuid, StepsVersion.version == target_version)
        .first()
    )

    if steps_version:
        return {
            "version": steps_version.version,
            "edit_source": steps_version.edit_source,
            "created_at": steps_version.created_at.isoformat()
            if steps_version.created_at
            else None,
            "steps_json": steps_version.steps_json,
        }

    # Fallback to storage
    if not job.steps_json_uri:
        raise HTTPException(status_code=404, detail="Steps not yet generated")

    try:
        storage = get_storage_service()
        key = storage.key_from_uri(job.steps_json_uri)
        content = storage.download_bytes(key)
        return {
            "version": 1,
            "edit_source": "llm",
            "steps_json": json.loads(content),
        }
    except Exception as e:
        logger.error(f"Failed to download steps.json: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve steps")


@router.put("/jobs/{job_id}/steps")
async def update_job_steps(job_id: str, request: StepsUpdateRequest, db: Session = Depends(get_db)):
    """
    Update steps.json for a job.

    - Validates the new steps against JSON schema
    - Creates a new version in steps_versions
    - Updates the storage with the new steps
    - Does NOT regenerate PPTX (use /regenerate/pptx for that)
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit steps for job in {job.status.value} status. Job must be SUCCEEDED.",
        )

    # Validate steps.json schema
    try:
        validate_steps_json(request.steps_json)
    except LLMValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={"error_code": ErrorCode.STEPS_SCHEMA_INVALID.value, "message": str(e)},
        )

    # Get current max version
    max_version = db.query(StepsVersion).filter(StepsVersion.job_id == job_uuid).count()
    new_version = max_version + 1

    # Create new steps version
    steps_version = StepsVersion(
        job_id=job_uuid,
        version=new_version,
        steps_json=request.steps_json,
        edit_source="manual",
        edit_note=request.edit_note,
    )
    db.add(steps_version)

    # Update job's current version
    job.current_steps_version = new_version
    job.updated_at = datetime.utcnow()

    # Upload new steps.json to storage
    try:
        storage = get_storage_service()
        steps_key = f"jobs/{job_id}/steps_v{new_version}.json"
        steps_bytes = json.dumps(request.steps_json, ensure_ascii=False, indent=2).encode("utf-8")
        storage.upload_bytes(steps_bytes, steps_key, "application/json")

        # Update main steps.json URI
        job.steps_json_uri = f"s3://{settings.s3_bucket}/{steps_key}"
    except Exception as e:
        logger.error(f"Failed to upload steps.json: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save steps")

    db.commit()

    logger.info(f"Steps updated for job {job_id}, version {new_version}")

    return {
        "job_id": str(job_id),
        "version": new_version,
        "message": "Steps updated successfully. Use /regenerate/pptx to regenerate the PowerPoint.",
    }


@router.post("/jobs/{job_id}/regenerate/pptx")
async def regenerate_pptx(job_id: str, db: Session = Depends(get_db)):
    """
    Regenerate PPTX from current steps.json.

    - Uses existing frames (does not re-extract)
    - Uses current steps version
    - Queues a PPTX-only generation task
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot regenerate PPTX for job in {job.status.value} status. Job must be SUCCEEDED.",
        )

    if not job.frames_prefix_uri:
        raise HTTPException(status_code=400, detail="No frames available for this job")

    if not job.steps_json_uri:
        raise HTTPException(status_code=400, detail="No steps available for this job")

    # Generate new trace ID
    trace_id = str(uuid.uuid4())[:8]

    # Update job status for regeneration
    job.status = JobStatus.RUNNING
    job.stage = "GENERATE_PPTX_ONLY"
    job.progress = 0
    job.error_code = None
    job.error_message = None
    job.trace_id = trace_id
    db.commit()

    # Queue the PPTX regeneration task
    task_id = f"{job_id}-pptx-{trace_id}"
    celery_app.send_task("app.workers.tasks.regenerate_pptx", args=[str(job_id)], task_id=task_id)

    logger.info(f"PPTX regeneration queued for job {job_id}")

    return {
        "job_id": str(job_id),
        "status": "RUNNING",
        "task_id": task_id,
        "message": "PPTX regeneration started",
    }


@router.get("/jobs/{job_id}/steps/versions")
async def get_steps_versions(job_id: str, db: Session = Depends(get_db)):
    """Get all versions of steps.json for a job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    versions = (
        db.query(StepsVersion)
        .filter(StepsVersion.job_id == job_uuid)
        .order_by(StepsVersion.version.desc())
        .all()
    )

    return {
        "job_id": str(job_id),
        "current_version": job.current_steps_version,
        "versions": [
            {
                "version": v.version,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "edit_source": v.edit_source,
                "edit_note": v.edit_note,
            }
            for v in versions
        ],
    }


@router.get("/jobs/{job_id}/download/pptx")
async def download_pptx(job_id: str, db: Session = Depends(get_db)):
    """Download PPTX file for a job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.pptx_uri:
        raise HTTPException(status_code=404, detail="PPTX not yet generated")

    try:
        storage = get_storage_service()
        key = storage.key_from_uri(job.pptx_uri)
        filename = job.title or "manual"
        url = storage.get_presigned_url(
            key,
            expires_in=3600,
            response_content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            response_content_disposition=_build_content_disposition(f"{filename}.pptx"),
        )
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate download URL")


@router.get("/jobs/{job_id}/download/frames")
async def download_frames(job_id: str, db: Session = Depends(get_db)):
    """Download frames ZIP for a job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.frames_prefix_uri:
        raise HTTPException(status_code=404, detail="Frames not yet generated")

    try:
        storage = get_storage_service()

        # Create or get existing zip
        zip_key = f"jobs/{job_id}/frames.zip"
        try:
            # Check if zip already exists
            storage.client.head_object(Bucket=storage.bucket, Key=zip_key)
        except Exception:
            # Create zip
            frames_prefix = storage.key_from_uri(job.frames_prefix_uri)
            zip_key = storage.create_frames_zip(str(job_id), frames_prefix)

        filename = f"{job.title or 'frames'}_frames"
        url = storage.get_presigned_url(
            zip_key,
            expires_in=3600,
            response_content_type="application/zip",
            response_content_disposition=_build_content_disposition(f"{filename}.zip"),
        )
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error(f"Failed to generate frames download URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate download URL")


@router.get("/jobs/{job_id}/frames/{frame_file}")
async def get_frame(job_id: str, frame_file: str, db: Session = Depends(get_db)):
    """Get a specific frame image."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.frames_prefix_uri:
        raise HTTPException(status_code=404, detail="Frames not yet generated")

    try:
        storage = get_storage_service()
        frames_prefix = storage.key_from_uri(job.frames_prefix_uri)
        normalized_frame = os.path.basename(frame_file)
        if normalized_frame != frame_file:
            raise HTTPException(status_code=400, detail="Invalid frame filename")

        frame_key = f"{frames_prefix}{normalized_frame}"

        url = storage.get_presigned_url(
            frame_key, expires_in=3600, response_content_type="image/png"
        )
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error(f"Failed to get frame: {e}")
        raise HTTPException(status_code=404, detail="Frame not found")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """
    Cancel a queued or running job.

    - Only QUEUED or RUNNING jobs can be canceled
    - Returns 409 Conflict for invalid state transitions
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [JobStatus.QUEUED, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job in {job.status.value} status. Only QUEUED or RUNNING jobs can be canceled.",
        )

    # Revoke Celery task
    celery_app.control.revoke(str(job_id), terminate=True)

    job.status = JobStatus.CANCELED
    job.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"Job canceled: {job_id}")

    return {"job_id": str(job_id), "status": "CANCELED", "message": "Job canceled successfully"}


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, db: Session = Depends(get_db)):
    """
    Retry a failed job.

    - Only FAILED jobs can be retried
    - Re-queues the job from the beginning
    - Returns 409 Conflict for invalid state transitions
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry job in {job.status.value} status. Only FAILED jobs can be retried.",
        )

    # Check if input video still exists
    if not job.input_video_uri:
        raise HTTPException(
            status_code=400,
            detail="Cannot retry job: input video not found",
        )

    # Generate new trace ID
    trace_id = str(uuid.uuid4())[:8]

    # Reset job state
    job.status = JobStatus.QUEUED
    job.stage = None
    job.progress = 0
    job.error_code = None
    job.error_message = None
    job.trace_id = trace_id
    job.updated_at = datetime.utcnow()
    db.commit()

    # Queue the processing task
    try:
        celery_app.send_task(
            "app.workers.tasks.process_video", args=[str(job_id)], task_id=str(job_id)
        )
    except Exception as e:
        logger.error(f"Failed to queue retry for job {job_id}: {e}")
        job.status = JobStatus.FAILED
        job.error_code = "QUEUE_ERROR"
        job.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to queue retry task")

    logger.info(f"Job retry queued: {job_id}")

    return {
        "job_id": str(job_id),
        "status": "QUEUED",
        "trace_id": trace_id,
        "message": "Job queued for retry",
    }


@router.get("/jobs/{job_id}/theme")
async def get_job_theme(job_id: str, db: Session = Depends(get_db)):
    """
    Get theme settings for a job.

    Returns default theme if no custom theme is set.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    theme = merge_theme_with_defaults(job.theme_json)
    return theme.model_dump()


@router.put("/jobs/{job_id}/theme")
async def update_job_theme(job_id: str, theme_update: ThemeUpdate, db: Session = Depends(get_db)):
    """
    Update theme settings for a job.

    Only updates provided fields, preserving existing values for others.
    Does NOT regenerate PPTX - use /regenerate/pptx for that.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update theme for job in {job.status.value} status. Job must be SUCCEEDED.",
        )

    # Get current theme or defaults
    current_theme = merge_theme_with_defaults(job.theme_json)

    # Update only provided fields
    update_data = theme_update.model_dump(exclude_unset=True)
    updated_theme_dict = current_theme.model_dump()
    updated_theme_dict.update(update_data)

    # Validate the merged theme
    try:
        updated_theme = Theme(**updated_theme_dict)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Save to database
    job.theme_json = updated_theme.model_dump()
    job.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"Theme updated for job {job_id}")

    return {
        "job_id": str(job_id),
        "theme": updated_theme.model_dump(),
        "message": "Theme updated successfully. Use /regenerate/pptx to apply changes to PPTX.",
    }


@router.post("/jobs/{job_id}/theme/logo")
async def upload_job_logo(
    job_id: str, logo_file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """
    Upload logo image for a job.

    - Accepts PNG/JPG files only
    - Maximum file size: 1MB
    - Saves to jobs/<job_id>/assets/logo.<ext>
    - Updates theme_json.logo_uri
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upload logo for job in {job.status.value} status. Job must be SUCCEEDED.",
        )

    # Validate file extension
    filename = logo_file.filename or "logo.png"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Allowed: {', '.join(ALLOWED_LOGO_EXTENSIONS)}",
        )

    # Validate content type
    content_type = logo_file.content_type or ""
    if content_type not in ALLOWED_LOGO_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type: {content_type}. Allowed: {', '.join(ALLOWED_LOGO_CONTENT_TYPES)}",
        )

    # Check file size
    logo_file.file.seek(0, 2)
    file_size = logo_file.file.tell()
    logo_file.file.seek(0)

    if file_size > MAX_LOGO_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Logo file too large ({file_size / 1024:.1f}KB). Maximum: {MAX_LOGO_SIZE_BYTES / 1024:.0f}KB",
        )

    # Upload to storage
    try:
        storage = get_storage_service()
        logo_key = f"jobs/{job_id}/assets/logo{ext}"
        storage.upload_file(logo_file.file, logo_key, content_type)
        logo_uri = f"s3://{settings.s3_bucket}/{logo_key}"
    except Exception as e:
        logger.error(f"Failed to upload logo: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload logo")

    # Update theme with logo_uri
    current_theme = merge_theme_with_defaults(job.theme_json)
    updated_theme_dict = current_theme.model_dump()
    updated_theme_dict["logo_uri"] = logo_uri
    updated_theme = Theme(**updated_theme_dict)

    job.theme_json = updated_theme.model_dump()
    job.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"Logo uploaded for job {job_id}: {logo_key}")

    return {
        "job_id": str(job_id),
        "logo_uri": logo_uri,
        "message": "Logo uploaded successfully. Use /regenerate/pptx to apply to PPTX.",
    }


@router.get("/jobs/{job_id}/theme/logo")
async def get_job_logo(job_id: str, db: Session = Depends(get_db)):
    """
    Get logo image for a job.

    Returns a redirect to the presigned URL for the logo image.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    theme = merge_theme_with_defaults(job.theme_json)
    if not theme.logo_uri:
        raise HTTPException(status_code=404, detail="No logo configured for this job")

    try:
        storage = get_storage_service()
        logo_key = storage.key_from_uri(theme.logo_uri)
        ext = os.path.splitext(logo_key)[1].lower()
        content_type = "image/png" if ext == ".png" else "image/jpeg"

        url = storage.get_presigned_url(
            logo_key, expires_in=3600, response_content_type=content_type
        )
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error(f"Failed to get logo: {e}")
        raise HTTPException(status_code=404, detail="Logo not found")
