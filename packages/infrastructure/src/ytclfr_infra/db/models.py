"""Canonical SQLAlchemy ORM models for YTCLFR."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ytclfr_infra.db.database import Base


class UUIDPrimaryKeyMixin:
    """Reusable UUID primary key column."""

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)


class TimestampMixin:
    """Reusable timestamp columns for creation and update events."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Application user entity."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_created_at", "created_at"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("true")
    )


class PlaylistModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-managed playlist entity."""

    __tablename__ = "playlists"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_playlists_user_name"),
        Index("ix_playlists_user_id_created_at", "user_id", "created_at"),
        Index("ix_playlists_spotify_playlist_id", "spotify_playlist_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    spotify_playlist_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )


class VideoModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Video metadata entity."""

    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("youtube_video_id", name="uq_videos_youtube_video_id"),
        Index("ix_videos_user_id_created_at", "user_id", "created_at"),
        Index("ix_videos_playlist_id", "playlist_id"),
        Index("ix_videos_status", "status"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    playlist_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("playlists.id", ondelete="SET NULL"),
        nullable=True,
    )
    youtube_video_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sql_text("0")
    )
    storage_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=sql_text("'PENDING'")
    )


class JobModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Processing job entity."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_user_id_created_at", "user_id", "created_at"),
        Index("ix_jobs_video_id", "video_id"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    video_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="SET NULL"),
        nullable=True,
    )
    video_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=sql_text("'PENDING'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("5"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FrameModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Extracted frame entity."""

    __tablename__ = "frames"
    __table_args__ = (
        UniqueConstraint("video_id", "frame_index", name="uq_frames_video_id_frame_index"),
        CheckConstraint("frame_index >= 0", name="ck_frames_frame_index_non_negative"),
        CheckConstraint("timestamp_seconds >= 0", name="ck_frames_timestamp_non_negative"),
        Index("ix_frames_video_id_timestamp_seconds", "video_id", "timestamp_seconds"),
    )

    video_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    image_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OCRResultModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """OCR text output for a frame."""

    __tablename__ = "ocr_results"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_ocr_results_confidence_range"),
        Index("ix_ocr_results_frame_id", "frame_id"),
        Index("ix_ocr_results_job_id", "job_id"),
    )

    frame_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("frames.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    language: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sql_text("'en'")
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ParsedContentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """AI-parsed structured content entity."""

    __tablename__ = "parsed_content"
    __table_args__ = (
        Index("ix_parsed_content_job_id", "job_id"),
        Index("ix_parsed_content_video_id", "video_id"),
        Index("ix_parsed_content_content_type", "content_type"),
    )

    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    video_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="SET NULL"),
        nullable=True,
    )
    content_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=sql_text("'SUMMARY'"),
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'[]'::jsonb"),
    )
    entities: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'[]'::jsonb"),
    )
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


__all__ = [
    "UserModel",
    "VideoModel",
    "FrameModel",
    "OCRResultModel",
    "ParsedContentModel",
    "PlaylistModel",
    "JobModel",
]
