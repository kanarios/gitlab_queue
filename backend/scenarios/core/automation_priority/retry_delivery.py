import asyncio

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from gitlab_queue.webhooks.retry_manager import WebhookRetryManager
from gitlab_queue.webhooks.retry_processor import WebhookRetryProcessor

from ._helpers import automation_environment


async def retry_drained(manager):
    while await manager.get_events_ready_for_retry(project_id=123):
        await asyncio.sleep(0.01)


@scenario()
async def old_raw_retry_and_dlq_replay_reclassify_without_readmitting_the_waiting_entry():
    async with automation_environment() as env:
        with given("a waiting entry and an old webhook payload replayed through DLQ and the real retry processor"):
            original = await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            env.server.mrs = [mr_response(3, labels=["merge_queue", "dependencies"])]
            payload = {
                "object_kind": "merge_request",
                "project": {"id": 123},
                "object_attributes": {
                    "iid": 3,
                    "title": "MR3",
                    "state": "opened",
                    "action": "update",
                    "source_branch": "feature",
                    "target_branch": "main",
                },
                "labels": [{"title": "merge_queue"}, {"title": "dependencies"}],
                "changes": {
                    "labels": {
                        "previous": [{"title": "merge_queue"}],
                        "current": [{"title": "merge_queue"}, {"title": "dependencies"}],
                    }
                },
                "_queue_webhook": {"message_id": "old-delivery"},
            }
            manager = WebhookRetryManager(env.queue.db, max_attempts=1, base_delay_seconds=0)
            source = await manager.add_to_retry_queue("merge_request", payload, "outage", 123)
            await manager.mark_retry_failed(source, "outage", 123)
            dead = (await manager.get_dlq_entries(project_id=123))[0]
            await manager.retry_dlq_entry(dead.id, 123)
        with when("the actual retry worker consumes and acknowledges the replay"):
            processor = WebhookRetryProcessor(
                manager,
                env.settings,
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.handler.position_notifier,
                env.websocket,
            )
            task = asyncio.create_task(processor.run())
            try:
                await asyncio.wait_for(retry_drained(manager), 8)
            finally:
                processor.request_shutdown()
                await asyncio.wait_for(task, 8)
            current = await env.queue.get_queue_item(123, 3)
        with then("the old payload applies current policy to the same incarnation exactly once effectively"):
            assert current.priority == "automated"
            assert current.queue_id == original.queue_id
            assert current.queued_at == original.queued_at
            assert current.metadata_version == 1
            assert current.requeue_request is None
            assert await manager.get_dlq_entries(project_id=123) == []
            assert "Automated priority" in env.server.notes[3]
