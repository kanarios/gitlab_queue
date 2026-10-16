from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from gitlab_queue.core.processor import create_processor

from ._helpers import queue_environment


@scenario()
async def startup_recovers_priority():
    async with queue_environment() as env:
        with given("hotfix was added to an existing MR while the bot was down"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.mrs = [
                mr_response(1, labels=["merge_queue"]),
                mr_response(3, labels=["merge_queue", "hotfix"]),
            ]
            processor = create_processor(
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.settings,
                position_notifier=env.handler.position_notifier,
            )
            processor.set_websocket_manager(env.websocket)
            processor.request_shutdown()

        with when("the processor performs startup recovery before stopping"):
            await processor.run()

        with then("the recovered hotfix is next before any merge starts"):
            next_mr = await env.queue.get_next_mr(123)
            assert next_mr.mr_iid == 3
            assert next_mr.is_hotfix is True
            assert [iid for iid, body in env.server.comments] == [3, 1]
            assert [item["mr_iid"] for item in env.websocket.broadcast_calls[0]["queue"]] == [3, 1]
