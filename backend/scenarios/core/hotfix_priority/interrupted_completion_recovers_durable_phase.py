import asyncio

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.core.processor import create_processor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.db.database import Database

from ._helpers import queue_environment, queue_services


@scenario(
    [
        params("before", "POST", "/notes", "poll"),
        params("after", "POST", "/notes", "poll"),
        params("after", "PUT", "", "poll"),
        params("before", "POST", "/notes", "startup"),
        params("after", "POST", "/notes", "startup"),
        params("after", "PUT", "", "startup"),
    ]
)
async def interrupted_completion_recovers_durable_phase(side, method, suffix, entrypoint):
    async with queue_environment() as env:
        with given("a failed lifecycle interrupted around terminal HTTP or label cleanup"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.update_mr_state(123, 3, "rebasing", pipeline_id=101, expected_sha="original-sha")
            original = await env.queue.get_queue_item(123, 3)
            env.server.mrs = [mr_response(3, labels=["merge_queue", "hotfix"]), mr_response(1, labels=["merge_queue"])]
            entered, release = asyncio.Event(), asyncio.Event()
            barriers = {"before": env.server.barriers, "after": env.server.after_barriers}[side]
            barriers[(method, f"/api/v4/projects/123/merge_requests/3{suffix}")] = (entered, release)
            machine = await create_state_machine_for_mr(
                123, 3, env.handler.notifier, env.queue, position_notifier=env.handler.position_notifier
            )
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Original conflict")
            )
            await asyncio.wait_for(entered.wait(), 5)
            completion.cancel()
            with catched(asyncio.CancelledError):
                await completion
            env.server.barriers.clear()
            env.server.after_barriers.clear()
            database_url = env.queue.db.database_url
            await env.queue.db.close()

        with when("the persisted completion is retried after reopening the database"):
            async with Database(database_url) as db, queue_services(QueueManager(db), env.server) as recovered:
                processor = create_processor(
                    recovered.gitlab,
                    recovered.queue,
                    recovered.handler.notifier,
                    recovered.settings,
                    position_notifier=recovered.handler.position_notifier,
                )
                processor.request_shutdown()
                recover = {"poll": recovered.scheduler.sync_queue, "startup": processor.run}[entrypoint]
                await recover()
                await recovered.scheduler.sync_queue()
                history = await recovered.queue.get_recent_history(project_id=123)
                remaining = await recovered.queue.get_queue_item(123, 3)

        with then("original details survive exactly one archival and mandatory cleanup"):
            assert remaining is None
            assert len(history) == 1
            assert history[0].queued_at == original.queued_at
            assert history[0].started_at == original.started_at
            assert history[0].pipeline_id == 101
            assert history[0].state == "conflict"
            assert "Rebase conflict" in env.server.notes[3]
            assert "**Position:** 1 of 1" in env.server.notes[1]
            assert env.server.mrs[0]["labels"] == []
