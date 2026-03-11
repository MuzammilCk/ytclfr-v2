"""Unit tests for pipeline orchestration task behavior."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from ytclfr_worker.tasks import pipeline_tasks


class _FakeTask:
    """Minimal Celery task stub for invoking bound task functions."""

    def __init__(self) -> None:
        self.request = SimpleNamespace(retries=0)
        self.max_retries = 3


class _FakeAsyncResult:
    """Async result stub carrying a workflow identifier."""

    def __init__(self, workflow_id: str) -> None:
        self.id = workflow_id


class _FakeWorkflow:
    """Workflow stub that records scheduling calls."""

    def __init__(self, workflow_id: str) -> None:
        self._workflow_id = workflow_id
        self.apply_async_called = False

    def apply_async(self) -> _FakeAsyncResult:
        self.apply_async_called = True
        return _FakeAsyncResult(self._workflow_id)


class _RetryDelegated(Exception):
    """Sentinel exception raised by fake retry handler."""


class _FakeLifecycle:
    """Lifecycle service stub for pipeline task tests."""

    def __init__(self, *, fail_on_running: bool = False) -> None:
        self._fail_on_running = fail_on_running
        self.mark_running_calls: list[object] = []
        self.mark_failed_calls: list[tuple[object, str]] = []

    def mark_running(self, job_id: object) -> None:
        self.mark_running_calls.append(job_id)
        if self._fail_on_running:
            raise RuntimeError(f"db unavailable for {job_id}")

    def mark_failed(self, job_id: object, *, error_message: str) -> None:
        self.mark_failed_calls.append((job_id, error_message))


def test_run_pipeline_schedules_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task should mark running and enqueue chained stage workflow."""
    run_pipeline_func = pipeline_tasks.run_pipeline.__wrapped__.__func__
    job_id = str(uuid4())
    observed: dict[str, object] = {}
    workflow = _FakeWorkflow(workflow_id="workflow-123")
    lifecycle = _FakeLifecycle()

    def fake_chain(*signatures: object) -> _FakeWorkflow:
        observed["signature_count"] = len(signatures)
        return workflow

    monkeypatch.setattr(
        pipeline_tasks,
        "get_job_lifecycle_service",
        lambda: lifecycle,
    )
    monkeypatch.setattr(pipeline_tasks, "chain", fake_chain)

    result = run_pipeline_func(_FakeTask(), job_id)

    assert str(lifecycle.mark_running_calls[0]) == job_id
    assert observed["signature_count"] == 5
    assert workflow.apply_async_called is True
    assert result == {"job_id": job_id, "workflow_id": "workflow-123"}


def test_run_pipeline_marks_failed_when_mark_running_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task should mark failed and re-raise when mark_running fails."""
    run_pipeline_func = pipeline_tasks.run_pipeline.__wrapped__.__func__
    job_id = str(uuid4())
    chain_called = {"value": False}
    lifecycle = _FakeLifecycle(fail_on_running=True)

    def fake_chain(*signatures: object) -> _FakeWorkflow:
        _ = signatures
        chain_called["value"] = True
        return _FakeWorkflow("unexpected")

    monkeypatch.setattr(
        pipeline_tasks,
        "get_job_lifecycle_service",
        lambda: lifecycle,
    )
    monkeypatch.setattr(pipeline_tasks, "chain", fake_chain)

    fake_task = _FakeTask()
    with pytest.raises(RuntimeError):
        run_pipeline_func(fake_task, job_id)

    assert len(lifecycle.mark_failed_calls) == 1
    failed_job_id, failed_error = lifecycle.mark_failed_calls[0]
    assert str(failed_job_id) == job_id
    assert "pipeline orchestration failed:" in failed_error
    assert chain_called["value"] is False
