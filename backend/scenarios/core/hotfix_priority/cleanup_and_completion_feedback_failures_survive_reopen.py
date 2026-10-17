from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.db.database import Database

from ._helpers import queue_environment, queue_services


@scenario()
async def cleanup_and_completion_feedback_failures_survive_reopen():
    async with queue_environment() as env:
        with given("a final comment delivered before mandatory cleanup fails"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.update_mr_state(123, 3, "rebasing", pipeline_id=101)
            original = await env.queue.get_queue_item(123, 3)
            env.server.mrs = [mr_response(3, labels=["merge_queue"]), mr_response(1, labels=["merge_queue"])]
            env.server.failed_label_iids = {3}
            machine = await create_state_machine_for_mr(
                123, 3, env.handler.notifier, env.queue, position_notifier=env.handler.position_notifier
            )
            with catched(GitLabServerError) as cleanup_error:
                await machine.trigger_rebase_failed(conflicted_files=["app.py"], error_message="Original conflict")
            database_url = env.queue.db.database_url
            await env.queue.db.close()
            env.server.failed_label_iids.clear()
            env.server.failed_comment_iids = {1}

        with when("completion recovers but remaining feedback needs another restart"):
            async with Database(database_url) as db, queue_services(QueueManager(db), env.server) as recovered:
                await recovered.scheduler.sync_queue()
                pending = await recovered.queue.get_queue_item(123, 1)
                first_history = await recovered.queue.get_recent_history(project_id=123)
            env.server.failed_comment_iids.clear()
            async with Database(database_url) as db, queue_services(QueueManager(db), env.server) as recovered:
                await recovered.scheduler.sync_queue()
                await recovered.scheduler.sync_queue()
                final_history = await recovered.queue.get_recent_history(project_id=123)
                remaining = await recovered.queue.get_queue_item(123, 3)

        with then("cleanup, original history and remaining feedback all recover durably"):
            assert cleanup_error.type is GitLabServerError
            assert pending.pending_notification is not None
            assert len(first_history) == 1
            assert len(final_history) == 1
            assert final_history[0].queued_at == original.queued_at
            assert final_history[0].started_at == original.started_at
            assert final_history[0].pipeline_id == 101
            assert remaining is None
            assert "Rebase conflict" in env.server.notes[3]
            assert "**Position:** 1 of 1" in env.server.notes[1]
