import asyncio

from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import label_event, queue_environment


@scenario()
async def concurrent_duplicate_is_noop():
    async with queue_environment() as env:
        with given("two webhook handlers sharing a queue and the same priority event"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=2))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            second = MRWebhookHandler(
                env.settings,
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.handler.position_notifier,
                env.websocket,
            )
            event = label_event("update", ["merge_queue"], ["merge_queue", "hotfix"])

        with when("GitLab delivers both copies concurrently"):
            await asyncio.gather(env.handler.handle(event), second.handle(event))

        with then("each affected author receives one comment and one dashboard update"):
            assert [iid for iid, body in env.server.comments] == [3, 1, 2]
            assert env.server.comment_methods == ["POST", "POST", "POST"]
            assert len(env.websocket.broadcast_calls) == 1
