"""Main entry point for GitLab Merge Queue Bot.

Initializes all components, sets up graceful shutdown, and runs the processor.

Usage:
    python -m gitlab_queue

Environment Variables:
    See config.py for full list. Required:
    - GITLAB_QUEUE_GITLAB_TOKEN
    - GITLAB_QUEUE_GITLAB_PROJECT_ID
    - GITLAB_QUEUE_JWT_SECRET
    - GITLAB_QUEUE_WEBHOOK_SECRET (if webhooks enabled)
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import environ
import uvicorn

from gitlab_queue import __version__
from gitlab_queue.api.websocket import WebSocketManager
from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabCircuitOpenError, GitLabClient
from gitlab_queue.config import ConfigurationError, load_settings
from gitlab_queue.core.notifier import MRNotifier
from gitlab_queue.core.processor import MergeProcessor, create_processor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.core.scheduler import QueueScheduler, create_scheduler
from gitlab_queue.db.database import Database, DatabaseConnectionError
from gitlab_queue.dependencies import set_database
from gitlab_queue.health import ApplicationHealth, ComponentStatus, GitLabHealth
from gitlab_queue.jobs import AnalyticsJobProcessor, create_analytics_processor
from gitlab_queue.utils.logging import configure_logging, get_logger
from gitlab_queue.utils.shutdown import ShutdownManager, ShutdownReason
from gitlab_queue.webhooks import WebhookAppState, create_webhook_app
from gitlab_queue.webhooks.retry_manager import WebhookRetryManager
from gitlab_queue.webhooks.retry_processor import WebhookRetryProcessor, create_retry_processor

if TYPE_CHECKING:
    from gitlab_queue.config import Settings

log = get_logger(__name__)


# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_GITLAB_ERROR = 2
EXIT_RUNTIME_ERROR = 3


@dataclass
class Application:
    """Application container holding all initialized components.

    Provides structured access to components and cleanup coordination.
    """

    settings: Settings
    database: Database
    gitlab_client: GitLabClient
    queue_manager: QueueManager
    notifier: MRNotifier
    processor: MergeProcessor
    scheduler: QueueScheduler
    retry_manager: WebhookRetryManager
    retry_processor: WebhookRetryProcessor
    analytics_processor: AnalyticsJobProcessor
    shutdown_manager: ShutdownManager
    health: ApplicationHealth


async def verify_gitlab_access(client: GitLabClient, settings: Settings) -> None:
    """Verify GitLab token has required permissions.

    Performs a test API call to ensure the token is valid and has
    access to the configured project.

    Args:
        client: Initialized GitLab client.
        settings: Settings with project ID.

    Raises:
        GitLabAPIError: If verification fails.
    """
    log.debug(
        "Verifying GitLab access",
        project_id=settings.gitlab_project_id,
    )

    # Try to list MRs with the queue label - this verifies read access
    mrs = await client.list_mrs_with_label(settings.queue_label)

    log.info(
        "GitLab access verified",
        project_id=settings.gitlab_project_id,
        mrs_with_label=len(mrs),
    )


async def initialize_database_with_retry(
    settings: Settings,
    shutdown_event: asyncio.Event | None = None,
) -> Database:
    """Initialize database with indefinite retry on failure.

    Uses exponential backoff starting at base delay, capping at max delay.
    Continues retrying until successful or shutdown is requested.

    Args:
        settings: Application settings with database URL.
        shutdown_event: Optional event to check for shutdown request.

    Returns:
        Initialized Database instance.

    Raises:
        asyncio.CancelledError: If shutdown requested during retry.
    """
    delay = float(settings.database_retry_base_delay_seconds)
    max_delay = float(settings.database_retry_max_delay_seconds)
    attempt = 0

    while True:
        attempt += 1
        try:
            database = Database(database_url=settings.database_url)
            await database.initialize()

            if attempt > 1:
                log.info(
                    "Database connection established after retries",
                    attempt=attempt,
                )
            return database

        except DatabaseConnectionError as e:
            log.warning(
                "Database initialization failed, retrying",
                error=str(e),
                attempt=attempt,
                retry_delay_seconds=delay,
            )

            # Check for shutdown request
            if shutdown_event is not None and shutdown_event.is_set():
                raise asyncio.CancelledError("Shutdown requested during database init")

            # Wait with exponential backoff
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)


async def create_application(settings: Settings) -> Application:
    """Initialize all application components with graceful degradation.

    Components are initialized in dependency order:
    1. Shutdown manager (always first for cleanup registration)
    2. Database (retries indefinitely until available)
    3. GitLab client (may start in degraded mode if unavailable)
    4. Queue manager and other components

    Args:
        settings: Validated application settings.

    Returns:
        Fully initialized Application instance with health state.

    Raises:
        asyncio.CancelledError: If shutdown requested during database retry.
        GitLabAPIError: Only if startup_gitlab_required=True and GitLab fails.
    """
    log.info(
        "Initializing application",
        version=__version__,
        project_id=settings.gitlab_project_id,
        target_branch=settings.target_branch,
    )

    # Initialize health tracking
    health = ApplicationHealth()

    # 1. Initialize shutdown manager first (needed for cleanup registration)
    shutdown_manager = ShutdownManager(shutdown_timeout=30.0)

    # 2. Initialize database with retry (will retry indefinitely)
    log.info("Initializing database (will retry indefinitely if unavailable)")
    database = await initialize_database_with_retry(
        settings,
        shutdown_event=shutdown_manager._shutdown_event,
    )
    shutdown_manager.register_component("database", database.close)
    health.database = ComponentStatus.HEALTHY

    # Set database for FastAPI dependency injection
    set_database(database)

    # 3. Initialize GitLab client
    gitlab_client = GitLabClient(settings)
    shutdown_manager.register_component("gitlab_client", gitlab_client.close)

    # 4. Verify GitLab access (may fail if degraded mode allowed)
    gitlab_verified = False
    try:
        await verify_gitlab_access(gitlab_client, settings)
        gitlab_verified = True
        health.gitlab = GitLabHealth.from_circuit_breaker(gitlab_client.circuit_breaker)
    except (GitLabAPIError, GitLabCircuitOpenError) as e:
        if settings.startup_gitlab_required:
            raise
        log.warning(
            "GitLab verification failed, starting in degraded mode",
            error=str(e),
        )
        health.gitlab = GitLabHealth(
            status=ComponentStatus.UNHEALTHY,
            circuit_state="unknown",
            failure_count=0,
        )

    # 5. Initialize queue manager and ensure schema
    queue_manager = QueueManager(db=database)
    await queue_manager.ensure_schema()

    # 6. Initialize notifier
    notifier = MRNotifier(gitlab_client=gitlab_client, settings=settings)

    # 7. Create processor
    processor = create_processor(
        gitlab_client=gitlab_client,
        queue_manager=queue_manager,
        notifier=notifier,
        settings=settings,
    )

    # 8. Create scheduler for polling fallback
    scheduler = create_scheduler(
        gitlab_client=gitlab_client,
        queue_manager=queue_manager,
        settings=settings,
    )

    # 9. Initialize webhook retry manager and ensure schema
    retry_manager = WebhookRetryManager(
        db=database,
        max_attempts=settings.webhook_retry_max_attempts,
        base_delay_seconds=settings.webhook_retry_base_delay_seconds,
        max_delay_seconds=settings.webhook_retry_max_delay_seconds,
    )
    await retry_manager.ensure_schema()

    # 10. Create webhook retry processor
    retry_processor = create_retry_processor(
        retry_manager=retry_manager,
        settings=settings,
        gitlab_client=gitlab_client,
        queue_manager=queue_manager,
        notifier=notifier,
    )

    # 11. Create analytics job processor
    analytics_processor = create_analytics_processor(
        database=database,
        settings=settings,
    )

    mode = "normal" if gitlab_verified else "degraded"
    log.info(f"Application initialized in {mode} mode")

    return Application(
        settings=settings,
        database=database,
        gitlab_client=gitlab_client,
        queue_manager=queue_manager,
        notifier=notifier,
        processor=processor,
        scheduler=scheduler,
        retry_manager=retry_manager,
        retry_processor=retry_processor,
        analytics_processor=analytics_processor,
        shutdown_manager=shutdown_manager,
        health=health,
    )


async def run_application(app: Application) -> int:
    """Run the main application loop.

    Args:
        app: Initialized application.

    Returns:
        Exit code (0 for success).
    """
    # Register signal handlers
    app.shutdown_manager.register_signals()

    log.info(
        "Starting merge processor",
        poll_interval=app.settings.poll_interval_seconds,
    )

    # Track background tasks for proper cleanup
    webhook_server_task: asyncio.Task[None] | None = None
    retry_processor_task: asyncio.Task[None] | None = None
    scheduler_task: asyncio.Task[None] | None = None
    analytics_processor_task: asyncio.Task[None] | None = None

    try:
        # Run processor in background task
        processor_task = asyncio.create_task(app.processor.run())
        app.health.processor_running = True

        # Run scheduler in background task for polling fallback
        log.info("Starting queue scheduler for polling fallback")
        scheduler_task = asyncio.create_task(app.scheduler.run())

        # Run retry processor in background task
        log.info("Starting webhook retry processor")
        retry_processor_task = asyncio.create_task(app.retry_processor.run())

        # Run analytics job processor in background task
        log.info("Starting analytics job processor")
        analytics_processor_task = asyncio.create_task(app.analytics_processor.run())

        # Start webhook server if enabled
        if app.settings.webhook_enabled:
            log.info(
                "Starting webhook server",
                host=app.settings.webhook_host,
                port=app.settings.webhook_port,
            )

            # Create WebSocket manager for real-time dashboard updates
            websocket_manager = WebSocketManager()

            webhook_state = WebhookAppState(
                settings=app.settings,
                database=app.database,
                gitlab_client=app.gitlab_client,
                queue_manager=app.queue_manager,
                notifier=app.notifier,
                retry_manager=app.retry_manager,
                health=app.health,
                websocket_manager=websocket_manager,
            )
            app.health.webhook_server_running = True
            webhook_app = create_webhook_app(webhook_state)

            config = uvicorn.Config(
                webhook_app,
                host=app.settings.webhook_host,
                port=app.settings.webhook_port,
                log_level="warning",  # Suppress uvicorn logs, use structlog
                access_log=False,
            )
            uvicorn_server = uvicorn.Server(config)

            # Register server shutdown with manager
            app.shutdown_manager.register_component(
                "webhook_server",
                uvicorn_server.shutdown,
            )

            # Start server in background
            webhook_server_task = asyncio.create_task(uvicorn_server.serve())

        # Wait for shutdown signal
        reason = await app.shutdown_manager.wait_for_shutdown()

        log.info("Shutdown initiated", reason=reason.value)

        # Signal processors to stop
        app.processor.request_shutdown()
        app.scheduler.request_shutdown()
        app.retry_processor.request_shutdown()
        app.analytics_processor.request_shutdown()

        # Wait for processors to finish current iteration with timeout
        try:
            await asyncio.wait_for(processor_task, timeout=app.shutdown_manager.shutdown_timeout)
            log.info("Processor stopped gracefully")
        except TimeoutError:
            log.warning("Processor shutdown timeout, cancelling task")
            processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await processor_task

        # Wait for scheduler to finish
        if scheduler_task is not None:
            try:
                await asyncio.wait_for(scheduler_task, timeout=10.0)
                log.info("Scheduler stopped gracefully")
            except TimeoutError:
                log.warning("Scheduler shutdown timeout, cancelling task")
                scheduler_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await scheduler_task

        # Wait for retry processor to finish
        if retry_processor_task is not None:
            try:
                await asyncio.wait_for(retry_processor_task, timeout=10.0)
                log.info("Retry processor stopped gracefully")
            except TimeoutError:
                log.warning("Retry processor shutdown timeout, cancelling task")
                retry_processor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await retry_processor_task

        # Wait for analytics processor to finish
        if analytics_processor_task is not None:
            try:
                await asyncio.wait_for(analytics_processor_task, timeout=10.0)
                log.info("Analytics processor stopped gracefully")
            except TimeoutError:
                log.warning("Analytics processor shutdown timeout, cancelling task")
                analytics_processor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await analytics_processor_task

        # Cleanup all components (including webhook server via registered shutdown)
        success = await app.shutdown_manager.shutdown(reason)

        # Wait for webhook server task to complete after shutdown was triggered
        if webhook_server_task is not None:
            try:
                await asyncio.wait_for(webhook_server_task, timeout=5.0)
                log.debug("Webhook server stopped gracefully")
            except TimeoutError:
                log.warning("Webhook server shutdown timeout, cancelling task")
                webhook_server_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await webhook_server_task
            except Exception as e:
                log.warning("Webhook server error during shutdown", error=str(e))

        if success:
            log.info("Application shutdown complete")
            return EXIT_SUCCESS

        log.warning("Application shutdown completed with warnings")
        return EXIT_SUCCESS  # Still success, just logged warnings

    except Exception as e:
        log.exception("Unexpected error in main loop", error=str(e))
        return EXIT_RUNTIME_ERROR


async def async_main() -> int:
    """Async entry point with full error handling.

    Returns:
        Exit code for the process.
    """
    app: Application | None = None

    try:
        # Load and validate settings
        settings = load_settings()

        # Configure logging based on settings
        configure_logging(settings.log_level, settings.log_format)

        log.info(
            "GitLab Merge Queue Bot starting",
            version=__version__,
        )

        # Initialize application
        app = await create_application(settings)

        # Run main loop
        return await run_application(app)

    except environ.exceptions.MissingEnvValueError as e:
        # Logging might not be configured yet, use print
        print(f"Missing required environment variable: {e}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    except ValueError as e:
        # ValueError from type conversion in config
        print(f"Configuration error: {e}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    except asyncio.CancelledError:
        # Shutdown requested during startup (e.g., during database retry)
        log.info("Shutdown requested during startup")
        return EXIT_SUCCESS

    except GitLabAPIError as e:
        # Only raised if startup_gitlab_required=True
        log.error("GitLab API error during startup", error=str(e))
        return EXIT_GITLAB_ERROR

    except Exception as e:
        log.exception("Unexpected startup error", error=str(e))
        return EXIT_RUNTIME_ERROR

    finally:
        # Ensure cleanup even on error
        if app is not None:
            try:
                await app.shutdown_manager.shutdown(ShutdownReason.ERROR)
            except Exception as cleanup_error:
                log.exception("Error during cleanup", error=str(cleanup_error))


def main() -> None:
    """Synchronous entry point for CLI."""
    exit_code = asyncio.run(async_main())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()


__all__: list[str] = [
    "EXIT_CONFIG_ERROR",
    "EXIT_GITLAB_ERROR",
    "EXIT_RUNTIME_ERROR",
    "EXIT_SUCCESS",
    "Application",
    "async_main",
    "create_application",
    "initialize_database_with_retry",
    "main",
    "run_application",
    "verify_gitlab_access",
]
