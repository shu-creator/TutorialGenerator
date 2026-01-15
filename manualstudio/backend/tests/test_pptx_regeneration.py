"""Tests for PPTX regeneration functionality."""
import uuid

import pytest

from app.db.models import Job, JobStatus, StepsVersion


class TestPptxRegeneration:
    """Tests for POST /api/jobs/{job_id}/regenerate/pptx endpoint."""

    def test_regenerate_uses_latest_steps_version(
        self, client, test_db_session, succeeded_job, steps_fixture, mock_storage
    ):
        """Test that regeneration uses the latest steps version."""
        # Add a new version
        new_steps = steps_fixture.copy()
        new_steps["title"] = "Updated for Regeneration"

        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps",
            json={"steps_json": new_steps, "edit_note": "Update for regeneration test"}
        )
        assert response.status_code == 200
        new_version = response.json()["version"]

        # Verify the job has the new version
        test_db_session.refresh(succeeded_job)
        assert succeeded_job.current_steps_version == new_version

        # Queue regeneration
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.api.routes.celery_app.send_task", lambda *args, **kwargs: None)
            response = client.post(f"/api/jobs/{succeeded_job.id}/regenerate/pptx")
            assert response.status_code == 200

        # Verify job state
        test_db_session.refresh(succeeded_job)
        assert succeeded_job.status == JobStatus.RUNNING
        assert succeeded_job.stage == "GENERATE_PPTX_ONLY"
        # Version should remain unchanged
        assert succeeded_job.current_steps_version == new_version

    def test_regenerate_preserves_existing_frames(
        self, client, test_db_session, succeeded_job, mock_storage
    ):
        """Test that regeneration doesn't touch existing frames."""
        original_frames_uri = succeeded_job.frames_prefix_uri

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.api.routes.celery_app.send_task", lambda *args, **kwargs: None)
            response = client.post(f"/api/jobs/{succeeded_job.id}/regenerate/pptx")
            assert response.status_code == 200

        # Frames URI should remain unchanged
        test_db_session.refresh(succeeded_job)
        assert succeeded_job.frames_prefix_uri == original_frames_uri

    def test_regenerate_requires_frames(self, client, test_db_session, succeeded_job):
        """Test that regeneration fails if no frames available."""
        # Remove frames URI
        succeeded_job.frames_prefix_uri = None
        test_db_session.commit()

        response = client.post(f"/api/jobs/{succeeded_job.id}/regenerate/pptx")
        assert response.status_code == 400
        assert "frames" in response.json()["detail"].lower()

    def test_regenerate_requires_steps(self, client, test_db_session, succeeded_job):
        """Test that regeneration fails if no steps available."""
        # Remove steps URI
        succeeded_job.steps_json_uri = None
        test_db_session.commit()

        response = client.post(f"/api/jobs/{succeeded_job.id}/regenerate/pptx")
        assert response.status_code == 400
        assert "steps" in response.json()["detail"].lower()

    def test_regenerate_updates_trace_id(
        self, client, test_db_session, succeeded_job, mock_storage
    ):
        """Test that regeneration creates a new trace ID."""
        original_trace_id = succeeded_job.trace_id

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.api.routes.celery_app.send_task", lambda *args, **kwargs: None)
            response = client.post(f"/api/jobs/{succeeded_job.id}/regenerate/pptx")
            assert response.status_code == 200

        test_db_session.refresh(succeeded_job)
        # Trace ID should be updated for new task
        assert succeeded_job.trace_id != original_trace_id


class TestStepsVersioning:
    """Tests for steps versioning functionality."""

    def test_version_increments_on_edit(
        self, client, test_db_session, succeeded_job, steps_fixture, mock_storage
    ):
        """Test that version number increments on each edit."""
        initial_version = succeeded_job.current_steps_version

        # First edit
        modified_steps = steps_fixture.copy()
        modified_steps["title"] = "Edit 1"
        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps",
            json={"steps_json": modified_steps}
        )
        assert response.status_code == 200
        assert response.json()["version"] == initial_version + 1

        # Second edit
        modified_steps["title"] = "Edit 2"
        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps",
            json={"steps_json": modified_steps}
        )
        assert response.status_code == 200
        assert response.json()["version"] == initial_version + 2

    def test_versions_endpoint_returns_all_versions(
        self, client, test_db_session, succeeded_job, steps_fixture, mock_storage
    ):
        """Test that versions endpoint returns complete history."""
        # Create multiple versions
        for i in range(3):
            modified_steps = steps_fixture.copy()
            modified_steps["title"] = f"Version {i + 2}"
            response = client.put(
                f"/api/jobs/{succeeded_job.id}/steps",
                json={"steps_json": modified_steps, "edit_note": f"Edit {i + 1}"}
            )
            assert response.status_code == 200

        # Get versions
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps/versions")
        assert response.status_code == 200

        versions = response.json()["versions"]
        assert len(versions) == 4  # 1 initial + 3 edits

        # Verify ordering (descending by version)
        version_numbers = [v["version"] for v in versions]
        assert version_numbers == sorted(version_numbers, reverse=True)

    def test_can_retrieve_specific_version(
        self, client, test_db_session, succeeded_job, steps_fixture, mock_storage
    ):
        """Test that specific version can be retrieved."""
        # Create a new version
        modified_steps = steps_fixture.copy()
        modified_steps["title"] = "New Version Title"
        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps",
            json={"steps_json": modified_steps}
        )
        assert response.status_code == 200

        # Get version 1 (original)
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps?version=1")
        assert response.status_code == 200
        assert response.json()["version"] == 1
        assert response.json()["steps_json"]["title"] == steps_fixture["title"]

        # Get version 2 (edited)
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps?version=2")
        assert response.status_code == 200
        assert response.json()["version"] == 2
        assert response.json()["steps_json"]["title"] == "New Version Title"

    def test_default_retrieves_current_version(
        self, client, test_db_session, succeeded_job, steps_fixture, mock_storage
    ):
        """Test that default retrieval returns current version."""
        # Create new versions
        for i in range(2):
            modified_steps = steps_fixture.copy()
            modified_steps["title"] = f"Version {i + 2}"
            client.put(
                f"/api/jobs/{succeeded_job.id}/steps",
                json={"steps_json": modified_steps}
            )

        # Get without version param
        response = client.get(f"/api/jobs/{succeeded_job.id}/steps")
        assert response.status_code == 200

        test_db_session.refresh(succeeded_job)
        assert response.json()["version"] == succeeded_job.current_steps_version
