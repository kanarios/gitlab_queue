"""Test that ModelConverter handles invalid JSON labels gracefully."""

from __future__ import annotations

import vedro
from scenarios.integration.repositories._helpers import create_test_mr_model

from gitlab_queue.db.repositories import ModelConverter


class Scenario(vedro.Scenario):
    subject = "model converter handles invalid json labels gracefully"

    def given_mr_model_with_invalid_json_labels(self):
        """
        Create and store a test merge request model whose labels field contains an invalid JSON string.
        
        The created model is assigned to `self.mr` and has `iid=42` and `labels="not json"`.
        """
        self.mr = create_test_mr_model(iid=42, labels="not json")

    def when_mr_model_is_converted(self):
        """
        Convert the scenario's merge request model to a queue item and assign it to self.item.
        """
        self.item = ModelConverter.mr_model_to_queue_item(self.mr)

    def then_labels_should_be_empty_list(self):
        """
        Verify that the converted item's labels are an empty list.
        
        Asserts that self.item.labels is equal to [].
        """
        assert self.item.labels == []

    async def do_cleanup(self):
        """
        Performs scenario cleanup after execution.
        
        This lifecycle hook is implemented as a no-op and exists to allow asynchronous cleanup logic to be added later if needed.
        """
        pass
