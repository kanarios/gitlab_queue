import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from scenarios.fakes import create_mr
from scenarios.integration.repositories._helpers import create_test_mr_model
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.core.types import ProcessingResult
from gitlab_queue.db.repositories import MergeRequestRepository

from ._helpers import label_event, queue_environment


def hotfix_event(iid, previous):
    event = label_event("update", previous, ["hotfix"], updated_at=datetime.now(UTC).isoformat())
    return replace(event, object_attributes=replace(event.object_attributes, iid=iid))


@scenario()
async def equal_queue_timestamps_preserve_entry_order():
    async with queue_environment() as env:
        with given("three hotfixes with the same timestamp and a different numerical IID order"):
            timestamp = datetime(2026, 10, 17, tzinfo=UTC).isoformat()
            async with env.queue.db.transaction() as session:
                repository = MergeRequestRepository(session, project_id=123)
                for iid in (7, 2, 9):
                    await repository.add(
                        create_test_mr_model(iid=iid, is_hotfix=1, labels='["hotfix"]', queued_at=timestamp)
                    )

        with when("the queue and next candidate are read"):
            items = await env.queue.get_active_queue(123)
            next_mr = await env.queue.get_next_mr(123)

        with then("equal timestamps are ordered by stable entry identity"):
            assert [item.mr_iid for item in items] == [7, 2, 9]
            assert len({item.queued_at for item in items}) == 1
            assert [item.queue_id for item in items] == sorted(item.queue_id for item in items)
            assert next_mr.mr_iid == 7


@scenario()
async def older_promoted_entry_precedes_newer_hotfixes():
    async with queue_environment() as env:
        with given("an older ordinary entry and two newer hotfixes"):
            await env.queue.add_to_queue(123, create_mr(iid=90))
            original = await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.add_to_queue(123, create_mr(iid=40, labels=["hotfix"]), is_hotfix=True)
            await env.queue.add_to_queue(123, create_mr(iid=10, labels=["hotfix"]), is_hotfix=True)

        with when("the older entry gains hotfix priority"):
            await env.handler.handle(hotfix_event(3, ["merge_queue"]))

        with then("its preserved entry identity places it ahead of the newer hotfixes"):
            items = await env.queue.get_active_queue(123)
            assert [item.mr_iid for item in items] == [3, 40, 10, 90]
            assert (items[0].queue_id, items[0].queued_at) == (original.queue_id, original.queued_at)
            assert "**Position:** 1 of 4" in env.server.notes[3]


@scenario()
async def concurrent_distinct_hotfix_admissions_preserve_both_entries():
    async with queue_environment() as env:
        with given("two different new hotfix MRs delivered concurrently"):
            env.server.mrs = [mr_response(40, labels=["hotfix"]), mr_response(10, labels=["hotfix"])]

        with when("both webhook handlers admit their merge request"):
            await asyncio.gather(env.handler.handle(hotfix_event(40, [])), env.handler.handle(hotfix_event(10, [])))

        with then("both remain queued in their actual insertion order"):
            items = await env.queue.get_active_queue(123)
            assert len(items) == 2
            assert {item.mr_iid for item in items} == {40, 10}
            assert [item.queue_id for item in items] == sorted(item.queue_id for item in items)
            assert [item.is_hotfix for item in items] == [True, True]
            assert (await env.queue.get_next_mr(123)).queue_id == min(item.queue_id for item in items)


@dataclass
class PausedWorkflowProcessor(MergeProcessor):
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)
    execution: list[int] = field(default_factory=list)

    async def _execute_workflow(self, context):
        self.execution.append(context.mr_iid)
        await context.state_machine.trigger_start_processing()
        await self.queue_manager.update_mr_state(
            context.project_id, context.mr_iid, "rebasing", pipeline_id=777, expected_sha="running-sha"
        )
        self.entered.set()
        await self.release.wait()
        item = await self.queue_manager.get_queue_item(context.project_id, context.mr_iid)
        await self.queue_manager.complete_mr(
            context.project_id, context.mr_iid, "merged", expected_queue_id=item.queue_id
        )
        return ProcessingResult.SUCCESS


@scenario()
async def arriving_hotfix_does_not_preempt_running_merge_request():
    async with queue_environment() as env:
        with given("a processor paused inside the first MR's real processing state"):
            await env.queue.add_to_queue(123, create_mr(iid=100))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.mrs = [mr_response(100, labels=["merge_queue"]), mr_response(3, labels=["merge_queue"])]
            processor = PausedWorkflowProcessor(
                env.gitlab, env.queue, env.handler.notifier, env.settings, env.handler.position_notifier
            )
            running = asyncio.create_task(processor.run())
            await asyncio.wait_for(processor.entered.wait(), 5)
            original = await env.queue.get_queue_item(123, 100)
            env.server.mrs.append(mr_response(40, labels=["hotfix"]))

        with when("a different hotfix is admitted while that workflow remains in flight"):
            await env.handler.handle(hotfix_event(40, []))
            current = await env.queue.get_queue_item(123, 100)
            next_mr = await env.queue.get_next_mr(123)
            queue = await env.queue.get_active_queue(123)
            processor.request_shutdown()
            still_running = not running.done()
            current_iid = processor.current_mr_iid
            processor.release.set()
            await asyncio.wait_for(running, 5)

        with then("the active workflow is preserved and the hotfix becomes the next candidate"):
            assert still_running is True
            assert current_iid == 100
            assert processor.execution == [100]
            assert current.state == "rebasing"
            assert current.started_at == original.started_at
            assert current.pipeline_id == 777
            assert current.expected_sha == "running-sha"
            assert [item.mr_iid for item in queue] == [40, 100, 3]
            assert next_mr.mr_iid == 40
            assert [item["mr_iid"] for item in env.websocket.broadcast_calls[-1]["queue"]] == [40, 100, 3]
