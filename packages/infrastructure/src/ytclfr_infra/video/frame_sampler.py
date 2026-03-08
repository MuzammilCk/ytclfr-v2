"""Helpers for selecting frame subsets for downstream OCR."""

from pathlib import Path


def sample_frames(frame_paths: list[Path], max_frames: int) -> list[Path]:
    """Return at most ``max_frames`` from ordered frame paths."""
    if max_frames <= 0:
        return []
    return frame_paths[:max_frames]
