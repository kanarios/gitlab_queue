"""add_unique_iid_history

Revision ID: b8c5a3f12e47
Revises: a312c27ba5f7
Create Date: 2025-01-29 12:00:00.000000

Add unique constraint on iid in merge_requests_history table
to prevent duplicate history records from race conditions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b8c5a3f12e47"
down_revision: str | None = "a312c27ba5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    # Add unique index on iid to prevent duplicate history records
    # from race conditions between webhook handler and processor
    with op.batch_alter_table("merge_requests_history", schema=None) as batch_op:
        batch_op.create_index("idx_history_iid_unique", ["iid"], unique=True)


def downgrade() -> None:
    """Revert migration changes."""
    with op.batch_alter_table("merge_requests_history", schema=None) as batch_op:
        batch_op.drop_index("idx_history_iid_unique")
