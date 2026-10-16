from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from ._helpers import label_event, queue_environment


@scenario()
async def update_removes_last_trigger():
    async with queue_environment() as env:
        with given("an MR queued only by hotfix loses its last trigger label"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["hotfix"]), is_hotfix=True)
            env.server.mrs = [mr_response(3, labels=[])]
            event = label_event("update", ["hotfix"], [])

        with when("GitLab delivers the label removal as an update"):
            await env.handler.handle(event)

        with then("the MR leaves the active queue"):
            assert await env.queue.get_active_queue(123) == []
            assert await env.queue.get_next_mr(123) is None
            assert env.websocket.broadcast_calls[-1]["queue"] == []
