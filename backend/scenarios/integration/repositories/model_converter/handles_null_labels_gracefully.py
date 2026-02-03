"""Test that ModelConverter handles null labels gracefully."""

from __future__ import annotations

import vedro
from scenarios.integration.repositories._helpers import create_test_mr_model

from gitlab_queue.db.repositories import ModelConverter


class Scenario(vedro.Scenario):
    subject = "model converter handles null labels gracefully"

    def given_mr_model_with_null_labels(self):
        self.mr = create_test_mr_model(iid=42, labels=None)

    def when_mr_model_is_converted(self):
        self.item = ModelConverter.mr_model_to_queue_item(self.mr)

    def then_labels_should_be_empty_list(self):
        assert self.item.labels == []

    async def do_cleanup(self):
        pass
