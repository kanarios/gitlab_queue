"""Unit tests for Pipeline and Job models."""

import vedro

from gitlab_queue.models.pipeline import Pipeline


class Scenario(vedro.Scenario):
    subject = "pipeline is immutable (frozen)"

    def given_pipeline(self):
        self.pipeline = Pipeline(id=1, status="pending", sha="abc", ref="master")

    def when_trying_to_modify_pipeline(self):
        try:
            self.pipeline.status = "success"
            self.error = None
        except Exception as e:
            self.error = e

    def then_it_should_raise_frozen_error(self):
        assert self.error is not None
