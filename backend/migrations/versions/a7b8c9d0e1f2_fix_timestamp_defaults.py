"""Repair literal timestamp defaults while preserving SQLite identity high-water marks.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULTS = (
    ("merge_requests", "created_at"),
    ("merge_requests_history", "created_at"),
    ("webhook_retry_queue", "created_at"),
    ("webhook_dlq", "moved_to_dlq_at"),
)


def _sequence_high_water() -> dict[str, int]:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite" or not sa.inspect(bind).has_table("sqlite_sequence"):
        return {}
    return {row[0]: row[1] for row in bind.execute(sa.text("SELECT name, seq FROM sqlite_sequence"))}


def _alter_defaults(*, executable: bool) -> None:
    bind = op.get_bind()
    high_water = _sequence_high_water()
    default = sa.text("CURRENT_TIMESTAMP") if executable else "CURRENT_TIMESTAMP"
    for table, column in _DEFAULTS:
        with op.batch_alter_table(table, table_kwargs={"sqlite_autoincrement": True}) as batch:
            batch.alter_column(column, existing_type=sa.Text(), server_default=default, existing_nullable=True)
            if table == "webhook_dlq":
                batch.alter_column(
                    "original_created_at",
                    existing_type=sa.Text(),
                    nullable=executable,
                    existing_nullable=not executable,
                )
    if bind.dialect.name == "sqlite":
        for table, _ in _DEFAULTS:
            previous = high_water.get(table, 0)
            bind.execute(
                sa.text(
                    "INSERT INTO sqlite_sequence(name, seq) SELECT :name, :previous "
                    "WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = :name)"
                ),
                {"name": table, "previous": previous},
            )
            bind.execute(
                sa.text("UPDATE sqlite_sequence SET seq = MAX(seq, :previous) WHERE name = :name"),
                {"name": table, "previous": previous},
            )


def upgrade() -> None:
    # The original time of a literal is unknowable. Retain these rows as recent
    # rather than expiring them using an invented historical age. Valid dates
    # (including offsets) and optional creation NULLs are left untouched.
    repaired_at = datetime.now(UTC).isoformat()
    for table, column in (*_DEFAULTS, ("webhook_dlq", "original_created_at")):
        op.get_bind().execute(
            sa.text(f"UPDATE {table} SET {column} = :repaired WHERE {column} = 'CURRENT_TIMESTAMP'"),
            {"repaired": repaired_at},
        )
    op.get_bind().execute(
        sa.text("UPDATE webhook_dlq SET moved_to_dlq_at = :repaired WHERE moved_to_dlq_at IS NULL"),
        {"repaired": repaired_at},
    )
    _alter_defaults(executable=True)


def downgrade() -> None:
    # The old schema cannot represent unknown receipt dates. Refuse before any
    # schema changes rather than inventing provenance or discarding events.
    unknown = (
        op.get_bind()
        .execute(sa.text("SELECT COUNT(*) FROM webhook_dlq WHERE original_created_at IS NULL"))
        .scalar_one()
    )
    if unknown:
        raise RuntimeError(
            "Cannot downgrade DLQ with unknown original dates; explicitly requeue or delete these entries first."
        )
    # Reverses defaults; a repaired unknown historical date cannot be recovered.
    _alter_defaults(executable=False)
