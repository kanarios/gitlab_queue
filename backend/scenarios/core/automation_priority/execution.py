import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace

from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.core.hotfix_priority._helpers import queue_services
from scenarios.core.hotfix_priority.exact_running_arrival_order import WorkflowServer, admit, opened_mr
from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.core.queue import QueueManager

from ._helpers import automation_environment


async def archived(queue, count):
    while len(await queue.get_recent_history(limit=20, project_id=123)) != count:
        await asyncio.sleep(0.01)


@asynccontextmanager
async def running_automation_workflow(initial, blocked):
    server = WorkflowServer(
        blocked=blocked,
        entered={iid: asyncio.Event() for iid in blocked},
        release={iid: asyncio.Event() for iid in blocked},
        mrs=[opened_mr(iid, labels) for iid, labels in initial],
    )
    async with automation_environment(server_factory=lambda: server) as base:
        for iid, labels in initial:
            await base.queue.add_to_queue(123, create_mr(iid=iid, sha=f"sha-{iid}", labels=labels))
        foreign = QueueManager(base.queue.db)
        await foreign.add_to_queue(456, create_mr(iid=1))
        await foreign.add_to_queue(456, create_mr(iid=101, labels=["hotfix"]), is_hotfix=True)
        settings = replace(base.settings, application=created_test_settings(poll_interval_seconds=0))
        async with queue_services(base.queue, server, settings) as env:
            processor = MergeProcessor(
                env.gitlab, env.queue, env.handler.notifier, settings, env.handler.position_notifier
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
async def full_workflow_uses_three_bands_for_all_arrivals_during_the_running_mr():
    initial = [(1, ["merge_queue"]), (2, ["merge_queue"]), (3, ["merge_queue", "dependencies"])]
    async with running_automation_workflow(initial, {1}) as (env, processor):
        with given("ordinary MR1 is testing while ordinary MR2 and automated MR3 wait"):
            original = await env.queue.get_queue_item(123, 1)
            foreign = await env.queue.get_active_queue(456)

        with when("HF1, automated MR4, ordinary MR5 and HF2 arrive before MR1 finishes"):
            await admit(env, 101, ["hotfix"])
            await admit(env, 4, ["merge_queue", "dependencies"])
            await admit(env, 5, ["merge_queue"])
            await admit(env, 102, ["hotfix", "dependencies"])
            current = await env.queue.get_queue_item(123, 1)
            assert processor.current_mr_iid == 1
            assert (current.state, current.started_at, current.pipeline_id, current.expected_sha) == (
                original.state,
                original.started_at,
                original.pipeline_id,
                original.expected_sha,
            )
            assert [item.mr_iid for item in await env.queue.get_active_queue(123)] == [101, 102, 1, 2, 5, 3, 4]
            env.server.release[1].set()
            await asyncio.wait_for(archived(env.queue, 7), 12)

        with then("the real pipeline and merge workflow completes each incarnation in effective-band FIFO"):
            assert env.server.merged == [1, 101, 102, 2, 5, 3, 4]
            assert await env.queue.get_active_queue(456) == foreign
            history = await env.queue.get_recent_history(limit=20, project_id=123)
            assert len(history) == 7
            assert {item.state for item in history} == {"merged"}


@scenario()
async def automated_inflight_and_then_ordinary_inflight_are_never_preempted():
    async with running_automation_workflow([(1, ["merge_queue", "dependencies"])], {1, 2}) as (env, processor):
        with given("automated MR1 is already testing before higher-priority entries arrive"):
            original = await env.queue.get_queue_item(123, 1)
            foreign = await env.queue.get_active_queue(456)
            await admit(env, 2, ["merge_queue"])
            await admit(env, 3, ["merge_queue", "dependencies"])
            await admit(env, 101, ["hotfix"])
            current = await env.queue.get_queue_item(123, 1)
            assert processor.current_mr_iid == 1
            assert current.priority == "automated"
            assert current.started_at == original.started_at
            assert current.pipeline_id == original.pipeline_id
            env.server.release[1].set()
            await asyncio.wait_for(env.server.entered[2].wait(), 8)
            second = await env.queue.get_queue_item(123, 2)

        with when("HF2 arrives only after ordinary MR2 is already testing"):
            await admit(env, 102, ["hotfix"])
            current_second = await env.queue.get_queue_item(123, 2)
            assert processor.current_mr_iid == 2
            assert (current_second.state, current_second.started_at, current_second.pipeline_id) == (
                second.state,
                second.started_at,
                second.pipeline_id,
            )
            env.server.release[2].set()
            await asyncio.wait_for(archived(env.queue, 5), 12)

        with then("each running MR finishes before the next queued priority decision"):
            assert env.server.merged == [1, 101, 2, 102, 3]
            assert await env.queue.get_active_queue(456) == foreign
            assert len(await env.queue.get_recent_history(limit=20, project_id=123)) == 5
