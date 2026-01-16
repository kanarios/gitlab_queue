"""Unit tests for Pipeline and Job models."""

import vedro

from gitlab_queue.models.pipeline import Job


class Scenario(vedro.Scenario):
    subject = "create job with web URL"

    def when_job_is_created_with_url(self):
        self.job = Job(
            id=1000,
            name="build",
            status="running",
            stage="build",
            web_url="https://gitlab.com/project/-/jobs/1000",
        )

    def then_it_should_have_web_url(self):
        assert self.job.web_url == "https://gitlab.com/project/-/jobs/1000"
