"""Helper functions for queue state test scenarios."""

from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.library import Labels, MRState


def create_test_mr(
    iid: int,
    title: str = "Test MR",
    author_name: str = "Test User",
    author_username: str = "testuser",
) -> MergeRequest:
    """
    Create a MergeRequest object pre-filled with minimal, consistent test data.

    Parameters:
        iid (int): The MR internal ID; also used as the author's id and to derive SHA and branch names.
        title (str): MR title (defaults to "Test MR").
        author_name (str): Author's display name (defaults to "Test User").
        author_username (str): Author's username (defaults to "testuser").

    Returns:
        MergeRequest: A MergeRequest with state set to MRState.OPENED, labels containing Labels.FEATURE,
        sha formatted as "sha{iid}", source_branch "feature-{iid}", target_branch "master",
        merge_status "can_be_merged", and author populated with the provided identity fields.
    """
    return MergeRequest(
        iid=iid,
        title=title,
        state=MRState.OPENED,
        labels=[Labels.FEATURE],
        sha=f"sha{iid}",
        source_branch=f"feature-{iid}",
        target_branch="master",
        merge_status="can_be_merged",
        author=Author(id=iid, name=author_name, username=author_username),
    )
