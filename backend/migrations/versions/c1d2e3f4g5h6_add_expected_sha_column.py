"""add_expected_sha_column

Revision ID: c1d2e3f4g5h6
Revises: b8c5a3f12e47
Create Date: 2025-01-30 12:00:00.000000

Add expected_sha column to merge_requests table to track the expected
commit SHA after rebase for proper pipeline validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4g5h6"
down_revision: str | None = "b8c5a3f12e47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    # Add expected_sha column to merge_requests table
    with op.batch_alter_table("merge_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("expected_sha", sa.Text(), nullable=True))


def downgrade() -> None:
    """Revert migration changes."""
    with op.batch_alter_table("merge_requests", schema=None) as batch_op:
        batch_op.drop_column("expected_sha")
