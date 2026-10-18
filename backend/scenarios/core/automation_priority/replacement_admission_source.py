import json
from datetime import UTC, datetime, timedelta

from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from ._helpers import automation_environment
from .replacement_policy import admit_future, owned_lifecycle


def label_source_override(base, second):
    if second is None:
        return {}
    return {"label_snapshot": {"requested_at": (base + timedelta(seconds=second)).isoformat(), "precision_us": 1}}


@scenario(
    [
        params(
            ["merge_queue"],
            ["merge_queue", "dependencies"],
            ["merge_queue"],
            20,
            None,
            1,
            ["merge_queue", "dependencies"],
            "automated",
            30,
            1,
        ),
        params(
            ["merge_queue", "dependencies"],
            ["merge_queue"],
            ["merge_queue", "dependencies"],
            20,
            None,
            1,
            ["merge_queue"],
            "ordinary",
            30,
            1,
        ),
        params(
            ["merge_queue"],
            ["merge_queue", "dependencies"],
            ["merge_queue"],
            40,
            None,
            1,
            ["merge_queue"],
            "ordinary",
            40,
            1,
        ),
        params(
            ["merge_queue", "dependencies"],
            ["merge_queue"],
            ["merge_queue", "dependencies"],
            40,
            None,
            1,
            ["merge_queue", "dependencies"],
            "automated",
            40,
            1,
        ),
        params(
            ["merge_queue"],
            ["merge_queue", "dependencies"],
            ["merge_queue"],
            20,
            None,
            20_000_000,
            ["merge_queue", "dependencies"],
            "automated",
            20,
            20_000_000,
        ),
        params(
            ["merge_queue", "dependencies"],
            ["merge_queue"],
            ["merge_queue", "dependencies"],
            20,
            None,
            20_000_000,
            ["merge_queue", "dependencies"],
            "automated",
            20,
            20_000_000,
        ),
        params(
            ["merge_queue"],
            ["merge_queue", "dependencies"],
            ["merge_queue"],
            40,
            20,
            1,
            ["merge_queue", "dependencies"],
            "automated",
            30,
            1,
        ),
    ]
)
async def replacement_admission_preserves_independently_ordered_label_snapshot(
    initial,
    latest,
    incoming,
    admission_second,
    label_second,
    precision,
    expected,
    priority,
    clock_second,
    clock_precision,
):
    async with automation_environment() as env:
        with given("an original admission at t10 and an independently refreshed full label snapshot at t30"):
            owned = await owned_lifecycle(env)
            base = datetime.now(UTC) + timedelta(seconds=10)
            await admit_future(env, owned, initial, base + timedelta(seconds=10))
            await env.queue.refresh_requeue_labels(123, owned.queue_id, latest, base + timedelta(seconds=30))
            before = json.loads((await env.queue.get_queue_item(123, 3)).requeue_request)
            env.server.mrs = [mr_response(3, labels=expected)]

        with when("a distinct explicit admission is accepted and the owned generation completes"):
            accepted = await env.queue.defer_requeue(
                123,
                owned,
                {
                    "triggers": ["merge_queue"],
                    "labels": incoming,
                    "is_hotfix": False,
                    "requested_at": (base + timedelta(seconds=admission_second)).isoformat(),
                    "precision_us": precision,
                    "message_id": "second-admission",
                    "cancelled_events": [],
                    **label_source_override(base, label_second),
                },
            )
            pending = json.loads((await env.queue.get_queue_item(123, 3)).requeue_request)
            await env.scheduler.sync_queue()
            replacement = await env.queue.get_queue_item(123, 3)
            history = await env.queue.get_recent_history(project_id=123)

        with then("admission provenance advances while label source order independently controls classification"):
            assert accepted is True
            assert json.loads(pending["params"]["labels"]) == expected
            assert pending["label_snapshot"] == {
                "requested_at": (base + timedelta(seconds=clock_second)).isoformat(),
                "precision_us": clock_precision,
            }
            assert pending["requested_at"] == (base + timedelta(seconds=admission_second)).isoformat()
            assert pending["seen_messages"] == [*before["seen_messages"], "second-admission"]
            assert pending["token"] != before["token"]
            assert pending["triggers"] == ["merge_queue"]
            assert replacement.queue_id != owned.queue_id
            assert replacement.priority == priority
            assert replacement.labels == expected
            assert replacement.started_at is None
            assert len(history) == 1
            assert history[0].pipeline_id == 101
            assert history[0].queued_at == owned.queued_at
            assert set(env.server.mrs[0]["labels"]) == set(expected)
