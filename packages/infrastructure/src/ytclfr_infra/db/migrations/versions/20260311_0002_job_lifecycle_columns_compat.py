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
    import sqlalchemy as sa

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing = {c["name"] for c in inspector.get_columns("jobs")}

    if "started_at" not in existing:
        op.add_column("jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    if "completed_at" not in existing:
        op.add_column("jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    if "attempts" not in existing:
        op.add_column("jobs", sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False))


def downgrade() -> None:
    """No-op downgrade.

    The initial baseline migration already defines these columns. Dropping them on
    downgrade could remove baseline schema fields and break historical revisions.
    """
    return
