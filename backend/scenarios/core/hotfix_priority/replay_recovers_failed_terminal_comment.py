from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabServerError

from ._helpers import label_event, queue_environment


@scenario(
    [
        params("unlabeled", "opened", "Removed from queue"),
        params("close", "closed", "Removed from queue"),
        params("merge", "merged", "Successfully merged!"),
    ]
)
async def replay_recovers_failed_terminal_comment(action, state, expected_status):
    async with queue_environment() as env:
        with given("a terminal webhook whose first comment request fails"):
            await env.queue.add_to_queue(123, create_mr(iid=3))
            await env.handler.handle(label_event("update", ["merge_queue"], ["merge_queue", "hotfix"]))
            env.server.failed_comment_iids = {3}
            event = label_event(action, ["merge_queue", "hotfix"], [], state=state)
            with catched(GitLabServerError) as first_delivery:
                await env.handler.handle(event)
            env.server.failed_comment_iids.clear()
            env.server.mrs = [mr_response(3, labels=[], state=state)]

        with when("the webhook is replayed after GitLab recovers"):
            await env.handler.handle(event)

        with then("the terminal comment is delivered before the entry is retired"):
            assert first_delivery.type is GitLabServerError
            assert expected_status in env.server.notes[3]
            assert await env.queue.get_queue_item(123, 3) is None
