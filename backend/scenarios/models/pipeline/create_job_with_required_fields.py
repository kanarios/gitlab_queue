"""Unit tests for Pipeline and Job models."""

import vedro

from gitlab_queue.models.pipeline import Job


class Scenario(vedro.Scenario):
    subject = "create job with required fields"

    def given_job_data(self):
        self.job_id = 999
        self.name = "test"
        self.status = "success"
        self.stage = "test"

    def when_job_is_created(self):
        self.job = Job(
            id=self.job_id,
            name=self.name,
            status=self.status,
            stage=self.stage,
        )

    def then_it_should_have_correct_fields(self):
        assert self.job.id == self.job_id
        assert self.job.name == self.name
        assert self.job.status == self.status
        assert self.job.stage == self.stage
        assert self.job.web_url is None
