"""MR Notifier for GitLab Merge Queue Bot.

Manages MR comment notifications with mandatory feedback per ADR-006.
Each state transition MUST trigger a notification to keep authors informed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.models.mr import Note

log = get_logger(__name__)


# =============================================================================
# Comment Templates (ADR-006: Mandatory MR Feedback)
# =============================================================================

COMMENT_TEMPLATES: dict[str, str] = {
    # === QUEUE EVENTS ===
    "queued": """## 🤖 Merge Queue Bot

**Status:** ⏳ Added to queue

**Position:** {position} of {total}

**Estimated wait:** ~{estimated_minutes} min

**Queued at:** {queued_at}

---
_Bot will automatically rebase and merge when your turn comes._
_Remove `{queue_label}` label to exit queue._
""",
    "position_changed": """## 🤖 Merge Queue Bot

**Status:** ⏳ Waiting in queue

**Position:** {position} of {total} _(was {old_position})_

**Estimated wait:** ~{estimated_minutes} min

---
_Your position changed because MRs ahead were processed._
""",
    "position_changed_hotfix": """## 🤖 Merge Queue Bot

**Status:** ⏳ Waiting in queue

**Position:** {position} of {total} _(was {old_position})_

**Estimated wait:** ~{estimated_minutes} min

---
_Your position changed because a hotfix MR was inserted ahead._
""",
    "total_changed": """## 🤖 Merge Queue Bot

**Status:** ⏳ Waiting in queue

**Position:** {position} of {total} _(queue size changed from {old_total})_

**Estimated wait:** ~{estimated_minutes} min

---
_A new MR was added to the queue._
""",
    "total_changed_hotfix": """## 🤖 Merge Queue Bot

**Status:** ⏳ Waiting in queue

**Position:** {position} of {total} _(queue size changed from {old_total})_

**Estimated wait:** ~{estimated_minutes} min

---
_A hotfix MR was added to the queue._
""",
    # === PROCESSING EVENTS ===
    "rebasing": """## 🤖 Merge Queue Bot

**Status:** 🔄 Rebasing

**Started at:** {started_at}

Your turn! Rebasing onto `{target_branch}`...

---
_This usually takes 1-2 minutes._
""",
    "rebase_complete": """## 🤖 Merge Queue Bot

**Status:** ✅ Rebase complete

**Rebased at:** {rebased_at}

Waiting for pipeline to start...

---
_Pipeline should start automatically._
""",
    "testing": """## 🤖 Merge Queue Bot

**Status:** 🧪 Pipeline running

**Pipeline:** [{pipeline_id}]({pipeline_url})

**Started at:** {started_at}

Waiting for pipeline to complete...

---
_If pipeline fails, bot will retry failed jobs before removing from queue._
""",
    "job_retry": """## 🤖 Merge Queue Bot

**Status:** 🔁 Retrying failed jobs

**Pipeline:** [{pipeline_id}]({pipeline_url})

**Jobs being retried:**
{retried_jobs_formatted}

**Retry attempts per job:** {retried_counts_formatted} / {max_retries}

---
_Pipeline is still running. Monitoring results..._
""",
    "rebase_during_testing": """## 🤖 Merge Queue Bot

**Status:** 🔄 Rebase during testing ({rebase_count}/{max_attempts}){final_attempt_text}

Target branch changed while pipeline was running.
Previous pipeline cancelled, rebased and started new pipeline.

**New pipeline:** [{pipeline_id}]({pipeline_url})

---
_Monitoring new pipeline..._
""",
    # === SUCCESS EVENTS ===
    "merging": """## 🤖 Merge Queue Bot

**Status:** 🚀 Merging

**Pipeline:** [{pipeline_id}]({pipeline_url}) - Passed

Pipeline passed! Merging into `{target_branch}`...
""",
    "merged": """## 🤖 Merge Queue Bot

**Status:** ✅ Successfully merged!

**Merged at:** {merged_at}

**Time in queue:** {duration}

🎉 Your changes are now in `{target_branch}`.

---
_Thank you for using Merge Queue Bot!_
""",
    # === FAILURE EVENTS ===
    "conflict": """## 🤖 Merge Queue Bot

**Status:** ❌ Rebase conflict

**Failed at:** {failed_at}

Cannot rebase onto `{target_branch}` due to conflicts in:
{conflicted_files}

**Action required:**
1. Resolve conflicts locally
2. Push updated branch
3. Re-add `{queue_label}` label to rejoin queue

---
_MR has been removed from queue._
""",
    "pipeline_failed": """## 🤖 Merge Queue Bot

**Status:** ❌ Pipeline failed

**Pipeline:** [{pipeline_id}]({pipeline_url})

**Failed at:** {failed_at}

Pipeline failed. Retry attempts: {retry_summary}.

**Failed jobs:**
{failed_jobs}

**Action required:**
1. Fix failing tests/jobs
2. Push updated branch
3. Re-add `{queue_label}` label to rejoin queue

---
_MR has been removed from queue._
""",
    "timeout": """## 🤖 Merge Queue Bot

**Status:** ⏰ Timeout

**Failed at:** {failed_at}

**Time in queue:** {duration}

MR exceeded maximum wait time ({max_wait} hours).

**Possible reasons:**
- Pipeline taking too long
- Stuck in rebasing state

**Action required:**
Re-add `{queue_label}` label to rejoin queue.

---
_MR has been removed from queue._
""",
    "merge_failed": """## 🤖 Merge Queue Bot

**Status:** ❌ Merge failed

**Failed at:** {failed_at}

Merge operation failed: {error_message}

**Action required:**
1. Check merge conflicts or branch protection rules
2. Push updated branch
3. Re-add `{queue_label}` label to rejoin queue

---
_MR has been removed from queue._
""",
    "generic_failure": """## 🤖 Merge Queue Bot

**Status:** ❌ Processing failed

**Failed at:** {failed_at}

{error_message}

**Action required:**
1. Check the error above
2. Push updated branch
3. Re-add `{queue_label}` label to rejoin queue

---
_MR has been removed from queue._
""",
    # === WARNING EVENTS ===
    "stale_warning": """## 🤖 Merge Queue Bot

**Status:** ⚠️ Warning: Long wait time

**In queue since:** {queued_at}

**Time in queue:** {duration}

This MR has been waiting for more than {warning_hours} hours.

**Possible reasons:**
- MRs ahead are taking longer than expected
- High queue volume

**Options:**
- Wait for your turn (current position: {position})
- Remove `{queue_label}` label to exit queue and rejoin later

---
_This is a warning notification. MR is still in queue._
""",
    # === REMOVAL EVENTS ===
    "removed_label": """## 🤖 Merge Queue Bot

**Status:** 🚪 Removed from queue

**Removed at:** {removed_at}
**Was at position:** {position}

**Reason:** Label `{queue_label}` was removed while MR was {stage}.

No errors detected — this was a manual label removal, not a failure.

---
_Add label back to rejoin queue._
""",
    "removed_closed": """## 🤖 Merge Queue Bot

**Status:** 🚪 Removed from queue

**Removed at:** {removed_at}

**Reason:** MR was closed while in the merge queue.

**What to do:**
1. Reopen the MR if it was closed by mistake
2. Verify your changes are up to date with target branch
3. Add `{queue_label}` label to rejoin queue
""",
}

STATE_DESCRIPTIONS: dict[str, str] = {
    "queued": "waiting in queue",
    "rebasing": "being rebased",
    "testing": "running pipeline",
    "merging": "being merged",
}


# =============================================================================
# MRNotifier Class
# =============================================================================


@dataclass
class MRNotifier:
    """Manages MR comment notifications for the merge queue bot.

    Maintains a single pinned comment per MR that is updated with each
    state change. Uses GitLabClient.add_or_update_pinned_comment() which
    handles finding/updating existing bot comments via BOT_COMMENT_SIGNATURE.

    Per ADR-006 (Mandatory MR Feedback), every state transition MUST
    trigger a notification.

    Attributes:
        gitlab_client: GitLab API client for comment operations.
        settings: Application settings for queue_label, gitlab_url, etc.

    Example:
        >>> notifier = MRNotifier(gitlab_client, settings)
        >>> await notifier.notify(
        ...     mr_iid=42,
        ...     status="queued",
        ...     position=1,
        ...     total=5,
        ...     estimated_minutes=15,
        ...     queued_at=datetime.now(UTC),
        ... )
    """

    gitlab_client: GitLabClient
    settings: Settings

    async def notify(
        self,
        mr_iid: int,
        status: str,
        **context: Any,
    ) -> Note:
        """Update or create pinned comment for MR.

        Args:
            mr_iid: Merge request internal ID.
            status: Template key (queued, rebasing, testing, etc.).
            **context: Template variables to render.

        Returns:
            Note object from GitLab API.

        Raises:
            KeyError: If status is not a valid template key.
            GitLabAPIError: If comment update fails.
        """
        if status not in COMMENT_TEMPLATES:
            msg = f"Unknown notification status: {status}"
            raise KeyError(msg)

        log.debug(
            "Sending notification",
            mr_iid=mr_iid,
            status=status,
            context_keys=list(context.keys()),
        )

        body = self._render_template(status, **context)
        note = await self.gitlab_client.add_or_update_pinned_comment(mr_iid, body)

        log.info("Notification sent", mr_iid=mr_iid, status=status, note_id=note.id)
        return note

    def _render_template(self, status: str, **context: Any) -> str:
        """Render template with provided context.

        Automatically adds common context from settings:
        - queue_label

        Args:
            status: Template key.
            **context: Template variables.

        Returns:
            Rendered template string.
        """
        template = COMMENT_TEMPLATES[status]

        # Add common context from settings
        full_context: dict[str, Any] = {
            "queue_label": self.settings.queue_label,
            **context,
        }

        # Format special types
        for key, value in list(full_context.items()):
            if isinstance(value, datetime):
                full_context[key] = self._format_timestamp(value)
            elif key == "conflicted_files" and isinstance(value, list):
                error_msg = full_context.get("error_message", "")
                full_context[key] = self._format_file_list(value, error_message=error_msg)
            elif key == "failed_jobs" and isinstance(value, list):
                full_context[key] = self._format_job_list(value)

        # Format pipeline_failed: derive retry_summary from raw retried_jobs dict
        if status == "pipeline_failed":
            retried_jobs = full_context.get("retried_jobs", {})
            if isinstance(retried_jobs, dict):
                full_context["retry_summary"] = ", ".join(f"{j}: {c}" for j, c in retried_jobs.items()) or "0"
            else:
                full_context["retry_summary"] = "0"

        # Map previous_state to human-readable stage description
        if status == "removed_label":
            raw_state = full_context.get("previous_state", "queued")
            full_context["stage"] = STATE_DESCRIPTIONS.get(raw_state, raw_state)

        # Format job_retry specific fields
        if status == "job_retry":
            retried_jobs = full_context.get("retried_jobs", [])
            retried_counts = full_context.get("retried_counts", {})
            full_context["retried_jobs_formatted"] = self._format_job_list(retried_jobs)
            full_context["retried_counts_formatted"] = ", ".join(f"{j}: {c}" for j, c in retried_counts.items()) or "0"

        # Add final attempt text for rebase_during_testing
        if status == "rebase_during_testing":
            rebase_count = full_context.get("rebase_count", 0)
            max_attempts = full_context.get("max_attempts", 0)
            if rebase_count == max_attempts:
                full_context["final_attempt_text"] = " ⚠️ **Final attempt**"
            else:
                full_context["final_attempt_text"] = ""

        return template.format(**full_context)

    def _format_timestamp(self, dt: datetime) -> str:
        """Format datetime for display.

        Args:
            dt: Datetime to format.

        Returns:
            Formatted string like "2025-12-01 14:30 UTC".
        """
        return dt.strftime("%Y-%m-%d %H:%M UTC")

    def _format_file_list(self, files: list[str], *, error_message: str = "") -> str:
        """Format file list as markdown bullets.

        Args:
            files: List of file paths.
            error_message: Fallback error message when files are unavailable.

        Returns:
            Markdown formatted file list, limited to 10 items.
        """
        if not files:
            if error_message:
                return f"_{error_message}_"
            return "_(unknown files)_"
        formatted = [f"- `{f}`" for f in files[:10]]
        if len(files) > 10:
            formatted.append(f"- _...and {len(files) - 10} more_")
        return "\n".join(formatted)

    def _format_job_list(self, jobs: list[str]) -> str:
        """Format job list as markdown bullets.

        Args:
            jobs: List of job names.

        Returns:
            Markdown formatted job list, limited to 10 items.
        """
        if not jobs:
            return "_(unknown jobs)_"
        formatted = [f"- {j}" for j in jobs[:10]]
        if len(jobs) > 10:
            formatted.append(f"- _...and {len(jobs) - 10} more_")
        return "\n".join(formatted)

    async def build_pipeline_url(self, pipeline_id: int) -> str:
        """Build full GitLab pipeline URL.

        Args:
            pipeline_id: Pipeline ID.

        Returns:
            Full URL to the pipeline page.
        """
        project_url = await self.gitlab_client.get_project_web_url()
        return f"{project_url}/-/pipelines/{pipeline_id}"

    async def remove_queue_label(self, mr_iid: int) -> None:
        """Remove the queue label from an MR.

        Called when MR processing completes (merged, failed, removed)
        to prevent re-queueing by the scheduler.

        Args:
            mr_iid: Internal ID of the merge request.
        """
        try:
            await self.gitlab_client.remove_mr_label(mr_iid, self.settings.queue_label)
            log.info("Queue label removed from MR", mr_iid=mr_iid, label=self.settings.queue_label)
        except Exception as e:
            # Don't fail the whole operation if label removal fails
            log.warning(
                "Failed to remove queue label from MR",
                mr_iid=mr_iid,
                label=self.settings.queue_label,
                error=str(e),
            )


__all__: list[str] = [
    "COMMENT_TEMPLATES",
    "MRNotifier",
]
