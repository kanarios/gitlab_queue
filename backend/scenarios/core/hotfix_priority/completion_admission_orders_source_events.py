import asyncio
import json
from datetime import datetime, timedelta

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.state_machine import create_state_machine_for_mr

from ._helpers import ObservedQueue, label_event, queue_environment, queue_services


@scenario(
    [
        params("second"),
        params("millisecond"),
        params("newer_same_trigger"),
        params("second_old"),
        params("millisecond_old"),
        params("ambiguous_cancel_first"),
        params("ambiguous_cancel_last"),
        params("duplicate_message"),
        params("overlap_preserves_uncertainty"),
    ]
)
async def completion_admission_orders_source_events(case):
    async with queue_environment() as base, queue_services(ObservedQueue(base.queue.db), base.server) as env:
        tasks = []
        with given("terminal cleanup in flight on a real migrated database"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing")
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            entered, release = asyncio.Event(), asyncio.Event()
            path = "/api/v4/projects/123/merge_requests/3"
            env.server.barriers[("PUT", path)] = (entered, release)
            machine = await create_state_machine_for_mr(123, 3, env.handler.notifier, env.queue)
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=[], error_message="Conflict")
            )
            tasks.append(completion)
            await asyncio.wait_for(entered.wait(), 5)
            item = await env.queue.get_queue_item(123, 3)
            started = datetime.fromisoformat(json.loads(item.pending_completion)["finished_at"])
            if case == "second_old":
                timestamp = (started - timedelta(seconds=2)).strftime("%Y-%m-%d %H:%M:%S UTC")
            elif case == "millisecond_old":
                timestamp = (started - timedelta(seconds=2)).isoformat(timespec="milliseconds")
            elif case == "second" or case.startswith("ambiguous") or case == "overlap_preserves_uncertainty":
                timestamp = started.strftime("%Y-%m-%d %H:%M:%S UTC")
            elif case == "millisecond":
                timestamp = started.isoformat(timespec="milliseconds")
            else:
                timestamp = (started + timedelta(seconds=1)).isoformat()

        with when("a later enqueue is reported with its source timestamp precision"):
            if case == "ambiguous_cancel_first":
                env.queue.requeue_cancelled.clear()
                tasks.append(
                    asyncio.create_task(
                        env.handler.handle(label_event("unlabeled", ["hotfix"], [], updated_at=timestamp))
                    )
                )
                await asyncio.wait_for(env.queue.requeue_cancelled.wait(), 5)
            event = label_event("labeled", [], ["hotfix"], updated_at=timestamp, message_id="first")
            enqueue = asyncio.create_task(env.handler.handle(event))
            tasks.append(enqueue)
            if not case.endswith("_old"):
                await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
            if case == "ambiguous_cancel_last":
                env.queue.requeue_cancelled.clear()
                tasks.append(
                    asyncio.create_task(
                        env.handler.handle(label_event("unlabeled", ["hotfix"], [], updated_at=timestamp))
                    )
                )
                await asyncio.wait_for(env.queue.requeue_cancelled.wait(), 5)
            if case == "duplicate_message":
                saved = json.loads((await env.queue.get_queue_item(123, 3)).requeue_request)["token"]
                env.queue.requeue_saved.clear()
                tasks.append(asyncio.create_task(env.handler.handle(event)))
                await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
                assert json.loads((await env.queue.get_queue_item(123, 3)).requeue_request)["token"] == saved
            if case == "overlap_preserves_uncertainty":
                end = started.replace(microsecond=0) + timedelta(seconds=1)
                newer_at = started + (end - started) / 3
                cancel_at = started + 2 * (end - started) / 3
                env.queue.requeue_saved.clear()
                tasks.append(
                    asyncio.create_task(
                        env.handler.handle(label_event("labeled", [], ["hotfix"], updated_at=newer_at.isoformat()))
                    )
                )
                await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
                env.queue.requeue_cancelled.clear()
                tasks.append(
                    asyncio.create_task(
                        env.handler.handle(label_event("unlabeled", ["hotfix"], [], updated_at=cancel_at.isoformat()))
                    )
                )
                await asyncio.wait_for(env.queue.requeue_cancelled.wait(), 5)
            if case == "newer_same_trigger":
                env.queue.requeue_saved.clear()
                newer = label_event(
                    "labeled",
                    [],
                    ["hotfix"],
                    updated_at=(started + timedelta(seconds=3)).isoformat(),
                    message_id="newer",
                )
                tasks.append(asyncio.create_task(env.handler.handle(newer)))
                await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
                env.queue.requeue_cancelled.clear()
                middle = label_event(
                    "unlabeled",
                    ["hotfix"],
                    [],
                    updated_at=(started + timedelta(seconds=2)).isoformat(),
                    message_id="middle",
                )
                tasks.append(asyncio.create_task(env.handler.handle(middle)))
                await asyncio.wait_for(env.queue.requeue_cancelled.wait(), 5)
            env.server.barriers.clear()
            release.set()
            await asyncio.wait_for(asyncio.gather(*tasks), 5)

        with then("the newest requested hotfix is admitted exactly once"):
            current = await env.queue.get_queue_item(123, 3)
            if case.endswith("_old"):
                assert current is None
                assert env.server.mrs[0]["labels"] == []
            else:
                assert current is not None
                assert current.state == "queued"
                assert current.is_hotfix is True
                assert env.server.mrs[0]["labels"] == ["hotfix"]
            assert len(await env.queue.get_recent_history(project_id=123)) == 1
