"""Persist metadata revisions and pending priority notifications.

Revision ID: d4e5f6a7b8c9
Revises: c3d7f1a8b902
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d7f1a8b902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("merge_requests")}
    with op.batch_alter_table("merge_requests") as batch:
        if "metadata_version" not in columns:
            batch.add_column(sa.Column("metadata_version", sa.Integer(), nullable=False, server_default="0"))
        if "pending_notification" not in columns:
            batch.add_column(sa.Column("pending_notification", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("merge_requests") as batch:
        batch.drop_column("pending_notification")
        batch.drop_column("metadata_version")
