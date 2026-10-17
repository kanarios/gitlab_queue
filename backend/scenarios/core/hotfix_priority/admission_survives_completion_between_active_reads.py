import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.queue_completion import QueueCompletion
from gitlab_queue.models.completion import CompletionRequest

from ._helpers import label_event, queue_environment, queue_services


@dataclass
class PausedActiveQueue(QueueManager):
    pause_read: int = 0
    reads: int = 0
    captured: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def get_queue_item(self, project_id, mr_iid):
        item = await super().get_queue_item(project_id, mr_iid)
        if self.pause_read and item is not None and item.state == "rebasing":
            self.reads += 1
            if self.reads == self.pause_read:
                self.captured.set()
                await self.release.wait()
        return item


@scenario(
    [
        params("labeled", 1, True),
        params("update", 1, True),
        params("labeled", 2, True),
        params("update", 2, True),
        params("labeled", 2, False),
        params("update", 2, False),
        params("labeled", 3, False),
        params("update", 3, False),
    ]
)
async def admission_survives_completion_between_active_reads(action, boundary, timestamped):
    async with queue_environment() as base, queue_services(PausedActiveQueue(base.queue.db), base.server) as env:
        with given("a later explicit hotfix event paused after a real active snapshot"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing", pipeline_id=101, expected_sha="original")
            original = await env.queue.get_queue_item(123, 3)
            outcome_at = datetime.now(UTC)
            env.server.mrs = [mr_response(3, labels=["merge_queue", "hotfix"])]
            event = label_event(
                action,
                ["merge_queue"],
                ["merge_queue", "hotfix"],
                updated_at=(outcome_at + timedelta(seconds=1)).isoformat() if timestamped else None,
                user_id=99,
                message_id=f"{action}-{boundary}-{timestamped}",
            )
            env.queue.pause_read = boundary
            handling = asyncio.create_task(env.handler.handle(event))
            await asyncio.wait_for(env.queue.captured.wait(), 5)
            request = CompletionRequest(
                "failed",
                "conflict",
                "conflict",
                {
                    "failed_at": outcome_at,
                    "target_branch": "main",
                    "error_message": "Original conflict",
                    "conflicted_files": [],
                },
                queue_id=original.queue_id,
            )
            owned = await env.queue.prepare_completion(123, 3, request)
            assert owned.pending_completion is not None
            env.queue.release.set()

        with when("handling resumes and owned completion is recovered"):
            await asyncio.wait_for(handling, 5)
            await QueueCompletion(
                env.queue, env.handler.notifier, env.handler.position_notifier, env.websocket
            ).recover_all(123)
            await env.scheduler.sync_queue()
            current = await env.queue.get_queue_item(123, 3)
            history = await env.queue.get_recent_history(project_id=123)

        with then("one fresh hotfix retains its labels and original history is preserved"):
            assert current is not None
            assert current.queue_id != original.queue_id
            assert current.state == "queued" and current.is_hotfix is True
            assert current.started_at is None
            assert set(env.server.mrs[0]["labels"]) == {"merge_queue", "hotfix"}
            assert "Added to queue" in env.server.notes[3]
            assert len(await env.queue.get_active_queue(123)) == 1
            assert len(history) == 1
            assert history[0].queued_at == original.queued_at
            assert history[0].started_at == original.started_at
            assert history[0].pipeline_id == 101
            assert history[0].finished_at == outcome_at
            assert history[0].state == "conflict"
            assert json.loads(current.pending_completion or "null") is None
