import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from scenarios.contexts.database_backend import isolated_database_url
from scenarios.core.hotfix_priority._helpers import GitLabServer, queue_services
from scenarios.fakes import create_mr
from scenarios.transports.responses import mr_response
from vedro import given, scenario, then, when

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager
from gitlab_queue.webhooks.retry_processor import WebhookRetryProcessor


@dataclass
class DispatchServer(GitLabServer):
    arrivals: int = 0
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def respond(self, request):
        if request.method == "GET" and request.url.path.endswith("/merge_requests/3"):
            self.arrivals += 1
            if self.arrivals <= 2:
                if self.arrivals == 2:
                    self.entered.set()
                await self.release.wait()
        return await super().respond(request)


def payload(iid, label):
    return {
        "object_kind": "merge_request",
        "project": {"id": 123},
        "object_attributes": {
            "iid": iid,
            "title": f"MR{iid}",
            "state": "opened",
            "action": "update",
            "source_branch": f"feature-{iid}",
            "target_branch": "main",
            "updated_at": datetime.now(UTC).isoformat(),
        },
        "user": {"id": 42},
        "labels": [{"title": label}],
        "changes": {"labels": {"previous": [], "current": [{"title": label}]}},
        "_queue_webhook": {"event_uuid": f"chain-{iid}", "message_id": f"delivery-{iid}"},
    }


async def drained(manager, queue):
    while await manager.get_events_ready_for_retry(project_id=123):
        await asyncio.sleep(0.01)
    assert len(await queue.get_active_queue(123)) == 2


@scenario()
async def retry_processor_reopens_and_drains_with_at_least_once_dispatch():
    async with isolated_database_url() as database_url:
        with given("two webhook payloads persisted before process shutdown"):
            await run_migrations(database_url)
            async with Database(database_url) as database:
                manager = WebhookRetryManager(database, base_delay_seconds=0)
                await manager.add_to_retry_queue("merge_request", payload(3, "hotfix"), "outage", 123)
                await manager.add_to_retry_queue("merge_request", payload(4, "merge_queue"), "outage", 123)

        with when("two real retry processors reopen the store and overlap delivery before acknowledgment"):
            async with Database(database_url) as database:
                queue = QueueManager(database)
                foreign = await queue.add_to_queue(456, create_mr(iid=3))
                server = DispatchServer(mrs=[mr_response(3, labels=["hotfix"]), mr_response(4, labels=["merge_queue"])])
                async with queue_services(queue, server) as env:
                    manager = WebhookRetryManager(database, base_delay_seconds=0)
                    processors = [
                        WebhookRetryProcessor(
                            manager,
                            env.settings,
                            env.gitlab,
                            queue,
                            env.handler.notifier,
                            env.handler.position_notifier,
                            env.websocket,
                        )
                        for _ in range(2)
                    ]
                    tasks = [asyncio.create_task(processor.run()) for processor in processors]
                    try:
                        await asyncio.wait_for(server.entered.wait(), 8)
                        server.release.set()
                        await asyncio.wait_for(drained(manager, queue), 8)
                    finally:
                        server.release.set()
                        for processor in processors:
                            processor.request_shutdown()
                        await asyncio.wait_for(asyncio.gather(*tasks), 8)
                    items = await queue.get_active_queue(123)
                    dead = await manager.get_dlq_entries()
                    current_foreign = await queue.get_queue_item(456, 3)

        with then("duplicate dispatch neither resurrects retry rows nor duplicates the effective queue entry"):
            assert server.arrivals >= 2
            assert [item.mr_iid for item in items] == [3, 4]
            assert [item.is_hotfix for item in items] == [True, False]
            assert dead == []
            assert current_foreign == foreign
            assert [processor.is_processing for processor in processors] == [False, False]
