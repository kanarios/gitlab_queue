import asyncio
from dataclasses import replace

from scenarios.contexts.database_backend import isolated_database_url
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.core.hotfix_priority._helpers import GitLabServer, label_event, queue_services
from scenarios.transports.responses import mr_response
from vedro import catched, given, scenario, then, when

from gitlab_queue.config import ProjectConfig, Secret
from gitlab_queue.core.project_components import ProjectSettings
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations


@scenario()
async def same_iid_projects_use_their_own_policy_triggers_comments_and_snapshots():
    async with isolated_database_url() as url:
        await run_migrations(url)
        async with Database(url) as database:
            first = ProjectConfig(
                123,
                Secret("one"),
                queue_label="queue-one",
                hotfix_label="urgent-one",
                automation_labels=("dependencies",),
            )
            second = ProjectConfig(
                456, Secret("two"), queue_label="queue-two", hotfix_label="urgent-two", automation_labels=("renovate",)
            )
            queue = QueueManager(database, project_policies={123: first, 456: second})
            shared = created_test_settings()
            async with (
                queue_services(
                    queue,
                    GitLabServer(mrs=[mr_response(3, labels=["queue-one", "dependencies"])]),
                    ProjectSettings(first, shared),
                ) as one,
                queue_services(
                    queue,
                    GitLabServer(mrs=[mr_response(3, project_id=456, labels=["queue-two", "dependencies"])]),
                    ProjectSettings(second, shared),
                ) as two,
            ):
                with given("the same IID in two projects with different policies and trigger names"):
                    await one.handler.handle(label_event("labeled", [], ["queue-one", "dependencies"]))
                    await two.handler.handle(
                        replace(label_event("labeled", [], ["queue-two", "dependencies"]), project_id=456)
                    )
                    before_one = await queue.get_queue_item(123, 3)
                    before_two = await queue.get_queue_item(456, 3)
                with when("both projects concurrently move the same IID in opposite priority directions"):
                    await asyncio.gather(
                        one.handler.handle(label_event("unlabeled", ["queue-one", "dependencies"], ["queue-one"])),
                        two.handler.handle(
                            replace(
                                label_event("update", ["queue-two", "dependencies"], ["queue-two", "renovate"]),
                                project_id=456,
                            )
                        ),
                    )
                    after_one = await queue.get_queue_item(123, 3)
                    after_two = await queue.get_queue_item(456, 3)
                    with catched(ValueError) as error:
                        queue.classify_labels(789, ["queue-one", "dependencies"])
                with then("each incarnation retains its identity and no project receives another policy or feedback"):
                    assert [before_one.priority, before_two.priority] == ["automated", "ordinary"]
                    assert [after_one.priority, after_two.priority] == ["ordinary", "automated"]
                    assert (after_one.queue_id, after_one.queued_at) == (before_one.queue_id, before_one.queued_at)
                    assert (after_two.queue_id, after_two.queued_at) == (before_two.queue_id, before_two.queued_at)
                    assert "Ordinary priority" in one.server.notes[3]
                    assert "Automated priority" in two.server.notes[3]
                    assert set(one.websocket.broadcast_project_ids) == {123}
                    assert set(two.websocket.broadcast_project_ids) == {456}
                    assert error.type is ValueError
