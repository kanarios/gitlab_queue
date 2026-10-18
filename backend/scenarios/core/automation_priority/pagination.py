from dataclasses import dataclass, field

import httpx
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.core.hotfix_priority._helpers import GitLabServer
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabClient


@dataclass
class PagedGitLabServer(GitLabServer):
    pages: list[tuple[str, int]] = field(default_factory=list)
    omit_headers: bool = False

    def _response(self, request):
        if request.url.path.endswith("/merge_requests"):
            label = request.url.params["labels"]
            page = int(request.url.params.get("page", "1"))
            self.pages.append((label, page))
            matches = [mr for mr in self.mrs if label in mr["labels"]]
            start = (page - 1) * 100
            remaining = matches[start : start + 100]
            following = str(page + 1) if start + 100 < len(matches) else ""
            headers = {} if self.omit_headers else {"x-next-page": following}
            return httpx.Response(200, json=remaining, headers=headers)
        return super()._response(request)


@scenario([params(100, 1), params(101, 2), params(201, 3)])
async def label_discovery_returns_every_eligible_merge_request(count, page_count):
    with given("a paginated external label response crossing the one-page boundary"):
        server = PagedGitLabServer(mrs=[mr_response(iid, labels=["merge_queue"]) for iid in range(1, count + 1)])
        client = GitLabClient(created_test_settings(), transport=httpx.MockTransport(server.respond))

    with when("the real public GitLab client discovers the full queue-label set"):
        try:
            result = await client.list_mrs_with_label("merge_queue")
        finally:
            await client.close()

    with then("all records are returned and the transport confirms the expected page count"):
        assert len(result) == count
        assert result[-1].iid == count
        assert len(server.pages) == page_count


@scenario([params(100, 2), params(101, 2), params(201, 3)])
async def full_pages_without_headers_require_following_pages_to_prove_completion(count, page_count):
    with given("complete offset pages whose intermediary removed pagination response headers"):
        server = PagedGitLabServer(
            mrs=[mr_response(iid, labels=["merge_queue"]) for iid in range(1, count + 1)], omit_headers=True
        )
        client = GitLabClient(created_test_settings(), transport=httpx.MockTransport(server.respond))

    with when("public label discovery verifies completion through the terminal short page"):
        try:
            result = await client.list_mrs_with_label("merge_queue")
        finally:
            await client.close()

    with then("a full first page cannot silently hide remaining records"):
        assert len(result) == count
        assert result[-1].iid == count
        assert len(server.pages) == page_count
