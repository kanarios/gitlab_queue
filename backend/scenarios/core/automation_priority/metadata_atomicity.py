from contextlib import asynccontextmanager
from dataclasses import dataclass

from scenarios.core.hotfix_priority._helpers import label_event, queue_services
from scenarios.fakes import create_mr
from vedro import catched, given, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database

from ._helpers import automation_environment


@dataclass
class InterruptedIntentSession:
    session: object

    async def execute(self, statement, params=None):
        result = await self.session.execute(statement, params)
        if str(statement).startswith("UPDATE merge_requests SET pending_notification"):
            raise RuntimeError("interrupted after durable feedback write")
        return result


class InterruptedIntentDatabase(Database):
    @asynccontextmanager
    async def transaction(self):
        async with super().transaction() as session:
            yield InterruptedIntentSession(session)


@scenario()
async def automation_metadata_and_its_final_feedback_roll_back_atomically():
    async with automation_environment() as env:
        with given("real queue metadata and an injected failure after the notification SQL write"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            await env.queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
            before = await env.queue.get_active_queue(123)
        with when("the public handler's database transaction is interrupted between metadata and commit"):
            async with InterruptedIntentDatabase(env.queue.db.database_url) as database:
                queue = QueueManager(database, project_policies={123: env.settings.config})
                async with queue_services(queue, env.server, env.settings) as interrupted:
                    with catched(RuntimeError) as error:
                        await interrupted.handler.handle(
                            label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"])
                        )
            after = await env.queue.get_active_queue(123)
        with then("neither classification, revision, order nor partial feedback survives"):
            assert error.type is RuntimeError
            assert str(error.value) == "interrupted after durable feedback write"
            assert after == before
            assert env.server.comments == []
