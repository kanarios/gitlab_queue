from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.processor import create_processor

from ._helpers import queue_environment


@scenario([params("poll"), params("startup")])
async def later_label_snapshot_wins(entrypoint):
    async with queue_environment() as env:
        with given("a later hotfix-label snapshot disagrees with the queue-label snapshot"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.mrs = [
                mr_response(1, labels=["merge_queue"]),
                mr_response(3, labels=["merge_queue", "hotfix"]),
            ]
            env.server.label_snapshots["merge_queue"] = [
                mr_response(1, labels=["merge_queue"]),
                mr_response(3, labels=["merge_queue"]),
            ]
            processor = create_processor(
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.settings,
                position_notifier=env.handler.position_notifier,
            )
            processor.request_shutdown()
            sync = {"poll": env.scheduler.sync_queue, "startup": processor.run}[entrypoint]

        with when("the bot reconciles the two GitLab lists"):
            await sync()

        with then("the later hotfix snapshot determines priority"):
            next_mr = await env.queue.get_next_mr(123)
            assert next_mr.mr_iid == 3
            assert next_mr.is_hotfix is True
