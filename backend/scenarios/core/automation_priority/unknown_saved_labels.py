import json

import httpx
from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from sqlalchemy import text
from vedro import given, params, scenario, then, when

from gitlab_queue.config import Settings
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations
from gitlab_queue.main import create_application


@scenario([params(None), params("{broken"), params('{"partial": true}'), params("[1]")])
async def offline_startup_preserves_known_hotfix_and_unknown_saved_label_bytes(raw):
    async with isolated_database_url() as url:
        with given("a known hotfix with unavailable persisted labels and stale automation metadata"):
            await run_migrations(url)
            async with Database(url) as database:
                original = await QueueManager(database).add_to_queue(123, create_mr(iid=3, labels=[]), is_hotfix=True)
                async with database.transaction() as session:
                    await session.execute(
                        text("UPDATE merge_requests SET labels = :raw, is_automated = 1 WHERE project_id = 123"),
                        {"raw": raw},
                    )
            settings = Settings(
                database_url=url,
                gitlab_url="https://gitlab.test",
                jwt_secret="a" * 64,
                webhook_enabled=False,
                api_max_retries=1,
                projects_json=json.dumps([{"project_id": 123, "token": "test", "automation_labels": ["dependencies"]}]),
            )

        with when("the real startup barrier activates locally while GitLab returns503"):
            app = await create_application(
                settings, gitlab_transport=httpx.MockTransport(lambda _request: httpx.Response(503))
            )
            try:
                current = await app.queue_manager.get_queue_item(123, 3)
                async with app.database.session() as session:
                    persisted = (
                        await session.execute(text("SELECT labels FROM merge_requests WHERE project_id = 123"))
                    ).scalar()
                    await session.commit()
            finally:
                await app.gitlab_client.close()
                await app.database.close()

        with then("the local class is safe without inventing remote freshness or rewriting raw labels"):
            assert current.priority == "hotfix"
            assert current.is_automated is False
            assert current.labels == []
            assert current.queue_id == original.queue_id
            assert current.queued_at == original.queued_at
            assert persisted == raw
            assert app.processor.current_mr_iid is None
