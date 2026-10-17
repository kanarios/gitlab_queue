import asyncio
from dataclasses import replace

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.state_machine import create_state_machine_for_mr

from ._helpers import ObservedQueue, label_event, queue_environment, queue_services


@scenario([params("update", ["merge_queue"]), params("labeled", [])])
async def plain_update_during_completion_does_not_request_requeue(action, previous):
    async with queue_environment() as base, queue_services(ObservedQueue(base.queue.db), base.server) as env:
        with given("old trigger labels while completion's cleanup request waits"):
            original = await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing")
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("PUT", "/api/v4/projects/123/merge_requests/3")] = (entered, release)
            machine = await create_state_machine_for_mr(
                123, 3, env.handler.notifier, env.queue, position_notifier=env.handler.position_notifier
            )
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Conflict")
            )
            await asyncio.wait_for(entered.wait(), 5)
            event = label_event(action, previous, ["merge_queue"])
            event = replace(event, object_attributes=replace(event.object_attributes, updated_at=original.queued_at))

        with when("a plain update or old label replay overlaps cleanup"):
            env.queue.item_read.clear()
            update = asyncio.create_task(env.handler.handle(event))
            await asyncio.wait_for(env.queue.item_read.wait(), 5)
            release.set()
            await asyncio.wait_for(asyncio.gather(completion, update), 5)

        with then("only the original lifecycle completes"):
            assert await env.queue.get_queue_item(123, 3) is None
            assert len(await env.queue.get_recent_history(project_id=123)) == 1
            assert "Rebase conflict" in env.server.notes[3]
