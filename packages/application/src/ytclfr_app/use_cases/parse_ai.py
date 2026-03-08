"""Use case boundary for AI parsing of OCR text."""

from ytclfr_core.errors.exceptions import AIParsingError
from ytclfr_domain.entities.knowledge_item import KnowledgeItem


class ParseAIUseCase:
    """Parse OCR text into structured knowledge items."""

    def execute(self, ocr_text: str) -> list[KnowledgeItem]:
        """Placeholder implementation for AI parsing use case."""
        try:
            _ = ocr_text
            return []
        except Exception as exc:
            raise AIParsingError("AI parsing failed.") from exc
