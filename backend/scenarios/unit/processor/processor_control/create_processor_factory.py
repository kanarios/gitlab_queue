"""Test create_processor() factory function returns a MergeProcessor.

Line 1592: create_processor() factory creates a configured MergeProcessor.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import MergeProcessor, create_processor

from .._helpers import (
    create_mock_gitlab_client,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "create_processor factory returns a configured MergeProcessor"

    def given_dependencies(self):
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.notifier = create_mock_notifier()
        self.settings = create_mock_settings()

    def when_create_processor_is_called(self):
        self.processor = create_processor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            settings=self.settings,
        )

    def then_returns_merge_processor_instance(self):
        assert isinstance(self.processor, MergeProcessor)

    def and_dependencies_are_set(self):
        assert self.processor.gitlab_client is self.gitlab_client
        assert self.processor.queue_manager is self.queue_manager
        assert self.processor.notifier is self.notifier
        assert self.processor.settings is self.settings
