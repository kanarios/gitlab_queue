from scenarios.fakes import create_mr
from vedro import given, params, scenario, then, when

from ._helpers import label_event, queue_environment


@scenario([params("update"), params("labeled")])
async def repeated_label_event_is_noop(action):
    async with queue_environment() as env:
        with given("the hotfix label update has already been applied"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            event = label_event(action, ["merge_queue"], ["merge_queue", "hotfix"])
            await env.handler.handle(event)
            env.server.comments.clear()
            env.websocket.broadcast_calls.clear()

        with when("GitLab retries the same label event"):
            await env.handler.handle(event)

        with then("priority is retained without duplicate notifications"):
            assert [item.mr_iid for item in await env.queue.get_active_queue(123)] == [3, 1]
            assert env.server.comments == []
            assert env.websocket.broadcast_calls == []
