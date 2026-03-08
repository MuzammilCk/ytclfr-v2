"""Task package exports to ensure Celery task registration."""

from ytclfr_worker.tasks.ai_tasks import parse_text
from ytclfr_worker.tasks.ocr_tasks import run_ocr
from ytclfr_worker.tasks.output_tasks import generate_output
from ytclfr_worker.tasks.pipeline_tasks import run_pipeline
from ytclfr_worker.tasks.video_tasks import download_video, extract_frames

__all__ = [
    "run_pipeline",
    "download_video",
    "extract_frames",
    "run_ocr",
    "parse_text",
    "generate_output",
]
