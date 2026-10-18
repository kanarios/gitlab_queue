import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from scenarios.core.hotfix_priority._helpers import label_event, queue_services
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.models.completion import CompletionRequest

from ._helpers import automation_environment


async def owned_lifecycle(env):
    original = await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
    await env.queue.update_mr_state(123, 3, "rebasing", pipeline_id=101)
    request = CompletionRequest(
        "failed",
        "failed",
        "generic_failure",
        {"error_message": "Original failure", "failed_at": datetime.now(UTC)},
        queue_id=original.queue_id,
    )
    return await env.queue.prepare_completion(123, 3, request)


async def admit_future(env, owned, labels, requested_at):
    await env.queue.defer_requeue(
        123,
        owned,
        {
            "triggers": ["merge_queue"],
            "labels": labels,
            "is_hotfix": False,
            "requested_at": requested_at.isoformat(),
            "precision_us": 1,
            "message_id": "old-format-request",
            "cancelled_events": [],
        },
    )


@scenario()
async def automation_only_event_during_completion_does_not_create_a_future_request():
    async with automation_environment() as env:
        with given("an owned lifecycle without any explicit replacement admission"):
            await owned_lifecycle(env)
            env.server.mrs = [mr_response(3, labels=["merge_queue", "dependencies"])]

        with when("a newer automation-only label event overlaps completion"):
            await env.handler.handle(
                label_event(
                    "labeled",
                    ["merge_queue"],
                    ["merge_queue", "dependencies"],
                    updated_at=datetime.now(UTC).isoformat(),
                )
            )

        with then("only the old lifecycle completes and its independent automation label remains"):
            assert await env.queue.get_queue_item(123, 3) is None
            assert len(await env.queue.get_recent_history(project_id=123)) == 1
            assert env.server.mrs[0]["labels"] == ["dependencies"]


@scenario()
async def automation_only_event_does_not_resurrect_a_cancelled_replacement():
    async with automation_environment() as env:
        with given("an explicitly admitted then cancelled future generation"):
            owned = await owned_lifecycle(env)
            requested_at = datetime.now(UTC)
            await admit_future(env, owned, ["merge_queue"], requested_at)
            await env.queue.cancel_requeue(123, owned.queue_id, requested_at + timedelta(seconds=1))
            env.server.mrs = [mr_response(3, labels=["dependencies"])]

        with when("a later automation-only event arrives without a queue trigger"):
            await env.handler.handle(
                label_event(
                    "labeled", [], ["dependencies"], updated_at=(requested_at + timedelta(seconds=2)).isoformat()
                )
            )

        with then("the cancelled request remains cancelled without a replacement"):
            assert await env.queue.get_queue_item(123, 3) is None
            assert len(await env.queue.get_recent_history(project_id=123)) == 1
            assert env.server.mrs[0]["labels"] == ["dependencies"]


@scenario([params((), "ordinary"), params(("renovate",), "automated")])
async def old_requeue_payload_uses_current_project_policy_after_reopen(automation_labels, expected):
    async with automation_environment() as env:
        with given("an old-format durable request saved before a project policy restart"):
            owned = await owned_lifecycle(env)
            await admit_future(env, owned, ["merge_queue", "renovate"], datetime.now(UTC))
            pending = json.loads((await env.queue.get_queue_item(123, 3)).pending_completion)
            env.server.mrs = [mr_response(3, labels=["merge_queue", "renovate"])]
            database_url = env.queue.db.database_url
            await env.queue.db.close()
            policy = replace(env.settings.config, automation_labels=automation_labels)
            settings = replace(env.settings, config=policy)

        with when("the new policy activates before polling recovers the old request"):
            async with Database(database_url) as database:
                queue = QueueManager(database, project_policies={123: policy})
                await queue.activate_priorities(123)
                async with queue_services(queue, env.server, settings) as recovered:
                    await recovered.scheduler.sync_queue()
                    current = await queue.get_queue_item(123, 3)
                    history = await queue.get_recent_history(project_id=123)

        with then("replacement classification is fresh and the frozen original history stays unchanged"):
            assert current.queue_id != owned.queue_id
            assert current.priority == expected
            assert current.labels == ["merge_queue", "renovate"]
            assert current.started_at is None
            assert len(history) == 1
            assert history[0].pipeline_id == 101
            assert history[0].queued_at.isoformat() == pending["history"]["queued_at"]
            assert "is_automated" not in pending["history"]
            assert "priority" not in pending["history"]
