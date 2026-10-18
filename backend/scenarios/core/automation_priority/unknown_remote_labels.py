from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabAPIError

from ._helpers import automation_environment


@scenario([params({}), params({"labels": None})])
async def incomplete_remote_labels_are_not_an_authoritative_empty_snapshot(label_fields):
    async with automation_environment() as env:
        with given("saved automation metadata and a full discovery response without usable labels"):
            before = await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "dependencies"]))
            missing = {key: value for key, value in mr_response(3).items() if key != "labels"} | label_fields
            env.server.label_snapshots = {"merge_queue": [missing], "hotfix": []}

        with when("polling receives the incomplete remote snapshot"):
            with catched(GitLabAPIError) as error:
                await env.scheduler.sync_queue()
            after = await env.queue.get_queue_item(123, 3)

        with then("the sweep fails without reclassifying or deleting saved data"):
            assert error.type is GitLabAPIError
            assert after == before
            assert env.server.comments == []
