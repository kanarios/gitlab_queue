from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.fakes import FakeWebSocketManager

from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
from gitlab_queue.core.scheduler import QueueScheduler
from gitlab_queue.models.retorts import parse_merge_request_event
from gitlab_queue.webhooks.handlers import MRWebhookHandler

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from gitlab_queue.config import Settings
    from gitlab_queue.models.events import MergeRequestEvent


@dataclass
class GitLabServer:
    mrs: list[dict[str, Any]] = field(default_factory=list)
    comments: list[tuple[int, str]] = field(default_factory=list)
    notes: dict[int, str] = field(default_factory=dict)
    comment_methods: list[str] = field(default_factory=list)

    def respond(self, request: httpx.Request) -> httpx.Response:
        if "/notes" in request.url.path:
            mr_path = request.url.path.partition("/notes")[0]
            iid = int(mr_path.split("/")[-1])
            if request.method == "GET":
                if iid in self.notes:
                    return httpx.Response(200, json=[{"id": 100, "body": self.notes[iid]}])
                return httpx.Response(200, json=[])
            body = json.loads(request.content)["body"]
            self.comments.append((iid, body))
            self.comment_methods.append(request.method)
            self.notes[iid] = body
            return httpx.Response(201, json={"id": 100, "body": body})
        if request.url.path.endswith("/merge_requests"):
            label = request.url.params["labels"]
            return httpx.Response(200, json=[mr for mr in self.mrs if label in mr["labels"]])
        matches = [mr for mr in self.mrs if request.url.path.endswith(f"/merge_requests/{mr['iid']}")]
        if matches:
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


@asynccontextmanager
async def queue_environment() -> AsyncIterator[QueueEnvironment]:
    async with initialized_test_database() as db:
        queue = QueueManager(db=db)
        await queue.ensure_schema()
        settings = created_test_settings(project_id=123)
        server = GitLabServer()
        gitlab = GitLabClient(settings, transport=httpx.MockTransport(server.respond))
        notifier = MRNotifier(gitlab_client=gitlab, settings=settings)
        positions = QueuePositionNotifier(notifier=notifier, queue_manager=queue)
        websocket = FakeWebSocketManager()
        handler = MRWebhookHandler(settings, gitlab, queue, notifier, positions, websocket)
        scheduler = QueueScheduler(gitlab, queue, settings, position_notifier=positions)
        scheduler.set_websocket_manager(websocket)
        try:
            yield QueueEnvironment(queue, gitlab, server, settings, handler, scheduler, websocket)
        finally:
            await gitlab.close()


def label_event(action: str, previous: list[str], current: list[str]) -> MergeRequestEvent:
    return parse_merge_request_event(
        {
            "object_kind": "merge_request",
            "project": {"id": 123},
            "object_attributes": {
                "iid": 3,
                "title": "Urgent fix",
                "state": "opened",
                "action": action,
                "source_branch": "urgent-fix",
                "target_branch": "main",
            },
            "labels": [{"title": label} for label in current],
            "changes": {
                "labels": {
                    "previous": [{"title": label} for label in previous],
                    "current": [{"title": label} for label in current],
                }
            },
        }
    )
