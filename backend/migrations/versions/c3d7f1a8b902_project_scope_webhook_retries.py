"""Add project scope to webhook retry tables and backfill legacy data.

Revision ID: c3d7f1a8b902
Revises: f1a2b3c4d5e6
Create Date: 2026-09-24
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c3d7f1a8b902"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    return column in {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def _has_index(table: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspect(op.get_bind()).get_indexes(table))


def _add_project_scope(table: str, index_name: str, indexed_column: str) -> None:
    if not _table_exists(table):
        return

    if not _has_column(table, "project_id"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=False, server_default="0"))

    if not _has_index(table, index_name):
        op.create_index(index_name, table, ["project_id", indexed_column], unique=False)


def _ensure_webhook_tables() -> None:
    """Reconcile retry tables missing from partial pre-Alembic databases."""
    if not _table_exists("webhook_retry_queue"):
        op.create_table(
            "webhook_retry_queue",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("event_type", sa.Text(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("next_attempt_at", sa.Text(), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Text(), nullable=True, server_default="CURRENT_TIMESTAMP"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_retry_next_attempt", "webhook_retry_queue", ["next_attempt_at"])
        op.create_index("idx_retry_event_type", "webhook_retry_queue", ["event_type"])

    if not _table_exists("webhook_dlq"):
        op.create_table(
            "webhook_dlq",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("event_type", sa.Text(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=False),
            sa.Column("original_created_at", sa.Text(), nullable=False),
            sa.Column("moved_to_dlq_at", sa.Text(), nullable=True, server_default="CURRENT_TIMESTAMP"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_dlq_moved_at", "webhook_dlq", ["moved_to_dlq_at"])
        op.create_index("idx_dlq_event_type", "webhook_dlq", ["event_type"])


def _positive_project_id(raw_project_id: object) -> int | None:
    try:
        project_id = int(raw_project_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return project_id if project_id > 0 else None


def _has_unassigned_rows() -> bool:
    bind = op.get_bind()
    for table in (
        "merge_requests",
        "merge_requests_history",
        "analytics_hourly",
        "analytics_daily",
        "webhook_retry_queue",
        "webhook_dlq",
    ):
        if not _table_exists(table) or not _has_column(table, "project_id"):
            continue
        if bind.execute(text(f"SELECT 1 FROM {table} WHERE project_id = 0 LIMIT 1")).first():
            return True
    return False


def _legacy_project_id() -> int | None:
    """Resolve the owner of pre-project-scope rows without guessing."""
    legacy_project_id = _positive_project_id(os.getenv("GITLAB_QUEUE_GITLAB_PROJECT_ID"))
    projects_json = (os.getenv("GITLAB_QUEUE_PROJECTS") or "").strip()
    if not projects_json:
        if legacy_project_id is None and _has_unassigned_rows():
            raise RuntimeError(
                "Cannot migrate legacy project_id=0 rows without a valid project owner. "
                "Set GITLAB_QUEUE_GITLAB_PROJECT_ID to the former single project ID."
            )
        return legacy_project_id

    try:
        configured_projects = json.loads(projects_json)
        configured_ids = {
            project_id
            for project in configured_projects
            if isinstance(project, dict) and (project_id := _positive_project_id(project.get("project_id"))) is not None
        }
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Cannot migrate legacy rows: GITLAB_QUEUE_PROJECTS is invalid JSON") from error

    if legacy_project_id is not None and legacy_project_id in configured_ids:
        return legacy_project_id
    if _has_unassigned_rows():
        raise RuntimeError(
            "Cannot assign legacy project_id=0 rows when GITLAB_QUEUE_PROJECTS is set. "
            "Temporarily set GITLAB_QUEUE_GITLAB_PROJECT_ID to the former single project ID "
            "and ensure that project is present in GITLAB_QUEUE_PROJECTS."
        )
    return None


def _backfill_legacy_project() -> None:
    """Map sentinel rows to their explicitly or unambiguously identified owner."""
    project_id = _legacy_project_id()
    if project_id is None:
        return

    bind = op.get_bind()
    # Preserve rows if the destination already has the same project-scoped key.
    # This avoids uniqueness failures and avoids choosing between conflicting records.
    keyed_tables = (
        ("merge_requests", "iid"),
        ("merge_requests_history", "iid"),
        ("analytics_hourly", "timestamp"),
        ("analytics_daily", "date"),
        ("webhook_retry_queue", "id"),
        ("webhook_dlq", "id"),
    )
    for table, key_column in keyed_tables:
        if not _table_exists(table) or not _has_column(table, "project_id"):
            continue
        bind.execute(
            text(
                f"""UPDATE {table}
                    SET project_id = :project_id
                    WHERE project_id = 0
                      AND NOT EXISTS (
                          SELECT 1 FROM {table} AS destination
                          WHERE destination.project_id = :project_id
                            AND destination.{key_column} = {table}.{key_column}
                      )"""
            ),
            {"project_id": project_id},
        )

    if _has_unassigned_rows():
        raise RuntimeError(
            "Legacy project_id=0 rows conflict with existing data for the selected project. "
            "Resolve the duplicate project-scoped keys before restarting the migration."
        )


def upgrade() -> None:
    _ensure_webhook_tables()
    _add_project_scope("webhook_retry_queue", "idx_retry_project_next_attempt", "next_attempt_at")
    _add_project_scope("webhook_retry_queue", "idx_retry_project_event_type", "event_type")
    _add_project_scope("webhook_dlq", "idx_dlq_project_moved_at", "moved_to_dlq_at")
    _add_project_scope("webhook_dlq", "idx_dlq_project_event_type", "event_type")
    _backfill_legacy_project()


def downgrade() -> None:
    for table, index_name in (
        ("webhook_dlq", "idx_dlq_project_event_type"),
        ("webhook_dlq", "idx_dlq_project_moved_at"),
        ("webhook_retry_queue", "idx_retry_project_event_type"),
        ("webhook_retry_queue", "idx_retry_project_next_attempt"),
    ):
        if _table_exists(table) and _has_index(table, index_name):
            op.drop_index(index_name, table_name=table)

    for table in ("webhook_dlq", "webhook_retry_queue"):
        if _table_exists(table) and _has_column(table, "project_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("project_id")
