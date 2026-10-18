import asyncio
import json
from contextlib import asynccontextmanager

import httpx
from scenarios.contexts.api_helpers import created_mock_health, created_test_jwt
from scenarios.core.hotfix_priority._helpers import label_event
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, params, scenario, then, when

from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.core.processor import create_processor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager
from gitlab_queue.webhooks.router import WebhookAppState, create_webhook_app

from ._helpers import automation_environment


def queue_app(env):
    manager = WebSocketManager()
    env.handler.websocket_manager = manager
    env.scheduler.set_websocket_manager(manager)
    state = WebhookAppState(
        env.settings,
        env.queue.db,
        env.gitlab,
        env.queue,
        env.handler.notifier,
        env.handler.position_notifier,
        WebhookRetryManager(env.queue.db),
        created_mock_health(),
        manager,
    )
    return create_webhook_app(state), manager


@asynccontextmanager
async def websocket_messages(app, token):
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "scheme": "ws",
        "server": ("test", 80),
        "client": ("test", 12345),
        "path": "/ws/projects/123/queue",
        "raw_path": b"/ws/projects/123/queue",
        "root_path": "",
        "query_string": f"token={token}".encode(),
        "headers": [],
        "subprotocols": [],
    }
    await incoming.put({"type": "websocket.connect"})
    task = asyncio.create_task(app(scope, incoming.get, outgoing.put))
    try:
        accepted = await asyncio.wait_for(outgoing.get(), 5)
        yield accepted, outgoing
    finally:
        await incoming.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(task, 5)


async def seeded_wire_queue(env):
    await env.queue.add_to_queue(123, create_mr(iid=3, labels=["merge_queue", "dependencies"]))
    await env.queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
    await env.queue.add_to_queue(123, create_mr(iid=9, labels=["hotfix", "dependencies"]))
    await env.queue.add_to_queue(123, create_mr(iid=4, labels=["merge_queue", "dependencies"]))
    await QueueManager(env.queue.db).add_to_queue(456, create_mr(iid=3))
    env.server.mrs = [
        mr_response(3, labels=["merge_queue"]),
        mr_response(2, labels=["merge_queue"]),
        mr_response(9, labels=["hotfix", "dependencies"]),
        mr_response(4, labels=["merge_queue", "dependencies"]),
    ]


@scenario()
async def active_rest_adds_effective_priority_without_expanding_history():
    async with automation_environment() as env:
        with given("a real authenticated queue API with all priority bands and another project's same IID"):
            await seeded_wire_queue(env)
            await env.queue.add_to_queue(123, create_mr(iid=88, labels=["merge_queue", "dependencies"]))
            await env.queue.complete_mr(123, 88, "merged")
            app, _manager = queue_app(env)
            headers = {"Authorization": f"Bearer {created_test_jwt(env.settings, project_id=123)}"}

        with when("all active REST views and existing history views are requested"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test", headers=headers
            ) as client:
                active = await client.get("/api/projects/123/queue/active")
                detail = await client.get("/api/projects/123/queue/3")
                dashboard = await client.get("/api/projects/123/queue")
                history = await client.get("/api/projects/123/history")
                foreign = await client.get("/api/projects/456/queue/active")

        with then("active order, full-active positions and effective enum agree while history remains compatible"):
            assert [response.status_code for response in (active, detail, dashboard, history)] == [200] * 4
            items = active.json()["items"]
            assert [item["mr_iid"] for item in items] == [9, 2, 3, 4]
            assert [item["priority"] for item in items] == ["hotfix", "ordinary", "automated", "automated"]
            assert [item["position"] for item in items] == [1, 2, 3, 4]
            assert [item["is_hotfix"] for item in items] == [True, False, False, False]
            assert detail.json()["priority"] == "automated"
            assert detail.json()["position"] == 3
            assert [item["priority"] for item in dashboard.json()["queue"]] == [
                "hotfix",
                "ordinary",
                "automated",
                "automated",
            ]
            assert "priority" not in dashboard.json()["history"][0]
            assert "priority" not in history.json()["items"][0]
            assert foreign.status_code == 404
            assert app.openapi()["components"]["schemas"]["ActiveQueueItemSchema"]["properties"]["priority"][
                "enum"
            ] == ["hotfix", "ordinary", "automated"]


@scenario([params("webhook"), params("poll"), params("startup")])
async def initial_and_each_full_snapshot_producer_include_effective_priority(producer):
    async with automation_environment() as env:
        with given("an authenticated real ASGI WebSocket with a current three-band queue"):
            await seeded_wire_queue(env)
            app, manager = queue_app(env)
            token = created_test_jwt(env.settings, project_id=123)
            processor = create_processor(
                env.gitlab,
                env.queue,
                env.handler.notifier,
                env.settings,
                position_notifier=env.handler.position_notifier,
            )
            processor.set_websocket_manager(manager)
            processor.request_shutdown()
            refresh = {
                "webhook": lambda: env.handler.handle(
                    label_event("update", ["merge_queue", "dependencies"], ["merge_queue"])
                ),
                "poll": env.scheduler.sync_queue,
                "startup": processor.run,
            }[producer]

        with when("a full relabel snapshot is emitted by the selected public producer"):
            async with websocket_messages(app, token) as (accepted, messages):
                initial = json.loads((await asyncio.wait_for(messages.get(), 5))["text"])
                await refresh()
                changed = json.loads((await asyncio.wait_for(messages.get(), 5))["text"])

        with then("initial and refreshed wire classes follow server order and preserve the legacy flag"):
            assert accepted["type"] == "websocket.accept"
            assert initial["type"] == changed["type"] == "queue:updated"
            assert initial["data"]["project_id"] == changed["data"]["project_id"] == 123
            assert [item["mr_iid"] for item in initial["data"]["queue"]] == [9, 2, 3, 4]
            assert [item["priority"] for item in initial["data"]["queue"]] == [
                "hotfix",
                "ordinary",
                "automated",
                "automated",
            ]
            assert [item["mr_iid"] for item in changed["data"]["queue"]] == [9, 3, 2, 4]
            assert [item["priority"] for item in changed["data"]["queue"]] == [
                "hotfix",
                "ordinary",
                "ordinary",
                "automated",
            ]
            assert [item["position"] for item in changed["data"]["queue"]] == [1, 2, 3, 4]
            assert [item["is_hotfix"] for item in changed["data"]["queue"]] == [True, False, False, False]
