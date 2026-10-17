import json
from datetime import UTC, datetime, timedelta

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.queue_completion import QueueCompletion
from gitlab_queue.models.completion import CompletionRequest

from ._helpers import label_event, queue_environment


@scenario(
    [
        params("second", "failure"),
        params("millisecond", "failure"),
        params("second", "remove"),
        params("millisecond", "remove"),
        params("unknown", "failure"),
    ]
)
async def prior_promotion_is_consumed_before_completion(precision, outcome):
    async with queue_environment() as env:
        with given("an ordinary promotion causally applied before an outcome in the same source interval"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing")
            env.server.mrs = [mr_response(3, labels=["merge_queue", "hotfix"])]
            finished = datetime.now(UTC) + timedelta(seconds=1)
            source = (
                finished.strftime("%Y-%m-%d %H:%M:%S UTC")
                if precision == "second"
                else finished.isoformat(timespec="milliseconds")
            )
            if precision == "unknown":
                source = None
            event = label_event(
                "labeled",
                ["merge_queue"],
                ["merge_queue", "hotfix"],
                updated_at=source,
                message_id="consumed-promotion",
                user_id=99,
            )
            await env.handler.handle(event)
            item = await env.queue.get_queue_item(123, 3)
            assert item.is_hotfix is True
            assert json.loads(item.requeue_request)["applied_at"] is not None

        with when("completion consumes the prior action and its coarse replay arrives during ownership"):
            request = CompletionRequest(
                "failed" if outcome == "failure" else "removed",
                "conflict" if outcome == "failure" else "removed",
                "conflict" if outcome == "failure" else "removed_label",
                {
                    "failed_at" if outcome == "failure" else "removed_at": finished,
                    "target_branch": "main",
                    "conflicted_files": [],
                    "error_message": "Original outcome",
                    "position": 1,
                    "previous_state": "rebasing",
                },
                queue_id=item.queue_id,
            )
            await env.queue.prepare_completion(123, 3, request)
            await env.handler.handle(event)
            owned = await env.queue.get_queue_item(123, 3)
            assert owned.requeue_request is None
            if outcome == "remove":
                await env.handler.handle(
                    label_event(
                        "labeled",
                        [],
                        ["merge_queue"],
                        updated_at=(finished + timedelta(seconds=1)).isoformat(),
                        message_id="fresh-request",
                        user_id=99,
                    )
                )
                replacement = await env.queue.get_queue_item(123, 3)
                await env.handler.handle(event)
                unchanged = await env.queue.get_queue_item(123, 3)
                assert unchanged.queue_id == replacement.queue_id
                assert unchanged.is_hotfix is False
            await QueueCompletion(env.queue, env.handler.notifier, env.handler.position_notifier).recover_all(123)
            await env.scheduler.sync_queue()

        with then("the prior promotion cannot recreate or reprioritize a lifecycle"):
            current = await env.queue.get_queue_item(123, 3)
            if outcome == "remove":
                assert current.state == "queued" and current.is_hotfix is False
                assert env.server.mrs[0]["labels"] == ["merge_queue"]
            else:
                assert current is None
                assert env.server.mrs[0]["labels"] == []
            history = await env.queue.get_recent_history(project_id=123)
            assert len(history) == 1
            assert history[0].is_hotfix is True
            assert history[0].finished_at == finished
            if outcome == "failure":
                assert "Added to queue" not in env.server.notes[3]
