"""Backfill missing job lifecycle columns for legacy schemas.

Revision ID: 20260311_0002
Revises: 20260308_0001
Create Date: 2026-03-11 00:02:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260311_0002"
down_revision: Union[str, None] = "20260308_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ensure lifecycle columns exist on jobs table.

    This migration is intentionally idempotent. It protects environments that were
    bootstrapped before strict Alembic-only schema management and may be missing
    lifecycle columns used by the worker.
    """
    op.execute(
        "ALTER TABLE jobs "
        "ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE NULL"
    )
    op.execute(
        "ALTER TABLE jobs "
        "ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE NULL"
    )
    op.execute(
        "ALTER TABLE jobs "
        "ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0"
    )
    op.execute("UPDATE jobs SET attempts = 0 WHERE attempts IS NULL")
    op.execute("ALTER TABLE jobs ALTER COLUMN attempts SET DEFAULT 0")
    op.execute("ALTER TABLE jobs ALTER COLUMN attempts SET NOT NULL")


def downgrade() -> None:
    """No-op downgrade.

    The initial baseline migration already defines these columns. Dropping them on
    downgrade could remove baseline schema fields and break historical revisions.
    """
    return
