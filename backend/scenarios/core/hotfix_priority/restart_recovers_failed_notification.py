from pathlib import Path
from tempfile import TemporaryDirectory

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.processor import create_processor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations

from ._helpers import GitLabServer, label_event, queue_services


@scenario([params(3), params(1)])
async def restart_recovers_failed_notification(failed_iid):
    with TemporaryDirectory() as directory:
        database_url = f"sqlite+aiosqlite:///{Path(directory) / 'queue.db'}"
        server = GitLabServer()
        with given("a persisted priority change with an unavailable recipient before shutdown"):
            await run_migrations(database_url)
            async with Database(database_url) as db, queue_services(QueueManager(db), server) as env:
                await env.queue.add_to_queue(123, create_mr(iid=1))
                await env.queue.add_to_queue(123, create_mr(iid=2))
                await env.queue.add_to_queue(123, create_mr(iid=3))
                server.failed_comment_iids = {failed_iid}
                await env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            server.failed_comment_iids.clear()
            server.comments.clear()
            server.mrs = [
                mr_response(1, labels=["merge_queue"]),
                mr_response(2, labels=["merge_queue"]),
                mr_response(3, labels=["merge_queue", "hotfix"]),
            ]

        with when("a new bot reopens the database and performs startup recovery"):
            async with Database(database_url) as reopened:
                async with queue_services(QueueManager(reopened), server) as restarted:
                    processor = create_processor(
                        restarted.gitlab,
                        restarted.queue,
                        restarted.handler.notifier,
                        restarted.settings,
                        position_notifier=restarted.handler.position_notifier,
                    )
                    processor.request_shutdown()
                    await processor.run()
                    recovered = await restarted.queue.get_queue_item(123, failed_iid)
                    next_mr = await restarted.queue.get_next_mr(123)

        with then("only the failed recipient is repaired and priority remains active"):
            assert [iid for iid, body in server.comments] == [failed_iid]
            assert recovered.pending_notification is None
            assert next_mr.mr_iid == 3
            assert next_mr.is_hotfix is True
