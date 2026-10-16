from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from ._helpers import queue_environment


@scenario()
async def polling_recovers_priority():
    async with queue_environment() as env:
        with given("a queued MR gains hotfix while its webhook is lost"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            original = await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.mrs = [
                mr_response(1, labels=["merge_queue"]),
                mr_response(3, labels=["merge_queue", "hotfix"]),
            ]

        with when("the fallback scheduler synchronizes GitLab labels"):
            stats = await env.scheduler.sync_queue()

        with then("the existing MR becomes the next hotfix without being requeued"):
            queue = await env.queue.get_active_queue(123)
            assert [item.mr_iid for item in queue] == [3, 1]
            assert queue[0].queued_at == original.queued_at
            assert queue[0].is_hotfix is True
            assert stats.added == 0
            assert stats.removed == 0
            assert stats.updated == 1
            assert stats.unchanged == 1

        with then("comments and dashboard reflect the recovered priority"):
            assert [iid for iid, body in env.server.comments] == [3, 1]
            assert "Hotfix priority enabled" in env.server.comments[0][1]
            assert [item["mr_iid"] for item in env.websocket.broadcast_calls[0]["queue"]] == [3, 1]
