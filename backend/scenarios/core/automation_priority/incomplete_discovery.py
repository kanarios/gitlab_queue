from dataclasses import dataclass

import httpx
from scenarios.core.hotfix_priority._helpers import GitLabServer
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabAPIError

from ._helpers import automation_environment


@dataclass
class IncompleteLabelServer(GitLabServer):
    next_page: str = "invalid"
    endless: bool = False
    failing_label: str = "merge_queue"

    def _response(self, request):
        if request.url.path.endswith("/merge_requests") and request.url.params["labels"] == self.failing_label:
            page = int(request.url.params.get("page", "1"))
            next_page = str(page + 1) if self.endless else self.next_page
            return httpx.Response(
                200, json=[mr_response(3, labels=["merge_queue"])], headers={"x-next-page": next_page}
            )
        return super()._response(request)


@scenario(
    [
        params("invalid", False, "merge_queue"),
        params("1", False, "merge_queue"),
        params("0", False, "merge_queue"),
        params("3", False, "merge_queue"),
        params("", True, "merge_queue"),
        params("invalid", False, "hotfix"),
    ]
)
async def incomplete_discovery_cannot_reclassify_or_remove_existing_entries(next_page, endless, failing_label):
    server = IncompleteLabelServer(
        mrs=[mr_response(3, labels=["merge_queue"]), mr_response(2, labels=["merge_queue"])],
        next_page=next_page,
        endless=endless,
        failing_label=failing_label,
    )
    async with automation_environment(server_factory=lambda: server) as environment:
        with given("an automation entry and an ordinary entry omitted from an incomplete remote list"):
            await environment.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "dependencies"]))
            await environment.queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
            before = await environment.queue.get_active_queue(123)

        with when("the public scheduler encounters unsafe continuation or reaches the page cap"):
            with catched(GitLabAPIError) as incomplete:
                await environment.scheduler.sync_queue()
            after = await environment.queue.get_active_queue(123)

        with then("the incomplete snapshot is refused before metadata, membership or feedback changes"):
            assert incomplete.type is GitLabAPIError
            assert after == before
            assert server.comments == []
