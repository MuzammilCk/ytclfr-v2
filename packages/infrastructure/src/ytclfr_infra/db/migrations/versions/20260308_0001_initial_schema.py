"""Create initial YTCLFR PostgreSQL schema.

Revision ID: 20260308_0001
Revises: None
Create Date: 2026-03-08 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260308_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema for users, videos, frames, OCR, parsed content, playlists, and jobs."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)

    op.create_table(
        "playlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("spotify_playlist_id", sa.String(length=128), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_playlists_user_name"),
    )
    op.create_index("ix_playlists_user_id_created_at", "playlists", ["user_id", "created_at"], unique=False)
    op.create_index("ix_playlists_spotify_playlist_id", "playlists", ["spotify_playlist_id"], unique=False)

    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("playlist_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("youtube_video_id", sa.String(length=32), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("storage_path", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("youtube_video_id", name="uq_videos_youtube_video_id"),
    )
    op.create_index("ix_videos_user_id_created_at", "videos", ["user_id", "created_at"], unique=False)
    op.create_index("ix_videos_playlist_id", "videos", ["playlist_id"], unique=False)
    op.create_index("ix_videos_status", "videos", ["status"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("video_url", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)
    op.create_index("ix_jobs_user_id_created_at", "jobs", ["user_id", "created_at"], unique=False)
    op.create_index("ix_jobs_video_id", "jobs", ["video_id"], unique=False)

    op.create_table(
        "frames",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("timestamp_seconds", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("image_path", sa.String(length=2048), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("frame_index >= 0", name="ck_frames_frame_index_non_negative"),
        sa.CheckConstraint("timestamp_seconds >= 0", name="ck_frames_timestamp_non_negative"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id", "frame_index", name="uq_frames_video_id_frame_index"),
    )
    op.create_index(
        "ix_frames_video_id_timestamp_seconds",
        "frames",
        ["video_id", "timestamp_seconds"],
        unique=False,
    )

    op.create_table(
        "ocr_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("language", sa.String(length=16), server_default=sa.text("'en'"), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_ocr_results_confidence_range"),
        sa.ForeignKeyConstraint(["frame_id"], ["frames.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_results_frame_id", "ocr_results", ["frame_id"], unique=False)
    op.create_index("ix_ocr_results_job_id", "ocr_results", ["job_id"], unique=False)

    op.create_table(
        "parsed_content",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_type", sa.String(length=64), server_default=sa.text("'SUMMARY'"), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parsed_content_job_id", "parsed_content", ["job_id"], unique=False)
    op.create_index("ix_parsed_content_video_id", "parsed_content", ["video_id"], unique=False)
    op.create_index("ix_parsed_content_content_type", "parsed_content", ["content_type"], unique=False)


def downgrade() -> None:
    """Rollback initial YTCLFR schema."""
    op.drop_index("ix_parsed_content_content_type", table_name="parsed_content")
    op.drop_index("ix_parsed_content_video_id", table_name="parsed_content")
    op.drop_index("ix_parsed_content_job_id", table_name="parsed_content")
    op.drop_table("parsed_content")

    op.drop_index("ix_ocr_results_job_id", table_name="ocr_results")
    op.drop_index("ix_ocr_results_frame_id", table_name="ocr_results")
    op.drop_table("ocr_results")

    op.drop_index("ix_frames_video_id_timestamp_seconds", table_name="frames")
    op.drop_table("frames")

    op.drop_index("ix_jobs_video_id", table_name="jobs")
    op.drop_index("ix_jobs_user_id_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_videos_status", table_name="videos")
    op.drop_index("ix_videos_playlist_id", table_name="videos")
    op.drop_index("ix_videos_user_id_created_at", table_name="videos")
    op.drop_table("videos")

    op.drop_index("ix_playlists_spotify_playlist_id", table_name="playlists")
    op.drop_index("ix_playlists_user_id_created_at", table_name="playlists")
    op.drop_table("playlists")

    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_table("users")
