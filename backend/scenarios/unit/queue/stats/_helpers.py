"""Helper functions for stats test scenarios."""

from __future__ import annotations

from gitlab_queue.models.mr import Author, MergeRequest


def create_test_mr(
    iid: int,
    title: str = "Test MR",
    author_name: str = "Test User",
    author_username: str = "testuser",
) -> MergeRequest:
    """
    Create a MergeRequest object populated with minimal, deterministic fields for use in tests.

    Returns:
        MergeRequest: A MergeRequest with the provided `iid` and `title`, `state` set to "opened", `labels` set to ["feature"], `sha` formatted as "sha{iid}", `source_branch` formatted as "feature-{iid}", `target_branch` set to "master", `merge_status` set to "can_be_merged", and `author` set to an Author with `id` equal to `iid`, `name` equal to `author_name`, and `username` equal to `author_username`.
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
