"""Tests for export functionality (Markdown/HTML/SRT)."""

import uuid

from app.db.models import Job, JobStatus
from app.services.export import (
    _format_srt_timestamp,
    generate_html,
    generate_markdown,
    generate_srt,
)


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


class TestSRTTimestampFormatting:
    """Test SRT timestamp formatting function."""

    def test_format_zero_seconds(self):
        """Test formatting 0 seconds."""
        result = _format_srt_timestamp(0)
        assert result == "00:00:00,000"

    def test_format_simple_seconds(self):
        """Test formatting simple seconds."""
        result = _format_srt_timestamp(5.0)
        assert result == "00:00:05,000"

    def test_format_with_milliseconds(self):
        """Test formatting seconds with milliseconds."""
        result = _format_srt_timestamp(5.5)
        assert result == "00:00:05,500"

    def test_format_minutes(self):
        """Test formatting with minutes."""
        result = _format_srt_timestamp(65.0)
        assert result == "00:01:05,000"

    def test_format_hours(self):
        """Test formatting with hours."""
        result = _format_srt_timestamp(3665.0)  # 1 hour, 1 minute, 5 seconds
        assert result == "01:01:05,000"

    def test_format_complex_time(self):
        """Test formatting complex timestamp."""
        result = _format_srt_timestamp(3723.456)  # 1:02:03.456
        assert result == "01:02:03,456"

    def test_format_negative_becomes_zero(self):
        """Test that negative values become zero."""
        result = _format_srt_timestamp(-5.0)
        assert result == "00:00:00,000"


class TestSRTGeneration:
    """Test SRT generation from transcript segments."""

    def test_srt_basic_format(self, transcript_fixture):
        """Test basic SRT format generation."""
        srt = generate_srt(transcript_fixture)

        # Check sequence numbers
        assert "1\n" in srt
        assert "2\n" in srt

        # Check timestamp format
        assert "00:00:00,000 --> 00:00:05,000" in srt
        assert "00:00:05,000 --> 00:00:12,000" in srt

        # Check text content
        assert "経費精算システムの使い方を説明します" in srt

    def test_srt_contains_all_segments(self, transcript_fixture):
        """Test that SRT contains all transcript segments."""
        srt = generate_srt(transcript_fixture)

        # All 8 segments should have their text
        for segment in transcript_fixture:
            assert segment["text"] in srt

    def test_srt_empty_segments_returns_empty(self):
        """Test that empty segments list returns empty string."""
        result = generate_srt([])
        assert result == ""

    def test_srt_skips_empty_text(self):
        """Test that segments with empty text are skipped."""
        segments = [
            {"start_sec": 0, "end_sec": 5, "text": "First"},
            {"start_sec": 5, "end_sec": 10, "text": ""},  # Empty - should skip
            {"start_sec": 10, "end_sec": 15, "text": "   "},  # Whitespace - should skip
            {"start_sec": 15, "end_sec": 20, "text": "Third"},
        ]
        srt = generate_srt(segments)

        # Should only have entries for "First" and "Third"
        assert "First" in srt
        assert "Third" in srt
        # Verify empty text segments were skipped by checking sequence numbers
        assert "1\n" in srt  # First entry
        assert "2\n" in srt or srt.count("\n1\n") == 0  # Has a second entry

    def test_srt_sequence_numbers_are_continuous(self):
        """Test that sequence numbers are continuous even when skipping."""
        segments = [
            {"start_sec": 0, "end_sec": 5, "text": "First"},
            {"start_sec": 5, "end_sec": 10, "text": ""},  # Skipped
            {"start_sec": 10, "end_sec": 15, "text": "Second"},
        ]
        srt = generate_srt(segments)

        lines = srt.strip().split("\n")
        # First entry starts with "1"
        assert lines[0] == "1"
        # Second entry (after blank) should be "2" not "3"
        # Find the second sequence number
        sequence_numbers = [line for line in lines if line.isdigit()]
        assert sequence_numbers == ["1", "2"]

    def test_srt_long_video_timestamps(self):
        """Test SRT with timestamps over an hour."""
        segments = [
            {"start_sec": 3600, "end_sec": 3605, "text": "One hour mark"},
            {"start_sec": 7200, "end_sec": 7210, "text": "Two hour mark"},
        ]
        srt = generate_srt(segments)

        assert "01:00:00,000 --> 01:00:05,000" in srt
        assert "02:00:00,000 --> 02:00:10,000" in srt

    def test_srt_millisecond_precision(self):
        """Test that milliseconds are preserved correctly."""
        segments = [
            {"start_sec": 1.234, "end_sec": 5.678, "text": "Test"},
        ]
        srt = generate_srt(segments)

        assert "00:00:01,234 --> 00:00:05,678" in srt


class TestSRTAPIEndpoints:
    """Test SRT API endpoints."""

    def test_download_srt_success_from_db(
        self, client, succeeded_job, test_db_session, mock_storage
    ):
        """Test successful SRT download with transcript in DB."""
        # Add transcript segments to the job
        succeeded_job.transcript_segments = [
            {"start_sec": 0, "end_sec": 5, "text": "テストテキスト"},
            {"start_sec": 5, "end_sec": 10, "text": "二番目のセグメント"},
        ]
        test_db_session.commit()

        response = client.get(f"/api/jobs/{succeeded_job.id}/download/srt")

        assert response.status_code == 200
        assert "text/srt" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".srt" in response.headers.get("content-disposition", "")

        # Check content
        content = response.text
        assert "テストテキスト" in content
        assert "00:00:00,000 --> 00:00:05,000" in content

    def test_download_srt_success_from_storage(
        self, client, succeeded_job, test_db_session, mock_storage
    ):
        """Test SRT download with transcript in storage."""
        # Save transcript to mock storage
        import json

        transcript = [
            {"start_sec": 0, "end_sec": 5, "text": "ストレージからのテキスト"},
        ]
        transcript_key = f"jobs/{succeeded_job.id}/transcript/segments.json"
        mock_storage.upload_bytes(
            json.dumps(transcript).encode("utf-8"),
            transcript_key,
            "application/json",
        )
        succeeded_job.transcript_uri = f"s3://test-bucket/{transcript_key}"
        test_db_session.commit()

        response = client.get(f"/api/jobs/{succeeded_job.id}/download/srt")

        assert response.status_code == 200
        content = response.text
        assert "ストレージからのテキスト" in content

    def test_download_srt_job_not_found(self, client):
        """Test SRT download with non-existent job."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/jobs/{fake_id}/download/srt")

        assert response.status_code == 404

    def test_download_srt_invalid_job_id(self, client):
        """Test SRT download with invalid job ID."""
        response = client.get("/api/jobs/invalid-uuid/download/srt")

        assert response.status_code == 400
        assert "Invalid job ID" in response.json()["detail"]

    def test_download_srt_job_not_succeeded(self, client, test_db_session):
        """Test SRT download with non-succeeded job."""
        job = Job(
            id=uuid.uuid4(),
            status=JobStatus.RUNNING,
            title="Running Job",
        )
        test_db_session.add(job)
        test_db_session.commit()

        response = client.get(f"/api/jobs/{job.id}/download/srt")

        assert response.status_code == 400
        assert "SUCCEEDED" in response.json()["detail"]

    def test_download_srt_no_transcript(self, client, succeeded_job, test_db_session):
        """Test SRT download when no transcript available."""
        # Ensure no transcript segments
        succeeded_job.transcript_segments = None
        succeeded_job.transcript_uri = None
        test_db_session.commit()

        response = client.get(f"/api/jobs/{succeeded_job.id}/download/srt")

        assert response.status_code == 404
        assert "No transcript available" in response.json()["detail"]

    def test_download_srt_empty_transcript(self, client, succeeded_job, test_db_session):
        """Test SRT download with empty transcript list."""
        succeeded_job.transcript_segments = []
        test_db_session.commit()

        response = client.get(f"/api/jobs/{succeeded_job.id}/download/srt")

        assert response.status_code == 404

    def test_download_srt_transcript_with_only_empty_text(
        self, client, succeeded_job, test_db_session
    ):
        """Test SRT download when transcript has only empty text segments."""
        succeeded_job.transcript_segments = [
            {"start_sec": 0, "end_sec": 5, "text": ""},
            {"start_sec": 5, "end_sec": 10, "text": "   "},
        ]
        test_db_session.commit()

        response = client.get(f"/api/jobs/{succeeded_job.id}/download/srt")

        assert response.status_code == 404
        assert "no text" in response.json()["detail"]

    def test_download_srt_content_disposition_filename(
        self, client, succeeded_job, test_db_session, mock_storage
    ):
        """Test that SRT download has proper filename in Content-Disposition."""
        succeeded_job.title = "テスト動画マニュアル"
        succeeded_job.transcript_segments = [
            {"start_sec": 0, "end_sec": 5, "text": "テスト"},
        ]
        test_db_session.commit()

        response = client.get(f"/api/jobs/{succeeded_job.id}/download/srt")

        assert response.status_code == 200
        content_disposition = response.headers.get("content-disposition", "")
        assert ".srt" in content_disposition
