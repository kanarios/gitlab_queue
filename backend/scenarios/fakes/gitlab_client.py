from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gitlab_queue.clients.gitlab import RateLimitState
from gitlab_queue.utils.circuit_breaker import CircuitBreaker

from .models import create_job, create_mr, create_note, create_pipeline

if TYPE_CHECKING:
    from gitlab_queue.models.mr import MergeRequest, Note
    from gitlab_queue.models.pipeline import Job, Pipeline


@dataclass
class FakeGitLabClient:
    # Configurable responses
    mr_responses: dict[int, MergeRequest] = field(default_factory=dict)
    mr_response_sequence: list[MergeRequest] = field(default_factory=list)
    pipeline_responses: dict[int, Pipeline] = field(default_factory=dict)
    mr_pipelines_response: list[Pipeline] = field(default_factory=list)
    latest_pipeline_response: Pipeline | None = None
    pipeline_jobs_response: list[Job] | Exception = field(default_factory=list)
    rebase_result: bool = True
    rebase_status: tuple[bool, bool] = (False, False)
    rebase_status_sequence: list[tuple[bool, bool]] = field(default_factory=list)
    mr_conflicts: list[str] = field(default_factory=list)
    merge_result: MergeRequest | Exception | None = None
    listed_mrs: list[MergeRequest] = field(default_factory=list)
    listed_mrs_by_label: dict[str, list[MergeRequest]] = field(default_factory=dict)
    project_web_url: str = "https://gitlab.com/test/project"
    created_pipeline: Pipeline | None = None
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    rate_limit_state: RateLimitState = field(default_factory=RateLimitState)

    latest_pipeline_sequence: list[Pipeline | None] = field(default_factory=list)

    # Error injection
    retry_job_error: Exception | None = None
    get_mr_error: Exception | None = None
    rebase_mr_error: Exception | None = None
    cancel_pipeline_error: Exception | None = None
    list_mrs_error: Exception | None = None
    list_mrs_error_sequence: list[Exception | None] = field(default_factory=list)
    create_pipeline_error: Exception | None = None
    remove_label_error: Exception | None = None

    # Call recording
    retry_job_calls: list[int] = field(default_factory=list)
    rebase_calls: list[int] = field(default_factory=list)
    merge_calls: list[tuple[int, str | None]] = field(default_factory=list)
    cancel_pipeline_calls: list[int] = field(default_factory=list)
    remove_label_calls: list[tuple[int, str]] = field(default_factory=list)
    add_comment_calls: list[tuple[int, str]] = field(default_factory=list)
    create_pipeline_calls: list[str] = field(default_factory=list)
    get_mr_calls: list[int] = field(default_factory=list)
    get_latest_pipeline_calls: list[int] = field(default_factory=list)
    list_mrs_calls: list[str] = field(default_factory=list)
    check_rebase_status_calls: list[int] = field(default_factory=list)

    async def get_mr(self, iid: int) -> MergeRequest:
        self.get_mr_calls.append(iid)
        if self.get_mr_error:
            raise self.get_mr_error
        if self.mr_response_sequence:
            return self.mr_response_sequence.pop(0)
        if iid in self.mr_responses:
            return self.mr_responses[iid]
        return create_mr(iid=iid)

    async def list_mrs_with_label(self, label: str, *, state: str = "opened") -> list[MergeRequest]:
        self.list_mrs_calls.append(label)
        if self.list_mrs_error_sequence:
            error = self.list_mrs_error_sequence.pop(0)
            if error is not None:
                raise error
        elif self.list_mrs_error:
            raise self.list_mrs_error
        if self.listed_mrs_by_label:
            return self.listed_mrs_by_label.get(label, [])
        return self.listed_mrs

    async def rebase_mr(self, iid: int) -> bool:
        self.rebase_calls.append(iid)
        if self.rebase_mr_error:
            raise self.rebase_mr_error
        return self.rebase_result

    async def check_rebase_status(self, iid: int) -> tuple[bool, bool]:
        self.check_rebase_status_calls.append(iid)
        if self.rebase_status_sequence:
            idx = min(len(self.check_rebase_status_calls) - 1, len(self.rebase_status_sequence) - 1)
            return self.rebase_status_sequence[idx]
        return self.rebase_status

    async def get_mr_conflicts(self, iid: int) -> list[str]:
        return self.mr_conflicts

    async def merge_mr(self, iid: int, *, expected_sha: str | None = None) -> MergeRequest:
        self.merge_calls.append((iid, expected_sha))
        if isinstance(self.merge_result, Exception):
            raise self.merge_result
        if self.merge_result is not None:
            return self.merge_result
        return create_mr(iid=iid, state="merged")

    async def remove_mr_label(self, iid: int, label: str) -> MergeRequest:
        self.remove_label_calls.append((iid, label))
        if self.remove_label_error:
            raise self.remove_label_error
        if iid in self.mr_responses:
            return self.mr_responses[iid]
        return create_mr(iid=iid)

    async def get_mr_pipelines(self, iid: int) -> list[Pipeline]:
        return self.mr_pipelines_response

    async def get_latest_mr_pipeline(self, iid: int) -> Pipeline | None:
        self.get_latest_pipeline_calls.append(iid)
        if self.latest_pipeline_sequence:
            return self.latest_pipeline_sequence.pop(0)
        return self.latest_pipeline_response

    async def get_pipeline_status(self, pipeline_id: int) -> Pipeline:
        if pipeline_id in self.pipeline_responses:
            return self.pipeline_responses[pipeline_id]
        return create_pipeline(id=pipeline_id)

    async def retry_pipeline_job(self, job_id: int) -> Job:
        self.retry_job_calls.append(job_id)
        if self.retry_job_error:
            raise self.retry_job_error
        return create_job(id=job_id, status="pending")

    async def create_pipeline(self, ref: str) -> Pipeline:
        self.create_pipeline_calls.append(ref)
        if self.create_pipeline_error:
            raise self.create_pipeline_error
        if self.created_pipeline is not None:
            return self.created_pipeline
        return create_pipeline(ref=ref)

    async def cancel_pipeline(self, pipeline_id: int) -> Pipeline:
        self.cancel_pipeline_calls.append(pipeline_id)
        if self.cancel_pipeline_error:
            raise self.cancel_pipeline_error
        return create_pipeline(id=pipeline_id, status="canceled")

    async def get_pipeline_jobs(self, pipeline_id: int) -> list[Job]:
        if isinstance(self.pipeline_jobs_response, Exception):
            raise self.pipeline_jobs_response
        return self.pipeline_jobs_response

    async def add_comment(self, iid: int, body: str) -> Note:
        self.add_comment_calls.append((iid, body))
        return create_note()

    async def update_comment(self, iid: int, note_id: int, body: str) -> Note:
        return create_note(id=note_id, body=body)

    async def add_or_update_pinned_comment(self, iid: int, body: str) -> Note:
        self.add_comment_calls.append((iid, body))
        return create_note(body=body)

    async def get_project_web_url(self) -> str:
        return self.project_web_url

    async def close(self) -> None:
        pass
