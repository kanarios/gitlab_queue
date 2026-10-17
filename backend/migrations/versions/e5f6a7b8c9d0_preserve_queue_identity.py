"""Prevent SQLite from reusing a completed queue entry's identity.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rebuild_sqlite_queue(*, autoincrement: bool) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "merge_requests", recreate="always", table_kwargs={"sqlite_autoincrement": autoincrement}
        ):
            pass


def upgrade() -> None:
    _rebuild_sqlite_queue(autoincrement=True)


def downgrade() -> None:
    _rebuild_sqlite_queue(autoincrement=False)
