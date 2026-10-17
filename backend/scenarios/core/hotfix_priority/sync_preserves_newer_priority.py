import asyncio

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.processor import create_processor

from ._helpers import label_event, queue_environment


@scenario(
    [
        params("poll", {}),
        params("startup", {}),
        params("poll", {"hotfix": []}),
        params("startup", {"hotfix": []}),
    ]
)
async def sync_preserves_newer_priority(entrypoint, label_snapshots):
    async with queue_environment() as env:
        with given("a sync paused after reading the old queue-label snapshot"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.mrs = [mr_response(1, labels=["merge_queue"]), mr_response(3, labels=["merge_queue"])]
            env.server.label_snapshots = label_snapshots
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

        with when("a webhook promotes the MR before the old sync finishes"):
            task = asyncio.create_task(sync())
            await asyncio.wait_for(entered.wait(), 5)
            await env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            env.server.mrs[1]["labels"] = ["merge_queue", "hotfix"]
            release.set()
            await asyncio.wait_for(task, 5)

        with then("the newer priority survives without false removal feedback"):
            next_mr = await env.queue.get_next_mr(123)
            assert next_mr.mr_iid == 3
            assert next_mr.is_hotfix is True
            assert [iid for iid, body in env.server.comments] == [3, 1]
            assert "Hotfix priority enabled" in env.server.notes[3]
