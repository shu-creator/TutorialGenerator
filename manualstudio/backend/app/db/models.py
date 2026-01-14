"""Database models."""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Integer, Text, DateTime, Enum, Float, JSON
from sqlalchemy.dialects.postgresql import UUID

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
    candidate_frames = Column(JSON, nullable=True)

    # Error handling
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    trace_id = Column(String(50), nullable=True)

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
            "error_code": self.error_code,
            "error_message": self.error_message,
            "trace_id": self.trace_id,
            "outputs": {
                "steps_json": self.steps_json_uri is not None,
                "pptx": self.pptx_uri is not None,
                "frames": self.frames_prefix_uri is not None,
            }
        }
