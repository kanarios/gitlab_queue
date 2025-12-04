"""Webhook handlers for GitLab Merge Queue Bot.

Handles merge request webhook events from GitLab, managing queue
operations based on label changes and MR state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.models.events import MergeRequestEvent, PipelineEvent

log = get_logger(__name__)


@dataclass
class MRWebhookHandler:
    """Handles merge request webhook events.

    Processes GitLab webhook events for merge requests, managing queue
    operations based on label changes, merges, and closes.

    Attributes:
        settings: Application configuration.
        gitlab_client: GitLab API client.
        queue_manager: Queue manager for MR operations.
    """

    settings: Settings
    gitlab_client: GitLabClient
    queue_manager: QueueManager

    async def handle(self, event: MergeRequestEvent) -> None:
        """Dispatch event to appropriate handler based on action.

        Args:
            event: The merge request webhook event.
        """
        action = event.object_attributes.action
        mr_iid = event.object_attributes.iid

        log.info(
            "Handling MR webhook event",
            action=action,
            mr_iid=mr_iid,
            state=event.object_attributes.state,
        )

        handlers = {
            "labeled": self._handle_labeled,
            "unlabeled": self._handle_unlabeled,
            "merge": self._handle_merge,
            "close": self._handle_close,
            "update": self._handle_update,
        }

        handler = handlers.get(action)
        if handler:
            await handler(event)
        else:
            log.debug("Ignoring unhandled action", action=action, mr_iid=mr_iid)

    async def _handle_labeled(self, event: MergeRequestEvent) -> None:
        """Handle label addition to MR.

        Adds MR to queue if queue_label was added.

        Args:
            event: The merge request webhook event.
        """
        if not self._was_queue_label_added(event):
            log.debug(
                "Queue label not added, ignoring",
                mr_iid=event.object_attributes.iid,
                queue_label=self.settings.queue_label,
            )
            return

        mr_iid = event.object_attributes.iid

        # Fetch full MR data from API
        mr = await self.gitlab_client.get_mr(mr_iid)

        # Detect if this is a hotfix
        is_hotfix = self.settings.hotfix_label in event.labels

        # Add to queue
        await self.queue_manager.add_to_queue(mr, is_hotfix=is_hotfix)

        log.info(
            "MR added to queue via webhook",
            mr_iid=mr_iid,
            is_hotfix=is_hotfix,
            title=mr.title,
        )

    async def _handle_unlabeled(self, event: MergeRequestEvent) -> None:
        """Handle label removal from MR.

        Removes MR from queue if queue_label was removed.

        Args:
            event: The merge request webhook event.
        """
        if not self._was_queue_label_removed(event):
            log.debug(
                "Queue label not removed, ignoring",
                mr_iid=event.object_attributes.iid,
                queue_label=self.settings.queue_label,
            )
            return

        mr_iid = event.object_attributes.iid

        removed = await self.queue_manager.remove_from_queue(mr_iid)

        if removed:
            log.info("MR removed from queue via label removal", mr_iid=mr_iid)
        else:
            log.debug("MR was not in queue", mr_iid=mr_iid)

    async def _handle_merge(self, event: MergeRequestEvent) -> None:
        """Handle MR merge event.

        Cleans up queue entry for merged MR.

        Args:
            event: The merge request webhook event.
        """
        mr_iid = event.object_attributes.iid

        # Remove from queue (idempotent)
        removed = await self.queue_manager.remove_from_queue(mr_iid)

        if removed:
            log.info("MR cleaned up from queue after merge", mr_iid=mr_iid)
        else:
            log.debug("Merged MR was not in queue", mr_iid=mr_iid)

    async def _handle_close(self, event: MergeRequestEvent) -> None:
        """Handle MR close event.

        Removes MR from queue when closed.

        Args:
            event: The merge request webhook event.
        """
        mr_iid = event.object_attributes.iid

        removed = await self.queue_manager.remove_from_queue(mr_iid)

        if removed:
            log.info("MR removed from queue after close", mr_iid=mr_iid)
        else:
            log.debug("Closed MR was not in queue", mr_iid=mr_iid)

    async def _handle_update(self, event: MergeRequestEvent) -> None:
        """Handle MR update event.

        Resets MR to queued state if new commits are pushed while processing.

        Args:
            event: The merge request webhook event.
        """
        mr_iid = event.object_attributes.iid

        # Check if MR is in queue
        queue_item = await self.queue_manager.get_queue_item(mr_iid)

        if queue_item is None:
            log.debug("Updated MR not in queue", mr_iid=mr_iid)
            return

        # If MR is being processed (rebasing or testing), reset to queued
        processing_states = ("rebasing", "testing")
        if queue_item.state in processing_states:
            log.info(
                "Resetting MR to queued due to update",
                mr_iid=mr_iid,
                previous_state=queue_item.state,
            )
            await self.queue_manager.update_mr_state(mr_iid, "queued")
        else:
            log.debug(
                "MR update ignored, not in processing state",
                mr_iid=mr_iid,
                current_state=queue_item.state,
            )

    def _was_queue_label_added(self, event: MergeRequestEvent) -> bool:
        """Check if queue label was added in this event.

        Args:
            event: The merge request webhook event.

        Returns:
            True if queue_label was added, False otherwise.
        """
        if not event.label_changes:
            return False

        added = set(event.label_changes.current) - set(event.label_changes.previous)
        return self.settings.queue_label in added

    def _was_queue_label_removed(self, event: MergeRequestEvent) -> bool:
        """Check if queue label was removed in this event.

        Args:
            event: The merge request webhook event.

        Returns:
            True if queue_label was removed, False otherwise.
        """
        if not event.label_changes:
            return False

        removed = set(event.label_changes.previous) - set(event.label_changes.current)
        return self.settings.queue_label in removed


@dataclass
class PipelineWebhookHandler:
    """Handles pipeline webhook events.

    Processes GitLab webhook events for pipelines, managing state transitions
    based on pipeline success, failure, or cancellation.

    Attributes:
        settings: Application configuration.
        gitlab_client: GitLab API client.
        queue_manager: Queue manager for MR operations.
        notifier: MR notifier for state machine notifications.
    """

    settings: Settings
    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier

    async def handle(self, event: PipelineEvent) -> None:
        """Dispatch event to appropriate handler based on pipeline status.

        Args:
            event: The pipeline webhook event.
        """
        status = event.object_attributes.status
        mr_iid = event.merge_request_iid
        pipeline_id = event.object_attributes.id

        log.info(
            "Handling pipeline webhook event",
            status=status,
            pipeline_id=pipeline_id,
            mr_iid=mr_iid,
        )

        # Skip if pipeline is not associated with an MR
        if mr_iid is None:
            log.debug("Pipeline not associated with MR, ignoring", pipeline_id=pipeline_id)
            return

        handlers = {
            "success": self._handle_success,
            "failed": self._handle_failed,
            "canceled": self._handle_canceled,
        }

        handler = handlers.get(status)
        if handler:
            await handler(event)
        else:
            log.debug(
                "Ignoring unhandled pipeline status",
                status=status,
                pipeline_id=pipeline_id,
                mr_iid=mr_iid,
            )

    async def _handle_success(self, event: PipelineEvent) -> None:
        """Handle successful pipeline completion.

        Triggers transition to merging state if MR is in testing state.

        Args:
            event: The pipeline webhook event.
        """
        mr_iid = event.merge_request_iid
        if mr_iid is None:
            return

        pipeline_id = event.object_attributes.id

        # Check if MR is in queue
        queue_item = await self.queue_manager.get_queue_item(mr_iid)
        if queue_item is None:
            log.debug("MR not in queue, ignoring pipeline success", mr_iid=mr_iid)
            return

        # Only process if MR is in testing state
        if queue_item.state != "testing":
            log.debug(
                "MR not in testing state, ignoring pipeline success",
                mr_iid=mr_iid,
                current_state=queue_item.state,
            )
            return

        log.info(
            "Pipeline success for MR in testing state",
            mr_iid=mr_iid,
            pipeline_id=pipeline_id,
        )

        # Create state machine and trigger pipeline success
        state_machine = await create_state_machine_for_mr(
            mr_iid=mr_iid,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            target_branch=self.settings.target_branch,
        )
        await state_machine.trigger_pipeline_success()

    async def _handle_failed(self, event: PipelineEvent) -> None:
        """Handle failed pipeline.

        Either marks pipeline as failed for retry or fails the MR if retries exhausted.

        Args:
            event: The pipeline webhook event.
        """
        mr_iid = event.merge_request_iid
        if mr_iid is None:
            return

        pipeline_id = event.object_attributes.id

        # Check if MR is in queue
        queue_item = await self.queue_manager.get_queue_item(mr_iid)
        if queue_item is None:
            log.debug("MR not in queue, ignoring pipeline failure", mr_iid=mr_iid)
            return

        # Only process if MR is in testing state
        if queue_item.state != "testing":
            log.debug(
                "MR not in testing state, ignoring pipeline failure",
                mr_iid=mr_iid,
                current_state=queue_item.state,
            )
            return

        current_retry_count = queue_item.retry_count or 0
        max_retries = self.settings.pipeline_retry_count

        if current_retry_count < max_retries:
            # Retries available - update state for processor to handle retry
            log.info(
                "Pipeline failed, marking for retry",
                mr_iid=mr_iid,
                pipeline_id=pipeline_id,
                retry_count=current_retry_count,
                max_retries=max_retries,
            )
            await self.queue_manager.update_mr_state(
                mr_iid,
                "testing",
                pipeline_status="failed",
            )
        else:
            # No retries left - fail the MR
            log.info(
                "Pipeline failed, no retries remaining",
                mr_iid=mr_iid,
                pipeline_id=pipeline_id,
                retry_count=current_retry_count,
            )
            state_machine = await create_state_machine_for_mr(
                mr_iid=mr_iid,
                notifier=self.notifier,
                queue_manager=self.queue_manager,
                target_branch=self.settings.target_branch,
            )
            await state_machine.trigger_pipeline_failed(
                failed_jobs=[],
                retry_count=current_retry_count,
                error_message=f"Pipeline {pipeline_id} failed after {current_retry_count} retries",
            )

    async def _handle_canceled(self, event: PipelineEvent) -> None:
        """Handle canceled pipeline.

        Treats cancellation as a failure without retry possibility.

        Args:
            event: The pipeline webhook event.
        """
        mr_iid = event.merge_request_iid
        if mr_iid is None:
            return

        pipeline_id = event.object_attributes.id

        # Check if MR is in queue
        queue_item = await self.queue_manager.get_queue_item(mr_iid)
        if queue_item is None:
            log.debug("MR not in queue, ignoring pipeline cancellation", mr_iid=mr_iid)
            return

        # Only process if MR is in testing state
        if queue_item.state != "testing":
            log.debug(
                "MR not in testing state, ignoring pipeline cancellation",
                mr_iid=mr_iid,
                current_state=queue_item.state,
            )
            return

        log.info(
            "Pipeline canceled for MR in testing state",
            mr_iid=mr_iid,
            pipeline_id=pipeline_id,
        )

        # Fail the MR without retry on cancellation
        state_machine = await create_state_machine_for_mr(
            mr_iid=mr_iid,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            target_branch=self.settings.target_branch,
        )
        await state_machine.trigger_pipeline_failed(
            failed_jobs=[],
            retry_count=queue_item.retry_count or 0,
            error_message=f"Pipeline {pipeline_id} was canceled",
        )


__all__: list[str] = [
    "MRWebhookHandler",
    "PipelineWebhookHandler",
]
