"""add_retried_jobs_column

Revision ID: c754365eda26
Revises: d61e3097360d
Create Date: 2026-02-28 10:00:00.000000

Add retried_jobs column to merge_requests table to persist per-job retry
counts across processor restarts. Enables job-level retry instead of
full pipeline retry via rebase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c754365eda26"
down_revision: str | None = "d61e3097360d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("merge_requests")]

    if "retried_jobs" not in columns:
        with op.batch_alter_table("merge_requests", schema=None) as batch_op:
            batch_op.add_column(sa.Column("retried_jobs", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    """Revert migration changes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("merge_requests")]

    if "retried_jobs" in columns:
        with op.batch_alter_table("merge_requests", schema=None) as batch_op:
            batch_op.drop_column("retried_jobs")
