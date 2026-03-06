"""Test _get_failed_jobs returns empty list on exception.

When get_pipeline_jobs raises an unexpected exception, _get_failed_jobs
should catch the error and return an empty list rather than propagating
the exception to the caller.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "get failed jobs returns empty list on exception"

    def given_processor_with_failing_pipeline_jobs_fetch(self):
        self.processor = create_mock_processor()
        self.processor.gitlab_client.pipeline_jobs_response = Exception("Connection error")

    async def when_get_failed_jobs_is_called(self):
        self.result = await self.processor._get_failed_jobs(pipeline_id=100)

    def then_result_is_empty_list(self):
        assert self.result == []
