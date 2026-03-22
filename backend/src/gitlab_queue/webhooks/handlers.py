"""Webhook handlers for GitLab Merge Queue Bot.

Handles merge request webhook events from GitLab, managing queue
operations based on label changes and MR state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from statemachine.exceptions import TransitionNotAllowed

from gitlab_queue.core.state_machine import calculate_duration, create_state_machine_for_mr
from gitlab_queue.models.events import MergeRequestEvent, PipelineEvent
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from gitlab_queue.api.websocket import WebSocketManager
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.protocols import StateMachineFactoryProtocol
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
    from gitlab_queue.models.queue_item import QueueItem

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
        position_notifier: Queue position notifier for MR notifications.
        websocket_manager: WebSocket manager for real-time UI updates.
    """

    settings: Settings
    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier | None = None
    position_notifier: QueuePositionNotifier | None = None
    websocket_manager: WebSocketManager | None = None
    state_machine_factory: StateMachineFactoryProtocol = field(default=create_state_machine_for_mr)

    async def _notify_position_after_add(
        self,
        project_id: int,
        mr_iid: int,
        is_hotfix: bool,
        positions_before: dict[int, int],
        old_total: int,
    ) -> None:
        """Send position notifications after adding MR to queue.

        Args:
            project_id: GitLab project ID.
            mr_iid: The MR's internal ID.
            is_hotfix: Whether the MR is a hotfix.
            positions_before: Positions captured before adding.
            old_total: Total queue size before adding.
        """
        if not self.position_notifier:
            return

        try:
            await self.position_notifier.notify_initial_position(project_id, mr_iid)

            if positions_before:
                await self.position_notifier.notify_affected_mrs_after_mr_added(
                    project_id,
                    mr_iid,
                    positions_before,
                    old_total,
                    is_hotfix=is_hotfix,
                )
        except Exception as e:
            log.warning(
                "Failed to send position notification",
                mr_iid=mr_iid,
                error=str(e),
            )

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

        Adds MR to queue if queue_label or hotfix_label was added.
        Hotfix label acts as both queue trigger and priority flag.

        Args:
            event: The merge request webhook event.
        """
        queue_label_added = self._was_queue_label_added(event)
        hotfix_label_added = self._was_hotfix_label_added(event)

        if not queue_label_added and not hotfix_label_added:
            log.debug(
                "Neither queue nor hotfix label added, ignoring",
                mr_iid=event.object_attributes.iid,
                queue_label=self.settings.queue_label,
                hotfix_label=self.settings.hotfix_label,
            )
            return

        mr_iid = event.object_attributes.iid

        # Hotfix if hotfix label is present (either just added or already there)
        is_hotfix = self.settings.hotfix_label in event.labels

        # Check if MR is already in queue
        existing_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)

        if existing_item is not None:
            # MR already in queue - refresh metadata to keep it current
            await self._refresh_queue_item_metadata(event.project_id, mr_iid, event)
            return

        # Capture positions before adding (for notifying existing MRs about queue changes)
        positions_before: dict[int, int] = {}
        old_total: int = 0
        if self.position_notifier:
            positions_before = await self.position_notifier.capture_queue_positions(event.project_id)
            old_total = await self.queue_manager.get_queue_length(event.project_id)

        # Fetch full MR data from API for new queue entry
        mr = await self.gitlab_client.get_mr(mr_iid)

        # Add to queue
        await self.queue_manager.add_to_queue(event.project_id, mr, is_hotfix=is_hotfix)

        log.info(
            "MR added to queue via webhook",
            mr_iid=mr_iid,
            is_hotfix=is_hotfix,
            title=mr.title,
        )

        # Send position notification
        await self._notify_position_after_add(event.project_id, mr_iid, is_hotfix, positions_before, old_total)

    async def _handle_unlabeled(self, event: MergeRequestEvent) -> None:
        """Handle label removal from MR.

        Removes MR from queue if queue_label was removed, or if hotfix_label
        was removed and queue_label is not present.

        Args:
            event: The merge request webhook event.
        """
        queue_label_removed = self._was_queue_label_removed(event)
        hotfix_label_removed = self._was_hotfix_label_removed(event)

        # Check if MR still has a trigger label after removal
        has_queue_label = self.settings.queue_label in event.labels
        has_hotfix_label = self.settings.hotfix_label in event.labels

        # Remove from queue if:
        # 1. Queue label was removed AND hotfix is not present, OR
        # 2. Hotfix label was removed AND queue label is not present
        queue_trigger_lost = queue_label_removed and not has_hotfix_label
        hotfix_trigger_lost = hotfix_label_removed and not has_queue_label
        should_remove = queue_trigger_lost or hotfix_trigger_lost

        if not should_remove:
            # MR stays in queue - refresh metadata to keep it current
            await self._refresh_queue_item_metadata(event.project_id, event.object_attributes.iid, event)
            return

        mr_iid = event.object_attributes.iid

        queue_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)
        if queue_item is None:
            log.debug("MR was not in queue", mr_iid=mr_iid)
            return

        if self.notifier:
            state_machine = await self.state_machine_factory(
                event.project_id,
                mr_iid=mr_iid,
                notifier=self.notifier,
                queue_manager=self.queue_manager,
                target_branch=event.object_attributes.target_branch,
                websocket_manager=self.websocket_manager,
                position_notifier=self.position_notifier,
            )
            try:
                await state_machine.trigger_mark_removed(reason="label_removed")
                log.info("MR removed from queue via state machine", mr_iid=mr_iid)
            except TransitionNotAllowed:
                log.warning(
                    "SM transition failed (terminal state race), falling back to direct removal",
                    mr_iid=mr_iid,
                    current_state=state_machine.current_state.id,
                )
                await self.queue_manager.complete_mr(
                    event.project_id,
                    mr_iid,
                    status="removed",
                    failure_reason="label_removed",
                )
                await self._remove_queue_label(mr_iid)
                log.info("MR removed from queue via fallback", mr_iid=mr_iid)
        else:
            removed = await self.queue_manager.remove_from_queue(event.project_id, mr_iid)
            if removed:
                log.info("MR removed from queue via label removal", mr_iid=mr_iid)

        await self._broadcast_queue_update()

    async def _handle_merge(self, event: MergeRequestEvent) -> None:
        """Handle MR merge event.

        Cleans up queue entry for merged MR using state machine for proper
        status tracking and notifications.

        Args:
            event: The merge request webhook event.
        """
        mr_iid = event.object_attributes.iid

        queue_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)
        if queue_item is None:
            log.debug("Merged MR was not in queue", mr_iid=mr_iid)
            return

        if self.notifier:
            state_machine = await self.state_machine_factory(
                event.project_id,
                mr_iid=mr_iid,
                notifier=self.notifier,
                queue_manager=self.queue_manager,
                target_branch=event.object_attributes.target_branch,
                websocket_manager=self.websocket_manager,
                position_notifier=self.position_notifier,
            )
            current_state = state_machine.current_state.id
            if current_state == "merging":
                try:
                    await state_machine.trigger_merge_success()
                except TransitionNotAllowed:
                    log.warning(
                        "SM transition failed in _handle_merge (terminal state race), falling back to direct removal",
                        mr_iid=mr_iid,
                        current_state=state_machine.current_state.id,
                    )
                    await self.queue_manager.complete_mr(event.project_id, mr_iid, status="merged")
                    await self._remove_queue_label(mr_iid)
                finally:
                    await self._broadcast_queue_update()
                    log.info("MR cleaned up from queue after merge", mr_iid=mr_iid)
            elif current_state in ("queued", "rebasing", "testing"):
                # MR merged externally while still active in queue.
                # Can't use trigger_merge_success (requires merging state),
                # and trigger_mark_removed sends wrong notification.
                # Replicate on_enter_merged behavior manually.
                duration = calculate_duration(queue_item.queued_at)

                await self.notifier.notify(
                    mr_iid,
                    "merged",
                    merged_at=datetime.now(UTC),
                    duration=duration,
                    target_branch=event.object_attributes.target_branch,
                )

                if self.websocket_manager:
                    await self.websocket_manager.broadcast_mr_completed(
                        mr_iid,
                        "merged",
                        finished_at=datetime.now(UTC),
                    )

                positions_before: dict[int, int] = {}
                old_total: int = 0
                if self.position_notifier:
                    positions_before = await self.position_notifier.capture_queue_positions(event.project_id)
                    old_total = await self.queue_manager.get_queue_length(event.project_id)

                await self.queue_manager.complete_mr(event.project_id, mr_iid, status="merged")
                await self._remove_queue_label(mr_iid)

                if self.position_notifier and positions_before:
                    await self.position_notifier.notify_affected_mrs_after_completion(
                        event.project_id,
                        mr_iid,
                        positions_before,
                        old_total,
                    )

                await self._broadcast_queue_update()
                log.info("MR cleaned up from queue after merge", mr_iid=mr_iid)
            else:
                # Terminal state (race condition) — MR is already being handled
                log.debug(
                    "MR already in terminal state on merge webhook",
                    mr_iid=mr_iid,
                    state=current_state,
                )
        else:
            await self.queue_manager.remove_from_queue(event.project_id, mr_iid)
            await self._remove_queue_label(mr_iid)
            log.info("MR cleaned up from queue after merge", mr_iid=mr_iid)

    async def _handle_close(self, event: MergeRequestEvent) -> None:
        """Handle MR close event.

        Removes MR from queue when closed and removes queue label.

        Args:
            event: The merge request webhook event.
        """
        mr_iid = event.object_attributes.iid

        queue_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)
        if queue_item is None:
            log.debug("Closed MR was not in queue", mr_iid=mr_iid)
            return

        if self.notifier:
            state_machine = await self.state_machine_factory(
                event.project_id,
                mr_iid=mr_iid,
                notifier=self.notifier,
                queue_manager=self.queue_manager,
                target_branch=event.object_attributes.target_branch,
                websocket_manager=self.websocket_manager,
                position_notifier=self.position_notifier,
            )
            try:
                await state_machine.trigger_mark_removed(reason="closed")
            except TransitionNotAllowed:
                log.warning(
                    "SM transition failed (terminal state race), falling back to direct removal",
                    mr_iid=mr_iid,
                    current_state=state_machine.current_state.id,
                )
                await self.queue_manager.complete_mr(
                    event.project_id,
                    mr_iid,
                    status="removed",
                    failure_reason="closed",
                )
                await self._remove_queue_label(mr_iid)
            log.info("MR removed from queue after close", mr_iid=mr_iid)
        else:
            removed = await self.queue_manager.remove_from_queue(event.project_id, mr_iid)
            if removed:
                await self._remove_queue_label(mr_iid)
                log.info("MR removed from queue after close", mr_iid=mr_iid)

        await self._broadcast_queue_update()

    async def _handle_update(self, event: MergeRequestEvent) -> None:
        """Handle MR update event.

        If MR has queue label or hotfix label but is not in active queue, adds it.
        Does NOT reset state for MRs already being processed - this avoids race conditions
        with bot-initiated rebases.

        Args:
            event: The merge request webhook event.
        """
        mr_iid = event.object_attributes.iid

        # Check if MR has a trigger label (queue_label OR hotfix_label)
        has_queue_label = self.settings.queue_label in event.labels
        has_hotfix_label = self.settings.hotfix_label in event.labels
        has_trigger_label = has_queue_label or has_hotfix_label

        # Check if MR is in queue
        queue_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)

        # Terminal states - MR is not actively in queue
        terminal_states = ("removed", "failed", "merged")
        is_in_active_queue = queue_item is not None and queue_item.state not in terminal_states

        if not is_in_active_queue:
            if has_trigger_label:
                # Capture positions before adding (for notifying existing MRs about queue changes)
                positions_before: dict[int, int] = {}
                old_total: int = 0
                if self.position_notifier:
                    positions_before = await self.position_notifier.capture_queue_positions(event.project_id)
                    old_total = await self.queue_manager.get_queue_length(event.project_id)

                # MR has label but not in active queue - add it
                mr = await self.gitlab_client.get_mr(mr_iid)
                is_hotfix = has_hotfix_label
                await self.queue_manager.add_to_queue(event.project_id, mr, is_hotfix=is_hotfix)
                log.info(
                    "MR added to queue via update webhook",
                    mr_iid=mr_iid,
                    is_hotfix=is_hotfix,
                    title=mr.title,
                )
                # Broadcast queue update to UI
                await self._broadcast_queue_update()

                # Send position notification
                await self._notify_position_after_add(event.project_id, mr_iid, is_hotfix, positions_before, old_total)
            else:
                log.debug("Updated MR not in queue and no trigger label", mr_iid=mr_iid)
            return

        # Log update but don't reset state - this avoids race conditions with bot rebases
        # At this point queue_item is not None (checked by is_in_active_queue)
        assert queue_item is not None
        log.debug(
            "MR update received",
            mr_iid=mr_iid,
            current_state=queue_item.state,
            rebase_in_progress=event.object_attributes.rebase_in_progress,
        )

    async def _remove_queue_label(self, mr_iid: int) -> None:
        """Remove queue label from MR.

        Called when MR is merged or closed externally (not by the bot)
        to ensure the queue label is cleaned up.

        Args:
            mr_iid: The MR's internal ID.
        """
        try:
            await self.gitlab_client.remove_mr_label(mr_iid, self.settings.queue_label)
            log.info(
                "Queue label removed from MR",
                mr_iid=mr_iid,
                label=self.settings.queue_label,
            )
        except Exception as e:
            # Don't fail the whole operation if label removal fails
            log.warning(
                "Failed to remove queue label from MR",
                mr_iid=mr_iid,
                label=self.settings.queue_label,
                error=str(e),
            )

    async def _broadcast_queue_update(self) -> None:
        """Broadcast current queue state to all WebSocket clients."""
        if not self.websocket_manager:
            return

        try:
            queue_items = await self.queue_manager.get_active_queue(self.settings.gitlab_project_id)
            queue_stats = await self.queue_manager.get_queue_stats(self.settings.gitlab_project_id)

            # Convert queue items to dicts for WebSocket
            queue_data = []
            for i, item in enumerate(queue_items, start=1):
                queue_data.append(
                    {
                        "mr_iid": item.mr_iid,
                        "title": item.title,
                        "author": {
                            "name": item.author_name,
                            "username": item.author_username,
                            "avatar_url": item.author_avatar,
                        },
                        "target_branch": item.target_branch,
                        "status": item.state,
                        "is_hotfix": item.is_hotfix,
                        "labels": item.labels,
                        "queued_at": item.queued_at.isoformat(),
                        "started_at": item.started_at.isoformat() if item.started_at else None,
                        "position": i,
                    }
                )

            await self.websocket_manager.broadcast_queue_updated(queue_data, queue_stats)
            log.debug(
                "Broadcast queue update to WebSocket clients",
                queue_length=len(queue_data),
            )
        except Exception as e:
            log.warning("Failed to broadcast queue update", error=str(e))

    async def _refresh_queue_item_metadata(
        self,
        project_id: int,
        mr_iid: int,
        event: MergeRequestEvent,
    ) -> None:
        """Refresh labels and is_hotfix for a queued MR.

        Called when labels change but MR stays in queue, to keep
        the queue/UI metadata current.

        Args:
            mr_iid: The MR's internal ID.
            event: The merge request webhook event with current labels.
        """
        is_hotfix = self.settings.hotfix_label in event.labels
        await self.queue_manager.update_hotfix_status(
            project_id,
            mr_iid=mr_iid,
            is_hotfix=is_hotfix,
            labels=list(event.labels),
        )
        log.info(
            "Refreshed MR queue metadata",
            mr_iid=mr_iid,
            is_hotfix=is_hotfix,
            labels_count=len(event.labels),
        )

    def _was_label_changed(
        self,
        event: MergeRequestEvent,
        label: str,
        *,
        added: bool,
    ) -> bool:
        """Check if a specific label was added or removed in this event.

        Args:
            event: The merge request webhook event.
            label: The label to check for.
            added: If True, check if label was added; if False, check if removed.

        Returns:
            True if the label change occurred, False otherwise.
        """
        if not event.label_changes:
            return False

        if added:
            changed = set(event.label_changes.current) - set(event.label_changes.previous)
        else:
            changed = set(event.label_changes.previous) - set(event.label_changes.current)

        return label in changed

    def _was_queue_label_added(self, event: MergeRequestEvent) -> bool:
        """Check if queue label was added in this event."""
        return self._was_label_changed(event, self.settings.queue_label, added=True)

    def _was_queue_label_removed(self, event: MergeRequestEvent) -> bool:
        """Check if queue label was removed in this event."""
        return self._was_label_changed(event, self.settings.queue_label, added=False)

    def _was_hotfix_label_added(self, event: MergeRequestEvent) -> bool:
        """Check if hotfix label was added in this event."""
        return self._was_label_changed(event, self.settings.hotfix_label, added=True)

    def _was_hotfix_label_removed(self, event: MergeRequestEvent) -> bool:
        """Check if hotfix label was removed in this event."""
        return self._was_label_changed(event, self.settings.hotfix_label, added=False)


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
        position_notifier: Queue position notifier for position change notifications.
        websocket_manager: WebSocket manager for real-time UI updates.
    """

    settings: Settings
    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier
    position_notifier: QueuePositionNotifier | None = None
    websocket_manager: WebSocketManager | None = None
    state_machine_factory: StateMachineFactoryProtocol = field(default=create_state_machine_for_mr)

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

    async def _validate_pipeline_event(
        self,
        event: PipelineEvent,
        event_type: str,
    ) -> QueueItem | None:
        """Validate pipeline event and return queue item if valid.

        Performs common validation for all pipeline event handlers:
        1. Check MR IID is present
        2. Check MR is in queue
        3. Check MR is in testing state
        4. Check pipeline ID matches (not an old pipeline)
        5. Check SHA matches (race condition prevention)

        Args:
            event: The pipeline webhook event.
            event_type: Event type for logging ("success", "failure", "cancellation").

        Returns:
            QueueItem if event should be processed, None otherwise.
        """
        mr_iid = event.merge_request_iid
        if mr_iid is None:
            return None

        pipeline_id = event.object_attributes.id

        queue_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)
        if queue_item is None:
            log.debug(f"MR not in queue, ignoring pipeline {event_type}", mr_iid=mr_iid)
            return None

        if queue_item.state != "testing":
            log.debug(
                f"MR not in testing state, ignoring pipeline {event_type}",
                mr_iid=mr_iid,
                current_state=queue_item.state,
            )
            return None

        if queue_item.pipeline_id is not None and queue_item.pipeline_id != pipeline_id:
            # Check if incoming pipeline is a valid newer replacement
            pipeline_sha = event.object_attributes.sha
            if (
                queue_item.expected_sha is not None
                and pipeline_sha is not None
                and pipeline_sha == queue_item.expected_sha
                and pipeline_id > queue_item.pipeline_id
            ):
                log.info(
                    f"Switching to newer pipeline via {event_type} webhook",
                    mr_iid=mr_iid,
                    old_pipeline_id=queue_item.pipeline_id,
                    new_pipeline_id=pipeline_id,
                )
                await self.queue_manager.update_mr_state(
                    event.project_id,
                    mr_iid,
                    queue_item.state,
                    pipeline_id=pipeline_id,
                    retried_jobs={},
                )
                # Re-fetch updated queue item
                queue_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)
                return queue_item

            log.debug(
                f"Ignoring pipeline {event_type} for old pipeline",
                mr_iid=mr_iid,
                event_pipeline_id=pipeline_id,
                current_pipeline_id=queue_item.pipeline_id,
            )
            return None

        pipeline_sha = event.object_attributes.sha
        if queue_item.expected_sha is not None and queue_item.expected_sha != pipeline_sha:
            log.debug(
                f"Ignoring pipeline {event_type} for wrong SHA (old pipeline after rebase)",
                mr_iid=mr_iid,
                event_sha=pipeline_sha[:8],
                expected_sha=queue_item.expected_sha[:8],
            )
            return None

        return queue_item

    async def _handle_success(self, event: PipelineEvent) -> None:
        """Handle successful pipeline completion."""
        queue_item = await self._validate_pipeline_event(event, "success")
        if queue_item is None:
            return

        # mr_iid is guaranteed non-None by _validate_pipeline_event
        mr_iid = event.merge_request_iid
        assert mr_iid is not None
        pipeline_id = event.object_attributes.id

        # Re-fetch to detect concurrent state change (e.g. processor already moved to merging)
        fresh_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)
        if fresh_item is None or fresh_item.state != "testing":
            log.debug(
                "MR not in testing state, skipping pipeline success transition",
                mr_iid=mr_iid,
                pipeline_id=pipeline_id,
                current_state=fresh_item.state if fresh_item else None,
            )
            return

        if fresh_item.pipeline_id is not None and fresh_item.pipeline_id != pipeline_id:
            log.debug(
                "Pipeline ID mismatch, skipping stale pipeline success",
                mr_iid=mr_iid,
                expected_pipeline=fresh_item.pipeline_id,
                received_pipeline=pipeline_id,
            )
            return

        event_sha = event.object_attributes.sha
        if fresh_item.expected_sha and fresh_item.expected_sha != event_sha:
            log.debug(
                "SHA mismatch, skipping stale pipeline success",
                mr_iid=mr_iid,
                expected_sha=fresh_item.expected_sha,
                received_sha=event_sha,
            )
            return

        log.info(
            "Pipeline success for MR in testing state",
            mr_iid=mr_iid,
            pipeline_id=pipeline_id,
        )

        state_machine = await self.state_machine_factory(
            event.project_id,
            mr_iid=mr_iid,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            target_branch=fresh_item.target_branch,
            websocket_manager=self.websocket_manager,
            position_notifier=self.position_notifier,
        )
        try:
            await state_machine.trigger_pipeline_success()
        except TransitionNotAllowed:
            log.warning(
                "SM transition failed in _handle_success (concurrent state change)",
                mr_iid=mr_iid,
                current_state=state_machine.current_state.id,
            )

    async def _handle_failed(self, event: PipelineEvent) -> None:
        """Handle failed pipeline."""
        queue_item = await self._validate_pipeline_event(event, "failure")
        if queue_item is None:
            return

        # mr_iid is guaranteed non-None by _validate_pipeline_event
        mr_iid = event.merge_request_iid
        assert mr_iid is not None
        pipeline_id = event.object_attributes.id

        # Re-fetch queue item to detect concurrent state changes (e.g. rebase during testing)
        fresh_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)
        if fresh_item is None or fresh_item.state != "testing":
            log.debug(
                "MR state changed, skipping pipeline failure",
                mr_iid=mr_iid,
                current_state=fresh_item.state if fresh_item else None,
            )
            return
        if fresh_item.pipeline_id is not None and fresh_item.pipeline_id != pipeline_id:
            log.debug(
                "Pipeline ID mismatch after re-fetch, skipping stale failure",
                mr_iid=mr_iid,
                expected_pipeline=fresh_item.pipeline_id,
                received_pipeline=pipeline_id,
            )
            return

        current_retry_count = fresh_item.get_max_job_retry_count()

        # Mark pipeline as failed; processor handles retry logic
        log.info(
            "Pipeline failed, marking as failed",
            mr_iid=mr_iid,
            pipeline_id=pipeline_id,
            retry_count=current_retry_count,
        )
        await self.queue_manager.update_mr_state(
            event.project_id,
            mr_iid,
            "testing",
            pipeline_status="failed",
        )

    async def _handle_canceled(self, event: PipelineEvent) -> None:
        """Handle canceled pipeline."""
        queue_item = await self._validate_pipeline_event(event, "cancellation")
        if queue_item is None:
            return

        # mr_iid is guaranteed non-None by _validate_pipeline_event
        mr_iid = event.merge_request_iid
        assert mr_iid is not None
        pipeline_id = event.object_attributes.id

        # Re-fetch queue item to detect concurrent state changes (e.g. rebase during testing)
        fresh_item = await self.queue_manager.get_queue_item(event.project_id, mr_iid)
        if fresh_item is None or fresh_item.state != "testing":
            log.debug(
                "MR state changed, skipping pipeline cancellation",
                mr_iid=mr_iid,
                current_state=fresh_item.state if fresh_item else None,
            )
            return
        if fresh_item.pipeline_id is not None and fresh_item.pipeline_id != pipeline_id:
            log.debug(
                "Pipeline ID mismatch after re-fetch, skipping stale cancellation",
                mr_iid=mr_iid,
                expected_pipeline=fresh_item.pipeline_id,
                received_pipeline=pipeline_id,
            )
            return

        # Check if a newer pipeline exists before marking as failed
        newer_pipelines = []
        if fresh_item.expected_sha is not None:
            all_pipelines = await self.gitlab_client.get_mr_pipelines(mr_iid)
            newer_pipelines = [
                p
                for p in all_pipelines
                if p.id > pipeline_id and p.sha is not None and p.sha == fresh_item.expected_sha
            ]

        if newer_pipelines:
            best = max(newer_pipelines, key=lambda p: p.id)
            log.info(
                "Canceled pipeline has newer replacement, switching",
                mr_iid=mr_iid,
                old_pipeline_id=pipeline_id,
                new_pipeline_id=best.id,
            )
            await self.queue_manager.update_mr_state(
                event.project_id,
                mr_iid,
                "testing",
                pipeline_id=best.id,
                retried_jobs={},
            )
        else:
            current_retry_count = fresh_item.get_max_job_retry_count()
            log.info(
                "Pipeline canceled, no replacement found, marking as failed",
                mr_iid=mr_iid,
                pipeline_id=pipeline_id,
                retry_count=current_retry_count,
            )
            await self.queue_manager.update_mr_state(
                event.project_id,
                mr_iid,
                "testing",
                pipeline_status="failed",
            )


@dataclass
class WebhookHandler:
    """Unified webhook handler for integration tests.

    Combines MRWebhookHandler and PipelineWebhookHandler functionality
    for backward compatibility with integration tests.

    Attributes:
        queue_manager: Queue manager for MR operations.
        gitlab_client: GitLab API client.
        settings: Application configuration.
        notifier: Optional MR notifier for state machine notifications.
        position_notifier: Optional queue position notifier.
        websocket_manager: WebSocket manager for real-time UI updates.
    """

    queue_manager: QueueManager
    gitlab_client: GitLabClient
    settings: Settings
    notifier: MRNotifier | None = None
    position_notifier: QueuePositionNotifier | None = None
    websocket_manager: WebSocketManager | None = None

    def __post_init__(self) -> None:
        if self.notifier is None:
            from gitlab_queue.core.notifier import MRNotifier

            self.notifier = MRNotifier(gitlab_client=self.gitlab_client, settings=self.settings)

    async def handle_merge_request_event(self, webhook_payload: dict[str, Any]) -> None:
        """Handle merge request webhook event.

        Args:
            webhook_payload: Raw webhook payload dict.
        """
        from gitlab_queue.models.retorts import parse_webhook_event

        event = parse_webhook_event(webhook_payload)
        if isinstance(event, MergeRequestEvent):
            assert self.notifier is not None
            handler = MRWebhookHandler(
                settings=self.settings,
                gitlab_client=self.gitlab_client,
                queue_manager=self.queue_manager,
                notifier=self.notifier,
                position_notifier=self.position_notifier,
                websocket_manager=self.websocket_manager,
            )
            await handler.handle(event)

    async def handle_pipeline_event(self, webhook_payload: dict[str, Any]) -> None:
        """Handle pipeline webhook event.

        Args:
            webhook_payload: Raw webhook payload dict.
        """
        from gitlab_queue.models.retorts import parse_webhook_event

        event = parse_webhook_event(webhook_payload)
        if isinstance(event, PipelineEvent):
            assert self.notifier is not None
            handler = PipelineWebhookHandler(
                settings=self.settings,
                gitlab_client=self.gitlab_client,
                queue_manager=self.queue_manager,
                notifier=self.notifier,
                position_notifier=self.position_notifier,
                websocket_manager=self.websocket_manager,
            )
            await handler.handle(event)

    async def validate_webhook(self, payload: dict[str, Any], secret_token: str | None = None) -> bool:
        """Validate webhook authenticity and project ID.

        Args:
            payload: Webhook payload.
            secret_token: Secret token from webhook headers.

        Returns:
            True if webhook is valid, False otherwise.
        """
        from gitlab_queue.models.events import validate_webhook_token

        # Validate secret if configured
        if self.settings.webhook_secret:
            if not secret_token:
                return False
            if not validate_webhook_token(
                secret_token,
                self.settings.webhook_secret.get_secret_value(),
            ):
                return False

        # Validate project ID
        project_id = payload.get("project", {}).get("id")
        return bool(project_id == self.settings.gitlab_project_id)


__all__: list[str] = [
    "MRWebhookHandler",
    "PipelineWebhookHandler",
    "WebhookHandler",
]
