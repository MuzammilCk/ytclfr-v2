"""Domain value object for video processing states.

All video lifecycle transitions use this enum. Replaces the bare string
literals previously scattered across task_support.py.
"""

from enum import StrEnum


class VideoStatus(StrEnum):
    """Allowed processing states for a source video record."""

    # Initial state set by the API on submission.
    PENDING = "PENDING"

    # Broad in-progress state used by the pipeline orchestrator.
    PROCESSING = "PROCESSING"

    # Fine-grained stage states emitted by individual Celery tasks.
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    EXTRACTING_FRAMES = "EXTRACTING_FRAMES"
    FRAMES_EXTRACTED = "FRAMES_EXTRACTED"
    RUNNING_OCR = "RUNNING_OCR"
    OCR_COMPLETED = "OCR_COMPLETED"
    PARSING_TEXT = "PARSING_TEXT"
    TEXT_PARSED = "TEXT_PARSED"
    GENERATING_OUTPUT = "GENERATING_OUTPUT"

    # Terminal states.
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
