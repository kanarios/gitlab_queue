"""History API passes the selected project ID to its injected UoW factory."""

from __future__ import annotations

import vedro
from scenarios.contexts.api_helpers import created_test_app
from scenarios.fakes import FakeUnitOfWork
from starlette.testclient import TestClient

from gitlab_queue.auth.jwt_handler import create_access_token


class Scenario(vedro.Scenario):
    subject = "project scoped UoW factory receives selected project ID"

    def given_two_configured_projects_and_factory(self):
        self.app, self.state = created_test_app()
        self.state.project_components = {101: None, 202: None}
        self.received_project_ids: list[int] = []
        uow = FakeUnitOfWork()

        def create_uow(database, project_id):
            self.received_project_ids.append(project_id)
            return uow

        self.state.uow_factory = create_uow
        self.client = TestClient(self.app, raise_server_exceptions=False)
        token = create_access_token(
            {"id": 1, "username": "member", "project_ids": [101, 202]},
            self.state.settings,
        )
        self.headers = {"Authorization": f"Bearer {token}"}

    def when_second_projects_history_is_requested(self):
        self.response = self.client.get("/api/projects/202/history", headers=self.headers)

    def then_factory_receives_the_resolved_project_id(self):
        assert self.response.status_code == 200
        assert self.received_project_ids == [202]
