"""An unavailable label list must remain distinct from a complete empty list."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "fetch_mrs_by_label reports incomplete discovery when GitLabAPIError is raised"

    def given_processor_with_gitlab_api_error(self):
        self.processor = create_mock_processor()

        self.processor.gitlab_client.list_mrs_error = GitLabAPIError("Internal server error")

    async def when_fetch_mrs_by_label_is_called(self):
        self.result = await self.processor._fetch_mrs_by_label("merge_queue")

    def then_result_is_incomplete(self):
        assert self.result is None
