"""Test that ModelConverter handles null labels gracefully."""

from __future__ import annotations

import vedro
from scenarios.integration.repositories._helpers import create_test_mr_model

from gitlab_queue.db.repositories import ModelConverter


class Scenario(vedro.Scenario):
    subject = "model converter handles null labels gracefully"

    def given_mr_model_with_null_labels(self):
        """
        Prepare a merge request model with labels set to None and assign it to self.mr.

        Creates a test MR model with iid 42 and labels=None for use in the scenario.
        """
        self.mr = create_test_mr_model(iid=42, labels=None)

    def when_mr_model_is_converted(self):
        """
        Convert the stored merge request model to a queue item and save it on the scenario.

        Sets self.item to the result of converting self.mr using the ModelConverter.
        """
        self.item = ModelConverter.mr_model_to_queue_item(self.mr)

    def then_labels_should_be_empty_list(self):
        """
        Assert that the converted queue item's labels list is empty.

        Raises:
            AssertionError: If `self.item.labels` is not an empty list.
        """
        assert self.item.labels == []

    async def do_cleanup(self):
        """
        No-op cleanup hook for the scenario.

        This placeholder method performs no actions. Override in subclasses to run cleanup steps after the scenario completes.
        """
        pass
