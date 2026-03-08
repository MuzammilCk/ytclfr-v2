"""Unit tests for OCR persistence helper behavior."""

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from ytclfr_infra.ocr.ocr_engine import OCRLine
from ytclfr_worker.tasks import task_support


class _FakeQuery:
    """Chainable fake SQLAlchemy query object."""

    def __init__(self, session: "_FakeSession") -> None:
        self._session = session

    def filter(self, *args: object, **kwargs: object) -> "_FakeQuery":
        _ = (args, kwargs)
        return self

    def delete(self) -> None:
        self._session.deleted = True


class _FakeSession:
    """Minimal session stub for testing persistence logic."""

    def __init__(self) -> None:
        self.deleted = False
        self.added: list[object] = []

    def query(self, model: object) -> _FakeQuery:
        _ = model
        return _FakeQuery(self)

    def add(self, model_instance: object) -> None:
        self.added.append(model_instance)


def test_persist_ocr_results_filters_low_confidence(monkeypatch) -> None:
    """Only high-confidence OCR lines should be persisted and merged."""
    fake_session = _FakeSession()

    @contextmanager
    def fake_session_scope(_factory: object):
        yield fake_session

    monkeypatch.setattr(task_support, "get_session_factory", lambda: object())
    monkeypatch.setattr(task_support, "session_scope", fake_session_scope)

    frame_id = uuid4()
    job_id = uuid4()
    frame_path = Path("storage/job/frames/frame_0001.jpg")
    lines = [
        OCRLine(
            timestamp_seconds=2.0,
            text="KEEP_ME",
            confidence=0.91,
            source_image=frame_path,
        ),
        OCRLine(
            timestamp_seconds=4.0,
            text="DROP_ME",
            confidence=0.22,
            source_image=frame_path,
        ),
    ]

    merged_text = task_support.persist_ocr_results(
        job_id=job_id,
        frame_refs=[
            {
                "frame_id": str(frame_id),
                "image_path": str(frame_path),
                "timestamp_seconds": 2.0,
                "source_type": "interval_2s",
            }
        ],
        ocr_lines=lines,
        min_confidence=0.5,
    )

    assert fake_session.deleted is True
    assert merged_text == "KEEP_ME"
    assert len(fake_session.added) == 1
    persisted = fake_session.added[0]
    assert getattr(persisted, "job_id") == job_id
    assert getattr(persisted, "frame_id") == frame_id
    assert getattr(persisted, "text") == "KEEP_ME"
    assert float(getattr(persisted, "confidence")) == 0.91
    payload = getattr(persisted, "raw_payload")
    assert payload["source_image"] == str(frame_path)
    assert payload["timestamp_seconds"] == 2.0

