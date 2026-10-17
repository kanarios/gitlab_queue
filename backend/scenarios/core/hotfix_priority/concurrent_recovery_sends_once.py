import asyncio

from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier

from ._helpers import ObservedQueue, label_event, queue_environment


@scenario()
async def concurrent_recovery_sends_once():
    async with queue_environment() as env:
        with given("two drainers share a pending comment while the first HTTP request waits"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.failed_comment_iids = {3}
            await env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            env.server.failed_comment_iids.clear()
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("POST", "/api/v4/projects/123/merge_requests/3/notes")] = (entered, release)
            second_queue = ObservedQueue(env.queue.db)
            second = QueuePositionNotifier(MRNotifier(env.gitlab, env.settings, second_queue), second_queue)

        with when("both drainers read the pending intent before either acknowledges it"):
            first_drain = asyncio.create_task(env.handler.position_notifier.retry_pending(123))
            await asyncio.wait_for(entered.wait(), 5)
            second_drain = asyncio.create_task(second.retry_pending(123))
            await asyncio.wait_for(second_queue.queue_read.wait(), 5)
            release.set()
            await asyncio.wait_for(asyncio.gather(first_drain, second_drain), 5)

        with then("the persisted intent creates exactly one pinned comment"):
            assert [iid for iid, body in env.server.comments] == [3]
            assert env.server.comment_methods == ["POST"]
            assert (await env.queue.get_queue_item(123, 3)).pending_notification is None
