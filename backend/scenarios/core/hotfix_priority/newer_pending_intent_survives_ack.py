import asyncio

from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from ._helpers import ObservedQueue, label_event, queue_environment, queue_services


@scenario()
async def newer_pending_intent_survives_ack():
    async with queue_environment() as env:
        with given("an old pending priority comment waiting on HTTP"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.failed_comment_iids = {3}
            await env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            env.server.failed_comment_iids.clear()
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("POST", "/api/v4/projects/123/merge_requests/3/notes")] = (entered, release)
            second_queue = ObservedQueue(env.queue.db)

        with when("priority is removed before the old comment is acknowledged"):
            async with queue_services(second_queue, env.server) as second:
                old_drain = asyncio.create_task(env.handler.position_notifier.retry_pending(123))
                await asyncio.wait_for(entered.wait(), 5)
                removal = asyncio.create_task(
                    second.handler.handle(label_event("update", ["merge_queue", "hotfix"], ["merge_queue"]))
                )
                await asyncio.wait_for(second_queue.metadata_updated.wait(), 5)
                release.set()
                await asyncio.wait_for(asyncio.gather(old_drain, removal), 5)

        with then("the newer intent repairs the comment to the current priority"):
            assert "Hotfix priority removed" in env.server.notes[3]
            assert env.server.comment_methods == ["POST", "PUT"]
            item = await env.queue.get_queue_item(123, 3)
            assert item.is_hotfix is False
            assert item.pending_notification is None
