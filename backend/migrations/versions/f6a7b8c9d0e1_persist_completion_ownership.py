"""Persist recoverable completion and deferred requeue ownership.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("merge_requests")}
    for name in ("pending_completion", "requeue_request", "ignored_label_events"):
        if name not in columns:
            op.add_column("merge_requests", sa.Column(name, sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("merge_requests", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.drop_column("ignored_label_events")
        batch.drop_column("requeue_request")
        batch.drop_column("pending_completion")
