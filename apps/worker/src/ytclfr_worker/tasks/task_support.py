"""Shared task utilities for worker pipeline stages.

Responsibilities after refactoring:
- Provide lru_cached getter factories for all shared adapters and services.
- Keep infrastructure-level helpers (persist_frames, persist_ocr_results,
  load_job_context, retry_or_fail) that do not belong in the application layer.

Removed from this module (moved to application layer):
- mark_job_running / mark_job_failed / mark_job_completed  -> JobLifecycleService
- update_video_status                                       -> JobLifecycleService
- persist_parsed_output                                     -> PersistOutputUseCase
"""

import asyncio
from collections.abc import Coroutine
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from threading import Thread
from typing import Any, TypeVar
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session, sessionmaker

from ytclfr_app.services.job_lifecycle_service import JobLifecycleService
from ytclfr_app.use_cases.parse_ai import ParseAIUseCase
from ytclfr_app.use_cases.persist_output import PersistOutputUseCase
from ytclfr_app.use_cases.run_ocr import RunOCRUseCase
from ytclfr_core.config import Settings, get_settings
from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_core.logging.logger import get_logger
from ytclfr_core.monitoring import capture_exception, record_task_error, record_task_retry
from ytclfr_infra.ai.action_engine import ActionEngine
from ytclfr_infra.ai.openrouter_client import OpenRouterClient
from ytclfr_infra.db import models
from ytclfr_infra.db.database import build_engine, build_session_factory, session_scope
from ytclfr_infra.db.repositories.sqlalchemy_job_repository import SQLAlchemyJobRepository
from ytclfr_infra.db.repositories.sqlalchemy_knowledge_repository import (
    SQLAlchemyKnowledgeRepository,
)
from ytclfr_infra.db.repositories.sqlalchemy_video_repository import SQLAlchemyVideoRepository
from ytclfr_infra.execution.command_runner import CommandRunner
from ytclfr_infra.ocr.ocr_engine import OCRLine, PaddleOCREngine
from ytclfr_infra.ocr.text_cleaner import TextCleaner
from ytclfr_infra.queue.redis_event_publisher import NoOpEventPublisher, RedisEventPublisher
from ytclfr_infra.video.frame_extractor import ExtractedFrame, FrameExtractor
from ytclfr_infra.video.youtube_downloader import YouTubeDownloader

logger = get_logger(__name__)
_T = TypeVar("_T")


# ---------------------------------------------------------------------------
# Core infrastructure getters
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_worker_settings() -> Settings:
    """Return shared worker settings."""
    return get_settings()


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Create and cache session factory for worker operations."""
    settings = get_worker_settings()
    engine = build_engine(settings)
    return build_session_factory(engine)


@lru_cache(maxsize=1)
def get_downloader() -> YouTubeDownloader:
    """Build downloader adapter."""
    settings = get_worker_settings()
    return YouTubeDownloader(
        yt_dlp_binary=settings.yt_dlp_bin,
        max_duration_seconds=settings.max_video_duration,
        cookies_from_browser=settings.yt_dlp_cookies_from_browser,
        cookie_file=settings.yt_dlp_cookie_file,
        retry_without_cookies=settings.yt_dlp_retry_without_cookies,
        player_client=settings.yt_dlp_player_client,
        sleep_interval=settings.yt_dlp_sleep_interval,
        max_sleep_interval=settings.yt_dlp_max_sleep_interval,
        extractor_args=settings.yt_dlp_extractor_args,
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
    """Build text normalisation and deduplication utility."""
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


# ---------------------------------------------------------------------------
# Application-layer service getters
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_event_publisher() -> RedisEventPublisher | NoOpEventPublisher:
    """Build Redis event publisher, falling back to no-op on failure."""
    settings = get_worker_settings()
    try:
        return RedisEventPublisher(redis_url=str(settings.redis_url))
    except Exception:
        logger.warning("Redis event publisher unavailable; using no-op fallback.")
        return NoOpEventPublisher()


@lru_cache(maxsize=1)
def get_job_lifecycle_service() -> JobLifecycleService:
    """Build JobLifecycleService with wired repository and event publisher."""
    factory = get_session_factory()
    return JobLifecycleService(
        job_repository=SQLAlchemyJobRepository(factory),
        video_repository=SQLAlchemyVideoRepository(factory),
        event_publisher=get_event_publisher(),
    )


@lru_cache(maxsize=1)
def get_run_ocr_use_case() -> RunOCRUseCase:
    """Build RunOCRUseCase with wired adapters."""
    return RunOCRUseCase(
        ocr_engine=get_ocr_engine(),
        text_cleaner=get_text_cleaner(),
    )


@lru_cache(maxsize=1)
def get_parse_ai_use_case() -> ParseAIUseCase:
    """Build ParseAIUseCase with wired AI client."""
    return ParseAIUseCase(ai_client=get_ai_client())


@lru_cache(maxsize=1)
def get_persist_output_use_case() -> PersistOutputUseCase:
    """Build PersistOutputUseCase with wired knowledge repository."""
    factory = get_session_factory()
    return PersistOutputUseCase(
        knowledge_repository=SQLAlchemyKnowledgeRepository(factory)
    )


# ---------------------------------------------------------------------------
# Infrastructure helpers shared across tasks
# ---------------------------------------------------------------------------


def run_coroutine_sync(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run an async coroutine from sync task code.

    If a loop is already running in the current thread, execute the coroutine in a
    dedicated thread with its own event loop to avoid RuntimeError.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[_T] = []
    errors: list[BaseException] = []

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result.append(loop.run_until_complete(coro))
        except BaseException as exc:  # pragma: no cover - exceptional path
            errors.append(exc)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if errors:
        raise errors[0]
    if not result:
        raise RuntimeError("Coroutine execution did not return a result.")
    return result[0]


def _parse_job_uuid(job_id: str) -> UUID:
    """Parse task-provided job id safely."""
    try:
        return UUID(job_id)
    except Exception as exc:
        raise RepositoryError(f"Invalid job id: {job_id}") from exc


def load_job_context(job_id: str) -> tuple[UUID, UUID, str]:
    """Load job/video identifiers and source URL from the database."""
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
    """Return per-job working directory path."""
    settings = get_worker_settings()
    return Path(settings.storage_path) / str(job_id)


def persist_frames(
    video_id: UUID, frames: list[ExtractedFrame]
) -> list[dict[str, str | float]]:
    """Replace frame records for a video and return frame references."""
    factory = get_session_factory()
    frame_refs: list[dict[str, str | float]] = []
    with session_scope(factory) as session:
        session.query(models.FrameModel).filter(
            models.FrameModel.video_id == video_id
        ).delete()
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
    """Persist OCR rows and return merged OCR text for downstream stages."""
    factory = get_session_factory()
    frame_id_by_path = {
        str(ref["image_path"]): UUID(str(ref["frame_id"]))
        for ref in frame_refs
        if ref.get("image_path") and ref.get("frame_id")
    }
    text_lines: list[str] = []
    with session_scope(factory) as session:
        session.query(models.OCRResultModel).filter(
            models.OCRResultModel.job_id == job_id
        ).delete()
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


def retry_or_fail(task: Task, exc: Exception, job_id: str, stage: str) -> None:
    """Retry a task or mark pipeline as permanently failed when retries exhausted."""
    max_retries = int(task.max_retries or 0)
    current_retries = int(task.request.retries)
    task_name = getattr(task, "name", "unknown")

    if current_retries >= max_retries:
        error_message = f"{stage} failed permanently: {exc}"
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
            get_job_lifecycle_service().mark_failed(
                job_id=_parse_job_uuid(job_id), error_message=error_message
            )
        except Exception:
            logger.exception("Failed to update job failure status after exhausting retries.")
        raise exc

    countdown = min(300, 2 ** (current_retries + 1))
    record_task_retry(task_name=task_name, stage=stage)
    raise task.retry(exc=exc, countdown=countdown)
