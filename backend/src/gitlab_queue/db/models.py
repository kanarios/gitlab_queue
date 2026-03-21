"""SQLAlchemy ORM models for GitLab Merge Queue Bot.

Defines declarative models for database tables, used by Alembic
for migration generation and optional ORM-based queries.

Note: The application currently uses raw SQL for operations.
These models enable Alembic autogenerate and provide type-safe
ORM access if needed in the future.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class MergeRequestModel(Base):
    """ORM model for the merge_requests table.

    Stores active merge requests in the queue with their processing state.
    Matches the schema in core/queue.py.
    """

    __tablename__ = "merge_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    iid: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    author_username: Mapped[str] = mapped_column(Text, nullable=False)
    author_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued", server_default="queued")
    is_hotfix: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    labels: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_branch: Mapped[str] = mapped_column(Text, nullable=False)
    queued_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipeline_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    stale_warning_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint("project_id", "iid", name="uq_mr_project_iid"),
        Index("idx_mr_project_id", "project_id"),
        Index("idx_mr_status", "status"),
        Index("idx_mr_queued_at", "queued_at"),
        Index("idx_mr_iid", "iid"),
        Index("idx_mr_finished_at", "finished_at"),
    )

    def __repr__(self) -> str:
        return f"<MergeRequest(iid={self.iid}, status={self.status!r})>"


class WebhookRetryModel(Base):
    """ORM model for the webhook_retry_queue table.

    Stores failed webhook events for retry processing.
    Matches the schema in webhooks/retry_manager.py.
    """

    __tablename__ = "webhook_retry_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    next_attempt_at: Mapped[str] = mapped_column(Text, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        Index("idx_retry_next_attempt", "next_attempt_at"),
        Index("idx_retry_event_type", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<WebhookRetry(id={self.id}, event_type={self.event_type!r})>"


class WebhookDLQModel(Base):
    """ORM model for the webhook_dlq (Dead Letter Queue) table.

    Stores webhook events that failed all retry attempts.
    Matches the schema in webhooks/retry_manager.py.
    """

    __tablename__ = "webhook_dlq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_error: Mapped[str] = mapped_column(Text, nullable=False)
    original_created_at: Mapped[str] = mapped_column(Text, nullable=False)
    moved_to_dlq_at: Mapped[str | None] = mapped_column(Text, nullable=True, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        Index("idx_dlq_moved_at", "moved_to_dlq_at"),
        Index("idx_dlq_event_type", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<WebhookDLQ(id={self.id}, event_type={self.event_type!r})>"


class MergeRequestHistoryModel(Base):
    """ORM model for the merge_requests_history table.

    Stores completed merge requests (merged, failed, conflict, timeout, removed).
    Retention: 1 year. Matches ADR-004 schema.
    """

    __tablename__ = "merge_requests_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    iid: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    author_username: Mapped[str] = mapped_column(Text, nullable=False)
    author_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    is_hotfix: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    labels: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_branch: Mapped[str] = mapped_column(Text, nullable=False)
    queued_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str] = mapped_column(Text, nullable=False)
    wait_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipeline_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipeline_failed_jobs: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint("project_id", "iid", name="uq_history_project_iid"),
        Index("idx_history_project_id", "project_id"),
        Index("idx_history_finished_at", "finished_at"),
        Index("idx_history_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<MergeRequestHistory(iid={self.iid}, status={self.status!r})>"


class AnalyticsHourlyModel(Base):
    """ORM model for the analytics_hourly table.

    Stores hourly queue snapshots for trend analysis.
    Retention: 30 days. Matches ADR-004 schema.
    """

    __tablename__ = "analytics_hourly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    queue_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_wait_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "timestamp", name="uq_hourly_project_timestamp"),
        Index("idx_hourly_project_id", "project_id"),
        Index("idx_hourly_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AnalyticsHourly(timestamp={self.timestamp!r})>"


class AnalyticsDailyModel(Base):
    """ORM model for the analytics_daily table.

    Stores daily aggregated statistics for long-term analytics.
    Retention: forever. Matches ADR-004 schema.
    """

    __tablename__ = "analytics_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    date: Mapped[str] = mapped_column(Text, nullable=False)
    total_processed: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_count: Mapped[int] = mapped_column(Integer, nullable=False)
    hotfix_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_wait_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_processing_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_queue_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "date", name="uq_daily_project_date"),
        Index("idx_daily_project_id", "project_id"),
        Index("idx_daily_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<AnalyticsDaily(date={self.date!r})>"
