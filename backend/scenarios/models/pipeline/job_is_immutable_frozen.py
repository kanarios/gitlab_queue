"""Unit tests for Pipeline and Job models."""

import vedro

from gitlab_queue.models.pipeline import Job


class Scenario(vedro.Scenario):
    subject = "job is immutable (frozen)"

    def given_job(self):
        self.job = Job(id=1, name="test", status="pending", stage="test")

    def when_trying_to_modify_job(self):
        try:
            self.job.status = "success"
            self.error = None
        except Exception as e:
            self.error = e

    def then_it_should_raise_frozen_error(self):
        assert self.error is not None
