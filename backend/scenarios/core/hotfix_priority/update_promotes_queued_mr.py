from scenarios.fakes import create_mr
from vedro import given, params, scenario, then, when

from ._helpers import label_event, queue_environment


@scenario([params("update"), params("labeled")])
async def update_promotes_queued_mr(action):
    async with queue_environment() as env:
        with given("three waiting MRs and hotfix added to the last one"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=2))
            original = await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.add_to_queue(456, create_mr(iid=3))
            event = label_event(action, ["merge_queue"], ["merge_queue", "hotfix"])
            await env.handler.position_notifier.notify_initial_position(123, 3)
            env.server.comments.clear()
            env.server.comment_methods.clear()

        with when("GitLab delivers the label update"):
            await env.handler.handle(event)

        with then("the hotfix is first to merge with its original queue entry"):
            queue = await env.queue.get_active_queue(123)
            assert [item.mr_iid for item in queue] == [3, 1, 2]
            assert queue[0].queued_at == original.queued_at
            assert queue[0].is_hotfix is True
            assert queue[0].labels == ["merge_queue", "hotfix"]
            next_mr = await env.queue.get_next_mr(123)
            assert next_mr.mr_iid == 3
            foreign_item = await env.queue.get_queue_item(456, 3)
            assert foreign_item.is_hotfix is False

        with then("the author and affected MRs receive updated positions"):
            assert [iid for iid, body in env.server.comments] == [3, 1, 2]
            assert "Hotfix priority enabled" in env.server.comments[0][1]
            assert "**Position:** 1 of 3" in env.server.comments[0][1]
            assert "**Position:** 2 of 3" in env.server.comments[1][1]
            assert "**Position:** 3 of 3" in env.server.comments[2][1]
            assert env.server.comment_methods == ["PUT", "POST", "POST"]

        with then("the dashboard receives the new order"):
            assert [item["mr_iid"] for item in env.websocket.broadcast_calls[0]["queue"]] == [3, 1, 2]
