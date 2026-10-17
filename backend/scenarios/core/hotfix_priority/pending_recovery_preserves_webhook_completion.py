import asyncio

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.auth.jwt_handler import create_access_token
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import CompletionSocket, label_event, queue_environment


@scenario(
    [
        params("unlabeled", "opened", "Removed from queue"),
        params("close", "closed", "Removed from queue"),
        params("merge", "merged", "Successfully merged!"),
    ]
)
async def pending_recovery_preserves_webhook_completion(action, state, expected_status):
    async with queue_environment() as env:
        with given("pending hotfix feedback before terminal webhook handling"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.failed_comment_iids = {3}
            await env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            env.server.failed_comment_iids.clear()
            env.server.comments.clear()
            env.server.mrs = [mr_response(3, labels=[], state=state)]
            manager = WebSocketManager()
            socket = CompletionSocket()
            token = create_access_token({"id": 1, "username": "author", "project_id": 123}, env.settings)
            await manager.connect(socket, token, env.settings, project_id=123)
            handler = MRWebhookHandler(
                env.settings,
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.handler.position_notifier,
                manager,
            )
            event = label_event(action, ["merge_queue", "hotfix"], [], state=state)

        with when("recovery runs after the terminal comment while its websocket delivery waits"):
            completion = asyncio.create_task(handler.handle(event))
            await asyncio.wait_for(socket.entered.wait(), 5)
            terminal_comment = env.server.notes[3]
            await env.handler.position_notifier.retry_pending(123)
            socket.release.set()
            await asyncio.wait_for(completion, 5)

        with then("the terminal feedback survives and remaining authors see their new position"):
            assert expected_status in env.server.notes[3]
            assert env.server.notes[3] == terminal_comment
            assert await env.queue.get_queue_item(123, 3) is None
            assert (await env.queue.get_mr_state(123, 3))["started_at"] is None
            assert "**Position:** 1 of 1" in env.server.notes[1]
