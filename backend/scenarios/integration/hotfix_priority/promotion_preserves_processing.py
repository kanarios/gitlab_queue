from scenarios.fakes import create_mr
from vedro import given, params, scenario, then, when

from ._helpers import label_event, queue_environment


@scenario([params("rebasing"), params("testing"), params("merging")])
async def promotion_preserves_processing(state):
    async with queue_environment() as env:
        with given("the MR receiving hotfix is already being processed"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(
                123,
                3,
                state,
                pipeline_id=100,
                expected_sha="current-sha",
                retried_jobs={"tests": 1},
            )
            original = await env.queue.get_queue_item(123, 3)
            event = label_event("update", ["merge_queue"], ["merge_queue", "hotfix"])

        with when("the priority changes during processing"):
            await env.handler.handle(event)

        with then("only labels and priority change, preserving workflow and comment"):
            item = await env.queue.get_queue_item(123, 3)
            assert item.state == state
            assert item.started_at == original.started_at
            assert item.pipeline_id == 100
            assert item.expected_sha == "current-sha"
            assert item.retried_jobs == {"tests": 1}
            assert item.is_hotfix is True
            assert env.server.comments == []
            assert env.websocket.broadcast_calls[0]["queue"][0]["status"] == state
