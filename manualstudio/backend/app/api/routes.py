"""API routes for ManualStudio."""
import json
import os
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Body
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger, set_trace_id, get_trace_id
from app.core.exceptions import (
    VideoTooLargeError,
    VideoTooLongError,
    UnsupportedFormatError,
    JobNotFoundError,
    ErrorCode,
)
from app.db import get_db, Job, JobStatus, StepsVersion
from app.services.storage import get_storage_service
from app.services.llm import validate_steps_json, LLMValidationError
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
router = APIRouter(prefix="/api")
settings = get_settings()


class StepsUpdateRequest(BaseModel):
    """Request body for updating steps."""
    steps_json: dict
    edit_note: Optional[str] = None


def _build_content_disposition(filename: str) -> str:
    safe_name = quote(filename, safe="")
    return f"attachment; filename*=UTF-8''{safe_name}"


@router.post("/jobs")
async def create_job(
    video_file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    goal: Optional[str] = Form(None),
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
            detail=f"Unsupported video format: {ext}. Supported: mp4, mov, avi, mkv, webm"
        )

    # Check file size
    video_file.file.seek(0, 2)
    file_size = video_file.file.tell()
    video_file.file.seek(0)

    max_size = settings.max_video_size_bytes
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Video file too large ({file_size / 1024 / 1024:.1f}MB). Maximum: {max_size / 1024 / 1024:.0f}MB"
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
            "app.workers.tasks.process_video",
            args=[str(job_id)],
            task_id=str(job_id)
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
            "message": "Job created and queued for processing"
        }
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
async def get_job_steps(
    job_id: str,
    version: Optional[int] = None,
    db: Session = Depends(get_db)
):
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
    steps_version = db.query(StepsVersion).filter(
        StepsVersion.job_id == job_uuid,
        StepsVersion.version == target_version
    ).first()

    if steps_version:
        return {
            "version": steps_version.version,
            "edit_source": steps_version.edit_source,
            "created_at": steps_version.created_at.isoformat() if steps_version.created_at else None,
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
async def update_job_steps(
    job_id: str,
    request: StepsUpdateRequest,
    db: Session = Depends(get_db)
):
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
            detail=f"Cannot edit steps for job in {job.status.value} status. Job must be SUCCEEDED."
        )

    # Validate steps.json schema
    try:
        validate_steps_json(request.steps_json)
    except LLMValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.STEPS_SCHEMA_INVALID.value,
                "message": str(e)
            }
        )

    # Get current max version
    max_version = db.query(StepsVersion).filter(
        StepsVersion.job_id == job_uuid
    ).count()
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
        "message": "Steps updated successfully. Use /regenerate/pptx to regenerate the PowerPoint."
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
            detail=f"Cannot regenerate PPTX for job in {job.status.value} status. Job must be SUCCEEDED."
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
    celery_app.send_task(
        "app.workers.tasks.regenerate_pptx",
        args=[str(job_id)],
        task_id=task_id
    )

    logger.info(f"PPTX regeneration queued for job {job_id}")

    return {
        "job_id": str(job_id),
        "status": "RUNNING",
        "task_id": task_id,
        "message": "PPTX regeneration started"
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

    versions = db.query(StepsVersion).filter(
        StepsVersion.job_id == job_uuid
    ).order_by(StepsVersion.version.desc()).all()

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
        ]
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
            response_content_disposition=_build_content_disposition(f"{filename}.pptx")
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
        except:
            # Create zip
            frames_prefix = storage.key_from_uri(job.frames_prefix_uri)
            zip_key = storage.create_frames_zip(str(job_id), frames_prefix)

        filename = f"{job.title or 'frames'}_frames"
        url = storage.get_presigned_url(
            zip_key,
            expires_in=3600,
            response_content_type="application/zip",
            response_content_disposition=_build_content_disposition(f"{filename}.zip")
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
            frame_key,
            expires_in=3600,
            response_content_type="image/png"
        )
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error(f"Failed to get frame: {e}")
        raise HTTPException(status_code=404, detail="Frame not found")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a queued or running job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [JobStatus.QUEUED, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in {job.status.value} status"
        )

    # Revoke Celery task
    celery_app.control.revoke(str(job_id), terminate=True)

    job.status = JobStatus.CANCELED
    db.commit()

    logger.info(f"Job canceled: {job_id}")

    return {"job_id": str(job_id), "status": "CANCELED"}
