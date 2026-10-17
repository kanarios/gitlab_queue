import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.db.database import Database

from ._helpers import ObservedQueue, label_event, queue_environment, queue_services


@dataclass
class PausedReadDatabase(Database):
    read: asyncio.Event = field(default_factory=asyncio.Event)
    resume: asyncio.Event = field(default_factory=asyncio.Event)
    pause: bool = False

    @asynccontextmanager
    async def transaction(self):
        async with super().transaction() as session:
            yield PausedSession(self, session)


@dataclass
class PausedSession:
    db: PausedReadDatabase
    session: object

    async def execute(self, statement, params=None):
        result = await self.session.execute(statement, params)
        if self.db.pause and str(statement).startswith("SELECT requeue_request"):
            self.db.pause = False
            self.db.read.set()
            await self.db.resume.wait()
        return result


@scenario([params("enqueue"), params("cancel")])
async def concurrent_completion_admission_is_not_lost(first_writer):
    async with (
        queue_environment() as base,
        queue_services(ObservedQueue(base.queue.db), base.server) as env,
        PausedReadDatabase(base.queue.db.database_url) as other_db,
        queue_services(ObservedQueue(other_db), base.server) as other,
    ):
        with given("two webhook handlers reading the same deferred request on real database connections"):
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
            await asyncio.wait_for(entered.wait(), 5)
            start = datetime.now(UTC)
            initial = asyncio.create_task(
                env.handler.handle(label_event("labeled", [], ["merge_queue"], updated_at=start.isoformat()))
            )
            await asyncio.wait_for(env.queue.requeue_saved.wait(), 5)
            newer_at = (start + timedelta(seconds=3)).isoformat()
            newer = label_event("labeled", [], ["hotfix"], updated_at=newer_at)
            cancellation = label_event(
                "unlabeled", ["merge_queue"], [], updated_at=(start + timedelta(seconds=2)).isoformat()
            )
            other_db.pause = True
            first = asyncio.create_task(other.handler.handle(newer if first_writer == "enqueue" else cancellation))
            await asyncio.wait_for(other_db.read.wait(), 5)

        with when("the other handler commits first and the stale conditional writer resumes"):
            env.queue.requeue_saved.clear()
            env.queue.requeue_cancelled.clear()
            second = asyncio.create_task(env.handler.handle(cancellation if first_writer == "enqueue" else newer))
            changed = env.queue.requeue_cancelled if first_writer == "enqueue" else env.queue.requeue_saved
            await asyncio.wait_for(changed.wait(), 5)
            other_db.resume.set()
            changed = other.queue.requeue_saved if first_writer == "enqueue" else other.queue.requeue_cancelled
            await asyncio.wait_for(changed.wait(), 5)
            current = await env.queue.get_queue_item(123, 3)
            assert json.loads(current.requeue_request)["requested_at"] == newer_at
            env.server.barriers.clear()
            release.set()
            await asyncio.wait_for(asyncio.gather(completion, initial, first, second), 5)

        with then("the newest action survives either conditional write order"):
            current = await env.queue.get_queue_item(123, 3)
            assert current.is_hotfix is True
            assert env.server.mrs[0]["labels"] == ["hotfix"]
            assert len(await env.queue.get_recent_history(project_id=123)) == 1


@scenario()
async def completion_admission_precedes_mr_lookup():
    async with queue_environment() as env:
        with given("a completion awaiting cleanup and a blocked full MR lookup"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing")
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            entered, release = asyncio.Event(), asyncio.Event()
            lookup, never = asyncio.Event(), asyncio.Event()
            path = "/api/v4/projects/123/merge_requests/3"
            env.server.barriers[("PUT", path)] = (entered, release)
            env.server.barriers[("GET", path)] = (lookup, never)
            machine = await create_state_machine_for_mr(123, 3, env.handler.notifier, env.queue)
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=[], error_message="Conflict")
            )
            await asyncio.wait_for(entered.wait(), 5)

        with when("an explicit label event overlaps the finalization"):
            enqueue = asyncio.create_task(
                env.handler.handle(label_event("labeled", [], ["hotfix"], updated_at=datetime.now(UTC).isoformat()))
            )
            # Both tasks become runnable; completion can race admission, while
            # a full-MR HTTP request cannot provide admission durability.
            release.set()
            await asyncio.wait_for(asyncio.gather(completion, enqueue), 5)

        with then("the request survives without depending on the blocked lookup"):
            assert lookup.is_set() is False
            current = await env.queue.get_queue_item(123, 3)
            assert current.is_hotfix is True
            assert env.server.mrs[0]["labels"] == ["hotfix"]
