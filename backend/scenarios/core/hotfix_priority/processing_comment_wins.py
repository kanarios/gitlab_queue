import asyncio

from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.state_machine import create_state_machine_for_mr

from ._helpers import ObservedQueue, label_event, queue_environment


@scenario()
async def processing_comment_wins_for_later_recipient():
    async with queue_environment() as env:
        with given("priority feedback pauses before another recipient begins processing"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=2))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("POST", "/api/v4/projects/123/merge_requests/3/notes")] = (entered, release)
            second_queue = QueueManager(env.queue.db)
            second_notifier = MRNotifier(env.gitlab, env.settings, second_queue)
            processing = await create_state_machine_for_mr(123, 1, second_notifier, second_queue, target_branch="main")

        with when("the recipient starts processing during the priority notification batch"):
            update = asyncio.create_task(
                env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            )
            await asyncio.wait_for(entered.wait(), 5)
            await processing.trigger_start_processing()
            release.set()
            await asyncio.wait_for(update, 5)

        with then("the processing comment survives the remaining batch"):
            assert "**Status:** 🔄 Rebasing" in env.server.notes[1]
            assert [iid for iid, body in env.server.comments] == [1, 3, 2]
            assert (await env.queue.get_queue_item(123, 1)).state == "rebasing"


@scenario()
async def processing_comment_wins_for_same_recipient():
    async with queue_environment() as env:
        with given("two notifiers share a database and the initial priority comment is in flight"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("POST", "/api/v4/projects/123/merge_requests/3/notes")] = (entered, release)
            second_queue = ObservedQueue(env.queue.db)
            second_notifier = MRNotifier(env.gitlab, env.settings, second_queue)
            processing = await create_state_machine_for_mr(123, 3, second_notifier, second_queue, target_branch="main")

        with when("processing changes state while the same MR's priority write awaits HTTP"):
            update = asyncio.create_task(
                env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            )
            await asyncio.wait_for(entered.wait(), 5)
            transition = asyncio.create_task(processing.trigger_start_processing())
            await asyncio.wait_for(second_queue.state_updated.wait(), 5)
            release.set()
            await asyncio.wait_for(asyncio.gather(update, transition), 5)

        with then("processing updates the single comment after the waiting write finishes"):
            assert "**Status:** 🔄 Rebasing" in env.server.notes[3]
            assert env.server.comment_methods == ["POST", "PUT"]
            assert (await env.queue.get_queue_item(123, 3)).state == "rebasing"
