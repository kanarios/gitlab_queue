import asyncio

from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.auth.jwt_handler import create_access_token
from gitlab_queue.core.state_machine import create_state_machine_for_mr

from ._helpers import CompletionSocket, label_event, queue_environment


@scenario([params("update", ["merge_queue"]), params("labeled", [])])
async def completion_does_not_archive_replacement(action, previous):
    async with queue_environment() as env:
        with given("a failed lifecycle whose final websocket delivery waits"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.update_mr_state(123, 3, "rebasing", pipeline_id=101, expected_sha="original-sha")
            original = await env.queue.get_queue_item(123, 3)
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            socket = CompletionSocket()
            manager = WebSocketManager()
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

        with when("a new queue event overlaps the old completion callback"):
            completion = asyncio.create_task(
                machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Original conflict")
            )
            await asyncio.wait_for(socket.entered.wait(), 5)
            env.server.mrs = [mr_response(3, labels=["merge_queue"])]
            await env.handler.handle(label_event(action, previous, ["merge_queue"]))
            replacement = await env.queue.get_queue_item(123, 3)
            socket.release.set()
            await asyncio.wait_for(completion, 5)

        with then("the old lifecycle owns its history while the new generation stays queued"):
            current = await env.queue.get_queue_item(123, 3)
            history = await env.queue.get_recent_history(project_id=123)
            assert replacement is not None
            assert current is not None
            assert current.queue_id == replacement.queue_id
            assert current.queue_id != original.queue_id
            assert current.state == "queued"
            assert current.started_at is None
            assert len(history) == 1
            assert history[0].queued_at == original.queued_at
            assert history[0].started_at == original.started_at
            assert history[0].pipeline_id == 101
            assert "Added to queue" in env.server.notes[3]
