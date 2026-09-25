"""A failed project verification remains unhealthy until a request succeeds."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import vedro
from fastapi.testclient import TestClient
from scenarios.contexts.api_helpers import created_mock_settings, created_webhook_state
from scenarios.transports import GitLabMockTransport
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabClient, GitLabServerError
from gitlab_queue.health import ApplicationHealth, ComponentStatus, GitLabHealth
from gitlab_queue.main import verify_gitlab_access
from gitlab_queue.webhooks.router import create_webhook_app


class Scenario(vedro.Scenario):
    subject = "failed startup project health stays unhealthy until GitLab succeeds"

    async def given_project_verification_failed_during_startup(self):
        self.settings = created_mock_settings(gitlab_project_id=101)
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            "/api/v4/projects/101/merge_requests",
            [httpx.Response(500, json={"message": "GitLab unavailable"}), httpx.Response(200, json=[])],
        )
        self.gitlab_client = GitLabClient.for_project(
            self.settings.projects[0],
            self.settings,
            transport=self.transport,
        )

        with catched(GitLabAPIError) as self.startup_error:
            await verify_gitlab_access(self.gitlab_client, self.settings.projects[0])

        self.project_health = GitLabHealth(
            status=ComponentStatus.UNHEALTHY,
            circuit_state="unknown",
            failure_count=0,
        )
        self.state = created_webhook_state(settings=self.settings)
        self.state.health = ApplicationHealth(
            database=ComponentStatus.HEALTHY,
            gitlab=self.project_health,
            gitlab_by_project={101: self.project_health},
            processor_running=True,
            webhook_server_running=True,
        )
        self.state.gitlab_client = self.gitlab_client
        self.state.project_components = {
            101: SimpleNamespace(gitlab_client=self.gitlab_client, health=self.project_health)
        }
        self.http_client = TestClient(create_webhook_app(self.state))

    async def when_project_client_later_succeeds(self):
        self.health_before_success = self.http_client.get("/health")
        self.project_mrs = await self.gitlab_client.list_mrs_with_label(self.settings.queue_label)
        self.health_after_success = self.http_client.get("/health")

    def then_health_remains_unhealthy_then_tracks_the_success(self):
        assert self.startup_error.type is GitLabServerError
        assert self.health_before_success.status_code == 200
        assert self.health_before_success.json()["components"]["gitlab"] == "unhealthy"
        assert self.project_mrs == []
        assert self.gitlab_client.last_request_succeeded is True
        assert self.health_after_success.status_code == 200
        assert self.health_after_success.json()["components"]["gitlab"] == "healthy"

    async def do_cleanup(self):
        await self.gitlab_client.close()
