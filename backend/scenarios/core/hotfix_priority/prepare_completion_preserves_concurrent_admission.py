import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.queue_completion import QueueCompletion
from gitlab_queue.db.database import Database
from gitlab_queue.models.completion import CompletionRequest

from ._helpers import label_event, queue_environment, queue_services


@dataclass
class PausedPrepareDatabase(Database):
    pause: bool = False
    captured: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    @asynccontextmanager
    async def transaction(self):
        async with super().transaction() as session:
            yield PausedPrepareSession(self, session)


@dataclass
class PausedPrepareSession:
    db: PausedPrepareDatabase
    session: object

    async def execute(self, statement, params=None):
        result = await self.session.execute(statement, params)
        if self.db.pause and "SELECT * FROM merge_requests WHERE iid" in str(statement):
            self.db.pause = False
            self.db.captured.set()
            await self.db.release.wait()
        return result


@scenario()
async def prepare_completion_preserves_concurrent_admission():
    async with (
        queue_environment() as base,
        PausedPrepareDatabase(base.queue.db.database_url) as db,
        queue_services(QueueManager(db), base.server) as env,
    ):
        with given("completion has read a prior active admission that it would consume"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing", pipeline_id=101)
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            prior = label_event(
                "labeled",
                [],
                ["merge_queue"],
                updated_at=datetime.now(UTC).isoformat(),
                message_id="prior",
                user_id=99,
            )
            await env.handler.handle(prior)
            original = await env.queue.get_queue_item(123, 3)
            finished = datetime.now(UTC)
            request = CompletionRequest(
                "failed",
                "conflict",
                "conflict",
                {
                    "failed_at": finished,
                    "target_branch": "main",
                    "error_message": "Original conflict",
                    "conflicted_files": [],
                },
                queue_id=original.queue_id,
            )
            db.pause = True
            preparing = asyncio.create_task(env.queue.prepare_completion(123, 3, request))
            await asyncio.wait_for(db.captured.wait(), 5)

        with when("a newer explicit admission commits before the conditional completion write"):
            env.server.mrs[0]["labels"] = ["merge_queue", "hotfix"]
            await env.handler.handle(
                label_event(
                    "labeled",
                    ["merge_queue"],
                    ["merge_queue", "hotfix"],
                    updated_at=(finished + timedelta(seconds=1)).isoformat(),
                    message_id="newer",
                    user_id=99,
                )
            )
            db.release.set()
            owned = await asyncio.wait_for(preparing, 5)
            assert json.loads(owned.requeue_request)["admission_key"] == "newer"
            await QueueCompletion(env.queue, env.handler.notifier, env.handler.position_notifier).recover_all(123)
            replacement = await env.queue.get_queue_item(123, 3)
            await env.handler.handle(prior)
            assert (await env.queue.get_queue_item(123, 3)).queue_id == replacement.queue_id

        with then("retrying preparation retains the exact newer token and original outcome"):
            current = await env.queue.get_queue_item(123, 3)
            assert current.queue_id != original.queue_id
            assert current.state == "queued" and current.is_hotfix is True
            assert current.started_at is None
            assert set(env.server.mrs[0]["labels"]) == {"merge_queue", "hotfix"}
            history = await env.queue.get_recent_history(project_id=123)
            assert len(history) == 1 and history[0].pipeline_id == 101
            assert history[0].finished_at == finished
