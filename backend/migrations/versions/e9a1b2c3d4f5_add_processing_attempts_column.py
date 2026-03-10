"""add_processing_attempts_column

Revision ID: e9a1b2c3d4f5
Revises: c754365eda26
Create Date: 2026-03-10 12:00:00.000000

Add processing_attempts column to merge_requests table to track how many
times an MR has been retried after transient errors. Enables permanent
failure after exceeding max_processing_attempts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e9a1b2c3d4f5"
down_revision: str | None = "c754365eda26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("merge_requests")]

    if "processing_attempts" not in columns:
        with op.batch_alter_table("merge_requests", schema=None) as batch_op:
            batch_op.add_column(sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    """Revert migration changes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("merge_requests")]

    if "processing_attempts" in columns:
        with op.batch_alter_table("merge_requests", schema=None) as batch_op:
            batch_op.drop_column("processing_attempts")
