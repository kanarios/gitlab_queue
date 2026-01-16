"""Unit tests for Pipeline and Job models."""

import vedro

from gitlab_queue.models.pipeline import Pipeline


class Scenario(vedro.Scenario):
    subject = "pipeline can have various statuses"

    def given_valid_statuses(self):
        self.statuses = ["pending", "running", "success", "failed", "canceled"]

    def when_pipelines_are_created_with_each_status(self):
        self.pipelines = [
            Pipeline(id=i, status=status, sha=f"sha{i}", ref="master") for i, status in enumerate(self.statuses)
        ]

    def then_all_pipelines_should_have_correct_status(self):
        for pipeline, expected_status in zip(self.pipelines, self.statuses, strict=False):
            assert pipeline.status == expected_status
