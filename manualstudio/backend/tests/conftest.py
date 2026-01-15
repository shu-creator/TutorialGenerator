"""Pytest fixtures for ManualStudio tests."""

import json
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.database import Base, get_db
from app.db.models import Job, JobStatus, StepsVersion
from app.main import app

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ============================================================================
# Test Settings
# ============================================================================


@pytest.fixture(scope="session")
def test_settings():
    """Test settings with mock providers."""
    return Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        s3_endpoint_url="http://localhost:9000",
        s3_bucket="test-bucket",
        s3_access_key="test",
        s3_secret_key="test",
        llm_provider="mock",
        transcribe_provider="mock",
        max_video_minutes=5,
        max_video_size_mb=100,
    )


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine with SQLite in-memory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def override_get_db(test_db_session):
    """Override the get_db dependency for testing."""

    def _override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    return _override_get_db


# ============================================================================
# Mock Storage Service
# ============================================================================


class MockStorageService:
    """Mock storage service for testing."""

    def __init__(self):
        self._storage: dict[str, bytes] = {}
        self.bucket = "test-bucket"
        self.client = MagicMock()

    def upload_file(self, file_obj, key: str, content_type: str = None):
        """Upload file to mock storage."""
        if hasattr(file_obj, "read"):
            self._storage[key] = file_obj.read()
            file_obj.seek(0)
        else:
            self._storage[key] = file_obj

    def upload_bytes(self, data: bytes, key: str, content_type: str = None):
        """Upload bytes to mock storage."""
        self._storage[key] = data

    def download_file(self, key: str, local_path: str):
        """Download file from mock storage."""
        if key in self._storage:
            with open(local_path, "wb") as f:
                f.write(self._storage[key])
        else:
            raise Exception(f"Key not found: {key}")

    def download_bytes(self, key: str) -> bytes:
        """Download bytes from mock storage."""
        if key in self._storage:
            return self._storage[key]
        raise Exception(f"Key not found: {key}")

    def key_from_uri(self, uri: str) -> str:
        """Extract key from S3 URI."""
        if uri.startswith("s3://"):
            parts = uri[5:].split("/", 1)
            return parts[1] if len(parts) > 1 else ""
        return uri

    def get_presigned_url(self, key: str, expires_in: int = 3600, **kwargs) -> str:
        """Generate mock presigned URL."""
        return f"http://mock-storage/{key}"

    def create_frames_zip(self, job_id: str, frames_prefix: str) -> str:
        """Create mock frames zip."""
        return f"jobs/{job_id}/frames.zip"


@pytest.fixture(scope="function")
def mock_storage():
    """Create mock storage service."""
    return MockStorageService()


# ============================================================================
# Test Client
# ============================================================================


@pytest.fixture(scope="function")
def client(override_get_db, mock_storage, test_settings) -> Generator[TestClient, None, None]:
    """Create test client with mocked dependencies."""
    # Override database dependency
    app.dependency_overrides[get_db] = override_get_db

    # Patch settings and storage
    with (
        patch("app.core.config.get_settings", return_value=test_settings),
        patch("app.services.storage.get_storage_service", return_value=mock_storage),
        patch("app.api.routes.get_storage_service", return_value=mock_storage),
    ):
        with TestClient(app) as test_client:
            yield test_client

    app.dependency_overrides.clear()


# ============================================================================
# Job Fixtures
# ============================================================================


@pytest.fixture
def sample_job(test_db_session) -> Job:
    """Create a sample job in the database."""
    job = Job(
        id=uuid.uuid4(),
        status=JobStatus.QUEUED,
        title="Test Manual",
        goal="Test goal",
        language="ja",
        progress=0,
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)
    return job


@pytest.fixture
def succeeded_job(test_db_session) -> Job:
    """Create a succeeded job with steps.json."""
    job = Job(
        id=uuid.uuid4(),
        status=JobStatus.SUCCEEDED,
        title="Completed Manual",
        goal="Test completed job",
        language="ja",
        progress=100,
        video_duration_sec=60.0,
        video_fps=30.0,
        video_resolution="1920x1080",
        steps_json_uri="s3://test-bucket/jobs/test/steps.json",
        pptx_uri="s3://test-bucket/jobs/test/output.pptx",
        frames_prefix_uri="s3://test-bucket/jobs/test/frames/",
        current_steps_version=1,
    )
    test_db_session.add(job)
    test_db_session.commit()

    # Add initial steps version
    steps_data = load_fixture("steps.json")
    steps_version = StepsVersion(
        job_id=job.id,
        version=1,
        steps_json=steps_data,
        edit_source="llm",
        edit_note="Initial generation",
    )
    test_db_session.add(steps_version)
    test_db_session.commit()
    test_db_session.refresh(job)
    return job


# ============================================================================
# Fixture Data Loaders
# ============================================================================


def load_fixture(filename: str) -> dict:
    """Load a fixture file."""
    fixture_path = FIXTURES_DIR / filename
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def transcript_fixture() -> list[dict]:
    """Load transcript fixture."""
    return load_fixture("transcript.json")


@pytest.fixture
def steps_fixture() -> dict:
    """Load steps fixture."""
    return load_fixture("steps.json")


# ============================================================================
# Temp Files
# ============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_video_file():
    """Create a mock video file for testing."""
    # Create a minimal MP4-like header (not a real video, just for upload testing)
    content = b"\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d"  # Minimal ftyp box
    content += b"\x00" * 1024  # Padding
    return content
