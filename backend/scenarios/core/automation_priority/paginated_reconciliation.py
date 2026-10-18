from dataclasses import dataclass

import httpx
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import catched, given, params, scenario, then, when

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.core.queue import QueueManager

from ._helpers import automation_environment
from .pagination import PagedGitLabServer


@dataclass
class OverlappingPageServer(PagedGitLabServer):
    def _response(self, request):
        if request.url.path.endswith("/merge_requests") and request.url.params["labels"] == "merge_queue":
            page = int(request.url.params.get("page", "1"))
            self.pages.append(("merge_queue", page))
            rows = list(self.mrs)
            rows[2] = mr_response(3, labels=["merge_queue"])
            rows.insert(100, mr_response(3, labels=["merge_queue", "hotfix", "dependencies"]))
            start = (page - 1) * 100
            return httpx.Response(
                200,
                json=rows[start : start + 100],
                headers={"x-next-page": str(page + 1) if start + 100 < len(rows) else ""},
            )
        return super()._response(request)


@scenario([params(100), params(101), params(201)])
async def complete_paginated_union_deduplicates_pages_and_triggers_before_current_policy_admission(count):
    server = OverlappingPageServer(mrs=[mr_response(iid, labels=["merge_queue"]) for iid in range(1, count + 1)])
    server.mrs[2]["labels"] = ["merge_queue", "hotfix", "dependencies"]
    server.mrs[-1]["labels"] = ["merge_queue", "dependencies"]
    async with automation_environment(server_factory=lambda: server) as env:
        with given("100, 101 or201 eligible MRs with overlapping queue pages and both trigger lists"):
            foreign = await QueueManager(env.queue.db).add_to_queue(456, create_mr(iid=3))
        with when("complete polling discovers then repeats the exact paginated union"):
            first = await env.scheduler.sync_queue()
            second = await env.scheduler.sync_queue()
            rows = await env.queue.get_active_queue(123)
            hotfix = await env.queue.get_queue_item(123, 3)
        with then("one incarnation per MR uses the latest full snapshot and the final automated page is retained"):
            assert first.added == count
            assert second.added == second.updated == second.removed == 0
            assert len(rows) == count
            assert [item.mr_iid for item in rows] == [3, 1, 2, *range(4, count), count]
            assert hotfix.labels == ["merge_queue", "hotfix", "dependencies"]
            assert hotfix.priority == "hotfix"
            assert hotfix.is_automated is True
            assert rows[-1].priority == "automated"
            assert await env.queue.get_queue_item(456, 3) == foreign


@dataclass
class FailingSecondPageServer(PagedGitLabServer):
    fail: bool = True

    def _response(self, request):
        if self.fail and request.url.path.endswith("/merge_requests") and request.url.params.get("page") == "2":
            return httpx.Response(503, json={"message": "unavailable"})
        return super()._response(request)


@scenario()
async def later_page_http_failure_preserves_saved_data_and_healthy_replay_converges():
    server = FailingSecondPageServer(mrs=[mr_response(iid, labels=["merge_queue"]) for iid in range(1, 202)])
    server.mrs[2]["labels"] = ["merge_queue", "dependencies"]
    async with automation_environment(server_factory=lambda: server) as env:
        with given("saved rows on first and last pages while the second HTTP page fails"):
            await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "dependencies"]))
            await env.queue.add_to_queue(123, create_mr(iid=201, labels=["merge_queue"]))
            before = await env.queue.get_active_queue(123)
        with when("the failed sweep is retried only after the remote pages become available"):
            with catched(GitLabServerError) as error:
                await env.scheduler.sync_queue()
            unchanged = await env.queue.get_active_queue(123)
            server.fail = False
            result = await env.scheduler.sync_queue()
            rows = await env.queue.get_active_queue(123)
        with then("the incomplete list performs no mutation and the complete sweep preserves original FIFO identities"):
            assert error.type is GitLabServerError
            assert unchanged == before
            assert result.added == 199
            assert len(rows) == 201
            assert rows[0].mr_iid == 201
            assert rows[-1].mr_iid == 3
            assert rows[-1].priority == "automated"
            assert rows[0].queue_id == before[0].queue_id
