"""AI parsing module using OpenRouter with strict schema validation."""

import asyncio
import json
import re
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ytclfr_core.config import Settings
from ytclfr_core.errors.exceptions import AIParsingError

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


class VideoType(str, Enum):
    """Supported high-level video categories."""

    MUSIC = "music"
    MOVIE = "movie"
    RECIPE = "recipe"
    BOOKS = "books"
    TUTORIAL = "tutorial"


class MusicData(BaseModel):
    """Structured extraction for music videos."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    artist: str | None = None
    genre: str | None = None
    mood: str | None = None
    themes: list[str] = Field(default_factory=list)
    notable_lyrics: list[str] = Field(default_factory=list)


class MovieData(BaseModel):
    """Structured extraction for movie clips/trailers."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    genre: str | None = None
    characters: list[str] = Field(default_factory=list)
    plot_points: list[str] = Field(default_factory=list)
    setting: str | None = None
    themes: list[str] = Field(default_factory=list)


class RecipeData(BaseModel):
    """Structured extraction for recipe videos."""

    model_config = ConfigDict(extra="forbid")

    dish_name: str | None = None
    cuisine: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    cook_time_minutes: int | None = Field(default=None, ge=0, le=1440)
    tools: list[str] = Field(default_factory=list)


class BooksData(BaseModel):
    """Structured extraction for books/review videos."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    author: str | None = None
    key_ideas: list[str] = Field(default_factory=list)
    notable_quotes: list[str] = Field(default_factory=list)
    chapter_topics: list[str] = Field(default_factory=list)


class TutorialData(BaseModel):
    """Structured extraction for tutorials/courses."""

    model_config = ConfigDict(extra="forbid")

    topic: str | None = None
    prerequisites: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)


class StructuredData(BaseModel):
    """Type-specific structured payload container."""

    model_config = ConfigDict(extra="forbid")

    music: MusicData | None = None
    movie: MovieData | None = None
    recipe: RecipeData | None = None
    books: BooksData | None = None
    tutorial: TutorialData | None = None


class AIParsedPayload(BaseModel):
    """Strict validated schema for AI parsing output."""

    model_config = ConfigDict(extra="forbid")

    video_type: VideoType
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1, max_length=12000)
    points: list[str] = Field(default_factory=list, max_length=100)
    entities: list[str] = Field(default_factory=list, max_length=200)
    structured_data: StructuredData

    @model_validator(mode="after")
    def validate_structured_payload(self) -> "AIParsedPayload":
        """Ensure `structured_data` includes the selected video type section."""
        expected_key = self.video_type.value
        value_by_type = {
            "music": self.structured_data.music,
            "movie": self.structured_data.movie,
            "recipe": self.structured_data.recipe,
            "books": self.structured_data.books,
            "tutorial": self.structured_data.tutorial,
        }
        if value_by_type[expected_key] is None:
            raise ValueError(
                f"structured_data.{expected_key} must be present for video_type={expected_key}."
            )
        return self


class OpenRouterAIParser:
    """OpenRouter-based parser with strict JSON validation and retries."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._schema = AIParsedPayload.model_json_schema()
        self._max_retries = int(settings.openrouter_parse_max_retries)

    async def parse_ocr_text(self, ocr_text: str) -> dict[str, Any]:
        """Parse OCR text to validated structured JSON."""
        normalized_input = str(ocr_text or "").strip()
        if not normalized_input:
            raise AIParsingError("OCR text is empty; cannot parse.")

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                content = await self._request_completion(
                    ocr_text=normalized_input,
                    attempt=attempt,
                    previous_error=(str(last_error) if last_error else None),
                )
                parsed_object = self._parse_json_content(content)
                validated = AIParsedPayload.model_validate(parsed_object)
                return validated.model_dump(mode="json")
            except (ValidationError, json.JSONDecodeError, AIParsingError) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await self._sleep_before_retry(attempt)
            except Exception as exc:
                last_error = AIParsingError(
                    f"OpenRouter request failed on attempt {attempt}: "
                    f"{exc.__class__.__name__}: {exc}"
                )
                last_error.__cause__ = exc
                if attempt >= self._max_retries:
                    break
                await self._sleep_before_retry(attempt)

        raise AIParsingError(
            f"OpenRouter parsing failed after {self._max_retries} attempt(s)."
        ) from last_error

    async def _request_completion(
        self,
        ocr_text: str,
        attempt: int,
        previous_error: str | None,
    ) -> object:
        """Send one parsing request to OpenRouter and return raw content."""
        endpoint = f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        messages = self._build_messages(
            ocr_text=ocr_text,
            attempt=attempt,
            previous_error=previous_error,
        )
        payload = {
            "model": self._settings.openrouter_model,
            "messages": messages,
            "temperature": 0.0,
        }

        async with httpx.AsyncClient(timeout=self._settings.openrouter_timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise AIParsingError("Unexpected OpenRouter response shape.") from exc

    def _build_messages(
        self,
        ocr_text: str,
        attempt: int,
        previous_error: str | None,
    ) -> list[dict[str, str]]:
        """Build prompts that enforce strict schema and category constraints."""
        schema_json = json.dumps(self._schema, ensure_ascii=True)
        rules = (
            "Return ONLY a valid JSON object. "
            "Do not add markdown, explanations, or extra keys. "
            "video_type must be one of: music, movie, recipe, books, tutorial. "
            "Output must satisfy the provided JSON schema exactly."
        )
        system_prompt = (
            "You are an information extraction engine.\n"
            f"{rules}\n"
            f"JSON_SCHEMA={schema_json}"
        )
        user_prompt = f"OCR_TEXT:\n{ocr_text}"
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if attempt > 1 and previous_error:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Previous answer was invalid. Fix it and return valid JSON only. "
                        f"Validation error: {previous_error}"
                    ),
                }
            )
        return messages

    def _parse_json_content(self, content: object) -> dict[str, Any]:
        """Parse raw model content into JSON object."""
        if isinstance(content, dict):
            return content
        if isinstance(content, list):
            flattened = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    flattened.append(str(item.get("text", "")))
                else:
                    flattened.append(str(item))
            content = "\n".join(flattened)
        if not isinstance(content, str):
            raise AIParsingError("Model content is not JSON-compatible.")

        text = content.strip()
        if not text:
            raise AIParsingError("Model returned empty content.")

        fenced_match = _FENCED_JSON_RE.search(text)
        if fenced_match:
            text = fenced_match.group(1).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            json_start = text.find("{")
            json_end = text.rfind("}")
            if json_start < 0 or json_end <= json_start:
                raise
            parsed = json.loads(text[json_start : json_end + 1])

        if not isinstance(parsed, dict):
            raise AIParsingError("Parsed content must be a JSON object.")
        return parsed

    async def _sleep_before_retry(self, attempt: int) -> None:
        """Backoff between validation retries."""
        delay_seconds = min(5, attempt)
        await asyncio.sleep(delay_seconds)


class OpenRouterClient(OpenRouterAIParser):
    """Backward-compatible alias for existing imports."""
