import asyncio
from dataclasses import replace

from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from ._helpers import automation_environment


@scenario()
async def concurrent_duplicate_automation_relabel_has_one_effective_change_and_feedback_batch():
    async with automation_environment() as env:
        with given("two simultaneous deliveries of the same automation-only label addition"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            await env.queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
            event = label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"], message_id="same-message")
        with when("both public handlers run concurrently"):
            await asyncio.gather(env.handler.handle(event), env.handler.handle(event))
            current = await env.queue.get_queue_item(123, 3)
        with then("one atomic transition owns one note per affected recipient and one full snapshot"):
            assert current.metadata_version == 1
            assert [item.mr_iid for item in await env.queue.get_active_queue(123)] == [2, 3]
            assert env.server.comment_attempts == [3, 2]
            assert len(env.websocket.broadcast_calls) == 1


@scenario([params(3, 2, [3, 2]), params(2, 3, [2, 3])])
async def distinct_simultaneous_automated_arrivals_keep_the_allocated_id_fifo(first, second, expected):
    async with automation_environment() as env:
        with given("two distinct automated arrivals waiting on independent external HTTP barriers"):
            labels = ["merge_queue", "dependencies"]
            env.server.mrs = [mr_response(3, labels=labels), mr_response(2, labels=labels)]
            entered = {iid: asyncio.Event() for iid in (3, 2)}
            release = {iid: asyncio.Event() for iid in (3, 2)}
            env.server.barriers = {
                ("GET", f"/api/v4/projects/123/merge_requests/{iid}"): (entered[iid], release[iid]) for iid in (3, 2)
            }
            event = label_event("labeled", [], labels)
            tasks = {
                iid: asyncio.create_task(
                    env.handler.handle(
                        replace(
                            event,
                            object_attributes=replace(event.object_attributes, iid=iid),
                            message_id=f"arrival-{iid}",
                        )
                    )
                )
                for iid in (3, 2)
            }
            await asyncio.wait_for(asyncio.gather(*(item.wait() for item in entered.values())), 5)
        with when("the controlled commit schedules complete in either arrival order"):
            try:
                release[first].set()
                await asyncio.wait_for(tasks[first], 5)
                release[second].set()
                await asyncio.wait_for(tasks[second], 5)
            finally:
                for item in release.values():
                    item.set()
                await asyncio.wait_for(asyncio.gather(*tasks.values()), 5)
            rows = await env.queue.get_active_queue(123)
        with then("FIFO follows the original assigned row IDs rather than IID or task scheduling"):
            assert [item.mr_iid for item in rows] == expected
            assert [item.priority for item in rows] == ["automated", "automated"]
            assert rows[0].queue_id < rows[1].queue_id
