from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from ._helpers import label_event, queue_environment


@scenario()
async def first_mr_gets_priority_feedback():
    async with queue_environment() as env:
        with given("the only waiting MR receives hotfix"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            event = label_event("update", ["merge_queue"], ["merge_queue", "hotfix"])

        with when("the priority is enabled without changing the position"):
            await env.handler.handle(event)

        with then("the author receives confirmation even though the MR stays first"):
            assert [iid for iid, body in env.server.comments] == [3]
            assert "Hotfix priority enabled" in env.server.comments[0][1]
            assert "**Position:** 1 of 1" in env.server.comments[0][1]
