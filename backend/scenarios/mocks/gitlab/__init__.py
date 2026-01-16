"""GitLab API mock functions.

Each module in this package provides mocks for a specific URL pattern:
- mocked_gitlab_get_mr.py: GET /merge_requests/:iid
- mocked_gitlab_list_mrs.py: GET /merge_requests
- mocked_gitlab_rebase.py: PUT /merge_requests/:iid/rebase
- mocked_gitlab_merge.py: PUT /merge_requests/:iid/merge
- mocked_gitlab_pipelines.py: GET /pipelines/:id and GET /merge_requests/:iid/pipelines
- mocked_gitlab_comments.py: POST/PUT /merge_requests/:iid/notes
- mocked_gitlab_notes.py: GET /merge_requests/:iid/notes
- mocked_gitlab_conflicts.py: GET /merge_requests/:iid/conflicts
- mocked_gitlab_jobs.py: POST /jobs/:id/retry and GET /pipelines/:id/jobs
- mocked_gitlab_rate_limit.py: Rate limit response handling
"""

from scenarios.mocks.gitlab._base import JJ_MOCK_URL, get_mock_url
from scenarios.mocks.gitlab.mocked_gitlab_comments import (
    mocked_gitlab_add_comment,
    mocked_gitlab_update_comment,
)
from scenarios.mocks.gitlab.mocked_gitlab_conflicts import mocked_gitlab_get_conflicts
from scenarios.mocks.gitlab.mocked_gitlab_get_mr import mocked_gitlab_get_mr
from scenarios.mocks.gitlab.mocked_gitlab_jobs import (
    mocked_gitlab_pipeline_jobs,
    mocked_gitlab_retry_job,
)
from scenarios.mocks.gitlab.mocked_gitlab_list_mrs import mocked_gitlab_list_mrs
from scenarios.mocks.gitlab.mocked_gitlab_merge import mocked_gitlab_merge
from scenarios.mocks.gitlab.mocked_gitlab_notes import mocked_gitlab_get_notes
from scenarios.mocks.gitlab.mocked_gitlab_pipelines import (
    mocked_gitlab_mr_pipelines,
    mocked_gitlab_pipeline,
)
from scenarios.mocks.gitlab.mocked_gitlab_rate_limit import mocked_gitlab_rate_limit
from scenarios.mocks.gitlab.mocked_gitlab_rebase import mocked_gitlab_rebase

__all__ = [
    "JJ_MOCK_URL",
    "get_mock_url",
    "mocked_gitlab_add_comment",
    "mocked_gitlab_get_conflicts",
    "mocked_gitlab_get_mr",
    "mocked_gitlab_get_notes",
    "mocked_gitlab_list_mrs",
    "mocked_gitlab_merge",
    "mocked_gitlab_mr_pipelines",
    "mocked_gitlab_pipeline",
    "mocked_gitlab_pipeline_jobs",
    "mocked_gitlab_rate_limit",
    "mocked_gitlab_rebase",
    "mocked_gitlab_retry_job",
    "mocked_gitlab_update_comment",
]
