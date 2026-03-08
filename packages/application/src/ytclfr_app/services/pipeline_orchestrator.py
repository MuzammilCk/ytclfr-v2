"""Application service that dispatches background processing workflows."""

from typing import Protocol
from uuid import UUID

from ytclfr_core.errors.exceptions import YTCLFRError


class PipelineDispatcher(Protocol):
    """Abstraction for scheduling pipeline jobs to background infrastructure."""

    def enqueue_pipeline(self, job_id: UUID) -> None:
        """Enqueue the full processing pipeline for a job."""


class PipelineOrchestrator:
    """Coordinates dispatch of long-running workflows."""

    def __init__(self, dispatcher: PipelineDispatcher) -> None:
        self._dispatcher = dispatcher

    def dispatch(self, job_id: UUID) -> None:
        """Dispatch a job to asynchronous worker execution."""
        try:
            self._dispatcher.enqueue_pipeline(job_id)
        except Exception as exc:
            raise YTCLFRError("Failed to dispatch pipeline job.") from exc
