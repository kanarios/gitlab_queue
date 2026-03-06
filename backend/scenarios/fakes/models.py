from __future__ import annotations

from datetime import UTC, datetime

from gitlab_queue.models.mr import Author, MergeRequest, Note
from gitlab_queue.models.pipeline import Job, Pipeline


def create_author(
    *,
    id: int = 1,
    name: str = "Test User",
    username: str = "testuser",
    avatar_url: str | None = None,
) -> Author:
    return Author(id=id, name=name, username=username, avatar_url=avatar_url)


def create_mr(
    *,
    iid: int = 42,
    title: str = "Test MR",
    state: str = "opened",
    labels: list[str] | None = None,
    sha: str = "abc123",
    source_branch: str = "feature",
    target_branch: str = "master",
    merge_status: str = "can_be_merged",
    author: Author | None = None,
    has_conflicts: bool = False,
    rebase_in_progress: bool = False,
    web_url: str | None = None,
) -> MergeRequest:
    return MergeRequest(
        iid=iid,
        title=title,
        state=state,
        labels=labels if labels is not None else ["merge_queue"],
        sha=sha,
        source_branch=source_branch,
        target_branch=target_branch,
        merge_status=merge_status,
        author=author or create_author(),
        has_conflicts=has_conflicts,
        rebase_in_progress=rebase_in_progress,
        web_url=web_url,
    )


def create_pipeline(
    *,
    id: int = 100,
    status: str = "success",
    sha: str = "abc123",
    ref: str = "feature",
    web_url: str | None = None,
    created_at: datetime | None = None,
) -> Pipeline:
    return Pipeline(
        id=id,
        status=status,
        sha=sha,
        ref=ref,
        web_url=web_url if web_url is not None else f"https://gitlab.com/pipeline/{id}",
        created_at=created_at or datetime.now(UTC),
    )


def create_job(
    *,
    id: int = 1,
    name: str = "test-job",
    status: str = "failed",
    stage: str = "test",
    web_url: str | None = None,
) -> Job:
    return Job(id=id, name=name, status=status, stage=stage, web_url=web_url)


def create_note(
    *,
    id: int = 1,
    body: str = "test note",
    author: Author | None = None,
    system: bool = False,
) -> Note:
    return Note(id=id, body=body, author=author or create_author(), system=system)
