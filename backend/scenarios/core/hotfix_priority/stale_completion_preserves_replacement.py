from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from ._helpers import queue_environment


@scenario()
async def stale_completion_preserves_replacement():
    async with queue_environment() as env:
        with given("an archived lifecycle and a new generation of the same MR"):
            original = await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.complete_mr(123, 3, "merged", expected_queue_id=original.queue_id)
            replacement = await env.queue.add_to_queue(123, create_mr(iid=3))

        with when("the old generation's completion is retried"):
            completed = await env.queue.complete_mr(123, 3, "merged", expected_queue_id=original.queue_id)

        with then("neither the new row nor the original history is changed"):
            current = await env.queue.get_queue_item(123, 3)
            history = await env.queue.get_recent_history(project_id=123)
            assert completed is False
            assert current.queue_id == replacement.queue_id
            assert current.state == "queued"
            assert len(history) == 1
            assert history[0].queued_at == original.queued_at
