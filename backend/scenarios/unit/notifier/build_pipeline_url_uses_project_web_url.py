"""Test: build_pipeline_url uses project web URL from GitLab API."""

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.notifier import MRNotifier


class Scenario(vedro.Scenario):
    subject = "build pipeline url uses project web url from GitLab API"

    def given_notifier(self):
        self.gitlab_client = MagicMock()
        self.gitlab_client.get_project_web_url = AsyncMock(return_value="https://gitlab.example.com/group/project")

        self.settings = MagicMock()
        self.settings.gitlab_url = "https://should-not-be-used.example.com"

        self.notifier = MRNotifier(
            gitlab_client=self.gitlab_client,
            settings=self.settings,
        )

    async def when_build_pipeline_url_is_called(self):
        self.url = await self.notifier.build_pipeline_url(456)

    def then_url_should_contain_project_path(self):
        assert self.url == "https://gitlab.example.com/group/project/-/pipelines/456"

    def and_gitlab_api_should_be_called(self):
        self.gitlab_client.get_project_web_url.assert_awaited_once()
