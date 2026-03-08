"""Unit tests for strict OpenRouter AI parsing behavior."""

import asyncio
import json

import pytest

from ytclfr_core.config import Settings
from ytclfr_core.errors.exceptions import AIParsingError
from ytclfr_infra.ai.ai_parser import OpenRouterAIParser


def _build_settings() -> Settings:
    """Create deterministic settings for parser tests."""
    return Settings.model_validate(
        {
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "INFO",
            "API_PORT": 8000,
            "DATABASE_URL": "postgresql+psycopg://ytclfr:ytclfr@127.0.0.1:5432/ytclfr",
            "REDIS_URL": "redis://127.0.0.1:6379/0",
            "OPENROUTER_API_KEY": "test_api_key_123",
            "SPOTIFY_CLIENT_ID": "id",
            "SPOTIFY_CLIENT_SECRET": "secret_123",
            "STORAGE_PATH": "./storage",
            "MAX_VIDEO_DURATION": 3600,
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENROUTER_MODEL": "openai/gpt-4o-mini",
            "OPENROUTER_TIMEOUT_SECONDS": 30,
            "OPENROUTER_PARSE_MAX_RETRIES": 3,
            "SPOTIFY_AUTH_URL": "https://accounts.spotify.com/api/token",
            "SPOTIFY_API_BASE_URL": "https://api.spotify.com/v1",
            "SPOTIFY_TIMEOUT_SECONDS": 30,
        }
    )


def _valid_payload_text() -> str:
    """Return one valid model output string following strict schema."""
    return json.dumps(
        {
            "video_type": "tutorial",
            "confidence": 0.93,
            "summary": "Step-by-step Python tutorial for beginners.",
            "points": ["Install Python", "Create virtual environment"],
            "entities": ["Python", "virtual environment"],
            "structured_data": {
                "music": None,
                "movie": None,
                "recipe": None,
                "books": None,
                "tutorial": {
                    "topic": "Python basics",
                    "prerequisites": ["Computer"],
                    "steps": ["Install Python", "Run first script"],
                    "tools": ["Python", "Terminal"],
                    "outcomes": ["Can run Python programs"],
                },
            },
        }
    )


def test_parser_accepts_valid_json(monkeypatch) -> None:
    """Parser should validate and return strict JSON payload."""
    parser = OpenRouterAIParser(_build_settings())

    async def fake_request(ocr_text: str, attempt: int, previous_error: str | None) -> str:
        _ = (ocr_text, attempt, previous_error)
        return _valid_payload_text()

    async def fake_sleep(attempt: int) -> None:
        _ = attempt
        return None

    monkeypatch.setattr(parser, "_request_completion", fake_request)
    monkeypatch.setattr(parser, "_sleep_before_retry", fake_sleep)

    result = asyncio.run(parser.parse_ocr_text("some ocr text"))

    assert result["video_type"] == "tutorial"
    assert result["structured_data"]["tutorial"]["topic"] == "Python basics"
    assert result["summary"]


def test_parser_retries_when_json_invalid(monkeypatch) -> None:
    """Parser should retry when initial response is not valid JSON."""
    parser = OpenRouterAIParser(_build_settings())
    responses = iter(["not-json-response", _valid_payload_text()])
    attempts: list[int] = []

    async def fake_request(ocr_text: str, attempt: int, previous_error: str | None) -> str:
        _ = (ocr_text, previous_error)
        attempts.append(attempt)
        return next(responses)

    async def fake_sleep(attempt: int) -> None:
        _ = attempt
        return None

    monkeypatch.setattr(parser, "_request_completion", fake_request)
    monkeypatch.setattr(parser, "_sleep_before_retry", fake_sleep)

    result = asyncio.run(parser.parse_ocr_text("ocr text"))

    assert result["video_type"] == "tutorial"
    assert attempts == [1, 2]


def test_parser_raises_after_retries(monkeypatch) -> None:
    """Parser should fail after max retries when schema remains invalid."""
    parser = OpenRouterAIParser(_build_settings())

    async def fake_request(ocr_text: str, attempt: int, previous_error: str | None) -> str:
        _ = (ocr_text, attempt, previous_error)
        return json.dumps({"video_type": "invalid-type"})

    async def fake_sleep(attempt: int) -> None:
        _ = attempt
        return None

    monkeypatch.setattr(parser, "_request_completion", fake_request)
    monkeypatch.setattr(parser, "_sleep_before_retry", fake_sleep)

    with pytest.raises(AIParsingError):
        asyncio.run(parser.parse_ocr_text("ocr text"))

