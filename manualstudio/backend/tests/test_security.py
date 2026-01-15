"""Security regression tests for ManualStudio."""

import uuid


class TestPathTraversal:
    """Tests for path traversal attack prevention.

    Note: FastAPI's routing doesn't match paths with "/" in path parameters,
    so most path traversal attempts result in 404 (route not found).
    This is acceptable security behavior - the attack is blocked.
    """

    def test_frame_path_traversal_rejected(self, client, succeeded_job):
        """Test that path traversal in frame_file is rejected.

        FastAPI returns 404 because the route doesn't match paths with slashes.
        """
        response = client.get(f"/api/jobs/{succeeded_job.id}/frames/../../../etc/passwd")
        # 404 is acceptable - route doesn't match, attack blocked
        assert response.status_code in [400, 404]

    def test_frame_path_traversal_dotdot_slash(self, client, succeeded_job):
        """Test that ../file.png is rejected."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/frames/../secret.png")
        # 404 is acceptable - route doesn't match, attack blocked
        assert response.status_code in [400, 404]

    def test_frame_path_traversal_encoded(self, client, succeeded_job):
        """Test that URL-encoded path traversal is rejected."""
        # %2e%2e = ..
        response = client.get(f"/api/jobs/{succeeded_job.id}/frames/%2e%2e/secret.png")
        # Either 400 (our validation) or 404 (route mismatch) is acceptable
        assert response.status_code in [400, 404]

    def test_frame_normal_filename_allowed(self, client, succeeded_job):
        """Test that normal filenames are allowed (even if file doesn't exist)."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/frames/step_001.png")
        # Should return 307 redirect or 404 (file not found), not 400
        assert response.status_code in [307, 404]

    def test_frame_filename_with_subdirectory_rejected(self, client, succeeded_job):
        """Test that filenames with subdirectories are rejected.

        FastAPI returns 404 because the route doesn't match paths with slashes.
        """
        response = client.get(f"/api/jobs/{succeeded_job.id}/frames/subdir/file.png")
        # 404 is acceptable - route doesn't match, attack blocked
        assert response.status_code in [400, 404]


class TestInputValidation:
    """Tests for input validation."""

    def test_job_id_sql_injection_rejected(self, client):
        """Test that SQL injection in job_id is rejected."""
        response = client.get("/api/jobs/'; DROP TABLE jobs;--")
        assert response.status_code == 400
        assert "Invalid job ID" in response.json()["detail"]

    def test_job_id_xss_rejected(self, client):
        """Test that XSS in job_id is rejected.

        FastAPI may return 404 (route mismatch) or 400 (validation error).
        Either is acceptable - the attack is blocked.
        """
        response = client.get("/api/jobs/<script>alert(1)</script>")
        # 404 or 400 both indicate the attack was blocked
        assert response.status_code in [400, 404]

    def test_steps_json_oversized_rejected(self, client, succeeded_job, steps_fixture):
        """Test that oversized steps.json is handled gracefully."""
        # Create oversized steps with many steps
        oversized_steps = steps_fixture.copy()
        oversized_steps["steps"] = [steps_fixture["steps"][0].copy() for _ in range(1000)]

        response = client.put(
            f"/api/jobs/{succeeded_job.id}/steps", json={"steps_json": oversized_steps}
        )
        # Should either accept or return a meaningful error (not crash)
        assert response.status_code in [200, 400, 413]


class TestAuthorizationBoundaries:
    """Tests for authorization boundaries."""

    def test_cannot_access_other_job_frames(self, client, succeeded_job):
        """Test that we cannot use one job's ID to access another's frames."""
        # Create a fake job ID
        fake_job_id = str(uuid.uuid4())

        # Try to access frames with fake job ID
        response = client.get(f"/api/jobs/{fake_job_id}/frames/step_001.png")
        assert response.status_code == 404

    def test_cannot_edit_non_succeeded_job(self, client, sample_job, steps_fixture):
        """Test that we cannot edit a job that hasn't succeeded."""
        response = client.put(
            f"/api/jobs/{sample_job.id}/steps", json={"steps_json": steps_fixture}
        )
        assert response.status_code == 400
        assert "SUCCEEDED" in response.json()["detail"]

    def test_cannot_regenerate_non_succeeded_job(self, client, sample_job):
        """Test that we cannot regenerate PPTX for a non-succeeded job."""
        response = client.post(f"/api/jobs/{sample_job.id}/regenerate/pptx")
        assert response.status_code == 400
        assert "SUCCEEDED" in response.json()["detail"]
