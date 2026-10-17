"""Concurrent public transfers of one retry source have one winner."""

import asyncio

from scenarios.contexts.database_backend import isolated_database_url
from vedro import given, scenario, then, when

from gitlab_queue.db.database import Database
from gitlab_queue.webhooks.retry_manager import RetryItemNotFoundError, WebhookRetryManager

from ._helpers import create_test_payload


@scenario()
async def concurrent_dlq_moves_insert_once():
    async with isolated_database_url() as database_url, Database(database_url) as database:
        with given("one due retry row in a real database"):
            manager = WebhookRetryManager(database, base_delay_seconds=0)
            await manager.ensure_schema()
            retry_id = await manager.add_to_retry_queue(
                "merge_request", create_test_payload(), "initial", project_id=303
            )

        with when("two callers concurrently move the same source to DLQ"):
            results = await asyncio.gather(
                manager.move_retry_to_dlq(retry_id, "removed project", project_id=303),
                manager.move_retry_to_dlq(retry_id, "removed project", project_id=303),
                return_exceptions=True,
            )
            dead = await manager.get_dlq_entries(project_id=303)

        with then("one transfer wins and the other reports a stale source"):
            assert results.count(None) == 1
            assert sum(isinstance(result, RetryItemNotFoundError) for result in results) == 1
            assert len(dead) == 1
            assert dead[0].project_id == 303
            assert dead[0].attempt_count == 0
            assert await manager.get_events_ready_for_retry(project_id=303) == []
