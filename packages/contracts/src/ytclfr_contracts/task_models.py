"""Celery task payload models."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class PipelineTaskPayload(BaseModel):
    """Payload for end-to-end pipeline execution."""

    job_id: UUID


class FrameReference(BaseModel):
    """Frame identity and storage path."""

    frame_id: UUID
    image_path: str
    timestamp_seconds: float
    source_type: str


class DownloadVideoTaskResult(BaseModel):
    """Payload emitted by the download stage."""

    job_id: UUID
    video_id: UUID
    video_url: str
    title: str | None = None
    job_dir: str
    video_path: str


class ExtractFramesTaskResult(BaseModel):
    """Payload emitted by the frame extraction stage."""

    job_id: UUID
    video_id: UUID
    video_url: str
    title: str | None = None
    job_dir: str
    video_path: str
    fps: int
    frames: list[FrameReference]


class OCRTaskResult(BaseModel):
    """Payload emitted by OCR stage."""

    job_id: UUID
    video_id: UUID
    video_url: str
    title: str | None = None
    job_dir: str
    ocr_text: str


class ParseTextTaskResult(BaseModel):
    """Payload emitted by AI parsing stage."""

    job_id: UUID
    video_id: UUID
    video_url: str
    title: str | None = None
    job_dir: str
    ocr_text: str
    parsed_payload: dict[str, Any]


class GenerateOutputTaskResult(BaseModel):
    """Payload emitted by final output stage."""

    job_id: UUID
    video_id: UUID
    status: str
