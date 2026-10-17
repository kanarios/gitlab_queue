from vedro import given, scenario, then, when

from gitlab_queue.webhooks.retry_manager import WebhookRetryManager

from ._helpers import migrated_storage


@scenario()
async def migrated_retry_lifecycle():
    async with migrated_storage() as database:
        with given("a migrated retry store with an immediately due JSON event"):
            manager = WebhookRetryManager(database, max_attempts=1, base_delay_seconds=0)
            payload = {
                "object_kind": "merge_request",
                "project": {"id": 123},
                "nested": {"values": [None, "Привет", 3]},
            }
            retry_id = await manager.add_to_retry_queue("merge_request", payload, "temporary failure", project_id=123)

        with when("the event exhausts retry, is manually requeued and acknowledged"):
            ready = await manager.get_events_ready_for_retry(project_id=123)
            moved = await manager.mark_retry_failed(retry_id, "final failure", project_id=123)
            dead = await manager.get_dlq_entries(project_id=123)
            reset_id = await manager.retry_dlq_entry(dead[0].id, project_id=123)
            reset = await manager.get_events_ready_for_retry(project_id=123)
            await manager.mark_retry_success(reset_id, project_id=123)

        with then("payload and project survive while attempts reset and both queues become empty"):
            assert ready[0].id == retry_id
            assert ready[0].payload == payload
            assert moved is True
            assert dead[0].attempt_count == 1
            assert dead[0].project_id == 123
            assert dead[0].moved_to_dlq_at.tzinfo is not None
            assert reset[0].id == reset_id
            assert reset[0].payload == payload
            assert reset[0].attempt_count == 0
            assert await manager.get_events_ready_for_retry() == []
            assert await manager.get_dlq_entries() == []
