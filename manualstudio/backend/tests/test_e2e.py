"""End-to-end smoke tests for ManualStudio."""

import uuid

import pytest

from app.db.models import JobStatus


class TestHealthCheck:
    """Basic health check tests."""

    def test_health_endpoint(self, client):
        """Test that health endpoint is accessible."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestJobLifecycle:
    """E2E tests for the job lifecycle."""

    def test_get_job_returns_correct_status(self, client, sample_job):
        """Test that GET /api/jobs/{job_id} returns correct job status."""
        response = client.get(f"/api/jobs/{sample_job.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == str(sample_job.id)
        assert data["status"] == "QUEUED"
        assert data["title"] == "Test Manual"
        assert data["language"] == "ja"

    def test_get_job_not_found(self, client):
        """Test 404 for non-existent job."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/jobs/{fake_id}")
        assert response.status_code == 404

    def test_cancel_queued_job(self, client, test_db_session, sample_job):
        """Test canceling a queued job."""
        with pytest.MonkeyPatch.context() as mp:
            # Mock Celery revoke
            mp.setattr("app.api.routes.celery_app.control.revoke", lambda *args, **kwargs: None)

            response = client.post(f"/api/jobs/{sample_job.id}/cancel")
            assert response.status_code == 200
            assert response.json()["status"] == "CANCELED"

        test_db_session.refresh(sample_job)
        assert sample_job.status == JobStatus.CANCELED


class TestSucceededJobFlow:
    """E2E tests for working with succeeded jobs."""

    def test_get_job_shows_outputs(self, client, succeeded_job):
        """Test that succeeded job shows outputs information."""
        response = client.get(f"/api/jobs/{succeeded_job.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "SUCCEEDED"
        assert "outputs" in data
        assert data["outputs"]["steps_json"] is True
        assert data["outputs"]["pptx"] is True
        assert data["outputs"]["frames"] is True
        assert data["current_steps_version"] == 1

    def test_get_steps_json(self, client, succeeded_job, steps_fixture):
        """Test retrieving steps.json from succeeded job."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps")
        assert response.status_code == 200

        data = response.json()
        assert data["version"] == 1
        assert data["edit_source"] == "llm"
        assert "steps_json" in data
        assert data["steps_json"]["title"] == steps_fixture["title"]

    def test_full_edit_flow(
        self, client, test_db_session, succeeded_job, steps_fixture, mock_storage
    ):
        """Test complete edit flow: get steps -> edit -> save -> verify."""
        # Step 1: Get current steps
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps")
        assert response.status_code == 200
        original_steps = response.json()["steps_json"]

        # Step 2: Modify steps
        modified_steps = original_steps.copy()
        modified_steps["title"] = "Updated E2E Test Manual"
        modified_steps["steps"][0]["telop"] = "E2Eテスト"
        modified_steps["steps"][0]["action"] = "E2Eテスト用に更新された操作です"

        # Step 3: Save modified steps
        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps",
            json={"steps_json": modified_steps, "edit_note": "E2E test edit"},
        )
        assert response.status_code == 200
        assert response.json()["version"] == 2

        # Step 4: Verify changes were saved
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps")
        assert response.status_code == 200
        saved_steps = response.json()

        assert saved_steps["version"] == 2
        assert saved_steps["edit_source"] == "manual"
        assert saved_steps["steps_json"]["title"] == "Updated E2E Test Manual"
        assert saved_steps["steps_json"]["steps"][0]["telop"] == "E2Eテスト"

        # Step 5: Verify version history
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps/versions")
        assert response.status_code == 200
        versions = response.json()

        assert versions["current_version"] == 2
        assert len(versions["versions"]) == 2

    def test_edit_flow_with_validation_error(self, client, succeeded_job, steps_fixture):
        """Test that invalid edits are rejected."""
        # Try to save invalid steps
        invalid_steps = steps_fixture.copy()
        invalid_steps["steps"][0]["start"] = "invalid-format"  # Should be MM:SS

        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps", json={"steps_json": invalid_steps}
        )
        assert response.status_code == 400

        # Verify original steps are unchanged
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps")
        assert response.status_code == 200
        assert response.json()["version"] == 1  # Still version 1

    def test_download_pptx_redirects(self, client, succeeded_job, mock_storage):
        """Test PPTX download returns redirect."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/download/pptx", follow_redirects=False)
        # Should redirect to presigned URL
        assert response.status_code == 307


class TestEditAndRegenerateFlow:
    """E2E tests for the complete edit + regenerate PPTX flow."""

    def test_edit_and_queue_regeneration(
        self, client, test_db_session, succeeded_job, steps_fixture, mock_storage
    ):
        """Test editing steps and queueing PPTX regeneration."""
        # Step 1: Edit steps
        modified_steps = steps_fixture.copy()
        modified_steps["title"] = "Regeneration Test Manual"

        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps", json={"steps_json": modified_steps}
        )
        assert response.status_code == 200
        new_version = response.json()["version"]

        # Step 2: Queue PPTX regeneration
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.api.routes.celery_app.send_task", lambda *args, **kwargs: None)

            response = client.post(f"/api/jobs/{succeeded_job.id}/regenerate/pptx")
            assert response.status_code == 200
            assert response.json()["status"] == "RUNNING"

        # Verify job status changed
        test_db_session.refresh(succeeded_job)
        assert succeeded_job.status == JobStatus.RUNNING
        assert succeeded_job.stage == "GENERATE_PPTX_ONLY"
        assert succeeded_job.current_steps_version == new_version


class TestMockProviders:
    """Tests to verify mock providers work correctly."""

    def test_mock_transcription_loads_fixture(self, transcript_fixture):
        """Verify transcript fixture is loadable."""
        assert len(transcript_fixture) > 0
        assert "text" in transcript_fixture[0]
        assert "start_sec" in transcript_fixture[0]
        assert "end_sec" in transcript_fixture[0]

    def test_mock_llm_loads_fixture(self, steps_fixture):
        """Verify steps fixture is loadable and valid."""
        assert "title" in steps_fixture
        assert "steps" in steps_fixture
        assert len(steps_fixture["steps"]) > 0

        # Verify step structure
        step = steps_fixture["steps"][0]
        required_fields = [
            "no",
            "start",
            "end",
            "shot",
            "frame_file",
            "telop",
            "action",
            "target",
            "narration",
        ]
        for field in required_fields:
            assert field in step, f"Missing required field: {field}"


class TestAPIValidation:
    """Tests for API input validation."""

    def test_invalid_uuid_format(self, client):
        """Test handling of invalid UUID format."""
        response = client.get("/api/jobs/not-a-uuid")
        assert response.status_code == 400
        assert "Invalid job ID" in response.json()["detail"]

    def test_empty_steps_json(self, client, succeeded_job):
        """Test rejection of empty steps_json."""
        response = client.put(f"/api/jobs/{succeeded_job.id}/steps", json={"steps_json": {}})
        assert response.status_code == 400

    def test_steps_with_missing_required_fields(self, client, succeeded_job):
        """Test rejection of steps missing required fields."""
        incomplete_steps = {
            "title": "Test",
            "goal": "Test",
            "language": "ja",
            # Missing 'source' and 'steps'
        }

        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps", json={"steps_json": incomplete_steps}
        )
        assert response.status_code == 400
