"""Repository-style protocol for publishing job lifecycle events.

Keeping the event publishing contract in the domain layer allows the
application service (JobLifecycleService) to depend on this abstraction
rather than on the concrete Redis implementation.
"""

from typing import Protocol
from uuid import UUID


class EventPublisher(Protocol):
    """Contract for broadcasting job status change notifications.

    Implementations may use Redis pub/sub, an in-process event bus,
    or a no-op stub for tests.
    """

    def publish_job_event(
        self,
        *,
        job_id: UUID,
        status: str,
        video_id: UUID | None,
        error_message: str | None,
    ) -> None:
        """Publish a job status change event to all registered subscribers.

        Args:
            job_id: Identifier of the job whose status changed.
            status: New job status string (e.g. "RUNNING", "COMPLETED").
            video_id: Associated video identifier, if available.
            error_message: Error detail for FAILED transitions, otherwise None.
        """
