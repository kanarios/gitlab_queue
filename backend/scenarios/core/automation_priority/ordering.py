from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from vedro import given, scenario, then, when

from gitlab_queue.config import ProjectConfig, Secret
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations


@scenario()
async def effective_bands_preserve_original_entry_order():
    async with isolated_database_url() as url:
        await run_migrations(url)
        async with Database(url) as database:
            with given("interleaved automated, ordinary and hotfix admissions for one project"):
                project = ProjectConfig(project_id=123, token=Secret("test-token"), automation_labels=("dependencies",))
                queue = QueueManager(database, project_policies={123: project})
                await queue.add_to_queue(123, create_mr(iid=7, labels=["merge_queue", "dependencies"]))
                await queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
                await queue.add_to_queue(123, create_mr(iid=9, labels=["hotfix"]))
                await queue.add_to_queue(123, create_mr(iid=4, labels=["merge_queue", "dependencies"]))
                await queue.add_to_queue(123, create_mr(iid=8, labels=["merge_queue"]))
                await queue.add_to_queue(123, create_mr(iid=1, labels=["hotfix", "dependencies"]))

            with when("the public queue returns its active order and next candidate"):
                items = await queue.get_active_queue(123)
                next_item = await queue.get_next_mr(123)

            with then("effective priority wins and the original row IDs break ties within each band"):
                assert [item.mr_iid for item in items] == [9, 1, 2, 8, 7, 4]
                assert [item.priority for item in items] == [
                    "hotfix",
                    "hotfix",
                    "ordinary",
                    "ordinary",
                    "automated",
                    "automated",
                ]
                assert next_item.mr_iid == 9
