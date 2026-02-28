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
        """
        Prepare a mock processor whose GitLab client raises GitLabNotFoundError for MR lookups.

        Sets self.processor to a mock created by create_mock_processor() and configures its gitlab_client.get_mr to raise GitLabNotFoundError("MR not found") when called.
        """
        self.processor = create_mock_processor()
        self.processor.gitlab_client.get_mr.side_effect = GitLabNotFoundError("MR not found")

    async def when_verify_mr_in_queue_is_called(self):
        """
        Call the processor's _verify_mr_in_queue with MR id 42 and save the outcome.

        This step invokes _verify_mr_in_queue(42) and assigns its return value to self.result for later assertions.
        """
        self.result = await self.processor._verify_mr_in_queue(42)

    def then_result_is_false(self):
        """
        Asserts that the stored test result is False.

        Raises:
            AssertionError: If self.result is not exactly False.
        """
        assert self.result is False
