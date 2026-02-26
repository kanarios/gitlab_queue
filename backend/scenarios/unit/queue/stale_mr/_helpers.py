"""Helper functions for stale_mr test scenarios."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from gitlab_queue.models.mr import Author, MergeRequest

if TYPE_CHECKING:
    from gitlab_queue.db.database import Database


async def backfill_queued_at_hours_ago(db: Database, *, iid: int, hours: int) -> None:
    """
    Backfill a merge request's queued_at timestamp to a specified number of hours in the past for testing.

    Parameters:
        iid (int): Internal ID of the merge request to update.
        hours (int): Number of hours to subtract from the current time when setting `queued_at`.
    """
    if hours <= 0:
        raise ValueError(f"hours must be positive, got {hours}")
    async with db.transaction() as session:
        await session.execute(
            text("UPDATE merge_requests SET queued_at = datetime('now', :offset) WHERE iid = :iid"),
            {"offset": f"-{hours} hours", "iid": iid},
        )


def create_test_mr(
    iid: int,
    title: str = "Test MR",
    author_name: str = "Test User",
    author_username: str = "testuser",
) -> MergeRequest:
    """
    Create a lightweight MergeRequest instance prefilled with sensible defaults for tests.

    Returns:
        MergeRequest: A MergeRequest populated with the given `iid`, `title`, and author info; default fields include state "opened", label ["feature"], generated `sha` and `source_branch`, target_branch "master", and merge_status "can_be_merged".
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
