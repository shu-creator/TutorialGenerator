"""Transcription service with provider abstraction."""
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import TranscriptionError, ErrorCode

logger = get_logger(__name__)

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"


@dataclass
class TranscriptSegment:
    """A segment of transcribed text with timestamps."""
    start_sec: float
    end_sec: float
    text: str


class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        language: str = "ja"
    ) -> list[TranscriptSegment]:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Language code

        Returns:
            List of transcript segments
        """
        pass


class OpenAITranscriptionProvider(TranscriptionProvider):
    """OpenAI Whisper transcription provider."""

    def __init__(self):
        settings = get_settings()
        if not settings.openai_api_key:
            raise TranscriptionError(
                "OPENAI_API_KEY not configured",
                ErrorCode.TRANSCRIBE_PROVIDER_ERROR.value
            )

        from openai import OpenAI
        self.client = OpenAI(api_key=settings.openai_api_key)

    @property
    def name(self) -> str:
        return "openai"

    def transcribe(
        self,
        audio_path: str,
        language: str = "ja"
    ) -> list[TranscriptSegment]:
        """Transcribe using OpenAI Whisper API."""
        try:
            logger.info(f"Transcribing audio with OpenAI Whisper: {audio_path}")

            with open(audio_path, "rb") as audio_file:
                # Use verbose_json to get timestamps
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

            segments = []
            for seg in response.segments:
                segments.append(TranscriptSegment(
                    start_sec=seg.start,
                    end_sec=seg.end,
                    text=seg.text.strip()
                ))

            logger.info(f"Transcription complete: {len(segments)} segments")
            return segments

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise TranscriptionError(
                f"Transcription failed: {e}",
                ErrorCode.TRANSCRIBE_FAILED.value
            )


class MockTranscriptionProvider(TranscriptionProvider):
    """Mock provider for testing - loads from fixture file."""

    def __init__(self, fixture_path: Optional[str] = None):
        """
        Initialize mock provider.

        Args:
            fixture_path: Optional path to fixture file. Defaults to tests/fixtures/transcript.json
        """
        self.fixture_path = fixture_path or str(FIXTURES_DIR / "transcript.json")

    @property
    def name(self) -> str:
        return "mock"

    def transcribe(
        self,
        audio_path: str,
        language: str = "ja"
    ) -> list[TranscriptSegment]:
        """Return transcript from fixture file."""
        logger.info(f"Mock transcription for: {audio_path}")

        try:
            if os.path.exists(self.fixture_path):
                with open(self.fixture_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    segments = [
                        TranscriptSegment(
                            start_sec=seg["start_sec"],
                            end_sec=seg["end_sec"],
                            text=seg["text"]
                        )
                        for seg in data
                    ]
                    logger.info(f"Loaded {len(segments)} segments from fixture")
                    return segments
        except Exception as e:
            logger.warning(f"Failed to load fixture, using default: {e}")

        # Fallback to hardcoded mock data
        return [
            TranscriptSegment(0, 5, "これはテスト用のサンプルテキストです。"),
            TranscriptSegment(5, 10, "画面の操作を説明します。"),
            TranscriptSegment(10, 15, "ボタンをクリックしてください。"),
        ]


class TranscriptionService:
    """Transcription service with provider abstraction."""

    def __init__(self, provider: Optional[str] = None):
        settings = get_settings()
        provider_name = provider or settings.transcribe_provider

        if provider_name == "openai":
            self._provider = OpenAITranscriptionProvider()
        elif provider_name == "mock":
            self._provider = MockTranscriptionProvider()
        else:
            raise TranscriptionError(
                f"Unknown transcription provider: {provider_name}",
                ErrorCode.TRANSCRIBE_PROVIDER_ERROR.value
            )

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def transcribe(
        self,
        audio_path: str,
        language: str = "ja"
    ) -> list[TranscriptSegment]:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Language code

        Returns:
            List of transcript segments
        """
        return self._provider.transcribe(audio_path, language)

    def segments_to_dict(self, segments: list[TranscriptSegment]) -> list[dict]:
        """Convert segments to serializable dictionaries."""
        return [
            {
                "start_sec": s.start_sec,
                "end_sec": s.end_sec,
                "text": s.text
            }
            for s in segments
        ]


def get_transcription_service(provider: Optional[str] = None) -> TranscriptionService:
    """Get transcription service instance."""
    return TranscriptionService(provider)
