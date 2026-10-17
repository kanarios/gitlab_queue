from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.processor import create_processor

from ._helpers import queue_environment


@scenario([params("poll"), params("startup")])
async def retained_removal_rejoins_on_missed_relabel(entrypoint):
    async with queue_environment() as env:
        with given("a poll-retained removal followed by an unobserved queue relabel"):
            original = await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.mrs = [mr_response(3, labels=[])]
            await env.scheduler.sync_queue()
            env.server.mrs = [mr_response(3, labels=["merge_queue", "hotfix"])]
            processor = create_processor(
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.settings,
                position_notifier=env.handler.position_notifier,
            )
            processor.request_shutdown()
            recover = {"poll": env.scheduler.sync_queue, "startup": processor.run}[entrypoint]

        with when("the next reconciliation discovers the lost relabel"):
            await recover()
            await env.scheduler.sync_queue()

        with then("the MR rejoins once with a fresh lifecycle and hotfix priority"):
            active = await env.queue.get_active_queue(123)
            assert len(active) == 1
            assert active[0].mr_iid == 3
            assert active[0].queue_id != original.queue_id
            assert active[0].state == "queued"
            assert active[0].is_hotfix is True
            assert active[0].started_at is None
