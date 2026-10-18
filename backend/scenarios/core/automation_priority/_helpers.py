from contextlib import asynccontextmanager

from scenarios.contexts.database_backend import isolated_database_url
from scenarios.contexts.gitlab_client_factory import created_test_settings
from scenarios.core.hotfix_priority._helpers import GitLabServer, queue_services

from gitlab_queue.config import ProjectConfig, Secret
from gitlab_queue.core.project_components import ProjectSettings
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.db.database import Database
from gitlab_queue.db.migrations import run_migrations


@asynccontextmanager
async def automation_environment(*, server_factory=GitLabServer, automation_labels=("dependencies", "renovate")):
    project = ProjectConfig(
        project_id=123, token=Secret("test-token"), target_branch="main", automation_labels=automation_labels
    )
    settings = ProjectSettings(project, created_test_settings())
    async with isolated_database_url() as url:
        await run_migrations(url)
        async with Database(url) as database:
            queue = QueueManager(database, project_policies={123: project})
            async with queue_services(queue, server_factory(), settings) as environment:
                yield environment
