from scenarios.fakes import create_mr
from vedro import given, params, scenario, then, when

from ._helpers import label_event, queue_environment


@scenario([params("update"), params("unlabeled")])
async def removing_hotfix_restores_fifo(action):
    async with queue_environment() as env:
        with given("a promoted MR keeps merge_queue when hotfix is removed"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=2))
            original = await env.queue.add_to_queue(
                123,
                create_mr(iid=3, labels=["merge_queue", "hotfix"]),
                is_hotfix=True,
            )
            event = label_event(action, ["merge_queue", "hotfix"], ["merge_queue"])

        with when("GitLab delivers the hotfix removal"):
            await env.handler.handle(event)

        with then("the MR returns to its original FIFO position"):
            queue = await env.queue.get_active_queue(123)
            assert [item.mr_iid for item in queue] == [1, 2, 3]
            assert queue[2].queued_at == original.queued_at
            assert queue[2].is_hotfix is False
            assert queue[2].labels == ["merge_queue"]

        with then("the author and affected MRs see the updated priority and positions"):
            assert [iid for iid, body in env.server.comments] == [3, 1, 2]
            assert "Hotfix priority removed" in env.server.comments[0][1]
            assert "**Position:** 3 of 3" in env.server.comments[0][1]
            assert [item["mr_iid"] for item in env.websocket.broadcast_calls[0]["queue"]] == [1, 2, 3]
