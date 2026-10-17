import asyncio

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.auth.jwt_handler import create_access_token
from gitlab_queue.core.processor import create_processor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import CompletionSocket, label_event, queue_environment, queue_services


@scenario(
    [
        params("merge", "merged", "Successfully merged!"),
        params("close", "closed", "Removed from queue"),
        params("unlabeled", "opened", "Removed from queue"),
    ]
)
async def interrupted_completion_recovers_after_reopen(action, state, final_feedback):
    async with queue_environment() as env:
        with given("completion interrupted while its websocket delivery waits"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.add_to_queue(123, create_mr(iid=1))
            original = await env.queue.get_queue_item(123, 3)
            env.server.mrs = [mr_response(1, labels=["merge_queue"]), mr_response(3, labels=[], state=state)]
            socket = CompletionSocket()
            manager = WebSocketManager()
            token = create_access_token({"id": 1, "username": "author", "project_id": 123}, env.settings)
            await manager.connect(socket, token, env.settings, project_id=123)
            handler = MRWebhookHandler(
                env.settings, env.gitlab, env.queue, env.handler.notifier, env.handler.position_notifier, manager
            )
            event = label_event(action, ["merge_queue"], [], state=state)
            completion = asyncio.create_task(handler.handle(event))
            await asyncio.wait_for(socket.entered.wait(), 5)
            completion.cancel()
            with catched(asyncio.CancelledError):
                await completion
            database_url = env.queue.db.database_url
            await env.queue.db.close()

        with when("startup, polling and webhook replay recover the reopened database"):
            async with Database(database_url) as db, queue_services(QueueManager(db), env.server) as recovered:
                processor = create_processor(
                    recovered.gitlab,
                    recovered.queue,
                    recovered.handler.notifier,
                    recovered.settings,
                    position_notifier=recovered.handler.position_notifier,
                )
                processor.request_shutdown()
                await processor.run()
                await recovered.scheduler.sync_queue()
                await recovered.handler.handle(event)
                remaining = await recovered.queue.get_queue_item(123, 3)
                history = await recovered.queue.get_recent_history(project_id=123)

        with then("the original lifecycle is archived once and remaining feedback is repaired"):
            assert remaining is None
            assert len(history) == 1
            assert history[0].queued_at == original.queued_at
            assert history[0].started_at is None
            assert final_feedback in env.server.notes[3]
            assert "**Position:** 1 of 1" in env.server.notes[1]
