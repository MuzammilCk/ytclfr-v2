"""Domain entity for parsed knowledge output."""

from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeItem:
    """Represents structured knowledge extracted from a video."""

    title: str
    description: str
    tags: list[str]
