"""Test _verify_mr_in_queue returns False on GitLabNotFoundError.

When the GitLab API returns a 404 for the MR (it was deleted or is
otherwise inaccessible), _verify_mr_in_queue should return False
without raising an exception.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabNotFoundError

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "verify mr in queue returns false when mr not found"

    def given_processor_with_mr_not_found(self):
        self.processor = create_mock_processor()
        self.processor.gitlab_client.get_mr.side_effect = GitLabNotFoundError("MR not found")

    async def when_verify_mr_in_queue_is_called(self):
        self.result = await self.processor._verify_mr_in_queue(42)

    def then_result_is_false(self):
        assert self.result is False
