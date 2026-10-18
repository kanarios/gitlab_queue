import asyncio

from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.processor import create_processor

from ._helpers import automation_environment


@scenario([params("rebasing"), params("testing"), params("merging")])
async def automation_relabel_keeps_the_running_workflow_and_processing_note(state):
    async with automation_environment() as env:
        with given("an inflight MR with its original pipeline, SHA and retry metadata"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            await env.queue.update_mr_state(
                123,
                3,
                state,
                pipeline_id=101,
                expected_sha="current-sha",
                retried_jobs={"tests": 1},
                processing_attempts=2,
            )
            before = await env.queue.get_queue_item(123, 3)
        with when("automation is added while this MR is running"):
            await env.handler.handle(label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"]))
            after = await env.queue.get_queue_item(123, 3)
        with then("only classification metadata changes"):
            assert after.priority == "automated"
            assert (
                after.queue_id,
                after.queued_at,
                after.state,
                after.started_at,
                after.pipeline_id,
                after.expected_sha,
                after.retried_jobs,
                after.processing_attempts,
            ) == (
                before.queue_id,
                before.queued_at,
                before.state,
                before.started_at,
                before.pipeline_id,
                before.expected_sha,
                before.retried_jobs,
                before.processing_attempts,
            )
            assert env.server.comments == []


async def relabel_entry(env):
    await env.handler.handle(label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"]))


async def recreate_entry(env):
    await env.queue.remove_from_queue(123, 3)
    await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "dependencies"]))


@scenario(
    [
        params("poll", relabel_entry, False),
        params("startup", relabel_entry, False),
        params("poll", recreate_entry, True),
        params("startup", recreate_entry, True),
    ]
)
async def stale_sync_cannot_restore_automation_metadata_of_an_old_revision_or_incarnation(entrypoint, change, recreate):
    async with automation_environment() as env:
        with given("a complete sync paused after receiving the previous ordinary label snapshot"):
            before = await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            await env.queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
            env.server.mrs = [mr_response(3, labels=["merge_queue"]), mr_response(2, labels=["merge_queue"])]
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

        with when("a newer automation snapshot wins before the stale sweep resumes"):
            task = asyncio.create_task(sync())
            try:
                await asyncio.wait_for(entered.wait(), 5)
                await change(env)
                saved = await env.queue.get_queue_item(123, 3)
                env.server.mrs[0]["labels"] = ["merge_queue", "dependencies"]
            finally:
                release.set()
                await asyncio.wait_for(task, 5)
            current = await env.queue.get_queue_item(123, 3)

        with then("neither both facts nor labels roll back and the correct row keeps its original FIFO slot"):
            assert current == saved
            assert current.priority == "automated"
            assert [item.mr_iid for item in await env.queue.get_active_queue(123)] == [2, 3]
            assert (current.queue_id != before.queue_id) is recreate
