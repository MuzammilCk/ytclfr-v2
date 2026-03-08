"""Shared task utilities for worker pipeline stages."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session, sessionmaker

from ytclfr_core.config import Settings, get_settings
from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_core.logging.logger import get_logger
from ytclfr_core.monitoring import capture_exception, record_task_error, record_task_retry
from ytclfr_core.utils.time_utils import utc_now
from ytclfr_domain.value_objects.job_status import JobStatus
from ytclfr_infra.ai.action_engine import ActionEngine
from ytclfr_infra.ai.openrouter_client import OpenRouterClient
from ytclfr_infra.db import models
from ytclfr_infra.db.database import Base, build_engine, build_session_factory, session_scope
from ytclfr_infra.execution.command_runner import CommandRunner
from ytclfr_infra.ocr.ocr_engine import OCRLine, PaddleOCREngine
from ytclfr_infra.ocr.text_cleaner import TextCleaner
from ytclfr_infra.video.frame_extractor import ExtractedFrame, FrameExtractor
from ytclfr_infra.video.youtube_downloader import YouTubeDownloader

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_worker_settings() -> Settings:
    """Return shared worker settings."""
    return get_settings()


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Create and cache session factory for worker operations."""
    settings = get_worker_settings()
    engine = build_engine(settings)
    Base.metadata.create_all(bind=engine)
    return build_session_factory(engine)


@lru_cache(maxsize=1)
def get_downloader() -> YouTubeDownloader:
    """Build downloader adapter."""
    settings = get_worker_settings()
    return YouTubeDownloader(
        yt_dlp_binary=settings.yt_dlp_bin,
        max_duration_seconds=settings.max_video_duration,
    )


@lru_cache(maxsize=1)
def get_frame_extractor() -> FrameExtractor:
    """Build frame extractor adapter using ffmpeg + PySceneDetect."""
    settings = get_worker_settings()
    return FrameExtractor(
        ffmpeg_binary=settings.ffmpeg_bin,
        command_runner=CommandRunner(),
        interval_seconds=2,
    )


@lru_cache(maxsize=1)
def get_ocr_engine() -> PaddleOCREngine:
    """Build OCR engine adapter."""
    settings = get_worker_settings()
    return PaddleOCREngine(
        language=settings.ocr_language,
        use_gpu=settings.ocr_use_gpu,
        batch_size=settings.ocr_batch_size,
        min_confidence=settings.ocr_min_confidence,
    )


@lru_cache(maxsize=1)
def get_text_cleaner() -> TextCleaner:
    """Build text normalization and deduplication utility."""
    return TextCleaner()


@lru_cache(maxsize=1)
def get_ai_client() -> OpenRouterClient:
    """Build OpenRouter client adapter."""
    settings = get_worker_settings()
    return OpenRouterClient(settings)


@lru_cache(maxsize=1)
def get_action_engine() -> ActionEngine:
    """Build final action generator."""
    settings = get_worker_settings()
    return ActionEngine(settings=settings)


def _parse_job_uuid(job_id: str) -> UUID:
    """Parse task-provided job id safely."""
    try:
        return UUID(job_id)
    except Exception as exc:
        raise RepositoryError(f"Invalid job id: {job_id}") from exc


def load_job_context(job_id: str) -> tuple[UUID, UUID, str]:
    """Load job/video identifiers and source URL from database."""
    job_uuid = _parse_job_uuid(job_id)
    factory = get_session_factory()
    with session_scope(factory) as session:
        job = session.get(models.JobModel, job_uuid)
        if job is None:
            raise RepositoryError(f"Job not found: {job_id}")
        if job.video_id is None:
            raise RepositoryError(f"Job has no video_id: {job_id}")
        return job.id, job.video_id, job.video_url


def get_job_work_dir(job_id: UUID) -> Path:
    """Return per-job working directory."""
    settings = get_worker_settings()
    return Path(settings.storage_path) / str(job_id)


def mark_job_running(job_id: str) -> None:
    """Mark job and video as running."""
    job_uuid = _parse_job_uuid(job_id)
    factory = get_session_factory()
    now = utc_now()
    with session_scope(factory) as session:
        job = session.get(models.JobModel, job_uuid)
        if job is None:
            raise RepositoryError(f"Job not found: {job_id}")
        job.status = JobStatus.RUNNING.value
        job.error_message = None
        job.started_at = job.started_at or now
        job.attempts = int(job.attempts or 0) + 1
        job.updated_at = now
        if job.video_id is not None:
            video = session.get(models.VideoModel, job.video_id)
            if video is not None:
                video.status = "PROCESSING"
                video.updated_at = now


def mark_job_failed(job_id: str, error_message: str) -> None:
    """Mark job and linked video as failed."""
    job_uuid = _parse_job_uuid(job_id)
    factory = get_session_factory()
    now = utc_now()
    with session_scope(factory) as session:
        job = session.get(models.JobModel, job_uuid)
        if job is None:
            raise RepositoryError(f"Job not found: {job_id}")
        job.status = JobStatus.FAILED.value
        job.error_message = error_message[:4000]
        job.completed_at = now
        job.updated_at = now
        if job.video_id is not None:
            video = session.get(models.VideoModel, job.video_id)
            if video is not None:
                video.status = "FAILED"
                video.updated_at = now


def mark_job_completed(job_id: str) -> None:
    """Mark job and linked video as completed."""
    job_uuid = _parse_job_uuid(job_id)
    factory = get_session_factory()
    now = utc_now()
    with session_scope(factory) as session:
        job = session.get(models.JobModel, job_uuid)
        if job is None:
            raise RepositoryError(f"Job not found: {job_id}")
        job.status = JobStatus.COMPLETED.value
        job.error_message = None
        job.completed_at = now
        job.updated_at = now
        if job.video_id is not None:
            video = session.get(models.VideoModel, job.video_id)
            if video is not None:
                video.status = "COMPLETED"
                video.updated_at = now


def update_video_status(
    video_id: UUID,
    status: str,
    storage_path: str | None = None,
    title: str | None = None,
) -> None:
    """Update video stage status and metadata."""
    factory = get_session_factory()
    with session_scope(factory) as session:
        video = session.get(models.VideoModel, video_id)
        if video is None:
            raise RepositoryError(f"Video not found: {video_id}")
        video.status = status
        video.updated_at = utc_now()
        if storage_path is not None:
            video.storage_path = storage_path
        if title is not None and title.strip():
            video.title = title.strip()


def persist_frames(video_id: UUID, frames: list[ExtractedFrame]) -> list[dict[str, str | float]]:
    """Replace frame records for a video and return frame references."""
    factory = get_session_factory()
    frame_refs: list[dict[str, str | float]] = []
    with session_scope(factory) as session:
        session.query(models.FrameModel).filter(models.FrameModel.video_id == video_id).delete()
        ordered_frames = sorted(frames, key=lambda item: item.timestamp_seconds)
        for frame_index, extracted in enumerate(ordered_frames):
            frame_model = models.FrameModel(
                video_id=video_id,
                frame_index=frame_index,
                timestamp_seconds=Decimal(str(max(0.0, extracted.timestamp_seconds))),
                image_path=str(extracted.image_path),
            )
            session.add(frame_model)
            session.flush()
            frame_refs.append(
                {
                    "frame_id": str(frame_model.id),
                    "image_path": str(extracted.image_path),
                    "timestamp_seconds": float(max(0.0, extracted.timestamp_seconds)),
                    "source_type": extracted.source_type,
                }
            )
    return frame_refs


def persist_ocr_results(
    job_id: UUID,
    frame_refs: list[dict[str, str | float]],
    ocr_lines: list[OCRLine],
    min_confidence: float = 0.0,
) -> str:
    """Persist OCR rows and return merged OCR text."""
    factory = get_session_factory()
    frame_id_by_path = {
        str(ref["image_path"]): UUID(str(ref["frame_id"]))
        for ref in frame_refs
        if ref.get("image_path") and ref.get("frame_id")
    }
    text_lines: list[str] = []
    with session_scope(factory) as session:
        session.query(models.OCRResultModel).filter(models.OCRResultModel.job_id == job_id).delete()
        for line in ocr_lines:
            frame_id = frame_id_by_path.get(str(line.source_image))
            if frame_id is None:
                continue
            if float(line.confidence) < float(min_confidence):
                continue
            confidence = Decimal(str(min(max(float(line.confidence), 0.0), 1.0)))
            session.add(
                models.OCRResultModel(
                    frame_id=frame_id,
                    job_id=job_id,
                    text=line.text,
                    confidence=confidence,
                    language="en",
                    raw_payload={
                        "source_image": str(line.source_image),
                        "timestamp_seconds": max(0.0, float(line.timestamp_seconds)),
                    },
                )
            )
            if line.text.strip():
                text_lines.append(line.text.strip())
    return "\n".join(text_lines)


def persist_parsed_output(job_id: UUID, video_id: UUID, parsed_payload: dict[str, Any]) -> None:
    """Persist parsed output rows for a job/video."""
    summary = str(parsed_payload.get("summary", "")).strip()
    points = [str(item).strip() for item in parsed_payload.get("points", []) if str(item).strip()]
    entities = [
        str(item).strip() for item in parsed_payload.get("entities", []) if str(item).strip()
    ]
    if not summary:
        summary = "\n".join(points)
    factory = get_session_factory()
    with session_scope(factory) as session:
        session.query(models.ParsedContentModel).filter(models.ParsedContentModel.job_id == job_id).delete()
        session.add(
            models.ParsedContentModel(
                job_id=job_id,
                video_id=video_id,
                content_type="SUMMARY",
                title="Video Summary",
                summary=summary,
                tags=entities,
                entities=entities,
                raw_response=parsed_payload,
            )
        )
        for point in points:
            session.add(
                models.ParsedContentModel(
                    job_id=job_id,
                    video_id=video_id,
                    content_type="POINT",
                    title="Key Point",
                    summary=point,
                    tags=entities,
                    entities=entities,
                    raw_response=None,
                )
            )


def retry_or_fail(task: Task, exc: Exception, job_id: str, stage: str) -> None:
    """Retry a task or mark pipeline as failed when retries are exhausted."""
    max_retries = int(task.max_retries or 0)
    current_retries = int(task.request.retries)
    task_name = getattr(task, "name", "unknown")
    if current_retries >= max_retries:
        error_message = f"{stage} failed permanently: {exc}"
        logger.exception(error_message)
        record_task_error(task_name=task_name, exception_type=exc.__class__.__name__)
        capture_exception(
            exc,
            context={
                "task_name": task_name,
                "stage": stage,
                "job_id": job_id,
                "is_permanent_failure": True,
            },
        )
        try:
            mark_job_failed(job_id=job_id, error_message=error_message)
        except Exception:
            logger.exception("Failed to update job failure status.")
        raise exc
    countdown = min(300, 2 ** (current_retries + 1))
    record_task_retry(task_name=task_name, stage=stage)
    raise task.retry(exc=exc, countdown=countdown)
