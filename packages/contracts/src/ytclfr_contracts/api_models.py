"""HTTP request and response models."""

from datetime import datetime
import re
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{11}$")


class SubmitJobRequest(BaseModel):
    """Request payload for submitting a video processing job."""

    video_url: HttpUrl


class SubmitJobResponse(BaseModel):
    """Response payload returned after job submission."""

    job_id: UUID
    status: str


class JobStatusResponse(BaseModel):
    """Response payload for job status lookups."""

    job_id: UUID
    video_id: UUID | None = None
    status: str
    error_message: str | None = None
    updated_at: datetime


class KnowledgeResponse(BaseModel):
    """Response payload for parsed knowledge data."""

    job_id: UUID
    items: list[dict]


class ProcessVideoRequest(BaseModel):
    """Request payload for starting video processing from a YouTube URL."""

    youtube_url: str = Field(min_length=1, max_length=2048)

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, value: str) -> str:
        """Validate that URL is a supported YouTube video URL."""
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("youtube_url must use http or https.")

        host = (parsed.hostname or "").lower()
        allowed_hosts = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
        if host not in allowed_hosts:
            raise ValueError("youtube_url must be from youtube.com or youtu.be.")

        if host == "youtu.be":
            video_id = parsed.path.strip("/")
            if not video_id:
                raise ValueError("youtube_url short format must include a video id.")
            if not _YOUTUBE_ID_RE.match(video_id):
                raise ValueError("youtube_url must include a valid 11-character video ID.")
            return value

        if parsed.path.startswith("/shorts/"):
            video_id = parsed.path.removeprefix("/shorts/").strip("/")
            if not video_id:
                raise ValueError("youtube_url shorts format must include a video id.")
            if not _YOUTUBE_ID_RE.match(video_id):
                raise ValueError("youtube_url must include a valid 11-character video ID.")
            return value

        if parsed.path != "/watch":
            raise ValueError("youtube_url must be a valid watch or shorts URL.")

        query = parse_qs(parsed.query)
        video_id = query.get("v", [""])[0].strip()
        if not video_id:
            raise ValueError("youtube_url watch format must include v query parameter.")
        if not _YOUTUBE_ID_RE.match(video_id):
            raise ValueError("youtube_url v parameter must be a valid 11-character video ID.")
        return value


class ProcessVideoResponse(BaseModel):
    """Response payload returned after process-video submission."""

    job_id: UUID


class ResultItem(BaseModel):
    """One parsed result item returned by result endpoint."""

    title: str
    description: str
    tags: list[str]
    action_output: dict[str, object] | None = None


class VideoResultResponse(BaseModel):
    """Response payload for parsed content by video identifier."""

    video_id: UUID
    items: list[ResultItem]
