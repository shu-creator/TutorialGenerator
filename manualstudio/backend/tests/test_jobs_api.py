"""Tests for job list, batch, cancel, and retry APIs."""

import io
import uuid

from app.db.models import Job, JobStatus


class TestListJobsAPI:
    """Test GET /api/jobs endpoint."""

    def test_list_jobs_empty(self, client):
        """Test listing jobs when no jobs exist."""
        response = client.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_jobs_with_data(self, client, test_db_session):
        """Test listing jobs with data."""
        # Create test jobs
        for i in range(5):
            job = Job(
                id=uuid.uuid4(),
                status=JobStatus.QUEUED,
                title=f"Test Job {i}",
                goal=f"Goal {i}",
                language="ja",
            )
            test_db_session.add(job)
        test_db_session.commit()

        response = client.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["total"] == 5

    def test_list_jobs_filter_by_status(self, client, test_db_session):
        """Test filtering jobs by status."""
        # Create jobs with different statuses
        job1 = Job(id=uuid.uuid4(), status=JobStatus.QUEUED, title="Queued Job")
        job2 = Job(id=uuid.uuid4(), status=JobStatus.SUCCEEDED, title="Succeeded Job")
        job3 = Job(id=uuid.uuid4(), status=JobStatus.FAILED, title="Failed Job")
        test_db_session.add_all([job1, job2, job3])
        test_db_session.commit()

        # Filter by QUEUED
        response = client.get("/api/jobs?status=QUEUED")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "QUEUED"

        # Filter by SUCCEEDED
        response = client.get("/api/jobs?status=SUCCEEDED")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "SUCCEEDED"

    def test_list_jobs_search(self, client, test_db_session):
        """Test searching jobs by title/goal."""
        job1 = Job(
            id=uuid.uuid4(), status=JobStatus.QUEUED, title="経費精算マニュアル", goal="経費申請"
        )
        job2 = Job(
            id=uuid.uuid4(), status=JobStatus.QUEUED, title="勤怠管理マニュアル", goal="勤怠入力"
        )
        test_db_session.add_all([job1, job2])
        test_db_session.commit()

        # Search by title
        response = client.get("/api/jobs?q=経費")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "経費" in data["items"][0]["title"]

        # Search by goal
        response = client.get("/api/jobs?q=勤怠入力")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "勤怠" in data["items"][0]["goal"]

    def test_list_jobs_pagination(self, client, test_db_session):
        """Test pagination."""
        # Create 25 jobs
        for i in range(25):
            job = Job(id=uuid.uuid4(), status=JobStatus.QUEUED, title=f"Job {i:02d}")
            test_db_session.add(job)
        test_db_session.commit()

        # First page
        response = client.get("/api/jobs?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total_pages"] == 3

        # Second page
        response = client.get("/api/jobs?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["page"] == 2

        # Third page (partial)
        response = client.get("/api/jobs?page=3&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["page"] == 3

    def test_list_jobs_invalid_status(self, client):
        """Test filtering with invalid status."""
        response = client.get("/api/jobs?status=INVALID")
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_list_jobs_sort_order(self, client, test_db_session):
        """Test sorting by created_at."""
        import time

        job1 = Job(id=uuid.uuid4(), status=JobStatus.QUEUED, title="First")
        test_db_session.add(job1)
        test_db_session.commit()

        time.sleep(0.01)  # Ensure different timestamps

        job2 = Job(id=uuid.uuid4(), status=JobStatus.QUEUED, title="Second")
        test_db_session.add(job2)
        test_db_session.commit()

        # Default: descending (newest first)
        response = client.get("/api/jobs?sort=-created_at")
        data = response.json()
        assert data["items"][0]["title"] == "Second"

        # Ascending (oldest first)
        response = client.get("/api/jobs?sort=created_at")
        data = response.json()
        assert data["items"][0]["title"] == "First"


class TestBatchJobsAPI:
    """Test POST /api/jobs/batch endpoint."""

    def test_batch_upload_single_file(self, client, mock_storage):
        """Test batch upload with single file."""
        video_content = b"\x00\x00\x00\x1c\x66\x74\x79\x70" + b"\x00" * 1024
        files = [("video_files", ("test.mp4", io.BytesIO(video_content), "video/mp4"))]

        response = client.post(
            "/api/jobs/batch",
            files=files,
            data={"title_prefix": "Test", "language": "ja"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total_created"] == 1
        assert data["total_errors"] == 0
        assert len(data["created"]) == 1
        assert data["created"][0]["file"] == "test.mp4"

    def test_batch_upload_multiple_files(self, client, mock_storage):
        """Test batch upload with multiple files."""
        video_content = b"\x00\x00\x00\x1c\x66\x74\x79\x70" + b"\x00" * 1024
        files = [
            ("video_files", ("video1.mp4", io.BytesIO(video_content), "video/mp4")),
            ("video_files", ("video2.mp4", io.BytesIO(video_content), "video/mp4")),
            ("video_files", ("video3.mov", io.BytesIO(video_content), "video/quicktime")),
        ]

        response = client.post(
            "/api/jobs/batch",
            files=files,
            data={"title_prefix": "Batch", "goal": "Testing batch upload"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total_created"] == 3
        assert data["total_errors"] == 0

    def test_batch_upload_with_invalid_file(self, client, mock_storage):
        """Test batch upload with mixed valid/invalid files."""
        video_content = b"\x00\x00\x00\x1c\x66\x74\x79\x70" + b"\x00" * 1024
        files = [
            ("video_files", ("valid.mp4", io.BytesIO(video_content), "video/mp4")),
            ("video_files", ("invalid.txt", io.BytesIO(b"text content"), "text/plain")),
        ]

        response = client.post("/api/jobs/batch", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["total_created"] == 1
        assert data["total_errors"] == 1
        assert "Unsupported video format" in data["errors"][0]["error"]

    def test_batch_upload_empty(self, client):
        """Test batch upload with no files."""
        response = client.post("/api/jobs/batch", files=[])
        assert response.status_code == 422  # FastAPI validation error

    def test_batch_upload_too_many_files(self, client):
        """Test batch upload exceeding limit."""
        video_content = b"\x00\x00\x00\x1c\x66\x74\x79\x70" + b"\x00" * 1024
        files = [
            ("video_files", (f"video{i}.mp4", io.BytesIO(video_content), "video/mp4"))
            for i in range(11)
        ]

        response = client.post("/api/jobs/batch", files=files)
        assert response.status_code == 400
        assert "Maximum 10 files" in response.json()["detail"]


class TestCancelJobAPI:
    """Test POST /api/jobs/{job_id}/cancel endpoint."""

    def test_cancel_queued_job(self, client, test_db_session):
        """Test canceling a QUEUED job."""
        job = Job(id=uuid.uuid4(), status=JobStatus.QUEUED, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELED"

        # Verify in database
        test_db_session.refresh(job)
        assert job.status == JobStatus.CANCELED

    def test_cancel_running_job(self, client, test_db_session):
        """Test canceling a RUNNING job."""
        job = Job(id=uuid.uuid4(), status=JobStatus.RUNNING, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELED"

    def test_cancel_succeeded_job_returns_409(self, client, test_db_session):
        """Test that canceling a SUCCEEDED job returns 409."""
        job = Job(id=uuid.uuid4(), status=JobStatus.SUCCEEDED, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/cancel")
        assert response.status_code == 409
        assert "Cannot cancel job in SUCCEEDED status" in response.json()["detail"]

    def test_cancel_failed_job_returns_409(self, client, test_db_session):
        """Test that canceling a FAILED job returns 409."""
        job = Job(id=uuid.uuid4(), status=JobStatus.FAILED, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/cancel")
        assert response.status_code == 409
        assert "Cannot cancel job in FAILED status" in response.json()["detail"]

    def test_cancel_already_canceled_job_returns_409(self, client, test_db_session):
        """Test that canceling an already CANCELED job returns 409."""
        job = Job(id=uuid.uuid4(), status=JobStatus.CANCELED, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/cancel")
        assert response.status_code == 409
        assert "Cannot cancel job in CANCELED status" in response.json()["detail"]

    def test_cancel_nonexistent_job(self, client):
        """Test canceling a non-existent job."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/api/jobs/{fake_id}/cancel")
        assert response.status_code == 404


class TestRetryJobAPI:
    """Test POST /api/jobs/{job_id}/retry endpoint."""

    def test_retry_failed_job(self, client, test_db_session, mock_storage):
        """Test retrying a FAILED job."""
        job = Job(
            id=uuid.uuid4(),
            status=JobStatus.FAILED,
            title="Test",
            input_video_uri="s3://bucket/jobs/test/input.mp4",
            error_code="TEST_ERROR",
            error_message="Test error",
        )
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/retry")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "QUEUED"
        assert "trace_id" in data

        # Verify in database
        test_db_session.refresh(job)
        assert job.status == JobStatus.QUEUED
        assert job.error_code is None
        assert job.error_message is None
        assert job.progress == 0

    def test_retry_queued_job_returns_409(self, client, test_db_session):
        """Test that retrying a QUEUED job returns 409."""
        job = Job(id=uuid.uuid4(), status=JobStatus.QUEUED, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/retry")
        assert response.status_code == 409
        assert "Cannot retry job in QUEUED status" in response.json()["detail"]

    def test_retry_running_job_returns_409(self, client, test_db_session):
        """Test that retrying a RUNNING job returns 409."""
        job = Job(id=uuid.uuid4(), status=JobStatus.RUNNING, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/retry")
        assert response.status_code == 409
        assert "Cannot retry job in RUNNING status" in response.json()["detail"]

    def test_retry_succeeded_job_returns_409(self, client, test_db_session):
        """Test that retrying a SUCCEEDED job returns 409."""
        job = Job(id=uuid.uuid4(), status=JobStatus.SUCCEEDED, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/retry")
        assert response.status_code == 409
        assert "Cannot retry job in SUCCEEDED status" in response.json()["detail"]

    def test_retry_canceled_job_returns_409(self, client, test_db_session):
        """Test that retrying a CANCELED job returns 409."""
        job = Job(id=uuid.uuid4(), status=JobStatus.CANCELED, title="Test")
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/retry")
        assert response.status_code == 409
        assert "Cannot retry job in CANCELED status" in response.json()["detail"]

    def test_retry_without_input_video(self, client, test_db_session):
        """Test retrying a job without input video."""
        job = Job(
            id=uuid.uuid4(),
            status=JobStatus.FAILED,
            title="Test",
            input_video_uri=None,
        )
        test_db_session.add(job)
        test_db_session.commit()

        response = client.post(f"/api/jobs/{job.id}/retry")
        assert response.status_code == 400
        assert "input video not found" in response.json()["detail"]

    def test_retry_nonexistent_job(self, client):
        """Test retrying a non-existent job."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/api/jobs/{fake_id}/retry")
        assert response.status_code == 404
