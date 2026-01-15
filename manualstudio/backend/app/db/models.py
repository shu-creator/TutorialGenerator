"""Database models."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class JobStatus(str, PyEnum):
    """Job status enumeration."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class JobStage(str, PyEnum):
    """Job processing stage enumeration."""

    INGEST = "INGEST"
    EXTRACT_AUDIO = "EXTRACT_AUDIO"
    TRANSCRIBE = "TRANSCRIBE"
    DETECT_SCENES = "DETECT_SCENES"
    EXTRACT_FRAMES = "EXTRACT_FRAMES"
    GENERATE_STEPS = "GENERATE_STEPS"
    GENERATE_PPTX = "GENERATE_PPTX"
    GENERATE_PPTX_ONLY = "GENERATE_PPTX_ONLY"
    FINALIZE = "FINALIZE"


class Job(Base):
    """Job model representing a video processing job."""

    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Status and progress
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED, nullable=False)
    stage = Column(String(50), nullable=True)
    progress = Column(Integer, default=0, nullable=False)

    # Input parameters
    title = Column(String(255), nullable=True)
    goal = Column(Text, nullable=True)
    language = Column(String(10), default="ja", nullable=False)

    # Video metadata
    video_duration_sec = Column(Float, nullable=True)
    video_fps = Column(Float, nullable=True)
    video_resolution = Column(String(20), nullable=True)

    # Storage URIs
    input_video_uri = Column(String(500), nullable=True)
    audio_uri = Column(String(500), nullable=True)
    steps_json_uri = Column(String(500), nullable=True)
    pptx_uri = Column(String(500), nullable=True)
    frames_prefix_uri = Column(String(500), nullable=True)

    # Processing metadata
    transcription_provider = Column(String(50), nullable=True)
    llm_provider = Column(String(50), nullable=True)
    transcript_segments = Column(JSON, nullable=True)
    transcript_uri = Column(String(500), nullable=True)  # Storage URI for transcript segments
    candidate_frames = Column(JSON, nullable=True)

    # Steps version tracking
    current_steps_version = Column(Integer, default=1, nullable=False)

    # Theme configuration (JSON)
    theme_json = Column(JSON, nullable=True)

    # Error handling
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    trace_id = Column(String(50), nullable=True)

    # Relationships
    steps_versions = relationship(
        "StepsVersion", back_populates="job", order_by="StepsVersion.version"
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status.value if self.status else None,
            "stage": self.stage,
            "progress": self.progress,
            "title": self.title,
            "goal": self.goal,
            "language": self.language,
            "video_duration_sec": self.video_duration_sec,
            "video_fps": self.video_fps,
            "video_resolution": self.video_resolution,
            "current_steps_version": self.current_steps_version,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "trace_id": self.trace_id,
            "outputs": {
                "steps_json": self.steps_json_uri is not None,
                "pptx": self.pptx_uri is not None,
                "frames": self.frames_prefix_uri is not None,
                "transcript": self.transcript_uri is not None,
            },
        }

    def get_current_steps_version(self) -> "StepsVersion":
        """Get the current steps version object."""
        for v in self.steps_versions:
            if v.version == self.current_steps_version:
                return v
        return None


class StepsVersion(Base):
    """Steps version model for tracking edits to steps.json."""

    __tablename__ = "steps_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Steps data
    steps_json = Column(JSON, nullable=False)

    # Edit metadata
    edit_source = Column(String(50), nullable=True)  # "llm", "manual", etc.
    edit_note = Column(Text, nullable=True)

    # Relationship
    job = relationship("Job", back_populates="steps_versions")

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "job_id": str(self.job_id),
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "edit_source": self.edit_source,
            "edit_note": self.edit_note,
            "steps_json": self.steps_json,
        }
