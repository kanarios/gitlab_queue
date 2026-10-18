from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from gitlab_queue.config import ProjectConfig, Secret
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations


@scenario()
async def local_activation_reclassifies_saved_labels_and_preserves_known_hotfix():
    async with isolated_database_url() as url:
        await run_migrations(url)
        async with Database(url) as database:
            with given("legacy active entries and a known hotfix with an incomplete saved label snapshot"):
                old = QueueManager(database)
                automated = await old.add_to_queue(123, create_mr(iid=7, labels=["merge_queue", "dependencies"]))
                ordinary = await old.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
                hotfix = await old.add_to_queue(123, create_mr(iid=9, labels=[]), is_hotfix=True)
                foreign = await old.add_to_queue(456, create_mr(iid=7, labels=["merge_queue", "dependencies"]))
                project = ProjectConfig(project_id=123, token=Secret("test-token"), automation_labels=("dependencies",))
                queue = QueueManager(database, project_policies={123: project})

            with when("startup locally activates the configured policy before any remote access"):
                result = await queue.activate_priorities(123)
                items = await queue.get_active_queue(123)
                unchanged_foreign = await queue.get_queue_item(456, 7)

            with then("known hotfix survives and only classification plus durable final-position feedback change"):
                assert [item.mr_iid for item in items] == [9, 2, 7]
                assert [item.priority for item in items] == ["hotfix", "ordinary", "automated"]
                assert [(item.queue_id, item.queued_at) for item in items] == [
                    (hotfix.queue_id, hotfix.queued_at),
                    (ordinary.queue_id, ordinary.queued_at),
                    (automated.queue_id, automated.queued_at),
                ]
                assert result["changed"] == 1
                assert items[0].pending_notification is None
                assert items[1].pending_notification is not None
                assert items[2].pending_notification is not None
                assert unchanged_foreign == foreign
