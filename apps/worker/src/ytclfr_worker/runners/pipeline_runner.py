"""End-to-end pipeline runner executed by Celery tasks."""

import asyncio
from pathlib import Path
from uuid import UUID

from ytclfr_core.config import Settings, get_settings
from ytclfr_core.errors.exceptions import YTCLFRError
from ytclfr_core.utils.time_utils import utc_now
from ytclfr_domain.entities.knowledge_item import KnowledgeItem
from ytclfr_domain.value_objects.job_status import JobStatus
from ytclfr_infra.ai.openrouter_client import OpenRouterClient
from ytclfr_infra.db.repositories.sqlalchemy_job_repository import SQLAlchemyJobRepository
from ytclfr_infra.db.repositories.sqlalchemy_knowledge_repository import SQLAlchemyKnowledgeRepository
from ytclfr_infra.db.session import build_engine, build_session_factory
from ytclfr_infra.execution.command_runner import CommandRunner
from ytclfr_infra.ocr.ocr_engine import OCRFrameInput, PaddleOCREngine
from ytclfr_infra.ocr.text_cleaner import TextCleaner
from ytclfr_infra.video.frame_extractor import FrameExtractor
from ytclfr_infra.video.youtube_downloader import YouTubeDownloader


class PipelineRunner:
    """Coordinates all processing stages for one job."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        engine = build_engine(self._settings)
        session_factory = build_session_factory(engine)

        self._job_repo = SQLAlchemyJobRepository(session_factory)
        self._knowledge_repo = SQLAlchemyKnowledgeRepository(session_factory)
        self._downloader = YouTubeDownloader(
            yt_dlp_binary=self._settings.yt_dlp_bin,
            max_duration_seconds=self._settings.max_video_duration,
        )
        self._frame_extractor = FrameExtractor(
            ffmpeg_binary=self._settings.ffmpeg_bin,
            command_runner=CommandRunner(),
            interval_seconds=2,
        )
        self._ocr = PaddleOCREngine(
            language=self._settings.ocr_language,
            use_gpu=self._settings.ocr_use_gpu,
            batch_size=self._settings.ocr_batch_size,
            min_confidence=self._settings.ocr_min_confidence,
        )
        self._text_cleaner = TextCleaner()
        self._ai = OpenRouterClient(self._settings)

    def run(self, job_id: UUID) -> None:
        """Execute full processing lifecycle for one job identifier."""
        job = self._job_repo.get(job_id)
        if job is None:
            raise YTCLFRError(f"Job not found: {job_id}")

        job.status = JobStatus.RUNNING
        job.updated_at = utc_now()
        self._job_repo.update(job)

        try:
            job_dir = Path(self._settings.working_directory) / str(job_id)
            video_result = self._downloader.download(job.video_url, job_dir / "video")
            frame_result = self._frame_extractor.extract_frames(
                video_path=video_result.video_path,
                output_dir=job_dir / "frames",
            )
            ocr_lines = self._ocr.extract_from_frames(
                [
                    OCRFrameInput(
                        image_path=frame.image_path,
                        timestamp_seconds=frame.timestamp_seconds,
                    )
                    for frame in frame_result.frames
                ]
            )
            ocr_text = "\n".join(line.text for line in ocr_lines if line.text.strip())
            cleaned_text = self._text_cleaner.clean_text(ocr_text).cleaned_text
            parsed = asyncio.run(self._ai.parse_ocr_text(cleaned_text))
            knowledge_items = self._build_knowledge_items(parsed)
            self._knowledge_repo.save_items(job_id, knowledge_items)
            job.status = JobStatus.COMPLETED
            job.error_message = None
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            raise
        finally:
            job.updated_at = utc_now()
            self._job_repo.update(job)

    def _build_knowledge_items(self, parsed: dict) -> list[KnowledgeItem]:
        """Map AI output dictionary to domain entities."""
        summary = str(parsed.get("summary", "")).strip()
        points = [str(point).strip() for point in parsed.get("points", []) if str(point).strip()]
        entities = [
            str(entity).strip() for entity in parsed.get("entities", []) if str(entity).strip()
        ]
        if not summary and not points:
            return []
        return [
            KnowledgeItem(
                title="Video Summary",
                description=summary or "\n".join(points),
                tags=entities,
            )
        ]
