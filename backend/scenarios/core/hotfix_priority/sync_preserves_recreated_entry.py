import asyncio

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.processor import create_processor

from ._helpers import queue_environment


@scenario([params("poll"), params("startup")])
async def sync_preserves_recreated_entry(entrypoint):
    async with queue_environment() as env:
        with given("an old sync snapshot of an ordinary queue entry"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.mrs = [mr_response(1, labels=["merge_queue"]), mr_response(3, labels=["merge_queue"])]
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("GET", "merge_queue")] = (entered, release)
            processor = create_processor(
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.settings,
                position_notifier=env.handler.position_notifier,
            )
            processor.request_shutdown()
            sync = {"poll": env.scheduler.sync_queue, "startup": processor.run}[entrypoint]

        with when("the old entry is removed and recreated as a hotfix before sync finishes"):
            task = asyncio.create_task(sync())
            await asyncio.wait_for(entered.wait(), 5)
            await env.queue.remove_from_queue(123, 3)
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "hotfix"]), is_hotfix=True)
            release.set()
            await asyncio.wait_for(task, 5)

        with then("the snapshot of the old incarnation cannot demote the replacement"):
            next_mr = await env.queue.get_next_mr(123)
            assert next_mr.mr_iid == 3
            assert next_mr.is_hotfix is True
            assert env.server.comments == []
