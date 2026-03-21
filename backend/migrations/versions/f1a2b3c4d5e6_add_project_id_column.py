"""add_project_id_column

Revision ID: f1a2b3c4d5e6
Revises: e9a1b2c3d4f5
Create Date: 2026-03-21 12:00:00.000000

Add project_id column to all tables to support multi-project deployments.
Changes UNIQUE(iid) to UNIQUE(project_id, iid) for project-scoped MR identity.
Backfills existing rows with project_id=0 (updated by application on first run).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e9a1b2c3d4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Naming convention for resolving unnamed constraints in SQLite batch mode.
# PostgreSQL auto-names constraints (e.g. 'table_col_key'), but SQLite leaves
# them unnamed. This convention lets Alembic batch mode find and drop them.
_NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s",
}


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    columns = [col["name"] for col in inspector.get_columns(table)]
    return column in columns


def _table_exists(inspector: sa.Inspector, table: str) -> bool:
    """Check if a table exists."""
    return table in inspector.get_table_names()


def _find_unique_constraint_name(inspector: sa.Inspector, table: str, columns: list[str]) -> str | None:
    """Find the name of a unique constraint on the given columns.

    PostgreSQL returns real names (e.g. 'merge_requests_iid_key').
    SQLite returns None for unnamed constraints.
    """
    for constraint in inspector.get_unique_constraints(table):
        if constraint["column_names"] == columns:
            return constraint.get("name")
    return None


def _drop_unique_and_replace(
    batch_op: sa.Any,
    inspector: sa.Inspector,
    table: str,
    old_columns: list[str],
    new_constraint_name: str,
    new_columns: list[str],
) -> None:
    """Drop old unique constraint and create a new composite one.

    Uses inspector to find the actual constraint name (PostgreSQL),
    falls back to naming_convention-generated name (SQLite batch mode).
    """
    real_name = _find_unique_constraint_name(inspector, table, old_columns)
    # real_name is set for PostgreSQL; for SQLite it's None but naming_convention
    # (passed to batch_alter_table) lets Alembic resolve it by column pattern.
    drop_name = real_name or f"uq_{table}_{old_columns[0]}"
    batch_op.drop_constraint(drop_name, type_="unique")
    batch_op.create_unique_constraint(new_constraint_name, new_columns)


def upgrade() -> None:
    """Apply migration changes."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # --- merge_requests ---
    if _table_exists(inspector, "merge_requests") and not _has_column(inspector, "merge_requests", "project_id"):
        with op.batch_alter_table("merge_requests", schema=None, naming_convention=_NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=False, server_default="0"))
            _drop_unique_and_replace(
                batch_op, inspector, "merge_requests", ["iid"], "uq_mr_project_iid", ["project_id", "iid"]
            )
            batch_op.create_index("idx_mr_project_id", ["project_id"])

    # --- merge_requests_history ---
    if _table_exists(inspector, "merge_requests_history") and not _has_column(
        inspector, "merge_requests_history", "project_id"
    ):
        with op.batch_alter_table("merge_requests_history", schema=None) as batch_op:
            batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=False, server_default="0"))
            # idx_history_iid_unique is a named unique index (created in migration b8c5a3f12e47)
            batch_op.drop_index("idx_history_iid_unique")
            batch_op.create_unique_constraint("uq_history_project_iid", ["project_id", "iid"])
            batch_op.create_index("idx_history_project_id", ["project_id"])

    # --- analytics_hourly ---
    if _table_exists(inspector, "analytics_hourly") and not _has_column(inspector, "analytics_hourly", "project_id"):
        with op.batch_alter_table("analytics_hourly", schema=None) as batch_op:
            batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=False, server_default="0"))
            batch_op.create_unique_constraint("uq_hourly_project_timestamp", ["project_id", "timestamp"])
            batch_op.create_index("idx_hourly_project_id", ["project_id"])

    # --- analytics_daily ---
    if _table_exists(inspector, "analytics_daily") and not _has_column(inspector, "analytics_daily", "project_id"):
        with op.batch_alter_table("analytics_daily", schema=None, naming_convention=_NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=False, server_default="0"))
            _drop_unique_and_replace(
                batch_op, inspector, "analytics_daily", ["date"], "uq_daily_project_date", ["project_id", "date"]
            )
            batch_op.create_index("idx_daily_project_id", ["project_id"])


def downgrade() -> None:
    """Revert migration changes."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # --- analytics_daily ---
    if _table_exists(inspector, "analytics_daily") and _has_column(inspector, "analytics_daily", "project_id"):
        with op.batch_alter_table("analytics_daily", schema=None) as batch_op:
            batch_op.drop_index("idx_daily_project_id")
            batch_op.drop_constraint("uq_daily_project_date", type_="unique")
            batch_op.create_unique_constraint("analytics_daily_date_key", ["date"])
            batch_op.drop_column("project_id")

    # --- analytics_hourly ---
    if _table_exists(inspector, "analytics_hourly") and _has_column(inspector, "analytics_hourly", "project_id"):
        with op.batch_alter_table("analytics_hourly", schema=None) as batch_op:
            batch_op.drop_index("idx_hourly_project_id")
            batch_op.drop_constraint("uq_hourly_project_timestamp", type_="unique")
            batch_op.drop_column("project_id")

    # --- merge_requests_history ---
    if _table_exists(inspector, "merge_requests_history") and _has_column(
        inspector, "merge_requests_history", "project_id"
    ):
        with op.batch_alter_table("merge_requests_history", schema=None) as batch_op:
            batch_op.drop_index("idx_history_project_id")
            batch_op.drop_constraint("uq_history_project_iid", type_="unique")
            batch_op.create_index("idx_history_iid_unique", ["iid"], unique=True)
            batch_op.drop_column("project_id")

    # --- merge_requests ---
    if _table_exists(inspector, "merge_requests") and _has_column(inspector, "merge_requests", "project_id"):
        with op.batch_alter_table("merge_requests", schema=None) as batch_op:
            batch_op.drop_index("idx_mr_project_id")
            batch_op.drop_constraint("uq_mr_project_iid", type_="unique")
            batch_op.create_unique_constraint("merge_requests_iid_key", ["iid"])
            batch_op.drop_column("project_id")
