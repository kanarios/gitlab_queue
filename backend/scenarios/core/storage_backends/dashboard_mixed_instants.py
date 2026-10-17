from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone

from scenarios.fakes import create_mr
from scenarios.integration.repositories._helpers import create_test_history_model
from vedro import given, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.repositories import HistoryRepository

from ._helpers import migrated_storage
from .retry_backoff_exact_boundaries import Clock


@scenario()
async def dashboard_mixed_instants_preserve_window_durations_and_projects():
    async with migrated_storage() as database:
        with given("all terminal outcomes, exact window boundaries and a foreign project's same IID"):
            clock = Clock(datetime.now(UTC))
            queue = QueueManager(database, clock=clock)
            cutoff = clock.instant - timedelta(days=7)
            recent = clock.instant - timedelta(hours=1)
            older = clock.instant - timedelta(hours=2)
            offset = timezone(timedelta(hours=5))
            specifications = [
                (
                    123,
                    1,
                    "merged",
                    recent.isoformat().replace("+00:00", "Z"),
                    (recent - timedelta(seconds=50)).isoformat(),
                    (recent - timedelta(seconds=40)).isoformat(),
                    10,
                    40,
                ),
                (
                    123,
                    2,
                    "failed",
                    older.astimezone(offset).isoformat(),
                    (older - timedelta(seconds=100)).isoformat(),
                    (older - timedelta(seconds=70)).isoformat(),
                    30,
                    70,
                ),
                (123, 3, "conflict", older.isoformat(), older.isoformat(), None, None, None),
                (123, 4, "timeout", older.isoformat(), older.isoformat(), None, None, None),
                (123, 5, "removed", older.isoformat(), older.isoformat(), None, None, None),
                (
                    123,
                    6,
                    "merged",
                    (cutoff - timedelta(microseconds=1)).astimezone(offset).isoformat(),
                    (cutoff - timedelta(microseconds=1, seconds=300)).isoformat(),
                    (cutoff - timedelta(microseconds=1, seconds=200)).isoformat(),
                    100,
                    200,
                ),
                (
                    123,
                    7,
                    "merged",
                    cutoff.strftime("%Y-%m-%d %H:%M:%S.%f"),
                    cutoff.isoformat(),
                    cutoff.isoformat(),
                    0,
                    0,
                ),
                (
                    456,
                    1,
                    "merged",
                    recent.isoformat(),
                    (recent - timedelta(seconds=1900)).isoformat(),
                    (recent - timedelta(seconds=1000)).isoformat(),
                    900,
                    1000,
                ),
                (
                    789,
                    1,
                    "merged",
                    clock.instant.isoformat(),
                    clock.instant.isoformat(),
                    clock.instant.isoformat(),
                    0,
                    0,
                ),
            ]
            rows = []
            for project, iid, status, finished, queued, started, wait, processing in specifications:
                row = create_test_history_model(
                    iid=iid,
                    status=status,
                    finished_at=finished,
                    queued_at=queued,
                    started_at=started,
                    wait_time_seconds=wait,
                    processing_time_seconds=processing,
                )
                row.project_id = project
                rows.append(row)
            async with database.transaction() as session:
                session.add_all(rows)
            await queue.add_to_queue(123, create_mr(iid=20))
            await queue.add_to_queue(123, create_mr(iid=21))
            await queue.update_mr_state(123, 21, "testing")
            await queue.add_to_queue(456, create_mr(iid=20))

        with when("raw dashboard windows and chronological history are requested"):
            stats = await queue.get_dashboard_stats(project_id=123)
            foreign = await queue.get_dashboard_stats(project_id=456)
            recent = await queue.get_recent_history(limit=1, project_id=123)
            async with database.session() as session:
                history = HistoryRepository(session, project_id=123)
                zero = await HistoryRepository(session, project_id=789).get_stats_for_date(clock.instant.date())
                latest = await history.get_recent(limit=1)
                await session.commit()

        with then("mixed formats compare as instants and foreign records cannot affect aggregates"):
            assert asdict(stats) == {
                "total_in_queue": 2,
                "merged_count": 2,
                "failed_count": 3,
                "success_rate": 40.0,
                "avg_wait_seconds": 13.3,
                "avg_processing_seconds": 20.0,
                "stats_window_days": 7,
            }
            assert (
                foreign.total_in_queue,
                foreign.merged_count,
                foreign.failed_count,
                foreign.avg_wait_seconds,
                foreign.avg_processing_seconds,
            ) == (1, 1, 0, 900.0, 1000.0)
            assert recent[0].mr_iid == latest[0].iid == 1
            assert zero.avg_wait_time_seconds == zero.avg_processing_time_seconds == 0.0
