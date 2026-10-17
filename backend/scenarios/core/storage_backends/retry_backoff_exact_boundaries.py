from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from vedro import catched, given, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.webhooks.retry_manager import RetryItemNotFoundError, WebhookRetryManager

from ._helpers import migrated_storage


@dataclass
class Clock:
    instant: datetime

    def __call__(self):
        return self.instant


@scenario()
async def retry_backoff_exact_boundaries_survive_reopen():
    async with migrated_storage() as database:
        with given("an offset timestamp and capped exponential backoff"):
            clock = Clock(datetime(2026, 10, 17, 22, 0, 0, 123456, tzinfo=timezone(timedelta(hours=5))))
            manager = WebhookRetryManager(
                database, max_attempts=4, base_delay_seconds=10, max_delay_seconds=25, clock=clock
            )
            payload = {
                "project": {"id": 123},
                "unicode": "ёж",
                "_queue_webhook": {"event_uuid": "chain", "message_id": "delivery"},
            }
            source = await manager.add_to_retry_queue("merge_request", payload, "initial", 123)

        with when("retry reaches each exact due instant and the store is reopened"):
            clock.instant += timedelta(seconds=10, microseconds=-1)
            assert await manager.get_events_ready_for_retry() == []
            clock.instant += timedelta(microseconds=1)
            first = (await manager.get_events_ready_for_retry())[0]
            await manager.mark_retry_failed(source, "one", 123)
            clock.instant += timedelta(seconds=20, microseconds=-1)
            assert await manager.get_events_ready_for_retry() == []
            clock.instant += timedelta(microseconds=1)
            second = (await manager.get_events_ready_for_retry())[0]
            await manager.mark_retry_failed(source, "two", 123)
            clock.instant += timedelta(seconds=25)
            await database.close()
            async with Database(database.database_url) as reopened:
                recovered_manager = WebhookRetryManager(
                    reopened, max_attempts=4, base_delay_seconds=10, max_delay_seconds=25, clock=clock
                )
                recovered = (await recovered_manager.get_events_ready_for_retry())[0]
                with catched(RetryItemNotFoundError) as wrong_project:
                    await recovered_manager.mark_retry_success(source, 456)
                await recovered_manager.mark_retry_failed(source, "three", 123)
                clock.instant += timedelta(seconds=25)
                moved = await recovered_manager.mark_retry_failed(source, "four", 123)
                dead = (await recovered_manager.get_dlq_entries(project_id=123))[0]

        with then("microsecond boundaries, attempts, capped timing and JSON provenance are preserved"):
            assert first.next_attempt_at == first.created_at + timedelta(seconds=10)
            assert second.next_attempt_at == first.next_attempt_at + timedelta(seconds=20)
            assert recovered.next_attempt_at == second.next_attempt_at + timedelta(seconds=25)
            assert recovered.attempt_count == 2
            assert recovered.payload == payload
            assert wrong_project.type is RetryItemNotFoundError
            assert moved is True
            assert dead.attempt_count == 4
            assert dead.moved_to_dlq_at == clock.instant
            assert dead.payload == payload
