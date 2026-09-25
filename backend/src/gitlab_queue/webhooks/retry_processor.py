"""Webhook Retry Processor for GitLab Merge Queue Bot.

Background task that processes the webhook retry queue, retrying failed
webhook events with exponential backoff.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from gitlab_queue.models.events import MergeRequestEvent, PipelineEvent
from gitlab_queue.models.retorts import parse_webhook_event
from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from gitlab_queue.api.websocket import WebSocketManager
    from gitlab_queue.clients.gitlab import GitLabClient
    from gitlab_queue.config import Settings
    from gitlab_queue.core.notifier import MRNotifier
    from gitlab_queue.core.project_components import ProjectComponents
    from gitlab_queue.core.queue import QueueManager
    from gitlab_queue.core.queue_position_notifier import QueuePositionNotifier
    from gitlab_queue.models.retry import RetryQueueItem
    from gitlab_queue.webhooks.handlers import MRWebhookHandler, PipelineWebhookHandler
    from gitlab_queue.webhooks.retry_manager import WebhookRetryManager

log = get_logger(__name__)


@dataclass
class WebhookRetryProcessor:
    """Background processor for webhook retry queue.

    Continuously polls the retry queue and processes events that are
    ready for retry. Failed retries are scheduled for later retry or
    moved to the DLQ after max attempts.

    Example:
        >>> processor = WebhookRetryProcessor(
        ...     retry_manager=retry_manager,
        ...     settings=settings,
        ...     gitlab_client=gitlab_client,
        ...     queue_manager=queue_manager,
        ...     notifier=notifier,
        ... )
        >>> task = asyncio.create_task(processor.run())
        >>> # ... later
        >>> processor.request_shutdown()
        >>> await task
    """

    retry_manager: WebhookRetryManager
    settings: Settings
    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier
    position_notifier: QueuePositionNotifier | None = None
    websocket_manager: WebSocketManager | None = None
    mr_handler_factory: Callable[..., MRWebhookHandler] | None = None
    pipeline_handler_factory: Callable[..., PipelineWebhookHandler] | None = None
    event_parser: Callable[[dict[str, Any]], MergeRequestEvent | PipelineEvent | None] | None = None
    project_components: Mapping[int, ProjectComponents] | None = None

    # Internal state
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _processing_count: int = field(default=0, init=False)
    _processing_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def set_websocket_manager(self, manager: WebSocketManager) -> None:
        """Set WebSocket manager for broadcasting queue updates.

        Args:
            manager: WebSocket manager instance.
        """
        self.websocket_manager = manager

    async def run(self) -> None:
        """Main processing loop - runs until shutdown signal.

        Continuously polls the retry queue and processes events.
        """
        log.info("Webhook retry processor starting")

        try:
            while not self._shutdown_event.is_set():
                try:
                    await self._process_iteration()
                except Exception as e:
                    log.exception("Retry processor iteration failed", error=str(e))

                # Cancellable sleep between iterations
                if not await self._interruptible_sleep(self.settings.webhook_retry_poll_interval_seconds):
                    break

        finally:
            log.info("Webhook retry processor stopped")

    async def _process_iteration(self) -> None:
        """Execute one iteration of the retry processing loop."""
        log.debug("Retry processor iteration started")

        # Fetch a bounded batch per project so a noisy project cannot starve
        # retry processing for every other configured project.
        if self.project_components is None:
            events = await self.retry_manager.get_events_ready_for_retry(limit=10)
        else:
            events = []
            for project_id in self.project_components:
                events.extend(await self.retry_manager.get_events_ready_for_retry(limit=10, project_id=project_id))

            # Removed projects are excluded from normal dispatch so that
            # configured projects retain their per-project retry budget.
            # Move their ready rows to the DLQ below instead of replaying them.
            events.extend(
                await self.retry_manager.get_events_ready_for_retry(
                    limit=10,
                    excluded_project_ids=tuple(self.project_components),
                )
            )

        if not events:
            log.debug("No events ready for retry")
            return

        log.info("Processing retry events", count=len(events))

        for item in events:
            if self._shutdown_event.is_set():
                log.info("Shutdown requested, stopping retry processing")
                break

            await self._process_retry_item(item)

    async def _process_retry_item(self, item: RetryQueueItem) -> None:
        """Process a single retry queue item.

        Args:
            item: The retry queue item to process.
        """
        log.info(
            "Processing retry item",
            retry_id=item.id,
            event_type=item.event_type,
            attempt=item.attempt_count + 1,
        )

        async with self._processing_lock:
            self._processing_count += 1

        try:
            if self.project_components is not None and item.project_id not in self.project_components:
                log.warning(
                    "Moving retry item for unconfigured project to DLQ",
                    retry_id=item.id,
                    project_id=item.project_id,
                )
                await self.retry_manager.move_retry_to_dlq(
                    item.id,
                    "Project is no longer configured; automatic retry was stopped",
                    project_id=item.project_id,
                )
                return

            # Parse the webhook event from stored payload
            parser = self.event_parser or parse_webhook_event
            event = parser(item.payload)

            if event is None:
                # Unknown event type - should not happen, move to DLQ
                error_msg = f"Unknown event type: {item.event_type}"
                log.warning(error_msg, retry_id=item.id)
                await self.retry_manager.mark_retry_failed(item.id, error_msg, project_id=item.project_id)
                return

            if self.project_components is not None and event.project_id != item.project_id:
                error_msg = "Stored project_id does not match webhook payload"
                await self.retry_manager.mark_retry_failed(item.id, error_msg, project_id=item.project_id)
                return

            # Process based on event type
            if isinstance(event, MergeRequestEvent):
                await self._handle_mr_event(event, item.project_id)
            elif isinstance(event, PipelineEvent):
                await self._handle_pipeline_event(event, item.project_id)
            else:
                error_msg = f"Unsupported event type: {type(event).__name__}"
                log.warning(error_msg, retry_id=item.id)
                await self.retry_manager.mark_retry_failed(item.id, error_msg, project_id=item.project_id)
                return

            # Success - remove from retry queue
            await self.retry_manager.mark_retry_success(item.id, project_id=item.project_id)
            log.info(
                "Retry succeeded",
                retry_id=item.id,
                event_type=item.event_type,
                attempt=item.attempt_count + 1,
            )

        except Exception as e:
            # Failed - schedule next retry or move to DLQ
            moved_to_dlq = await self.retry_manager.mark_retry_failed(item.id, str(e), project_id=item.project_id)

            if moved_to_dlq:
                log.warning(
                    "Event moved to DLQ after max retries",
                    retry_id=item.id,
                    event_type=item.event_type,
                    attempts=item.attempt_count + 1,
                    error=str(e),
                )
            else:
                log.info(
                    "Retry failed, scheduled for later",
                    retry_id=item.id,
                    event_type=item.event_type,
                    attempt=item.attempt_count + 1,
                    error=str(e),
                )

        finally:
            async with self._processing_lock:
                self._processing_count -= 1

    def _handler_kwargs(self, project_id: int) -> dict[str, Any]:
        """Common kwargs for webhook handler construction."""
        if self.project_components is not None:
            components = self.project_components[project_id]
            return {
                "settings": components.settings,
                "gitlab_client": components.gitlab_client,
                "queue_manager": self.queue_manager,
                "notifier": components.notifier,
                "position_notifier": components.position_notifier,
                "websocket_manager": self.websocket_manager,
            }
        return {
            "settings": self.settings,
            "gitlab_client": self.gitlab_client,
            "queue_manager": self.queue_manager,
            "notifier": self.notifier,
            "position_notifier": self.position_notifier,
            "websocket_manager": self.websocket_manager,
        }

    def _create_mr_handler(self, project_id: int) -> MRWebhookHandler:
        handler_kwargs = self._handler_kwargs(project_id)
        if self.mr_handler_factory is not None:
            return self.mr_handler_factory(**handler_kwargs)
        from gitlab_queue.webhooks.handlers import MRWebhookHandler

        return MRWebhookHandler(**handler_kwargs)

    def _create_pipeline_handler(self, project_id: int) -> PipelineWebhookHandler:
        handler_kwargs = self._handler_kwargs(project_id)
        if self.pipeline_handler_factory is not None:
            return self.pipeline_handler_factory(**handler_kwargs)
        from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

        return PipelineWebhookHandler(**handler_kwargs)

    async def _handle_mr_event(self, event: MergeRequestEvent, project_id: int = 0) -> None:
        """Handle a merge request webhook event."""
        handler = self._create_mr_handler(project_id)
        await handler.handle(event)

    async def _handle_pipeline_event(self, event: PipelineEvent, project_id: int = 0) -> None:
        """Handle a pipeline webhook event."""
        handler = self._create_pipeline_handler(project_id)
        await handler.handle(event)

    async def _interruptible_sleep(self, seconds: float) -> bool:
        """Sleep that can be interrupted by shutdown event.

        Args:
            seconds: Number of seconds to sleep.

        Returns:
            True if sleep completed, False if interrupted by shutdown.
        """
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=seconds,
            )
            return False
        except TimeoutError:
            return True

    def request_shutdown(self) -> None:
        """Request graceful shutdown of the processor."""
        log.info("Retry processor shutdown requested")
        self._shutdown_event.set()

    async def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """Wait for the processor to complete shutdown.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if shutdown completed, False if timeout.
        """
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=timeout,
            )
            return True
        except TimeoutError:
            return False

    @property
    def is_processing(self) -> bool:
        """Check if processor is currently processing events."""
        return self._processing_count > 0

    @property
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()


def create_retry_processor(
    retry_manager: WebhookRetryManager,
    settings: Settings,
    gitlab_client: GitLabClient,
    queue_manager: QueueManager,
    notifier: MRNotifier,
    position_notifier: QueuePositionNotifier | None = None,
    websocket_manager: WebSocketManager | None = None,
) -> WebhookRetryProcessor:
    """Create a configured WebhookRetryProcessor instance.

    Args:
        retry_manager: Retry queue manager.
        settings: Application settings.
        gitlab_client: GitLab API client.
        queue_manager: Queue manager for MR storage.
        notifier: Notifier for MR comments.
        websocket_manager: WebSocket manager for real-time UI updates.

    Returns:
        Configured WebhookRetryProcessor ready to run.
    """
    return WebhookRetryProcessor(
        retry_manager=retry_manager,
        settings=settings,
        gitlab_client=gitlab_client,
        queue_manager=queue_manager,
        notifier=notifier,
        position_notifier=position_notifier,
        websocket_manager=websocket_manager,
    )


__all__: list[str] = [
    "WebhookRetryProcessor",
    "create_retry_processor",
]
