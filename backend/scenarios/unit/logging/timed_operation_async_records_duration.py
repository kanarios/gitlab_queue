"""Test that timed_operation_async records execution duration."""

from __future__ import annotations

import asyncio
import logging
from io import StringIO

import vedro

from gitlab_queue.config import LogFormat, LogLevel
from gitlab_queue.utils.logging import (
    configure_logging,
    reset_logging,
    timed_operation_async,
)


class Scenario(vedro.Scenario):
    subject = "timed_operation_async records execution duration"

    def given_logging_configured_and_log_capture(self):
        reset_logging()
        configure_logging(LogLevel.DEBUG, LogFormat.JSON)
        # Capture log output via a string stream handler
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        formatter = logging.getLogger().handlers[0].formatter
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

    async def when_timed_async_operation_completes(self):
        async with timed_operation_async("test_operation", extra_key="test_val"):
            await asyncio.sleep(0.05)  # 50ms

    def then_log_output_should_contain_started_message(self):
        output = self.log_stream.getvalue()
        assert "test_operation started" in output, (
            f"Expected 'test_operation started' in log output, got: {output[:500]}"
        )

    def and_log_output_should_contain_completed_message(self):
        output = self.log_stream.getvalue()
        assert "test_operation completed" in output, (
            f"Expected 'test_operation completed' in log output, got: {output[:500]}"
        )

    def and_log_output_should_contain_duration(self):
        output = self.log_stream.getvalue()
        assert "duration_seconds" in output, f"Expected 'duration_seconds' in log output, got: {output[:500]}"

    def do_cleanup(self):
        reset_logging()


class Scenario2(vedro.Scenario):
    subject = "timed_operation_async logs failure on exception"

    def given_logging_configured_and_log_capture(self):
        reset_logging()
        configure_logging(LogLevel.DEBUG, LogFormat.JSON)
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        formatter = logging.getLogger().handlers[0].formatter
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

    async def when_timed_async_operation_fails(self):
        self.error_caught = False
        try:
            async with timed_operation_async("failing_op"):
                raise RuntimeError("Intentional failure")
        except RuntimeError:
            self.error_caught = True

    def then_error_should_have_been_caught(self):
        assert self.error_caught is True

    def and_log_output_should_contain_failed_message(self):
        output = self.log_stream.getvalue()
        assert "failing_op failed" in output, f"Expected 'failing_op failed' in log output, got: {output[:500]}"

    def and_log_output_should_contain_duration(self):
        output = self.log_stream.getvalue()
        assert "duration_seconds" in output, f"Expected 'duration_seconds' in log output, got: {output[:500]}"

    def do_cleanup(self):
        reset_logging()
