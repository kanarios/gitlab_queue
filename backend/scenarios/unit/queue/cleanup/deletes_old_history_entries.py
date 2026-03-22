"""Test scenario: cleanup_old_entries deletes entries with old finished_at."""

from __future__ import annotations

import vedro
from sqlalchemy import text

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.contexts.sqlite_client import initialized_test_database


def create_test_mr(
    iid: int,
    title: str = "Test MR",
    author_name: str = "Test User",
    author_username: str = "testuser",
) -> MergeRequest:
    """
    Builds a minimal MergeRequest instance for use in tests.

    Parameters:
        iid (int): Numeric IID for the merge request; used for `iid`, `sha`, and branch names.
        title (str): Merge request title.
        author_name (str): Author display name.
        author_username (str): Author username.

    Returns:
        MergeRequest: A MergeRequest populated with basic default fields and an associated Author.
    """
    return MergeRequest(
        iid=iid,
        title=title,
        state="opened",
        labels=["feature"],
        sha=f"sha{iid}",
        source_branch=f"feature-{iid}",
        target_branch="master",
        merge_status="can_be_merged",
        author=Author(id=iid, name=author_name, username=author_username),
    )


class Scenario(vedro.Scenario):
    subject = "cleanup old entries deletes entries with old finished at"

    async def given_queue_with_old_completed_mr(self):
        """
        Prepare a test database and queue containing a finished merge request with finished_at set two days in the past.

        Initializes a test SQLite database context, creates a QueueManager and required schema, enqueues a merge request with iid 42, marks it as finished, and adjusts its finished_at timestamp to two days ago so it is eligible for cleanup.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(99999, mr)
        # Set MR to terminal state so finished_at gets set
        await self.queue.update_mr_state(99999, 42, "merged")

        # Move finished_at to the past so cleanup finds it
        async with self.db.transaction() as session:
            await session.execute(
                text("UPDATE merge_requests SET finished_at = datetime('now', '-2 days') WHERE iid = :iid"),
                {"iid": 42},
            )

    async def when_cleanup_is_run(self):
        """
        Run the queue cleanup for entries older than one day and store the number of removed entries.

        Stores the deleted entry count on `self.deleted_count`.
        """
        self.deleted_count = await self.queue.cleanup_old_entries(99999, days=1)

    def then_should_delete_1_entry(self):
        """
        Assert that the cleanup removed exactly one queue entry.

        Raises an AssertionError if the stored deleted count is not equal to 1.
        """
        assert self.deleted_count == 1

    async def and_mr_should_not_exist_in_active_queue(self):
        """
        Asserts that the merge request with IID 42 is not present in the active queue.

        Raises:
            AssertionError: If a queue item with IID 42 exists.
        """
        item = await self.queue.get_queue_item(99999, 42)
        assert item is None

    async def do_cleanup(self):
        """
        Tears down the test database context.

        Exits the scenario's async database context to release resources created during setup.
        """
        await self._db_context.__aexit__(None, None, None)
