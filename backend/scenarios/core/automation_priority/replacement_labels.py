import asyncio
import json
from datetime import UTC, datetime, timedelta

from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.models.completion import CompletionRequest

from ._helpers import automation_environment


@scenario(
    [
        params(["merge_queue"], ["merge_queue", "dependencies"], 1, ["merge_queue", "dependencies"], "automated"),
        params(["merge_queue", "dependencies"], ["merge_queue"], 1, ["merge_queue"], "ordinary"),
        params(["merge_queue", "dependencies"], ["merge_queue"], -1, ["merge_queue", "dependencies"], "automated"),
        params(["merge_queue"], ["merge_queue", "dependencies"], 0, ["merge_queue", "dependencies"], "automated"),
    ]
)
async def automation_only_relabel_updates_an_admitted_future_generation(previous, current, seconds, expected, priority):
    async with automation_environment() as env:
        with given("an owned failed lifecycle and an explicit ordinary replacement request"):
            original = await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            await env.queue.update_mr_state(123, 3, "rebasing", pipeline_id=101)
            original = await env.queue.get_queue_item(123, 3)
            owned = await env.queue.prepare_completion(
                123,
                3,
                CompletionRequest(
                    "failed",
                    "failed",
                    "generic_failure",
                    {"error_message": "Original failure", "failed_at": datetime.now(UTC)},
                    queue_id=original.queue_id,
                ),
            )
            requested_at = datetime.now(UTC) + timedelta(seconds=2)
            await env.queue.defer_requeue(
                123,
                owned,
                {
                    "queue_id": original.queue_id,
                    "triggers": ["merge_queue"],
                    "labels": previous,
                    "is_hotfix": False,
                    "requested_at": requested_at.isoformat(),
                    "precision_us": 1,
                    "message_id": "explicit-requeue",
                    "cancelled_events": [],
                },
            )
            saved = json.loads((await env.queue.get_queue_item(123, 3)).requeue_request)
            env.server.mrs = [mr_response(3, labels=expected)]
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.after_mutation_barriers[("remove_labels", "/api/v4/projects/123/merge_requests/3")] = (
                entered,
                release,
            )
            event = label_event(
                "labeled",
                previous,
                current,
                updated_at=(requested_at + timedelta(seconds=seconds)).isoformat(),
                message_id="automation-only",
            )

        with when("the automation-only webhook arrives before replacement cleanup finishes"):
            handling = asyncio.create_task(env.handler.handle(event))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                pending = json.loads((await env.queue.get_queue_item(123, 3)).requeue_request)
            finally:
                release.set()
                await asyncio.wait_for(handling, 5)
            replacement = await env.queue.get_queue_item(123, 3)
            history = await env.queue.get_recent_history(project_id=123)

        with then("the new incarnation uses the final labels without renewing admission provenance"):
            assert json.loads(pending["params"]["labels"]) == expected
            assert pending["requested_at"] == saved["requested_at"]
            assert pending["precision_us"] == saved["precision_us"]
            assert pending["token"] == saved["token"]
            assert pending["seen_messages"] == saved["seen_messages"]
            assert replacement.queue_id != original.queue_id
            assert replacement.priority == priority
            assert replacement.labels == expected
            assert replacement.started_at is None
            assert len(history) == 1
            assert history[0].started_at == original.started_at
            assert history[0].pipeline_id == 101
            assert set(env.server.mrs[0]["labels"]) == set(expected)
