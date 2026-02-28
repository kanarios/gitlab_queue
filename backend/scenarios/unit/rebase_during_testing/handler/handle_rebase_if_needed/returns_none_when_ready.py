"""Test handle_rebase_if_needed returns (ctx, None) when READY."""

import vedro

from ..._helpers import (
    MockMergeRequest,
    create_context,
    create_handler,
    create_mock_gitlab_client,
)


class Scenario(vedro.Scenario):
    subject = "handle_rebase_if_needed returns (ctx, None) when READY"

    def given_handler_with_ready_mr(self):
        mr = MockMergeRequest(merge_status="can_be_merged", has_conflicts=False)
        self.client = create_mock_gitlab_client(mr=mr)
        self.handler = create_handler(gitlab_client=self.client)
        self.ctx = create_context()

    async def when_handle_rebase_if_needed_is_called(self):
        self.new_ctx, self.pipeline = await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_context_is_same(self):
        assert self.new_ctx is self.ctx

    def and_pipeline_is_none(self):
        assert self.pipeline is None
