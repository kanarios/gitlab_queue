import asyncio

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.auth.jwt_handler import create_access_token
from gitlab_queue.core.processor import create_processor
from gitlab_queue.core.state_machine import create_state_machine_for_mr

from ._helpers import CompletionSocket, label_event, queue_environment


@scenario(
    [
        params("queued", "timeout", "Timeout", "pending"),
        params("rebasing", "failed", "Rebase conflict", "pending"),
        params("merging", "merged", "Successfully merged!", "pending"),
        params("queued", "timeout", "Timeout", "poll"),
        params("rebasing", "failed", "Rebase conflict", "poll"),
        params("queued", "timeout", "Timeout", "startup"),
        params("rebasing", "failed", "Rebase conflict", "startup"),
    ]
)
async def pending_recovery_preserves_terminal_transition(initial_state, terminal, expected_status, recovery):
    async with queue_environment() as env:
        with given("pending priority feedback before a terminal state transition"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.failed_comment_iids = {3}
            await env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            env.server.failed_comment_iids.clear()
            env.server.mrs = [
                mr_response(1, labels=["merge_queue"]),
                mr_response(3, labels=["merge_queue", "hotfix"]),
            ]
            await env.queue.update_mr_state(123, 3, initial_state)
            original = await env.queue.get_queue_item(123, 3)
            manager = WebSocketManager()
            socket = CompletionSocket()
            token = create_access_token({"id": 1, "username": "author", "project_id": 123}, env.settings)
            await manager.connect(socket, token, env.settings, project_id=123)
            machine = await create_state_machine_for_mr(
                123,
                3,
                env.handler.notifier,
                env.queue,
                target_branch="main",
                websocket_manager=manager,
                position_notifier=env.handler.position_notifier,
            )
            transition = {
                "timeout": machine.trigger_timeout,
                "failed": lambda: machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Conflict"),
                "merged": machine.trigger_merge_success,
            }[terminal]
            processor = create_processor(
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.settings,
                position_notifier=env.handler.position_notifier,
            )
            processor.request_shutdown()
            retry = {
                "pending": lambda: env.handler.position_notifier.retry_pending(123),
                "poll": env.scheduler.sync_queue,
                "startup": processor.run,
            }[recovery]

        with when("pending recovery overlaps a terminal transition's websocket delivery"):
            completion = asyncio.create_task(transition())
            await asyncio.wait_for(socket.entered.wait(), 5)
            terminal_comment = env.server.notes[3]
            await retry()
            state_during_completion = (await env.queue.get_mr_state(123, 3))["status"]
            socket.release.set()
            await asyncio.wait_for(completion, 5)

        with then("the final comment describes completion and other waiting positions are refreshed"):
            assert expected_status in env.server.notes[3]
            assert env.server.notes[3] == terminal_comment
            assert state_during_completion == {"timeout": "timeout", "failed": "conflict", "merged": "merged"}[terminal]
            assert await env.queue.get_queue_item(123, 3) is None
            assert (await env.queue.get_mr_state(123, 3))["started_at"] == original.started_at
            assert "**Position:** 1 of 1" in env.server.notes[1]
