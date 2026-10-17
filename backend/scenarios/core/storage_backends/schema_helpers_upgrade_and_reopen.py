from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from sqlalchemy import inspect
from vedro import given, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager


@scenario()
async def schema_helpers_upgrade_and_reopen():
    async with isolated_database_url() as database_url:
        with given("a fresh database initialized through both production schema helpers twice"):
            async with Database(database_url) as database:
                queue, retry = QueueManager(database), WebhookRetryManager(database, base_delay_seconds=0)
                await queue.ensure_schema()
                await retry.ensure_schema()
                await queue.ensure_schema()
                await retry.ensure_schema()
                original = await queue.add_to_queue(123, create_mr(iid=3))
                retry_id = await retry.add_to_retry_queue("merge_request", {"project": {"id": 123}}, "failure", 123)

        with when("startup migrations stamp and reconcile that schema before reopening it"):
            await run_migrations(database_url)
            async with Database(database_url) as database:
                queue, retry = QueueManager(database), WebhookRetryManager(database)
                current = await queue.get_queue_item(123, 3)
                pending = await retry.get_events_ready_for_retry(project_id=123)
                async with database.engine.connect() as connection:
                    indexes = await connection.run_sync(lambda sync: inspect(sync).get_indexes("merge_requests"))

        with then("data and incarnation survive and the canonical project index exists"):
            assert current.queue_id == original.queue_id
            assert current.queued_at == original.queued_at
            assert pending[0].id == retry_id
            assert "idx_mr_project_id" in {index["name"] for index in indexes}
