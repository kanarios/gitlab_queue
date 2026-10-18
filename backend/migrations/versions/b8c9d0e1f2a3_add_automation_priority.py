"""Materialize active automation classification without changing historical outcomes.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns("merge_requests")}
    existing = columns.get("is_automated")
    if existing is not None:
        default = str(existing.get("default", "")).strip("()'\" ")
        if not isinstance(existing["type"], sa.Integer) or existing["nullable"] or default != "0":
            raise RuntimeError("Existing is_automated column does not match the canonical active schema")
        return
    op.add_column(
        "merge_requests", sa.Column("is_automated", sa.Integer(), nullable=False, server_default=sa.text("0"))
    )


def downgrade() -> None:
    # Native DROP COLUMN preserves the table's identity and SQLite AUTOINCREMENT high-water.
    op.drop_column("merge_requests", "is_automated")
