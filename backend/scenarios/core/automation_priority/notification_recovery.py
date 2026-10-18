import asyncio

from scenarios.core.hotfix_priority._helpers import ObservedQueue, label_event, queue_services
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.db.database import Database

from ._helpers import automation_environment


@scenario([params(3), params(2)])
async def first_or_later_automation_feedback_failure_is_repaired_after_reopen(failed_iid):
    async with automation_environment() as env:
        with given("an automation reorder whose first or later pinned note fails"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            await env.queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
            env.server.failed_comment_iids = {failed_iid}
            event = label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"])
            await env.handler.handle(event)
            attempts = list(env.server.comment_attempts)
            env.server.failed_comment_iids.clear()
            env.server.comments.clear()
            env.server.mrs = [
                mr_response(3, labels=["merge_queue", "dependencies"]),
                mr_response(2, labels=["merge_queue"]),
            ]
            url = env.queue.db.database_url
            await env.queue.db.close()
        with when("startup activation and identical polling reopen the durable pending notification"):
            async with Database(url) as database:
                queue = QueueManager(database, project_policies={123: env.settings.config})
                await queue.activate_priorities(123)
                async with queue_services(queue, env.server, env.settings) as recovered:
                    await recovered.scheduler.sync_queue()
                    await recovered.handler.handle(event)
                    rows = await queue.get_active_queue(123)
        with then("other recipients were attempted and only the failed recipient is repaired"):
            assert attempts == [3, 2]
            assert [iid for iid, _body in env.server.comments] == [failed_iid]
            assert [item.mr_iid for item in rows] == [2, 3]
            assert [item.priority for item in rows] == ["ordinary", "automated"]
            assert [item.pending_notification for item in rows] == [None, None]
            assert "Automated priority" in env.server.notes[3]


@scenario()
async def processing_comment_follows_an_inflight_automation_waiting_write():
    async with automation_environment() as env:
        with given("an automation feedback request blocked on the same MR's comment HTTP"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("POST", "/api/v4/projects/123/merge_requests/3/notes")] = (entered, release)
            other = ObservedQueue(env.queue.db, project_policies={123: env.settings.config})
            notifier = MRNotifier(env.gitlab, env.settings, other)
            machine = await create_state_machine_for_mr(123, 3, notifier, other, target_branch="main")
        with when("the real state machine starts processing while the waiting note is still in flight"):
            waiting = asyncio.create_task(
                env.handler.handle(label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"]))
            )
            await asyncio.wait_for(entered.wait(), 5)
            processing = asyncio.create_task(machine.trigger_start_processing())
            try:
                await asyncio.wait_for(other.state_updated.wait(), 5)
            finally:
                release.set()
                await asyncio.wait_for(asyncio.gather(waiting, processing), 5)
        with then("shared comment ordering leaves processing feedback as the final pinned note"):
            assert "**Status:** 🔄 Rebasing" in env.server.notes[3]
            assert env.server.comment_methods == ["POST", "PUT"]
            assert (await env.queue.get_queue_item(123, 3)).state == "rebasing"


@scenario()
async def a_newer_ordinary_intent_survives_the_old_automation_http_ack():
    async with automation_environment() as env:
        with given("a durable failed automation note being retried over HTTP"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue"]))
            env.server.failed_comment_iids = {3}
            await env.handler.handle(label_event("labeled", ["merge_queue"], ["merge_queue", "dependencies"]))
            env.server.failed_comment_iids.clear()
            entered, release = asyncio.Event(), asyncio.Event()
            env.server.barriers[("POST", "/api/v4/projects/123/merge_requests/3/notes")] = (entered, release)
            other = ObservedQueue(env.queue.db, project_policies={123: env.settings.config})
        with when("another handler changes the current band before the old HTTP acknowledgment"):
            async with queue_services(other, env.server, env.settings) as second:
                old = asyncio.create_task(env.handler.position_notifier.retry_pending(123))
                await asyncio.wait_for(entered.wait(), 5)
                newer = asyncio.create_task(
                    second.handler.handle(label_event("unlabeled", ["merge_queue", "dependencies"], ["merge_queue"]))
                )
                try:
                    await asyncio.wait_for(other.metadata_updated.wait(), 5)
                finally:
                    release.set()
                    await asyncio.wait_for(asyncio.gather(old, newer), 5)
        with then("the matching-token ACK rule lets fresh ordinary feedback repair the same note"):
            current = await env.queue.get_queue_item(123, 3)
            assert current.priority == "ordinary"
            assert current.pending_notification is None
            assert "Ordinary priority" in env.server.notes[3]
            assert env.server.comment_methods == ["POST", "PUT"]
