"""Helper functions for complete_mr test scenarios."""

from __future__ import annotations

from gitlab_queue.models.mr import Author, MergeRequest


def create_test_mr(
    iid: int,
    title: str = "Test MR",
    author_name: str = "Test User",
    author_username: str = "testuser",
) -> MergeRequest:
    """
    Constructs a MergeRequest object for tests with standard minimal fields.
    
    Parameters:
    	iid (int): Numeric internal ID for the merge request; also used as the author's id and to derive branch/sha values.
    	title (str): Title of the merge request.
    	author_name (str): Author's display name.
    	author_username (str): Author's username.
    
    Returns:
    	MergeRequest: A MergeRequest instance with `iid`, `title`, `state` set to "opened", `labels` set to ["feature"], `sha` set to "sha{iid}", `source_branch` set to "feature-{iid}", `target_branch` set to "master", `merge_status` set to "can_be_merged", and an `Author` whose `id` equals `iid` and whose `name` and `username` are set from the corresponding parameters.
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
