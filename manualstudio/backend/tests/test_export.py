"""Tests for export functionality (Markdown/HTML)."""

import uuid

from app.db.models import Job, JobStatus
from app.services.export import generate_html, generate_markdown


class TestMarkdownExport:
    """Test Markdown export generation."""

    def test_markdown_contains_title(self, steps_fixture):
        """Test that Markdown output contains the title."""
        markdown = generate_markdown(steps_fixture)

        assert "# 経費精算システム操作手順" in markdown

    def test_markdown_contains_goal(self, steps_fixture):
        """Test that Markdown output contains the goal."""
        markdown = generate_markdown(steps_fixture)

        assert "**目的**:" in markdown
        assert "新入社員向けに経費精算の申請方法を説明する" in markdown

    def test_markdown_contains_steps(self, steps_fixture):
        """Test that Markdown output contains all steps."""
        markdown = generate_markdown(steps_fixture)

        # Check step headers
        assert "### ステップ 1:" in markdown
        assert "### ステップ 2:" in markdown
        assert "### ステップ 3:" in markdown
        assert "### ステップ 4:" in markdown

        # Check step content
        assert "システムにアクセス" in markdown
        assert "ログイン" in markdown
        assert "新規申請を選択" in markdown
        assert "申請内容を入力" in markdown

    def test_markdown_contains_actions(self, steps_fixture):
        """Test that Markdown output contains action descriptions."""
        markdown = generate_markdown(steps_fixture)

        assert "**操作**:" in markdown
        assert "ブラウザを開き、経費精算システムのURLにアクセスします" in markdown

    def test_markdown_contains_cautions(self, steps_fixture):
        """Test that Markdown output contains caution notes."""
        markdown = generate_markdown(steps_fixture)

        assert "⚠️ **注意**:" in markdown
        assert "パスワードは3回間違えるとロックされます" in markdown

    def test_markdown_contains_common_mistakes(self, steps_fixture):
        """Test that Markdown output contains common mistakes section."""
        markdown = generate_markdown(steps_fixture)

        assert "## よくある間違い" in markdown
        assert "領収書をアップロードせずに申請してしまう" in markdown

    def test_markdown_contains_quiz(self, steps_fixture):
        """Test that Markdown output contains quiz section."""
        markdown = generate_markdown(steps_fixture)

        assert "## 確認クイズ" in markdown
        assert "経費申請時に必ず必要なものは何ですか？" in markdown

    def test_markdown_empty_steps(self):
        """Test Markdown generation with minimal data."""
        data = {"title": "Test Title"}
        markdown = generate_markdown(data)

        assert "# Test Title" in markdown


class TestHTMLExport:
    """Test HTML export generation."""

    def test_html_contains_title(self, steps_fixture):
        """Test that HTML output contains the title."""
        html = generate_html(steps_fixture)

        assert "<title>経費精算システム操作手順</title>" in html
        assert "<h1>経費精算システム操作手順</h1>" in html

    def test_html_contains_goal(self, steps_fixture):
        """Test that HTML output contains the goal."""
        html = generate_html(steps_fixture)

        assert "新入社員向けに経費精算の申請方法を説明する" in html

    def test_html_contains_steps(self, steps_fixture):
        """Test that HTML output contains all steps."""
        html = generate_html(steps_fixture)

        assert "ステップ 1:" in html
        assert "システムにアクセス" in html
        assert "ステップ 2:" in html
        assert "ログイン" in html

    def test_html_is_valid_document(self, steps_fixture):
        """Test that HTML output is a complete document."""
        html = generate_html(steps_fixture)

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "</head>" in html
        assert "<body>" in html
        assert "</body>" in html


class TestHTMLXSSPrevention:
    """Test XSS prevention in HTML export."""

    def test_script_tag_in_title_is_escaped(self):
        """Test that script tags in title are HTML-escaped."""
        malicious_data = {
            "title": '<script>alert("XSS")</script>Malicious Title',
            "steps": [],
        }
        html = generate_html(malicious_data)

        # Script tag should be escaped, not raw
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert 'alert("XSS")' not in html or "&quot;" in html

    def test_script_tag_in_goal_is_escaped(self):
        """Test that script tags in goal are HTML-escaped."""
        malicious_data = {
            "title": "Test",
            "goal": '<script>alert("XSS")</script>',
            "steps": [],
        }
        html = generate_html(malicious_data)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_script_tag_in_step_telop_is_escaped(self):
        """Test that script tags in step telop are HTML-escaped."""
        malicious_data = {
            "title": "Test",
            "steps": [
                {
                    "no": 1,
                    "telop": '<script>alert("XSS")</script>',
                    "action": "Test action",
                }
            ],
        }
        html = generate_html(malicious_data)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_script_tag_in_step_action_is_escaped(self):
        """Test that script tags in step action are HTML-escaped."""
        malicious_data = {
            "title": "Test",
            "steps": [
                {
                    "no": 1,
                    "telop": "Test",
                    "action": '<img src=x onerror="alert(1)">',
                }
            ],
        }
        html = generate_html(malicious_data)

        assert 'onerror="alert(1)"' not in html
        assert "&lt;img" in html

    def test_script_tag_in_narration_is_escaped(self):
        """Test that script tags in narration are HTML-escaped."""
        malicious_data = {
            "title": "Test",
            "steps": [
                {
                    "no": 1,
                    "telop": "Test",
                    "action": "Test",
                    "narration": "<script>document.cookie</script>",
                }
            ],
        }
        html = generate_html(malicious_data)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_script_tag_in_caution_is_escaped(self):
        """Test that script tags in caution are HTML-escaped."""
        malicious_data = {
            "title": "Test",
            "steps": [
                {
                    "no": 1,
                    "telop": "Test",
                    "action": "Test",
                    "caution": "<script>evil()</script>",
                }
            ],
        }
        html = generate_html(malicious_data)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_html_injection_in_common_mistakes_is_escaped(self):
        """Test that HTML injection in common_mistakes is escaped."""
        malicious_data = {
            "title": "Test",
            "steps": [],
            "common_mistakes": [
                {
                    "mistake": '<a href="javascript:alert(1)">Click me</a>',
                    "fix": "Don't click",
                }
            ],
        }
        html = generate_html(malicious_data)

        # The <a> tag should be escaped - check that it's not a real link
        assert '<a href="javascript:' not in html  # Raw tag should not exist
        assert "&lt;a href=" in html  # Escaped tag should exist

    def test_html_injection_in_quiz_is_escaped(self):
        """Test that HTML injection in quiz is escaped."""
        malicious_data = {
            "title": "Test",
            "steps": [],
            "quiz": [
                {
                    "type": "text",
                    "q": '<script>alert("quiz")</script>',
                    "a": "Answer",
                }
            ],
        }
        html = generate_html(malicious_data)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_all_html_special_chars_are_escaped(self):
        """Test that all HTML special characters are properly escaped."""
        malicious_data = {
            "title": "Test <>&\"' chars",
            "steps": [],
        }
        html = generate_html(malicious_data)

        # Check title in <title> and <h1> tags
        assert "&lt;" in html
        assert "&gt;" in html
        assert "&amp;" in html
        assert "&quot;" in html


class TestExportAPIEndpoints:
    """Test export API endpoints."""

    def test_download_markdown_success(self, client, succeeded_job, test_db_session, mock_storage):
        """Test successful Markdown download."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/download/markdown")

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")

        # Check content
        content = response.text
        assert "# " in content  # Has title
        assert "## 操作手順" in content

    def test_download_html_success(self, client, succeeded_job, test_db_session, mock_storage):
        """Test successful HTML download."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/download/html")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")

        # Check content
        content = response.text
        assert "<!DOCTYPE html>" in content
        assert "<html" in content

    def test_download_markdown_job_not_found(self, client):
        """Test Markdown download with non-existent job."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/jobs/{fake_id}/download/markdown")

        assert response.status_code == 404

    def test_download_html_job_not_found(self, client):
        """Test HTML download with non-existent job."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/jobs/{fake_id}/download/html")

        assert response.status_code == 404

    def test_download_markdown_invalid_job_id(self, client):
        """Test Markdown download with invalid job ID."""
        response = client.get("/api/jobs/invalid-uuid/download/markdown")

        assert response.status_code == 400
        assert "Invalid job ID" in response.json()["detail"]

    def test_download_html_invalid_job_id(self, client):
        """Test HTML download with invalid job ID."""
        response = client.get("/api/jobs/invalid-uuid/download/html")

        assert response.status_code == 400
        assert "Invalid job ID" in response.json()["detail"]

    def test_download_markdown_job_not_succeeded(self, client, test_db_session):
        """Test Markdown download with non-succeeded job."""
        job = Job(
            id=uuid.uuid4(),
            status=JobStatus.RUNNING,
            title="Test",
        )
        test_db_session.add(job)
        test_db_session.commit()

        response = client.get(f"/api/jobs/{job.id}/download/markdown")

        assert response.status_code == 400
        assert "SUCCEEDED" in response.json()["detail"]

    def test_download_html_job_not_succeeded(self, client, test_db_session):
        """Test HTML download with non-succeeded job."""
        job = Job(
            id=uuid.uuid4(),
            status=JobStatus.FAILED,
            title="Test",
        )
        test_db_session.add(job)
        test_db_session.commit()

        response = client.get(f"/api/jobs/{job.id}/download/html")

        assert response.status_code == 400
        assert "SUCCEEDED" in response.json()["detail"]

    def test_download_markdown_content_disposition(self, client, succeeded_job, mock_storage):
        """Test that Markdown download has proper filename in Content-Disposition."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/download/markdown")

        assert response.status_code == 200
        content_disposition = response.headers.get("content-disposition", "")
        assert ".md" in content_disposition or "markdown" in content_disposition.lower()

    def test_download_html_content_disposition(self, client, succeeded_job, mock_storage):
        """Test that HTML download has proper filename in Content-Disposition."""
        response = client.get(f"/api/jobs/{succeeded_job.id}/download/html")

        assert response.status_code == 200
        content_disposition = response.headers.get("content-disposition", "")
        assert ".html" in content_disposition
