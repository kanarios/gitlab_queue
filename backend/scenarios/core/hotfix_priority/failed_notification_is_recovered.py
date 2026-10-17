from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from ._helpers import label_event, queue_environment


@scenario([params(3, "poll"), params(1, "poll"), params(3, "replay"), params(1, "replay")])
async def failed_notification_is_recovered(failed_iid, recovery):
    async with queue_environment() as env:
        with given("a priority change whose first or later recipient is unavailable"):
            await env.queue.add_to_queue(123, create_mr(iid=1))
            await env.queue.add_to_queue(123, create_mr(iid=2))
            await env.queue.add_to_queue(123, create_mr(iid=3))
            env.server.failed_comment_iids = {failed_iid}
            event = label_event("update", ["merge_queue"], ["merge_queue", "hotfix"])
            await env.handler.handle(event)
            attempts_after_failure = list(env.server.comment_attempts)
            env.server.failed_comment_iids.clear()
            env.server.comments.clear()
            env.server.mrs = [
                mr_response(1, labels=["merge_queue"]),
                mr_response(2, labels=["merge_queue"]),
                mr_response(3, labels=["merge_queue", "hotfix"]),
            ]

            retry = {"poll": env.scheduler.sync_queue, "replay": lambda: env.handler.handle(event)}[recovery]

        with when("polling or duplicate delivery sees identical labels"):
            await retry()
            await env.scheduler.sync_queue()

        with then("other recipients were attempted and only the failed comment is retried"):
            assert attempts_after_failure == [3, 1, 2]
            assert [iid for iid, body in env.server.comments] == [failed_iid]
            queue = await env.queue.get_active_queue(123)
            assert [item.mr_iid for item in queue] == [3, 1, 2]
