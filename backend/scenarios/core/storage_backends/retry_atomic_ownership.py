import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

from vedro import catched, given, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.webhooks.retry_manager import DLQItemNotFoundError, WebhookRetryManager

from ._helpers import migrated_storage


@scenario()
async def concurrent_dlq_requeue_has_one_winner():
    async with migrated_storage() as database:
        with given("one migrated DLQ entry shared by two callers"):
            manager = WebhookRetryManager(database, max_attempts=1, base_delay_seconds=0)
            payload = {"project": {"id": 123}, "nested": ["ёж", None]}
            source = await manager.add_to_retry_queue("merge_request", payload, "first", 123)
            await manager.mark_retry_failed(source, "last", 123)
            dead = (await manager.get_dlq_entries(project_id=123))[0]

        with when("both callers return the same DLQ source to retry"):
            results = await asyncio.gather(
                manager.retry_dlq_entry(dead.id, 123), manager.retry_dlq_entry(dead.id, 123), return_exceptions=True
            )
            ready = await manager.get_events_ready_for_retry(project_id=123)

        with then("one reset retry replaces the source and the other caller is stale"):
            assert sum(isinstance(result, int) for result in results) == 1
            assert sum(isinstance(result, DLQItemNotFoundError) for result in results) == 1
            assert len(ready) == 1
            assert ready[0].attempt_count == 0
            assert ready[0].payload == payload
            assert ready[0].project_id == 123
            assert ready[0].id > source
            assert await manager.get_dlq_entries() == []


@scenario()
async def concurrent_failed_attempts_are_not_lost_after_reopen():
    async with migrated_storage() as database:
        with given("one retry row with room for two failed attempts"):
            manager = WebhookRetryManager(database, max_attempts=4, base_delay_seconds=0)
            source = await manager.add_to_retry_queue("merge_request", {"project": {"id": 123}}, "first", 123)

        with when("two callers record failures concurrently and the database reopens"):
            results = await asyncio.gather(
                manager.mark_retry_failed(source, "one", 123), manager.mark_retry_failed(source, "two", 123)
            )
            await database.close()
            async with Database(database.database_url) as reopened:
                ready = await WebhookRetryManager(reopened).get_events_ready_for_retry(project_id=123)

        with then("both increments are durable on the single source row"):
            assert results == [False, False]
            assert len(ready) == 1
            assert ready[0].id == source
            assert ready[0].attempt_count == 2


@dataclass
class FailingDestinationDatabase(Database):
    target: str = ""

    @asynccontextmanager
    async def transaction(self):
        async with super().transaction() as session:
            yield FailingDestinationSession(session, self.target)


@dataclass
class FailingDestinationSession:
    session: object
    target: str

    async def execute(self, statement, params=None):
        result = await self.session.execute(statement, params)
        if str(statement).lstrip().startswith(self.target):
            raise RuntimeError("destination failed after insertion")
        return result


@scenario()
async def failed_dlq_destination_rolls_back_attempt_and_source_deletion():
    async with (
        migrated_storage() as database,
        FailingDestinationDatabase(database.database_url, target="INSERT INTO webhook_dlq") as failing,
    ):
        with given("one retry source whose DLQ destination will fail"):
            manager = WebhookRetryManager(database, max_attempts=1, base_delay_seconds=0)
            source = await manager.add_to_retry_queue("merge_request", {"project": {"id": 123}}, "first", 123)

        with when("the failed attempt reaches a failing destination insertion"):
            with catched(RuntimeError) as error:
                await WebhookRetryManager(failing, max_attempts=1).mark_retry_failed(source, "last", 123)
            ready = await manager.get_events_ready_for_retry(project_id=123)

        with then("the source, attempt count and original error are restored atomically"):
            assert error.type is RuntimeError
            assert len(ready) == 1
            assert ready[0].id == source
            assert ready[0].attempt_count == 0
            assert ready[0].last_error == "first"
            assert await manager.get_dlq_entries() == []


@scenario()
async def failed_retry_destination_preserves_dlq_source():
    async with (
        migrated_storage() as database,
        FailingDestinationDatabase(database.database_url, target="INSERT INTO webhook_retry_queue") as failing,
    ):
        with given("one DLQ entry whose retry destination will fail"):
            manager = WebhookRetryManager(database, max_attempts=1, base_delay_seconds=0)
            source = await manager.add_to_retry_queue("merge_request", {"project": {"id": 123}}, "first", 123)
            await manager.mark_retry_failed(source, "last", 123)
            original = (await manager.get_dlq_entries(project_id=123))[0]

        with when("manual requeue fails after its destination insertion"), catched(RuntimeError) as error:
            await WebhookRetryManager(failing).retry_dlq_entry(original.id, 123)

        with then("the DLQ source remains intact and no retry leaks"):
            assert error.type is RuntimeError
            assert await manager.get_dlq_entries(project_id=123) == [original]
            assert await manager.get_events_ready_for_retry() == []
