"""Tests for steps API endpoints (PUT /api/jobs/{job_id}/steps)."""
import json
import uuid

import pytest

from app.db.models import Job, JobStatus, StepsVersion


class TestGetJobSteps:
    """Tests for GET /api/jobs/{job_id}/steps endpoint."""

    def test_get_steps_success(self, client, succeeded_job, steps_fixture):
        """Test successful retrieval of steps.json."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps")
        assert response.status_code == 200

        data = response.json()
        assert "steps_json" in data
        assert data["version"] == 1
        assert data["edit_source"] == "llm"
        assert len(data["steps_json"]["steps"]) == len(steps_fixture["steps"])

    def test_get_steps_specific_version(self, client, test_db_session, succeeded_job):
        """Test retrieval of specific version."""
        # Add another version
        new_steps = {
            "title": "Updated Manual",
            "goal": "Updated goal",
            "language": "ja",
            "source": {
                "video_duration_sec": 60.0,
                "video_fps": 30.0,
                "resolution": "1920x1080"
            },
            "steps": [
                {
                    "no": 1,
                    "start": "00:00",
                    "end": "00:30",
                    "shot": "00:15",
                    "frame_file": "step_001.png",
                    "telop": "新しいステップ",
                    "action": "更新された操作",
                    "target": "更新対象",
                    "narration": "更新されたナレーションです。"
                }
            ]
        }
        steps_version = StepsVersion(
            job_id=succeeded_job.id,
            version=2,
            steps_json=new_steps,
            edit_source="manual",
            edit_note="Manual edit"
        )
        test_db_session.add(steps_version)
        succeeded_job.current_steps_version = 2
        test_db_session.commit()

        # Get version 1
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps?version=1")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1

        # Get version 2
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps?version=2")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 2
        assert data["steps_json"]["title"] == "Updated Manual"

    def test_get_steps_job_not_found(self, client):
        """Test 404 when job doesn't exist."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/jobs/{fake_id}/steps")
        assert response.status_code == 404

    def test_get_steps_invalid_job_id(self, client):
        """Test 400 when job ID is invalid."""
        response = client.get("/api/jobs/invalid-uuid/steps")
        assert response.status_code == 400


class TestUpdateJobSteps:
    """Tests for PUT /api/jobs/{job_id}/steps endpoint."""

    def test_update_steps_success(self, client, test_db_session, succeeded_job, steps_fixture, mock_storage):
        """Test successful steps update."""
        # Modify steps
        updated_steps = steps_fixture.copy()
        updated_steps["title"] = "Updated Title"
        updated_steps["steps"][0]["telop"] = "変更済み"

        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps",
            json={"steps_json": updated_steps, "edit_note": "Test edit"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 2  # Should increment
        assert "message" in data

        # Verify database was updated
        test_db_session.refresh(succeeded_job)
        assert succeeded_job.current_steps_version == 2

        # Verify new version was created
        new_version = test_db_session.query(StepsVersion).filter(
            StepsVersion.job_id == succeeded_job.id,
            StepsVersion.version == 2
        ).first()
        assert new_version is not None
        assert new_version.edit_source == "manual"
        assert new_version.edit_note == "Test edit"
        assert new_version.steps_json["title"] == "Updated Title"

    def test_update_steps_invalid_schema(self, client, succeeded_job):
        """Test validation error for invalid schema."""
        invalid_steps = {
            "title": "Test",
            # Missing required fields
        }

        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps",
            json={"steps_json": invalid_steps}
        )

        assert response.status_code == 400
        data = response.json()
        assert "STEPS_SCHEMA_INVALID" in str(data["detail"])

    def test_update_steps_invalid_step_fields(self, client, succeeded_job, steps_fixture):
        """Test validation error for invalid step fields."""
        invalid_steps = steps_fixture.copy()
        # Invalid time format
        invalid_steps["steps"][0]["start"] = "invalid"

        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps",
            json={"steps_json": invalid_steps}
        )

        assert response.status_code == 400

    def test_update_steps_job_not_succeeded(self, client, sample_job):
        """Test 400 when job is not in SUCCEEDED status."""
        valid_steps = {
            "title": "Test",
            "goal": "Test",
            "language": "ja",
            "source": {
                "video_duration_sec": 60.0,
                "video_fps": 30.0,
                "resolution": "1920x1080"
            },
            "steps": []
        }

        response = client.put(
            f"/api/jobs/{sample_job.id}/steps",
            json={"steps_json": valid_steps}
        )

        assert response.status_code == 400
        assert "SUCCEEDED" in response.json()["detail"]

    def test_update_steps_job_not_found(self, client):
        """Test 404 when job doesn't exist."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/api/jobs/{fake_id}/steps",
            json={"steps_json": {}}
        )
        assert response.status_code == 404


class TestGetStepsVersions:
    """Tests for GET /api/jobs/{job_id}/steps/versions endpoint."""

    def test_get_versions_success(self, client, test_db_session, succeeded_job, steps_fixture):
        """Test successful retrieval of versions list."""
        # Add another version
        steps_version = StepsVersion(
            job_id=succeeded_job.id,
            version=2,
            steps_json=steps_fixture,
            edit_source="manual",
            edit_note="Second edit"
        )
        test_db_session.add(steps_version)
        succeeded_job.current_steps_version = 2
        test_db_session.commit()

        response = client.get(f"/api/jobs/{succeeded_job.id}/steps/versions")
        assert response.status_code == 200

        data = response.json()
        assert data["current_version"] == 2
        assert len(data["versions"]) == 2
        # Versions should be ordered descending
        assert data["versions"][0]["version"] == 2
        assert data["versions"][1]["version"] == 1

    def test_get_versions_job_not_found(self, client):
        """Test 404 when job doesn't exist."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/jobs/{fake_id}/steps/versions")
        assert response.status_code == 404


class TestRegeneratePptx:
    """Tests for POST /api/jobs/{job_id}/regenerate/pptx endpoint."""

    def test_regenerate_pptx_queues_task(self, client, test_db_session, succeeded_job, mock_storage):
        """Test that PPTX regeneration queues a task."""
        with pytest.MonkeyPatch.context() as mp:
            # Mock Celery send_task
            mock_send_task = lambda *args, **kwargs: None
            mp.setattr("app.api.routes.celery_app.send_task", mock_send_task)

            response = client.post(f"/api/jobs/{succeeded_job.id}/regenerate/pptx")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "RUNNING"
            assert "task_id" in data

        # Verify job status was updated
        test_db_session.refresh(succeeded_job)
        assert succeeded_job.status == JobStatus.RUNNING
        assert succeeded_job.stage == "GENERATE_PPTX_ONLY"

    def test_regenerate_pptx_job_not_succeeded(self, client, sample_job):
        """Test 400 when job is not SUCCEEDED."""
        response = client.post(f"/api/jobs/{sample_job.id}/regenerate/pptx")
        assert response.status_code == 400
        assert "SUCCEEDED" in response.json()["detail"]

    def test_regenerate_pptx_no_frames(self, client, test_db_session, succeeded_job):
        """Test 400 when no frames available."""
        succeeded_job.frames_prefix_uri = None
        test_db_session.commit()

        response = client.post(f"/api/jobs/{succeeded_job.id}/regenerate/pptx")
        assert response.status_code == 400
        assert "frames" in response.json()["detail"].lower()

    def test_regenerate_pptx_job_not_found(self, client):
        """Test 404 when job doesn't exist."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/api/jobs/{fake_id}/regenerate/pptx")
        assert response.status_code == 404
