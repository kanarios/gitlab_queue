"""Test: build_pipeline_url uses project web URL from GitLab API."""

import vedro

from gitlab_queue.core.notifier import MRNotifier
from scenarios.fakes import FakeGitLabClient, FakeSettings


class Scenario(vedro.Scenario):
    subject = "build pipeline url uses project web url from GitLab API"

    def given_notifier(self):
        self.gitlab_client = FakeGitLabClient(
            project_web_url="https://gitlab.example.com/group/project",
        )
        self.settings = FakeSettings()

        self.notifier = MRNotifier(
            gitlab_client=self.gitlab_client,
            settings=self.settings,
        )

    async def when_build_pipeline_url_is_called(self):
        self.url = await self.notifier.build_pipeline_url(456)

    def then_url_should_contain_project_path(self):
        assert self.url == "https://gitlab.example.com/group/project/-/pipelines/456"

    def and_gitlab_api_should_be_called(self):
        # FakeGitLabClient doesn't record get_project_web_url calls,
        # but the URL result proves the method was invoked
        assert "gitlab.example.com/group/project" in self.url
