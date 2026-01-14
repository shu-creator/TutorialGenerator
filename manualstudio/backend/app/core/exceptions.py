"""Custom exceptions for ManualStudio."""
from typing import Optional


class ManualStudioError(Exception):
    """Base exception for ManualStudio."""

    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code or "INTERNAL_ERROR"
        super().__init__(self.message)


class VideoValidationError(ManualStudioError):
    """Raised when video validation fails."""

    def __init__(self, message: str):
        super().__init__(message, "VIDEO_VALIDATION_ERROR")


class VideoTooLongError(VideoValidationError):
    """Raised when video exceeds maximum duration."""

    def __init__(self, duration_sec: float, max_sec: int):
        super().__init__(
            f"Video duration ({duration_sec:.1f}s) exceeds maximum allowed ({max_sec}s)"
        )
        self.code = "VIDEO_TOO_LONG"


class VideoTooLargeError(VideoValidationError):
    """Raised when video exceeds maximum file size."""

    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(
            f"Video size ({size_bytes / 1024 / 1024:.1f}MB) exceeds maximum allowed ({max_bytes / 1024 / 1024:.0f}MB)"
        )
        self.code = "VIDEO_TOO_LARGE"


class UnsupportedFormatError(VideoValidationError):
    """Raised when video format is not supported."""

    def __init__(self, format: str):
        super().__init__(f"Unsupported video format: {format}")
        self.code = "UNSUPPORTED_FORMAT"


class TranscriptionError(ManualStudioError):
    """Raised when transcription fails."""

    def __init__(self, message: str):
        super().__init__(message, "TRANSCRIPTION_ERROR")


class LLMError(ManualStudioError):
    """Raised when LLM processing fails."""

    def __init__(self, message: str):
        super().__init__(message, "LLM_ERROR")


class LLMValidationError(LLMError):
    """Raised when LLM output fails validation."""

    def __init__(self, message: str):
        super().__init__(message)
        self.code = "LLM_VALIDATION_ERROR"


class StorageError(ManualStudioError):
    """Raised when storage operations fail."""

    def __init__(self, message: str):
        super().__init__(message, "STORAGE_ERROR")


class JobNotFoundError(ManualStudioError):
    """Raised when job is not found."""

    def __init__(self, job_id: str):
        super().__init__(f"Job not found: {job_id}", "JOB_NOT_FOUND")


class FFmpegError(ManualStudioError):
    """Raised when FFmpeg operations fail."""

    def __init__(self, message: str):
        super().__init__(message, "FFMPEG_ERROR")
