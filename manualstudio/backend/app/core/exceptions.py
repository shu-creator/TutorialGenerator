"""Custom exceptions for ManualStudio."""

from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes for ManualStudio."""

    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Job errors
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_ALREADY_COMPLETED = "JOB_ALREADY_COMPLETED"
    JOB_CANCELED = "JOB_CANCELED"

    # Video errors
    VIDEO_VALIDATION_ERROR = "VIDEO_VALIDATION_ERROR"
    VIDEO_TOO_LONG = "VIDEO_TOO_LONG"
    VIDEO_TOO_LARGE = "VIDEO_TOO_LARGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"

    # Processing errors
    FFMPEG_FAILED = "FFMPEG_FAILED"
    AUDIO_EXTRACTION_FAILED = "AUDIO_EXTRACTION_FAILED"
    FRAME_EXTRACTION_FAILED = "FRAME_EXTRACTION_FAILED"

    # Transcription errors
    TRANSCRIBE_FAILED = "TRANSCRIBE_FAILED"
    TRANSCRIBE_PROVIDER_ERROR = "TRANSCRIBE_PROVIDER_ERROR"

    # LLM errors
    LLM_FAILED = "LLM_FAILED"
    LLM_SCHEMA_INVALID = "LLM_SCHEMA_INVALID"
    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"

    # PPTX errors
    PPTX_FAILED = "PPTX_FAILED"
    PPTX_TEMPLATE_ERROR = "PPTX_TEMPLATE_ERROR"

    # Storage errors
    STORAGE_ERROR = "STORAGE_ERROR"
    STORAGE_UPLOAD_FAILED = "STORAGE_UPLOAD_FAILED"
    STORAGE_DOWNLOAD_FAILED = "STORAGE_DOWNLOAD_FAILED"

    # Steps errors
    STEPS_NOT_FOUND = "STEPS_NOT_FOUND"
    STEPS_SCHEMA_INVALID = "STEPS_SCHEMA_INVALID"


class ManualStudioError(Exception):
    """Base exception for ManualStudio."""

    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code or ErrorCode.INTERNAL_ERROR.value
        super().__init__(self.message)


class VideoValidationError(ManualStudioError):
    """Raised when video validation fails."""

    def __init__(self, message: str):
        super().__init__(message, ErrorCode.VIDEO_VALIDATION_ERROR.value)


class VideoTooLongError(VideoValidationError):
    """Raised when video exceeds maximum duration."""

    def __init__(self, duration_sec: float, max_sec: int):
        super().__init__(
            f"Video duration ({duration_sec:.1f}s) exceeds maximum allowed ({max_sec}s)"
        )
        self.code = ErrorCode.VIDEO_TOO_LONG.value


class VideoTooLargeError(VideoValidationError):
    """Raised when video exceeds maximum file size."""

    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(
            f"Video size ({size_bytes / 1024 / 1024:.1f}MB) exceeds maximum allowed ({max_bytes / 1024 / 1024:.0f}MB)"
        )
        self.code = ErrorCode.VIDEO_TOO_LARGE.value


class UnsupportedFormatError(VideoValidationError):
    """Raised when video format is not supported."""

    def __init__(self, format: str):
        super().__init__(f"Unsupported video format: {format}")
        self.code = ErrorCode.UNSUPPORTED_FORMAT.value


class TranscriptionError(ManualStudioError):
    """Raised when transcription fails."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message, code or ErrorCode.TRANSCRIBE_FAILED.value)


class LLMError(ManualStudioError):
    """Raised when LLM processing fails."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message, code or ErrorCode.LLM_FAILED.value)


class LLMValidationError(LLMError):
    """Raised when LLM output fails validation."""

    def __init__(self, message: str):
        super().__init__(message, ErrorCode.LLM_SCHEMA_INVALID.value)


class StorageError(ManualStudioError):
    """Raised when storage operations fail."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message, code or ErrorCode.STORAGE_ERROR.value)


class JobNotFoundError(ManualStudioError):
    """Raised when job is not found."""

    def __init__(self, job_id: str):
        super().__init__(f"Job not found: {job_id}", ErrorCode.JOB_NOT_FOUND.value)


class FFmpegError(ManualStudioError):
    """Raised when FFmpeg operations fail."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message, code or ErrorCode.FFMPEG_FAILED.value)


class PPTXError(ManualStudioError):
    """Raised when PPTX generation fails."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message, code or ErrorCode.PPTX_FAILED.value)


class StepsValidationError(ManualStudioError):
    """Raised when steps.json validation fails."""

    def __init__(self, message: str):
        super().__init__(message, ErrorCode.STEPS_SCHEMA_INVALID.value)


class StepsNotFoundError(ManualStudioError):
    """Raised when steps.json is not found."""

    def __init__(self, job_id: str):
        super().__init__(f"Steps not found for job: {job_id}", ErrorCode.STEPS_NOT_FOUND.value)
