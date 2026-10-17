from dataclasses import replace

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.state_machine import create_state_machine_for_mr

from ._helpers import label_event, queue_environment


@scenario([params("update", ["merge_queue"]), params("labeled", [])])
async def stale_enqueue_replay_does_not_restart_completed_lifecycle(action, previous):
    async with queue_environment() as env:
        with given("a completed failure and an older event that still contains its trigger"):
            original = await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing")
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            event = label_event(action, previous, ["merge_queue"])
            event = replace(event, object_attributes=replace(event.object_attributes, updated_at=original.queued_at))
            machine = await create_state_machine_for_mr(
                123, 3, env.handler.notifier, env.queue, position_notifier=env.handler.position_notifier
            )
            await machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Conflict")
            final_feedback = env.server.notes[3]

        with when("the old enqueue event is replayed after completion"):
            await env.handler.handle(event)
            await env.scheduler.sync_queue()

        with then("the completed lifecycle stays archived with its final feedback"):
            assert await env.queue.get_queue_item(123, 3) is None
            assert len(await env.queue.get_recent_history(project_id=123)) == 1
            assert env.server.notes[3] == final_feedback
