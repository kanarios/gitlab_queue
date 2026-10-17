import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from gitlab_queue.core.state_machine import create_state_machine_for_mr

from ._helpers import ObservedQueue, label_event, queue_environment, queue_services


@scenario()
async def newer_enqueue_intent_survives_restore_ack():
    async with queue_environment() as base, queue_services(ObservedQueue(base.queue.db), base.server) as env:
        with given("a deferred enqueue whose trigger restoration is in flight"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing")
            original = await env.queue.get_queue_item(123, 3)
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            cleanup, run_cleanup = asyncio.Event(), asyncio.Event()
            restoring, finish_restore = asyncio.Event(), asyncio.Event()
            path = "/api/v4/projects/123/merge_requests/3"
            env.server.barriers[("PUT", path)] = (cleanup, run_cleanup)
            env.server.after_mutation_barriers[("add_labels", path)] = (restoring, finish_restore)
            machine = await create_state_machine_for_mr(
                123, 3, env.handler.notifier, env.queue, position_notifier=env.handler.position_notifier
            )
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Conflict")
            )
            await asyncio.wait_for(cleanup.wait(), 5)
            event = label_event("labeled", [], ["merge_queue"])
            event = replace(event, object_attributes=replace(event.object_attributes, updated_at=datetime.now(UTC)))
            enqueue = asyncio.create_task(env.handler.handle(event))
            await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
            env.server.barriers.clear()
            run_cleanup.set()
            await asyncio.wait_for(restoring.wait(), 5)

        with when("a newer hotfix enqueue is saved before the older restoration acknowledges"):
            env.server.mrs[0]["labels"] = ["merge_queue", "hotfix"]
            newer = label_event("labeled", ["merge_queue"], ["merge_queue", "hotfix"])
            newer = replace(newer, object_attributes=replace(newer.object_attributes, updated_at=datetime.now(UTC)))
            env.queue.requeue_saved.clear()
            promote = asyncio.create_task(env.handler.handle(newer))
            await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
            env.server.after_mutation_barriers.clear()
            finish_restore.set()
            await asyncio.wait_for(asyncio.gather(completion, enqueue, promote), 5)

        with then("only the newer request creates the replacement generation"):
            current = await env.queue.get_queue_item(123, 3)
            assert current.queue_id != original.queue_id
            assert current.state == "queued"
            assert current.is_hotfix is True
            assert current.labels == ["merge_queue", "hotfix"]
            assert len(await env.queue.get_recent_history(project_id=123)) == 1
            assert "Added to queue" in env.server.notes[3]
