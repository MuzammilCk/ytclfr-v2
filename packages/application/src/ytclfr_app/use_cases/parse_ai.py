"""Use case for AI parsing of OCR text.

Replaces the stub with a real implementation that delegates to the
OpenRouter client adapter injected at construction time.
"""

from __future__ import annotations

from typing import Any

from ytclfr_core.errors.exceptions import AIParsingError
from ytclfr_core.logging.logger import get_logger
from ytclfr_infra.ai.openrouter_client import OpenRouterClient

logger = get_logger(__name__)


class ParseAIUseCase:
    """Parse OCR text into a structured knowledge payload via OpenRouter.

    The client is injected so this use case can be tested with a fake
    implementation that avoids real API calls.
    """

    def __init__(self, ai_client: OpenRouterClient) -> None:
        self._client = ai_client

    async def execute(self, ocr_text: str) -> dict[str, Any]:
        """Send OCR text to the AI parser and return a validated payload.

        Args:
            ocr_text: Normalised, deduplicated text from the OCR stage.

        Returns:
            Validated AIParsedPayload dict with video_type, summary,
            points, entities, structured_data, and confidence.

        Raises:
            AIParsingError: If parsing fails or the schema is invalid
                            after all configured retries.
        """
        stripped = (ocr_text or "").strip()
        if not stripped:
            raise AIParsingError("Cannot parse empty OCR text.")

        try:
            result = await self._client.parse_ocr_text(stripped)
        except AIParsingError:
            raise
        except Exception as exc:
            raise AIParsingError(
                f"AI parsing failed unexpectedly: {exc.__class__.__name__}: {exc}"
            ) from exc

        logger.info(
            "AI parsing use case completed.",
            extra={
                "video_type": result.get("video_type"),
                "confidence": result.get("confidence"),
                "point_count": len(result.get("points", [])),
                "entity_count": len(result.get("entities", [])),
            },
        )
        return result
