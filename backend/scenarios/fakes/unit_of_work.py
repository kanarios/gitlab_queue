"""Fake UnitOfWork and repository fakes for analytics tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date, datetime


@dataclass
class HourlyStats:
    """Value object for hourly statistics."""

    total_processed: int = 0
    success_count: int = 0
    failed_count: int = 0
    avg_wait_time_seconds: float | None = None


@dataclass
class DailyAggregationResult:
    """Value object for daily aggregation result."""

    total_processed: int = 0


@dataclass
class PaginatedHistoryResult:
    """Value object for paginated history query result."""

    items: list[Any] = field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


@dataclass
class HistoryStatsResult:
    """Value object for history stats (summary/outcomes endpoints)."""

    total_processed: int = 0
    success_count: int = 0
    failed_count: int = 0
    conflict_count: int = 0
    timeout_count: int = 0
    avg_wait_time_seconds: float = 0
    avg_processing_time_seconds: float = 0


@dataclass
class AnalyticsMetrics:
    """Value object for analytics metrics (hourly endpoint)."""

    hourly_trend: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class HistoryItemModel:
    """Fake history item model matching DB model attributes."""

    iid: int = 0
    title: str = ""
    author_name: str = ""
    author_username: str = ""
    author_avatar: str = ""
    status: str = ""
    is_hotfix: bool = False
    labels: str = "[]"
    target_branch: str = ""
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    pipeline_id: int | None = None
    pipeline_status: str | None = None
    failure_reason: str | None = None


@dataclass
class FakeAnalyticsRepo:
    """Fake analytics repository with call recording."""

    save_hourly_snapshot_calls: list[dict[str, Any]] = field(default_factory=list)
    cleanup_hourly_calls: list[int] = field(default_factory=list)
    cleanup_hourly_result: int = 0
    aggregate_daily_calls: list[date] = field(default_factory=list)
    aggregate_daily_result: DailyAggregationResult | None = None
    metrics_result: AnalyticsMetrics = field(default_factory=AnalyticsMetrics)
    get_metrics_calls: list[int] = field(default_factory=list)

    async def save_hourly_snapshot(
        self,
        *,
        queue_depth: int,
        processed_count: int,
        success_count: int,
        failed_count: int,
        avg_wait_time_seconds: int | None,
    ) -> None:
        self.save_hourly_snapshot_calls.append(
            {
                "queue_depth": queue_depth,
                "processed_count": processed_count,
                "success_count": success_count,
                "failed_count": failed_count,
                "avg_wait_time_seconds": avg_wait_time_seconds,
            }
        )

    async def cleanup_hourly(self, retention_days: int) -> int:
        self.cleanup_hourly_calls.append(retention_days)
        return self.cleanup_hourly_result

    async def aggregate_daily(self, target_date: date) -> DailyAggregationResult | None:
        self.aggregate_daily_calls.append(target_date)
        return self.aggregate_daily_result

    async def get_metrics(self, period_days: int) -> AnalyticsMetrics:
        self.get_metrics_calls.append(period_days)
        return self.metrics_result


@dataclass
class FakeHistoryRepo:
    """Fake history repository with call recording."""

    hourly_stats: HourlyStats = field(default_factory=HourlyStats)
    cleanup_old_records_result: int = 0
    get_stats_calls: list[None] = field(default_factory=list)
    cleanup_old_records_calls: list[int] = field(default_factory=list)
    # API-specific fields
    get_history_result: PaginatedHistoryResult = field(default_factory=PaginatedHistoryResult)
    get_history_calls: list[dict[str, Any]] = field(default_factory=list)
    get_by_iid_result: HistoryItemModel | None = None
    get_by_iid_calls: list[int] = field(default_factory=list)
    stats_for_period_result: HistoryStatsResult = field(default_factory=HistoryStatsResult)
    get_stats_for_period_calls: list[dict[str, Any]] = field(default_factory=list)

    async def get_stats_for_last_hour(self) -> HourlyStats:
        self.get_stats_calls.append(None)
        return self.hourly_stats

    async def cleanup_old_records(self, retention_days: int) -> int:
        self.cleanup_old_records_calls.append(retention_days)
        return self.cleanup_old_records_result

    async def get_history(self, **kwargs: Any) -> PaginatedHistoryResult:
        self.get_history_calls.append(kwargs)
        return self.get_history_result

    async def get_by_iid(self, iid: int) -> HistoryItemModel | None:
        self.get_by_iid_calls.append(iid)
        return self.get_by_iid_result

    async def get_stats_for_period(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> HistoryStatsResult:
        self.get_stats_for_period_calls.append(
            {
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        return self.stats_for_period_result


@dataclass
class FakeMergeRequestsRepo:
    """Fake merge requests repository with call recording."""

    active_count: int = 0
    count_active_calls: list[None] = field(default_factory=list)

    async def count_active(self) -> int:
        self.count_active_calls.append(None)
        return self.active_count


@dataclass
class FakeUnitOfWork:
    """Fake UnitOfWork that works as async context manager."""

    analytics: FakeAnalyticsRepo = field(default_factory=FakeAnalyticsRepo)
    history: FakeHistoryRepo = field(default_factory=FakeHistoryRepo)
    merge_requests: FakeMergeRequestsRepo = field(default_factory=FakeMergeRequestsRepo)
    enter_error: Exception | None = None

    async def __aenter__(self) -> FakeUnitOfWork:
        if self.enter_error:
            raise self.enter_error
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass
