import asyncio
from contextlib import suppress
from datetime import UTC, datetime

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.db.database import Database

from ._helpers import ObservedQueue, label_event, queue_environment, queue_services


@scenario(
    [
        params(True, True, "early"),
        params(False, True, "early"),
        params(False, False, "early"),
        params(False, False, "late"),
        params(False, False, "late_user_cancel"),
    ]
)
async def cleanup_provenance_survives_lost_ack(echo_uuid, bot, delivery):
    async with queue_environment() as base, queue_services(ObservedQueue(base.queue.db), base.server) as env:
        with given("an explicit enqueue and a delivered own cleanup webhook before HTTP acknowledgment"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing")
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            env.server.authenticated_user = {"id": 1, "bot": bot}
            before, run = asyncio.Event(), asyncio.Event()
            after, finish = asyncio.Event(), asyncio.Event()
            key = ("PUT", "/api/v4/projects/123/merge_requests/3")
            env.server.barriers[key] = (before, run)
            env.server.after_barriers[key] = (after, finish)
            machine = await create_state_machine_for_mr(
                123, 3, env.handler.notifier, env.queue, position_notifier=env.handler.position_notifier
            )
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=[], error_message="Conflict")
            )
            await asyncio.wait_for(before.wait(), 5)
            enqueue = asyncio.create_task(
                env.handler.handle(label_event("labeled", [], ["hotfix"], updated_at=datetime.now(UTC).isoformat()))
            )
            await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
            run.set()
            await asyncio.wait_for(after.wait(), 5)
            operation = env.server.label_requests[-1].headers.get("X-Gitlab-Event-UUID") if echo_uuid else None
            reported_at = env.server.mrs[0]["updated_at"]
            if delivery.startswith("late"):
                reported_at = datetime.fromisoformat(reported_at).strftime("%Y-%m-%d %H:%M:%S UTC")
                env.server.barriers.clear()
                env.server.after_barriers.clear()
                finish.set()
                await asyncio.wait_for(asyncio.gather(completion, enqueue), 5)
                replacement = await env.queue.get_queue_item(123, 3)
                assert replacement.state == "queued"
                if delivery == "late_user_cancel":
                    reported_at = datetime.now(UTC).isoformat()
                    env.server.mrs[0]["labels"] = []
            own = asyncio.create_task(
                env.handler.handle(
                    label_event(
                        "unlabeled",
                        ["merge_queue"],
                        [],
                        updated_at=reported_at,
                        event_uuid=operation,
                        user_id=42 if delivery == "late_user_cancel" else 1,
                    )
                )
            )
            await asyncio.wait_for(own, 5)
            if delivery == "late":
                current = await env.queue.get_queue_item(123, 3)
                assert current is not None
                assert current.queue_id == replacement.queue_id
                assert "Added to queue" in env.server.notes[3]
            if delivery == "late_user_cancel":
                assert await env.queue.get_queue_item(123, 3) is None

        with when("the process stops before the mutation response and reopens its database"):
            for task in (completion, enqueue, own):
                task.cancel()
            for task in (completion, enqueue, own):
                with suppress(asyncio.CancelledError):
                    await task
            env.server.barriers.clear()
            env.server.after_barriers.clear()
            async with (
                Database(env.queue.db.database_url) as reopened,
                queue_services(QueueManager(reopened), env.server) as recovered,
            ):
                await recovered.scheduler.sync_queue()

        with then("the persisted operation provenance protects the explicit request"):
            current = await base.queue.get_queue_item(123, 3)
            if delivery == "late_user_cancel":
                assert current is None
                assert env.server.mrs[0]["labels"] == []
            else:
                assert current is not None
                assert current.is_hotfix is True
                assert env.server.mrs[0]["labels"] == ["hotfix"]
            assert len(await base.queue.get_recent_history(project_id=123)) == 1
