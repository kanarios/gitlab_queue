from vedro import given, scenario, then, when

from gitlab_queue.core.queue import QueueManager

from ._helpers import migrated_storage


@scenario()
async def dashboard_empty():
    async with migrated_storage() as database:
        with given("an empty migrated queue and history"):
            queue = QueueManager(database)

        with when("both global and project dashboard statistics are requested"):
            stats = await queue.get_dashboard_stats()
            project_stats = await queue.get_dashboard_stats(project_id=123)

        with then("all aggregates are numeric zeros"):
            assert stats.total_in_queue == project_stats.total_in_queue == 0
            assert stats.merged_count == project_stats.merged_count == 0
            assert stats.failed_count == project_stats.failed_count == 0
            assert stats.success_rate == project_stats.success_rate == 0.0
            assert stats.avg_wait_seconds == project_stats.avg_wait_seconds == 0.0
            assert stats.avg_processing_seconds == project_stats.avg_processing_seconds == 0.0
