"""Tests for LLM provider selection and configuration."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.exceptions import LLMError
from app.services.llm import (
    AnthropicLLMProvider,
    LLMService,
    MockLLMProvider,
    OpenAILLMProvider,
)


class TestLLMProviderSelection:
    """Test LLM provider selection based on configuration."""

    def test_selects_mock_provider(self):
        """Test that LLM_PROVIDER=mock selects MockLLMProvider."""
        settings = Settings(
            llm_provider="mock",
            database_url="sqlite:///:memory:",
        )
        with patch("app.services.llm.get_settings", return_value=settings):
            service = LLMService()
            assert service.provider_name == "mock"
            assert isinstance(service._provider, MockLLMProvider)

    def test_selects_openai_provider(self):
        """Test that LLM_PROVIDER=openai selects OpenAILLMProvider."""
        settings = Settings(
            llm_provider="openai",
            openai_api_key="sk-test-key",
            database_url="sqlite:///:memory:",
        )
        with (
            patch("app.services.llm.get_settings", return_value=settings),
            patch("openai.OpenAI"),
        ):
            service = LLMService()
            assert service.provider_name == "openai"
            assert isinstance(service._provider, OpenAILLMProvider)

    def test_selects_anthropic_provider(self):
        """Test that LLM_PROVIDER=anthropic selects AnthropicLLMProvider."""
        settings = Settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test-key",
            anthropic_model="claude-sonnet-4-20250514",
            anthropic_max_tokens=4000,
            database_url="sqlite:///:memory:",
        )
        mock_anthropic = MagicMock()
        with (
            patch("app.services.llm.get_settings", return_value=settings),
            patch.dict("sys.modules", {"anthropic": mock_anthropic}),
        ):
            service = LLMService()
            assert service.provider_name == "anthropic"
            assert isinstance(service._provider, AnthropicLLMProvider)

    def test_selects_anthropic_provider_with_claude_alias(self):
        """Test that LLM_PROVIDER=claude also selects AnthropicLLMProvider."""
        settings = Settings(
            llm_provider="claude",
            anthropic_api_key="sk-ant-test-key",
            anthropic_model="claude-sonnet-4-20250514",
            anthropic_max_tokens=4000,
            database_url="sqlite:///:memory:",
        )
        mock_anthropic = MagicMock()
        with (
            patch("app.services.llm.get_settings", return_value=settings),
            patch.dict("sys.modules", {"anthropic": mock_anthropic}),
        ):
            service = LLMService()
            assert service.provider_name == "anthropic"
            assert isinstance(service._provider, AnthropicLLMProvider)

    def test_explicit_provider_override(self):
        """Test that explicit provider parameter overrides settings."""
        settings = Settings(
            llm_provider="openai",
            openai_api_key="sk-test-key",
            database_url="sqlite:///:memory:",
        )
        with patch("app.services.llm.get_settings", return_value=settings):
            service = LLMService(provider="mock")
            assert service.provider_name == "mock"
            assert isinstance(service._provider, MockLLMProvider)

    def test_unknown_provider_raises_error(self):
        """Test that unknown LLM_PROVIDER raises LLMError."""
        settings = Settings(
            llm_provider="unknown",
            database_url="sqlite:///:memory:",
        )
        with patch("app.services.llm.get_settings", return_value=settings):
            with pytest.raises(LLMError) as exc_info:
                LLMService()
            assert "Unknown LLM provider: unknown" in str(exc_info.value)


class TestAnthropicProviderAPIKeyValidation:
    """Test Anthropic provider API key validation."""

    def test_missing_api_key_raises_error(self):
        """Test that missing ANTHROPIC_API_KEY raises clear error."""
        settings = Settings(
            llm_provider="anthropic",
            anthropic_api_key=None,
            database_url="sqlite:///:memory:",
        )
        with patch("app.services.llm.get_settings", return_value=settings):
            with pytest.raises(LLMError) as exc_info:
                LLMService()
            assert "ANTHROPIC_API_KEY not configured" in str(exc_info.value)

    def test_empty_api_key_raises_error(self):
        """Test that empty ANTHROPIC_API_KEY raises clear error."""
        settings = Settings(
            llm_provider="anthropic",
            anthropic_api_key="",
            database_url="sqlite:///:memory:",
        )
        with patch("app.services.llm.get_settings", return_value=settings):
            with pytest.raises(LLMError) as exc_info:
                LLMService()
            assert "ANTHROPIC_API_KEY not configured" in str(exc_info.value)


class TestOpenAIProviderAPIKeyValidation:
    """Test OpenAI provider API key validation."""

    def test_missing_api_key_raises_error(self):
        """Test that missing OPENAI_API_KEY raises clear error."""
        settings = Settings(
            llm_provider="openai",
            openai_api_key=None,
            database_url="sqlite:///:memory:",
        )
        with patch("app.services.llm.get_settings", return_value=settings):
            with pytest.raises(LLMError) as exc_info:
                LLMService()
            assert "OPENAI_API_KEY not configured" in str(exc_info.value)


class TestAnthropicProviderConfiguration:
    """Test Anthropic provider uses configuration values."""

    def test_uses_configured_model(self):
        """Test that Anthropic provider uses ANTHROPIC_MODEL from settings."""
        settings = Settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test-key",
            anthropic_model="claude-opus-4-20250514",
            anthropic_max_tokens=8000,
            database_url="sqlite:///:memory:",
        )
        mock_anthropic = MagicMock()
        with (
            patch("app.services.llm.get_settings", return_value=settings),
            patch.dict("sys.modules", {"anthropic": mock_anthropic}),
        ):
            service = LLMService()
            provider = service._provider
            assert provider.model == "claude-opus-4-20250514"
            assert provider.max_tokens == 8000

    def test_uses_default_model_when_not_configured(self):
        """Test that Anthropic provider uses default model when not configured."""
        settings = Settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test-key",
            database_url="sqlite:///:memory:",
        )
        mock_anthropic = MagicMock()
        with (
            patch("app.services.llm.get_settings", return_value=settings),
            patch.dict("sys.modules", {"anthropic": mock_anthropic}),
        ):
            service = LLMService()
            provider = service._provider
            assert provider.model == "claude-sonnet-4-20250514"
            assert provider.max_tokens == 4000


class TestMockProviderGenerateSteps:
    """Test MockLLMProvider generates valid steps.json."""

    def test_mock_provider_generates_valid_steps(self):
        """Test that mock provider generates schema-valid steps.json."""
        settings = Settings(
            llm_provider="mock",
            database_url="sqlite:///:memory:",
        )
        with patch("app.services.llm.get_settings", return_value=settings):
            service = LLMService()
            steps = service.generate_steps(
                title="Test Manual",
                goal="Test goal",
                language="ja",
                transcript_segments=[{"start_sec": 0, "end_sec": 10, "text": "Test transcript"}],
                candidate_frames=[{"time_mmss": "00:05", "filename": "candidate_001.png"}],
                video_info={"duration_sec": 30, "fps": 30, "resolution": "1920x1080"},
                transcription_provider="mock",
            )

            # Verify required fields
            assert "title" in steps
            assert "goal" in steps
            assert "language" in steps
            assert "source" in steps
            assert "steps" in steps
            assert isinstance(steps["steps"], list)
            assert len(steps["steps"]) > 0

            # Verify step structure
            step = steps["steps"][0]
            assert "no" in step
            assert "start" in step
            assert "end" in step
            assert "shot" in step
            assert "frame_file" in step
            assert "telop" in step
            assert "action" in step
            assert "target" in step
            assert "narration" in step

    def test_mock_provider_sets_provider_info(self):
        """Test that mock provider sets correct provider info in source."""
        settings = Settings(
            llm_provider="mock",
            database_url="sqlite:///:memory:",
        )
        with patch("app.services.llm.get_settings", return_value=settings):
            service = LLMService()
            steps = service.generate_steps(
                title="Test Manual",
                goal="Test goal",
                language="ja",
                transcript_segments=[],
                candidate_frames=[],
                video_info={"duration_sec": 30, "fps": 30, "resolution": "1920x1080"},
                transcription_provider="mock",
            )

            assert steps["source"]["transcription_provider"] == "mock"
            assert steps["source"]["llm_provider"] == "mock"
