from scenarios.contexts.database_backend import isolated_database_url
from scenarios.fakes import create_mr
from vedro import given, params, scenario, then, when

from gitlab_queue.config import ProjectConfig, Secret
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations
from gitlab_queue.db.repositories import MergeRequestRepository


@scenario()
async def repository_and_runtime_share_effective_order_and_positions():
    async with isolated_database_url() as url:
        await run_migrations(url)
        async with Database(url) as database:
            with given("an older automated entry followed by ordinary and hotfix entries"):
                project = ProjectConfig(project_id=123, token=Secret("test-token"), automation_labels=("dependencies",))
                queue = QueueManager(database, project_policies={123: project})
                await queue.add_to_queue(123, create_mr(iid=7, labels=["merge_queue", "dependencies"]))
                await queue.add_to_queue(123, create_mr(iid=2, labels=["merge_queue"]))
                await queue.add_to_queue(123, create_mr(iid=9, labels=["hotfix"]))

            with when("the ORM reader returns the order, candidate and automated entry position"):
                async with database.transaction() as session:
                    repository = MergeRequestRepository(session, project_id=123)
                    items = await repository.get_all_active()
                    next_item = await repository.get_next_queued()
                    position = await repository.get_position(7)
                runtime = await queue.get_active_queue(123)

            with then("both public readers follow the same literal effective-band order"):
                assert [item.iid for item in items] == [9, 2, 7]
                assert [item.mr_iid for item in runtime] == [9, 2, 7]
                assert next_item.iid == 9
                assert position == 3


@scenario(
    [
        params(("2026-10-18T03:00:00+00:00", "2026-10-18T02:00:00+00:00", "2026-10-18T01:00:00+00:00")),
        params(("2026-10-18T01:00:00+00:00", "2026-10-18T01:00:00+00:00", "2026-10-18T01:00:00+00:00")),
    ]
)
async def hotfix_fifo_uses_original_identity_despite_automation_and_queue_timestamps(timestamps):
    async with isolated_database_url() as url:
        await run_migrations(url)
        async with Database(url) as database:
            with given("three hotfixes with interleaved automation facts and non-ordering timestamps"):
                project = ProjectConfig(project_id=123, token=Secret("test-token"), automation_labels=("dependencies",))
                queue = QueueManager(database, project_policies={123: project})
                await queue.add_to_queue(123, create_mr(iid=7, labels=["hotfix", "dependencies"]))
                await queue.add_to_queue(123, create_mr(iid=2, labels=["hotfix"]))
                await queue.add_to_queue(123, create_mr(iid=9, labels=["hotfix", "dependencies"]))
                async with database.transaction() as session:
                    repository = MergeRequestRepository(session, project_id=123)
                    (await repository.get_by_iid(7)).queued_at = timestamps[0]
                    (await repository.get_by_iid(2)).queued_at = timestamps[1]
                    (await repository.get_by_iid(9)).queued_at = timestamps[2]

            with when("both public readers select the hotfix band"):
                runtime = await queue.get_active_queue(123)
                async with database.transaction() as session:
                    repository = MergeRequestRepository(session, project_id=123)
                    items = await repository.get_all_active()
                    next_item = await repository.get_next_queued()
                    position = await repository.get_position(2)

            with then("automation does not split hotfixes and timestamps do not replace original FIFO"):
                assert [item.mr_iid for item in runtime] == [7, 2, 9]
                assert [item.iid for item in items] == [7, 2, 9]
                assert [item.queued_at for item in items] == list(timestamps)
                assert next_item.iid == 7
                assert position == 2
