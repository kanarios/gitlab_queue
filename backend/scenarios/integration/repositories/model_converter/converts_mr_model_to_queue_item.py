"""Test that ModelConverter converts MergeRequestModel to QueueItem."""

from __future__ import annotations

import vedro
from scenarios.integration.repositories._helpers import create_test_mr_model

from gitlab_queue.db.repositories import ModelConverter
from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "model converter converts mr model to queue item"

    def given_mr_model(self):
        """
        Prepare a Merge Request model on self.mr populated with test data.
        
        Creates and assigns to self.mr a test MR model with preset fields used by the scenario, including iid 42, title "Test MR", author information ("Test User", "testuser", avatar URL), status "rebasing", hotfix flag set, labels ["merge_queue", "urgent"], target_branch "main", pipeline_id 1234 with status "running", retry_count 2, last_error "timeout", and stale_warning_sent flag set.
        """
        self.mr = create_test_mr_model(
            iid=42,
            title="Test MR",
            author_name="Test User",
            author_username="testuser",
            author_avatar="https://avatar.url/test.png",
            status="rebasing",
            is_hotfix=1,
            labels='["merge_queue", "urgent"]',
            target_branch="main",
            pipeline_id=1234,
            pipeline_status="running",
            retry_count=2,
            last_error="timeout",
            stale_warning_sent=1,
        )

    def when_mr_model_is_converted(self):
        """
        Convert the stored Merge Request model to a QueueItem and save it on self.item.
        
        This invokes ModelConverter.mr_model_to_queue_item with the MR model previously assigned to self.mr and stores the resulting QueueItem instance in self.item.
        """
        self.item = ModelConverter.mr_model_to_queue_item(self.mr)

    def then_queue_item_fields_should_match(self):
        """
        Assert that the converted QueueItem matches the expected Merge Request values.
        
        Checks that self.item is a QueueItem and that its fields equal the expected test values:
        mr_iid 42, title "Test MR", author_name "Test User", author_username "testuser",
        author_avatar "https://avatar.url/test.png", state "rebasing", is_hotfix True,
        labels ["merge_queue", "urgent"], target_branch "main", pipeline_id 1234,
        pipeline_status "running", retry_count 2, last_error "timeout", and
        stale_warning_sent True.
        """
        assert isinstance(self.item, QueueItem)
        assert self.item.mr_iid == 42
        assert self.item.title == "Test MR"
        assert self.item.author_name == "Test User"
        assert self.item.author_username == "testuser"
        assert self.item.author_avatar == "https://avatar.url/test.png"
        assert self.item.state == "rebasing"
        assert self.item.is_hotfix is True
        assert self.item.labels == ["merge_queue", "urgent"]
        assert self.item.target_branch == "main"
        assert self.item.pipeline_id == 1234
        assert self.item.pipeline_status == "running"
        assert self.item.retry_count == 2
        assert self.item.last_error == "timeout"
        assert self.item.stale_warning_sent is True

    async def do_cleanup(self):
        """
        Asynchronous cleanup hook invoked after the scenario; this implementation performs no action.
        """
        pass
