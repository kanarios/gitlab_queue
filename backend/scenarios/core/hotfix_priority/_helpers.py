from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

import httpx
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.fakes import FakeWebSocket, FakeWebSocketManager

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
from gitlab_queue.core.scheduler import QueueScheduler
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations
from gitlab_queue.models.retorts import parse_merge_request_event
from gitlab_queue.webhooks.handlers import MRWebhookHandler

if TYPE_CHECKING:
    from asyncio import Event
    from collections.abc import AsyncIterator

    from gitlab_queue.config import Settings
    from gitlab_queue.models.events import MergeRequestEvent


@dataclass
class GitLabServer:
    mrs: list[dict[str, Any]] = field(default_factory=list)
    comments: list[tuple[int, str]] = field(default_factory=list)
    notes: dict[int, str] = field(default_factory=dict)
    comment_methods: list[str] = field(default_factory=list)
    failed_comment_iids: set[int] = field(default_factory=set)
    comment_attempts: list[int] = field(default_factory=list)
    barriers: dict[tuple[str, str], tuple[Event, Event]] = field(default_factory=dict)
    label_snapshots: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    after_barriers: dict[tuple[str, str], tuple[Event, Event]] = field(default_factory=dict)
    failed_label_iids: set[int] = field(default_factory=set)
    after_mutation_barriers: dict[tuple[str, str], tuple[Event, Event]] = field(default_factory=dict)
    label_requests: list[httpx.Request] = field(default_factory=list)
    authenticated_user: dict[str, Any] = field(default_factory=lambda: {"id": 1, "bot": True})

    async def respond(self, request: httpx.Request) -> httpx.Response:
        response = self._response(request) if request.method == "GET" else None
        barrier = self.barriers.get((request.method, request.url.params.get("labels", request.url.path)))
        if barrier is not None:
            entered, release = barrier
            entered.set()
            await release.wait()
        result = response if response is not None else self._response(request)
        after = self.after_barriers.get((request.method, request.url.path))
        if after is not None:
            entered, release = after
            entered.set()
            await release.wait()
        if request.method == "PUT" and "/notes" not in request.url.path:
            mutation = next(iter(json.loads(request.content)), "")
            after_mutation = self.after_mutation_barriers.get((mutation, request.url.path))
            if after_mutation is not None:
                entered, release = after_mutation
                entered.set()
                await release.wait()
        return result

    def _response(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v4/user":
            return httpx.Response(200, json=self.authenticated_user)
        if "/notes" in request.url.path:
            mr_path = request.url.path.partition("/notes")[0]
            iid = int(mr_path.split("/")[-1])
            if request.method == "GET":
                if iid in self.notes:
                    return httpx.Response(200, json=[{"id": 100, "body": self.notes[iid]}])
                return httpx.Response(200, json=[])
            body = json.loads(request.content)["body"]
            self.comment_attempts.append(iid)
            if iid in self.failed_comment_iids:
                return httpx.Response(503, json={"message": "unavailable"})
            self.comments.append((iid, body))
            self.comment_methods.append(request.method)
            self.notes[iid] = body
            return httpx.Response(201, json={"id": 100, "body": body})
        if request.url.path.endswith("/merge_requests"):
            label = request.url.params["labels"]
            if label in self.label_snapshots:
                return httpx.Response(200, json=self.label_snapshots[label])
            return httpx.Response(
                200,
                json=[mr for mr in self.mrs if label in mr["labels"] and mr["state"] == request.url.params["state"]],
            )
        matches = [mr for mr in self.mrs if request.url.path.endswith(f"/merge_requests/{mr['iid']}")]
        if matches:
            if request.method == "PUT":
                self.label_requests.append(request)
                if matches[0]["iid"] in self.failed_label_iids:
                    return httpx.Response(503, json={"message": "unavailable"})
                data = json.loads(request.content)
                removed = data.get("remove_labels", "").split(",")
                added = data.get("add_labels", "").split(",")
                matches[0]["labels"] = list(
                    dict.fromkeys(
                        [label for label in matches[0]["labels"] if label not in removed]
                        + [label for label in added if label]
                    )
                )
                matches[0]["updated_at"] = datetime.now(UTC).isoformat()
            return httpx.Response(200, json=matches[0])
        return httpx.Response(404)


@dataclass
class QueueEnvironment:
    queue: QueueManager
    gitlab: GitLabClient
    server: GitLabServer
    settings: Settings
    handler: MRWebhookHandler
    scheduler: QueueScheduler
    websocket: FakeWebSocketManager


@dataclass
class ObservedQueue(QueueManager):
    state_updated: asyncio.Event = field(default_factory=asyncio.Event)
    queue_read: asyncio.Event = field(default_factory=asyncio.Event)
    metadata_updated: asyncio.Event = field(default_factory=asyncio.Event)
    requeue_saved: asyncio.Event = field(default_factory=asyncio.Event)
    requeue_cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    item_read: asyncio.Event = field(default_factory=asyncio.Event)

    async def get_queue_item(self, project_id, mr_iid):
        item = await super().get_queue_item(project_id, mr_iid)
        self.item_read.set()
        return item

    async def defer_requeue(self, project_id, mr, request):
        result = await super().defer_requeue(project_id, mr, request)
        self.requeue_saved.set()
        return result

    async def cancel_requeue(self, project_id, queue_id, event_at, **options):
        result = await super().cancel_requeue(project_id, queue_id, event_at, **options)
        self.requeue_cancelled.set()
        return result

    async def update_mr_state(self, project_id: int, mr_iid: int, state: str, **extra: Any) -> bool:
        result = await super().update_mr_state(project_id, mr_iid, state, **extra)
        self.state_updated.set()
        return result

    async def get_active_queue(self, project_id: int | None = None) -> list[Any]:
        result = await super().get_active_queue(project_id)
        self.queue_read.set()
        return result

    async def update_hotfix_status(self, project_id, mr_iid, is_hotfix, labels, **options):
        result = await super().update_hotfix_status(project_id, mr_iid, is_hotfix, labels, **options)
        self.metadata_updated.set()
        return result


@dataclass(eq=False)
class CompletionSocket(FakeWebSocket):
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict[str, Any]) -> None:
        await super().send_json(data)
        if data["type"] == "mr:completed":
            self.entered.set()
            await self.release.wait()


@asynccontextmanager
async def queue_environment(revision: str = "head") -> AsyncIterator[QueueEnvironment]:
    with TemporaryDirectory() as directory:
        database_url = f"sqlite+aiosqlite:///{Path(directory) / 'queue.db'}"
        await run_migrations(database_url, revision)
        async with Database(database_url) as db, queue_services(QueueManager(db), GitLabServer()) as env:
            yield env


@asynccontextmanager
async def queue_services(queue: QueueManager, server: GitLabServer) -> AsyncIterator[QueueEnvironment]:
    settings = created_test_settings(project_id=123)
    gitlab = GitLabClient(settings, transport=httpx.MockTransport(server.respond))
    notifier = MRNotifier(gitlab_client=gitlab, settings=settings, queue_manager=queue)
    positions = QueuePositionNotifier(notifier=notifier, queue_manager=queue)
    websocket = FakeWebSocketManager()
    handler = MRWebhookHandler(settings, gitlab, queue, notifier, positions, websocket)
    scheduler = QueueScheduler(gitlab, queue, settings, position_notifier=positions)
    scheduler.set_websocket_manager(websocket)
    try:
        yield QueueEnvironment(queue, gitlab, server, settings, handler, scheduler, websocket)
    finally:
        await gitlab.close()


def label_event(
    action: str,
    previous: list[str],
    current: list[str],
    *,
    state: str = "opened",
    updated_at: str | None = None,
    event_uuid: str | None = None,
    message_id: str | None = None,
    user_id: int = 42,
) -> MergeRequestEvent:
    return parse_merge_request_event(
        {
            "object_kind": "merge_request",
            "project": {"id": 123},
            "object_attributes": {
                "iid": 3,
                "title": "Urgent fix",
                "state": state,
                "action": action,
                "source_branch": "urgent-fix",
                "target_branch": "main",
                "updated_at": updated_at,
            },
            "_queue_webhook": {"event_uuid": event_uuid, "message_id": message_id},
            "user": {"id": user_id},
            "labels": [{"title": label} for label in current],
            "changes": {
                "labels": {
                    "previous": [{"title": label} for label in previous],
                    "current": [{"title": label} for label in current],
                }
            },
        }
    )
