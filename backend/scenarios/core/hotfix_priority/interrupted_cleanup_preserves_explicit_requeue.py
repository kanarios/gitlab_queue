import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.db.database import Database

from ._helpers import ObservedQueue, label_event, queue_environment, queue_services


@scenario(
    [
        params("merge_queue", False, "remove_labels"),
        params("hotfix", True, "remove_labels"),
        params("merge_queue", False, "add_labels"),
        params("hotfix", True, "add_labels"),
    ]
)
async def interrupted_cleanup_preserves_explicit_requeue(trigger, hotfix, mutation):
    async with (
        queue_environment() as original_env,
        queue_services(ObservedQueue(original_env.queue.db), original_env.server) as env,
    ):
        with given("an explicit new label request saved while the old cleanup waits"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing", pipeline_id=101)
            original = await env.queue.get_queue_item(123, 3)
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            entered, release = asyncio.Event(), asyncio.Event()
            before_cleanup, run_cleanup = asyncio.Event(), asyncio.Event()
            path = "/api/v4/projects/123/merge_requests/3"
            env.server.barriers[("PUT", path)] = (before_cleanup, run_cleanup)
            env.server.after_mutation_barriers[(mutation, path)] = (entered, release)
            machine = await create_state_machine_for_mr(
                123, 3, env.handler.notifier, env.queue, position_notifier=env.handler.position_notifier
            )
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Original conflict")
            )
            await asyncio.wait_for(before_cleanup.wait(), 5)
            env.server.mrs[0]["labels"] = [trigger]
            event = label_event("labeled", [], [trigger])
            event = replace(event, object_attributes=replace(event.object_attributes, updated_at=datetime.now(UTC)))
            enqueue = asyncio.create_task(env.handler.handle(event))
            await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
            env.server.barriers.clear()
            run_cleanup.set()
            await asyncio.wait_for(entered.wait(), 5)
            completion.cancel()
            enqueue.cancel()
            with catched(asyncio.CancelledError):
                await completion
            with catched(asyncio.CancelledError):
                await enqueue
            env.server.after_barriers.clear()
            env.server.after_mutation_barriers.clear()
            database_url = env.queue.db.database_url
            await env.queue.db.close()

        with when("polling resumes cleanup and the requested enqueue after reopening"):
            async with Database(database_url) as db, queue_services(QueueManager(db), env.server) as recovered:
                await asyncio.gather(recovered.scheduler.sync_queue(), recovered.handler.handle(event))
                await recovered.scheduler.sync_queue()
                current = await recovered.queue.get_queue_item(123, 3)
                history = await recovered.queue.get_recent_history(project_id=123)
                updates = [call for call in recovered.websocket.broadcast_calls if call["type"] == "queue_updated"]

        with then("a fresh generation retains the explicit trigger and the old history"):
            assert current is not None
            assert current.queue_id != original.queue_id
            assert current.state == "queued"
            assert current.is_hotfix is hotfix
            assert current.started_at is None
            assert len(history) == 1
            assert history[0].started_at == original.started_at
            assert history[0].pipeline_id == 101
            assert env.server.mrs[0]["labels"] == [trigger]
            assert "Added to queue" in env.server.notes[3]
            assert updates[-1]["queue"][0]["mr_iid"] == 3
