"""LLM service for generating steps.json."""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

import jsonschema

from app.core.config import get_settings
from app.core.exceptions import ErrorCode, LLMError, LLMValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"


# JSON Schema for steps.json validation
STEPS_JSON_SCHEMA = {
    "type": "object",
    "required": ["title", "goal", "language", "source", "steps"],
    "properties": {
        "title": {"type": "string"},
        "goal": {"type": "string"},
        "language": {"type": "string"},
        "source": {
            "type": "object",
            "required": ["video_duration_sec", "video_fps", "resolution"],
            "properties": {
                "video_duration_sec": {"type": "number"},
                "video_fps": {"type": "number"},
                "resolution": {"type": "string"},
                "transcription_provider": {"type": "string"},
                "llm_provider": {"type": "string"},
            },
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "no",
                    "start",
                    "end",
                    "shot",
                    "frame_file",
                    "telop",
                    "action",
                    "target",
                    "narration",
                ],
                "properties": {
                    "no": {"type": "integer", "minimum": 1},
                    "start": {"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}$"},
                    "end": {"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}$"},
                    "shot": {"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}$"},
                    "frame_file": {"type": "string"},
                    "telop": {"type": "string", "maxLength": 30},
                    "action": {"type": "string"},
                    "target": {"type": "string"},
                    "narration": {"type": "string"},
                    "caution": {"type": "string"},
                },
            },
        },
        "common_mistakes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["mistake", "fix"],
                "properties": {"mistake": {"type": "string"}, "fix": {"type": "string"}},
            },
        },
        "quiz": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "q", "a"],
                "properties": {
                    "type": {"type": "string", "enum": ["choice", "text"]},
                    "q": {"type": "string"},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "a": {"type": "string"},
                },
            },
        },
    },
}


SYSTEM_PROMPT = """あなたは操作マニュアル作成のエキスパートです。
動画の文字起こしとフレーム候補から、構造化された操作手順（steps.json）を生成してください。

# 重要なルール
- 出力はJSONのみ。前後の説明は禁止。
- 推測禁止。不明な情報は "unknown" と記載。
- 1ステップは約20秒を目安に区切る。
- telopは15文字以内で簡潔に。
- narrationは丁寧語（です・ます調）で1-2文。
- start/end/shotは必ずMM:SS形式（例: 01:30）。
- 各ステップのframe_fileは、提供されたcandidate_framesから最も適切なものを選択。

# 出力JSON形式
```json
{
  "title": "マニュアルタイトル",
  "goal": "このマニュアルの目的",
  "language": "ja",
  "source": {
    "video_duration_sec": 数値,
    "video_fps": 数値,
    "resolution": "WxH",
    "transcription_provider": "provider名",
    "llm_provider": "provider名"
  },
  "steps": [
    {
      "no": 1,
      "start": "00:00",
      "end": "00:20",
      "shot": "00:10",
      "frame_file": "step_001.png",
      "telop": "短いタイトル",
      "action": "実行する操作の説明",
      "target": "操作対象（不明ならunknown）",
      "narration": "丁寧語での説明文です。",
      "caution": "注意事項（任意）"
    }
  ],
  "common_mistakes": [
    {"mistake": "よくあるミス", "fix": "対処法"}
  ],
  "quiz": [
    {"type": "choice", "q": "質問", "choices": ["A", "B", "C", "D"], "a": "A"}
  ]
}
```"""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str) -> str:
        """Generate response from LLM."""
        pass


class OpenAILLMProvider(LLMProvider):
    """OpenAI LLM provider."""

    def __init__(self):
        settings = get_settings()
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY not configured", ErrorCode.LLM_PROVIDER_ERROR.value)

        from openai import OpenAI

        self.client = OpenAI(api_key=settings.openai_api_key)

    @property
    def name(self) -> str:
        return "openai"

    def generate(self, prompt: str, system_prompt: str) -> str:
        """Generate response using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise LLMError(f"OpenAI API call failed: {e}", ErrorCode.LLM_PROVIDER_ERROR.value)


class AnthropicLLMProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self):
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY not configured", ErrorCode.LLM_PROVIDER_ERROR.value)

        import anthropic

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model
        self.max_tokens = settings.anthropic_max_tokens

    @property
    def name(self) -> str:
        return "anthropic"

    def generate(self, prompt: str, system_prompt: str) -> str:
        """Generate response using Anthropic Claude."""
        try:
            logger.info(
                f"Calling Anthropic API with model={self.model}, max_tokens={self.max_tokens}"
            )
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise LLMError(f"Anthropic API call failed: {e}", ErrorCode.LLM_PROVIDER_ERROR.value)


class MockLLMProvider(LLMProvider):
    """Mock provider for testing - loads from fixture file."""

    def __init__(self, fixture_path: str | None = None):
        """
        Initialize mock provider.

        Args:
            fixture_path: Optional path to fixture file. Defaults to tests/fixtures/steps.json
        """
        self.fixture_path = fixture_path or str(FIXTURES_DIR / "steps.json")

    @property
    def name(self) -> str:
        return "mock"

    def generate(self, prompt: str, system_prompt: str) -> str:
        """Return steps.json from fixture file."""
        logger.info("Mock LLM generating steps.json from fixture")

        try:
            if os.path.exists(self.fixture_path):
                with open(self.fixture_path, encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded steps from fixture: {len(data.get('steps', []))} steps")
                    return json.dumps(data, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to load fixture, using default: {e}")

        # Fallback to hardcoded mock data
        return json.dumps(
            {
                "title": "テスト手順書",
                "goal": "テスト用のサンプル",
                "language": "ja",
                "source": {
                    "video_duration_sec": 30,
                    "video_fps": 30,
                    "resolution": "1920x1080",
                    "transcription_provider": "mock",
                    "llm_provider": "mock",
                },
                "steps": [
                    {
                        "no": 1,
                        "start": "00:00",
                        "end": "00:10",
                        "shot": "00:05",
                        "frame_file": "step_001.png",
                        "telop": "開始",
                        "action": "アプリケーションを起動します",
                        "target": "アプリアイコン",
                        "narration": "まず、アプリケーションを起動してください。",
                    }
                ],
                "common_mistakes": [],
                "quiz": [],
            },
            ensure_ascii=False,
        )


class LLMService:
    """LLM service for generating steps.json."""

    def __init__(self, provider: str | None = None):
        settings = get_settings()
        provider_name = provider or settings.llm_provider

        if provider_name == "openai":
            self._provider = OpenAILLMProvider()
        elif provider_name == "anthropic" or provider_name == "claude":
            self._provider = AnthropicLLMProvider()
        elif provider_name == "mock":
            self._provider = MockLLMProvider()
        else:
            raise LLMError(
                f"Unknown LLM provider: {provider_name}", ErrorCode.LLM_PROVIDER_ERROR.value
            )

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def generate_steps(
        self,
        title: str,
        goal: str,
        language: str,
        transcript_segments: list[dict],
        candidate_frames: list[dict],
        video_info: dict,
        transcription_provider: str,
        max_retries: int = 1,
    ) -> dict:
        """
        Generate steps.json from transcript and frame candidates.

        Args:
            title: Manual title
            goal: Manual goal
            language: Language code
            transcript_segments: List of transcript segments
            candidate_frames: List of candidate frame info
            video_info: Video metadata
            transcription_provider: Name of transcription provider used
            max_retries: Number of retries on validation failure

        Returns:
            Validated steps.json as dict
        """
        # Build user prompt
        prompt = self._build_prompt(
            title,
            goal,
            language,
            transcript_segments,
            candidate_frames,
            video_info,
            transcription_provider,
        )

        # Try to generate and validate
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Generating steps.json (attempt {attempt + 1})")

                if attempt > 0:
                    # Add retry instruction
                    retry_prompt = f"""前回の出力がJSON Schemaに合っていませんでした。
エラー: {last_error}

以下を修正して、正しいJSONを再出力してください:
{prompt}"""
                    response = self._provider.generate(retry_prompt, SYSTEM_PROMPT)
                else:
                    response = self._provider.generate(prompt, SYSTEM_PROMPT)

                # Parse and validate JSON
                steps_json = self._parse_and_validate(response)

                # Update source info
                steps_json["source"]["transcription_provider"] = transcription_provider
                steps_json["source"]["llm_provider"] = self.provider_name

                logger.info(f"Generated {len(steps_json['steps'])} steps")
                return steps_json

            except LLMValidationError as e:
                last_error = str(e)
                logger.warning(f"Validation failed on attempt {attempt + 1}: {e}")
                if attempt == max_retries:
                    raise

        raise LLMError("Failed to generate valid steps.json")

    def _build_prompt(
        self,
        title: str,
        goal: str,
        language: str,
        transcript_segments: list[dict],
        candidate_frames: list[dict],
        video_info: dict,
        transcription_provider: str,
    ) -> str:
        """Build the user prompt for LLM."""
        # Format transcript
        transcript_text = ""
        for seg in transcript_segments:
            start = seg.get("start_sec", 0)
            end = seg.get("end_sec", 0)
            text = seg.get("text", "")
            transcript_text += f"[{start:.1f}s - {end:.1f}s] {text}\n"

        # Format candidate frames
        frames_text = ""
        for frame in candidate_frames:
            time_mmss = frame.get("time_mmss", "00:00")
            filename = frame.get("filename", "")
            frames_text += f"- {time_mmss}: {filename}\n"

        prompt = f"""# 入力情報

## 基本情報
- タイトル: {title or "操作マニュアル"}
- 目的: {goal or "操作手順の説明"}
- 言語: {language}

## 動画情報
- 長さ: {video_info.get("duration_sec", 0):.1f}秒
- FPS: {video_info.get("fps", 30)}
- 解像度: {video_info.get("resolution", "unknown")}

## 文字起こし
{transcript_text if transcript_text else "(文字起こしなし)"}

## 利用可能なフレーム候補
{frames_text}

# 指示
上記の情報から、操作マニュアルのsteps.jsonを生成してください。
各ステップには適切なcandidate_framesから選んだframe_fileを指定してください。
出力形式でframe_fileを指定する際は、step_XXX.pngの形式に変換してください（例: candidate_001.png → step_001.png）。
JSONのみを出力してください。"""

        return prompt

    def _parse_and_validate(self, response: str) -> dict:
        """Parse and validate LLM response."""
        # Try to extract JSON from response
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Invalid JSON: {e}")

        # Validate against schema
        try:
            jsonschema.validate(data, STEPS_JSON_SCHEMA)
        except jsonschema.ValidationError as e:
            raise LLMValidationError(f"Schema validation failed: {e.message}")

        return data


def validate_steps_json(data: dict) -> None:
    """
    Validate steps.json against schema.

    Args:
        data: steps.json data to validate

    Raises:
        LLMValidationError: If validation fails
    """
    try:
        jsonschema.validate(data, STEPS_JSON_SCHEMA)
    except jsonschema.ValidationError as e:
        raise LLMValidationError(f"Schema validation failed: {e.message}")


def get_llm_service(provider: str | None = None) -> LLMService:
    """Get LLM service instance."""
    return LLMService(provider)
