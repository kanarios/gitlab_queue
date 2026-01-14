"""Graceful shutdown management for GitLab Queue Bot.

Provides signal handling and coordinated shutdown for all application components.
Integrates with asyncio event loop for proper async cleanup.

Example:
    >>> async def main():
    ...     shutdown_manager = ShutdownManager()
    ...     shutdown_manager.register_signals()
    ...     try:
    ...         await run_application()
    ...     finally:
    ...         await shutdown_manager.shutdown()
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = get_logger(__name__)


class ShutdownReason(Enum):
    """Reason for shutdown initiation."""

    SIGTERM = "sigterm"
    SIGINT = "sigint"
    PROGRAMMATIC = "programmatic"
    ERROR = "error"


@dataclass
class ShutdownManager:
    """Coordinates graceful shutdown across application components.

    Handles signal registration, shutdown sequencing, and resource cleanup.
    Designed to work with asyncio event loops and integrate with the
    existing MergeProcessor shutdown mechanism.

    Attributes:
        shutdown_timeout: Maximum seconds to wait for graceful shutdown.

    Example:
        >>> manager = ShutdownManager(shutdown_timeout=30.0)
        >>> manager.register_signals()
        >>> # ... run application ...
        >>> await manager.shutdown(ShutdownReason.SIGTERM)
    """

    shutdown_timeout: float = 30.0

    # Internal state (not part of constructor)
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _shutdown_reason: ShutdownReason | None = field(default=None, init=False)
    _components: list[tuple[str, Callable[[], Awaitable[None]]]] = field(
        default_factory=list, init=False
    )
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)
    _signals_registered: bool = field(default=False, init=False)

    def register_signals(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Register signal handlers for graceful shutdown.

        Registers handlers for SIGTERM and SIGINT. On Windows, only SIGINT
        is supported. Stores reference to event loop for signal handling.

        Args:
            loop: Event loop to use for signal handling. If None, uses
                  the running loop (must be called from async context).
        """
        if self._signals_registered:
            log.warning("Signal handlers already registered")
            return

        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                log.error("No running event loop - cannot register signals")
                return

        self._loop = loop
        signals_to_handle: list[signal.Signals] = [signal.SIGINT]

        # SIGTERM is only available on Unix-like systems
        if sys.platform != "win32":
            signals_to_handle.append(signal.SIGTERM)

        for sig in signals_to_handle:
            if sys.platform != "win32":
                # Unix: use loop.add_signal_handler for cleaner async integration
                loop.add_signal_handler(
                    sig,
                    self._handle_signal,
                    sig,
                )
            else:
                # Windows: use traditional signal handler
                signal.signal(sig, self._create_sync_handler(sig))

        self._signals_registered = True
        log.info(
            "Signal handlers registered",
            signals=[s.name for s in signals_to_handle],
        )

    def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle signal by setting shutdown event.

        Called directly on Unix (from loop.add_signal_handler).

        Args:
            sig: Signal that was received.
        """
        reason = ShutdownReason.SIGTERM if sig == signal.SIGTERM else ShutdownReason.SIGINT
        log.info(
            "Received signal",
            signal=sig.name,
            reason=reason.value,
        )

        if not self._shutdown_event.is_set():
            self._shutdown_reason = reason
            self._shutdown_event.set()

    def _create_sync_handler(self, sig: signal.Signals) -> Callable[[int, Any], None]:
        """Create synchronous signal handler for Windows.

        The handler schedules the async shutdown on the event loop.

        Args:
            sig: Signal to handle.

        Returns:
            Signal handler function.
        """

        def handler(signum: int, frame: Any) -> None:  # noqa: ARG001
            reason = ShutdownReason.SIGTERM if sig == signal.SIGTERM else ShutdownReason.SIGINT
            log.info(
                "Received signal",
                signal=sig.name,
                reason=reason.value,
            )

            if self._loop is not None and not self._shutdown_event.is_set():
                self._shutdown_reason = reason
                # Thread-safe way to set the event from signal context
                self._loop.call_soon_threadsafe(self._shutdown_event.set)

        return handler

    def unregister_signals(self) -> None:
        """Remove signal handlers and restore defaults."""
        if not self._signals_registered:
            return

        if self._loop is None:
            return

        signals_to_unregister: list[signal.Signals] = [signal.SIGINT]
        if sys.platform != "win32":
            signals_to_unregister.append(signal.SIGTERM)

        for sig in signals_to_unregister:
            if sys.platform != "win32":
                # Loop may be closed or signal not registered
                with contextlib.suppress(ValueError, RuntimeError):
                    self._loop.remove_signal_handler(sig)
            else:
                signal.signal(sig, signal.SIG_DFL)

        self._signals_registered = False
        log.debug("Signal handlers unregistered")

    def register_component(
        self,
        name: str,
        cleanup_func: Callable[[], Awaitable[None]],
    ) -> None:
        """Register a component for cleanup during shutdown.

        Components are cleaned up in reverse registration order (LIFO).

        Args:
            name: Human-readable component name for logging.
            cleanup_func: Async function to call during shutdown.
        """
        self._components.append((name, cleanup_func))
        log.debug("Registered component for cleanup", component=name)

    def request_shutdown(self, reason: ShutdownReason = ShutdownReason.PROGRAMMATIC) -> None:
        """Request graceful shutdown.

        Thread-safe method to initiate shutdown from any context.

        Args:
            reason: Why shutdown was requested.
        """
        if self._shutdown_event.is_set():
            log.debug("Shutdown already requested")
            return

        log.info("Shutdown requested", reason=reason.value)
        self._shutdown_reason = reason
        self._shutdown_event.set()

    async def wait_for_shutdown(self) -> ShutdownReason:
        """Wait until shutdown is requested.

        Returns:
            The reason shutdown was requested.
        """
        await self._shutdown_event.wait()
        return self._shutdown_reason or ShutdownReason.PROGRAMMATIC

    async def shutdown(self, reason: ShutdownReason | None = None) -> bool:
        """Execute graceful shutdown sequence.

        Cleans up all registered components in reverse order with timeout.

        Args:
            reason: Override reason if not already set.

        Returns:
            True if all components cleaned up successfully within timeout.
        """
        if reason is not None and self._shutdown_reason is None:
            self._shutdown_reason = reason

        if not self._shutdown_event.is_set():
            self._shutdown_event.set()

        log.info(
            "Starting shutdown sequence",
            reason=self._shutdown_reason.value if self._shutdown_reason else "unknown",
            component_count=len(self._components),
        )

        all_success = True

        # Cleanup components in reverse order (LIFO)
        for name, cleanup_func in reversed(self._components):
            log.info("Cleaning up component", component=name)
            try:
                await asyncio.wait_for(
                    cleanup_func(),
                    timeout=self.shutdown_timeout / max(len(self._components), 1),
                )
                log.debug("Component cleanup complete", component=name)
            except TimeoutError:
                log.warning(
                    "Component cleanup timeout",
                    component=name,
                )
                all_success = False
            except Exception as e:
                log.exception(
                    "Component cleanup failed",
                    component=name,
                    error=str(e),
                )
                all_success = False

        # Unregister signal handlers
        self.unregister_signals()

        if all_success:
            log.info("Shutdown sequence complete")
        else:
            log.warning("Shutdown sequence completed with errors")

        return all_success

    @property
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()

    @property
    def shutdown_reason(self) -> ShutdownReason | None:
        """Get the reason for shutdown, if requested."""
        return self._shutdown_reason


__all__: list[str] = [
    "ShutdownManager",
    "ShutdownReason",
]
