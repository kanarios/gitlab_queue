import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.state_machine import create_state_machine_for_mr

from ._helpers import ObservedQueue, label_event, queue_environment, queue_services


@scenario([params("user", [], 0), params("cleanup", [], 1), params("partial", ["hotfix"], 1)])
async def requeue_distinguishes_user_cancel_from_cleanup(removal, current_labels, expected_count):
    async with (
        queue_environment() as original_env,
        queue_services(ObservedQueue(original_env.queue.db), original_env.server) as env,
    ):
        with given("a deferred enqueue and a later label removal during old cleanup"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing")
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            before, run_cleanup = asyncio.Event(), asyncio.Event()
            after, finish_cleanup = asyncio.Event(), asyncio.Event()
            key = ("PUT", "/api/v4/projects/123/merge_requests/3")
            env.server.barriers[key] = (before, run_cleanup)
            env.server.after_barriers[key] = (after, finish_cleanup)
            machine = await create_state_machine_for_mr(
                123, 3, env.handler.notifier, env.queue, position_notifier=env.handler.position_notifier
            )
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Conflict")
            )
            await asyncio.wait_for(before.wait(), 5)
            enqueue_event = label_event("labeled", [], ["merge_queue", "hotfix"])
            enqueue_event = replace(
                enqueue_event, object_attributes=replace(enqueue_event.object_attributes, updated_at=datetime.now(UTC))
            )
            enqueue = asyncio.create_task(env.handler.handle(enqueue_event))
            await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
            run_cleanup.set()
            await asyncio.wait_for(after.wait(), 5)
            own_event_at = datetime.fromisoformat(env.server.mrs[0]["updated_at"])
            event_at = {"user": datetime.now(UTC), "partial": datetime.now(UTC), "cleanup": own_event_at}[removal]
            env.server.mrs[0]["labels"] = current_labels
            cancel_event = label_event("unlabeled", ["merge_queue", "hotfix"], current_labels)
            cancel_event = replace(
                cancel_event, object_attributes=replace(cancel_event.object_attributes, updated_at=event_at)
            )
            changed = {
                "user": env.queue.requeue_cancelled,
                "cleanup": env.queue.requeue_cancelled,
                "partial": env.queue.requeue_saved,
            }[removal]
            changed.clear()
            cancel = asyncio.create_task(env.handler.handle(cancel_event))
            await asyncio.wait_for(changed.wait(), 5)

        with when("completion and all overlapping events finish"):
            env.server.barriers.clear()
            env.server.after_barriers.clear()
            finish_cleanup.set()
            await asyncio.wait_for(asyncio.gather(completion, enqueue, cancel), 5)
            await env.scheduler.sync_queue()

        with then("only a user cancellation discards the deferred enqueue"):
            assert len(await env.queue.get_active_queue(123)) == expected_count
            assert len(await env.queue.get_recent_history(project_id=123)) == 1
