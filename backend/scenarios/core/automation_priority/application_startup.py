import json

import httpx
from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from gitlab_queue.config import Settings
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations
from gitlab_queue.main import create_application


@scenario()
async def application_activates_project_policy_before_remote_verification_and_runtime_tasks():
    async with isolated_database_url() as url:
        with given("an existing database whose saved automation labels predate the new project policy"):
            await run_migrations(url)
            async with Database(url) as database:
                old = QueueManager(database)
                original = await old.add_to_queue(123, create_mr(iid=7, labels=["merge_queue", "dependencies"]))
                await old.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
            settings = Settings(
                database_url=url,
                gitlab_url="https://gitlab.test",
                jwt_secret="a" * 64,
                webhook_enabled=False,
                projects_json=json.dumps(
                    [{"project_id": 123, "token": "test-token", "automation_labels": ["dependencies"]}]
                ),
            )
            observed_orders = []

            async def verify_request(request):
                async with Database(url) as observed_database:
                    rows = await QueueManager(observed_database).get_active_queue(123)
                    observed_orders.append([item.mr_iid for item in rows])
                return httpx.Response(200, json=[])

        with when("the real application initializes with an injected external transport"):
            app = await create_application(settings, gitlab_transport=httpx.MockTransport(verify_request))
            try:
                rows = await app.queue_manager.get_active_queue(123)
                item = await app.queue_manager.get_queue_item(123, 7)
                processing = app.processor.current_mr_iid
            finally:
                await app.gitlab_client.close()
                await app.database.close()

        with then("local activation is already complete at the first HTTP call and no processing has started"):
            assert observed_orders == [[2, 7]]
            assert [entry.mr_iid for entry in rows] == [2, 7]
            assert item.priority == "automated"
            assert (item.queue_id, item.queued_at) == (original.queue_id, original.queued_at)
            assert processing is None
