import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

import httpx
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response, pipeline_response
from vedro import given, scenario, then, when

from gitlab_queue.core.processor import MergeProcessor

from ._helpers import GitLabServer, label_event, queue_environment, queue_services


@dataclass
class WorkflowServer(GitLabServer):
    blocked: set[int] = field(default_factory=set)
    entered: dict[int, asyncio.Event] = field(default_factory=dict)
    release: dict[int, asyncio.Event] = field(default_factory=dict)
    reads: dict[int, int] = field(default_factory=dict)
    merged: list[int] = field(default_factory=list)

    async def respond(self, request):
        path = request.url.path
        if path == "/api/v4/projects/123":
            return httpx.Response(
                200,
                json={
                    "id": 123,
                    "web_url": "https://gitlab.example.com/project",
                    "path_with_namespace": "group/project",
                },
            )
        if path.endswith("/pipelines") and "/merge_requests/" in path:
            iid = int(path.split("/")[-2])
            self.reads[iid] = self.reads.get(iid, 0) + 1
            if iid in self.blocked and self.reads[iid] == 2:
                self.entered[iid].set()
                await self.release[iid].wait()
            return httpx.Response(200, json=[pipeline_response(10000 + iid, sha=f"sha-{iid}", status="success")])
        if path.endswith("/merge") and request.method == "PUT":
            iid = int(path.split("/")[-2])
            mr = next(mr for mr in self.mrs if mr["iid"] == iid)
            mr["state"] = "merged"
            self.merged.append(iid)
            return httpx.Response(200, json=mr)
        return await super().respond(request)


def opened_mr(iid, labels):
    return {**mr_response(iid, labels=labels, sha=f"sha-{iid}"), "diverged_commits_count": 0}


async def admit(env, iid, labels):
    env.server.mrs.append(opened_mr(iid, labels))
    event = label_event("update", [], labels, updated_at=datetime.now(UTC).isoformat(), message_id=f"admit-{iid}")
    await env.handler.handle(replace(event, object_attributes=replace(event.object_attributes, iid=iid)))


async def drained(queue):
    while await queue.get_queue_item(123, 4) is not None:
        await asyncio.sleep(0.01)


@asynccontextmanager
async def running_workflow(blocked):
    async with queue_environment() as base:
        server = WorkflowServer(
            blocked=blocked,
            entered={iid: asyncio.Event() for iid in blocked},
            release={iid: asyncio.Event() for iid in blocked},
            mrs=[opened_mr(iid, ["merge_queue"]) for iid in (1, 2, 3)],
        )
        for iid in (1, 2, 3):
            await base.queue.add_to_queue(123, create_mr(iid=iid, sha=f"sha-{iid}"))
        await base.queue.add_to_queue(456, create_mr(iid=1))
        await base.queue.add_to_queue(456, create_mr(iid=101, labels=["hotfix"]), is_hotfix=True)
        async with queue_services(base.queue, server, created_test_settings(poll_interval_seconds=0)) as env:
            processor = MergeProcessor(
                env.gitlab, env.queue, env.handler.notifier, env.settings, env.handler.position_notifier
            )
            task = asyncio.create_task(processor.run())
            try:
                await asyncio.wait_for(server.entered[1].wait(), 8)
                yield env, processor
            finally:
                processor.request_shutdown()
                for release in server.release.values():
                    release.set()
                await asyncio.wait_for(task, 8)


@scenario()
async def all_arrivals_during_mr1_keep_both_hotfixes_ahead_of_waiting_ordinary_mrs():
    async with running_workflow({1}) as (env, processor):
        with given("MR1 is testing while MR2 and MR3 wait"):
            original = await env.queue.get_queue_item(123, 1)
            foreign = await env.queue.get_active_queue(456)

        with when("HF1, ordinary MR4 and HF2 all arrive before MR1 finishes"):
            await admit(env, 101, ["hotfix"])
            await admit(env, 4, ["merge_queue"])
            await admit(env, 102, ["hotfix"])
            current = await env.queue.get_queue_item(123, 1)
            assert processor.current_mr_iid == 1
            assert (current.state, current.started_at, current.pipeline_id, current.expected_sha) == (
                original.state,
                original.started_at,
                original.pipeline_id,
                original.expected_sha,
            )
            assert current.state == "testing"
            assert [item.mr_iid for item in await env.queue.get_active_queue(123)] == [101, 102, 1, 2, 3, 4]
            env.server.release[1].set()
            await asyncio.wait_for(drained(env.queue), 8)

        with then("the actual merge workflow executes MR1, HF1, HF2, MR2, MR3, MR4"):
            assert env.server.merged == [1, 101, 102, 2, 3, 4]
            assert await env.queue.get_active_queue(456) == foreign
            history = await env.queue.get_recent_history(project_id=123)
            assert len(history) == 6
            assert {item.state for item in history} == {"merged"}


@scenario()
async def hotfix_arriving_after_mr2_starts_waits_for_that_inflight_workflow():
    async with running_workflow({1, 2}) as (env, processor):
        with given("HF1 and MR4 arrive while MR1 is testing"):
            await admit(env, 101, ["hotfix"])
            await admit(env, 4, ["merge_queue"])
            foreign = await env.queue.get_active_queue(456)
            env.server.release[1].set()
            await asyncio.wait_for(env.server.entered[2].wait(), 8)
            original = await env.queue.get_queue_item(123, 2)

        with when("HF2 arrives only after MR2 has already started testing"):
            await admit(env, 102, ["hotfix"])
            current = await env.queue.get_queue_item(123, 2)
            assert processor.current_mr_iid == 2
            assert env.server.merged == [1, 101]
            assert (current.state, current.started_at, current.pipeline_id, current.expected_sha) == (
                original.state,
                original.started_at,
                original.pipeline_id,
                original.expected_sha,
            )
            env.server.release[2].set()
            await asyncio.wait_for(drained(env.queue), 8)

        with then("MR2 completes before HF2, preserving the remaining ordinary order"):
            assert env.server.merged == [1, 101, 2, 102, 3, 4]
            assert await env.queue.get_active_queue(456) == foreign
