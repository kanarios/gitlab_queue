"""Helper functions for stale_mr test scenarios."""

from __future__ import annotations

from sqlalchemy import text

from gitlab_queue.core.database import DatabaseManager
from gitlab_queue.models.mr import Author, MergeRequest


async def backfill_queued_at_hours_ago(db: DatabaseManager, *, iid: int, hours: int) -> None:
    """Set queued_at to N hours ago for a given MR (raw SQL backfill for tests)."""
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
    """Create a test MergeRequest with minimal required fields."""
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
