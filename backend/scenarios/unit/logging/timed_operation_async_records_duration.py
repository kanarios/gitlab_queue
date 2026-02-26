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
        """
        Configure global logging for tests and attach an in-memory stream handler to capture log output.

        This sets logging to DEBUG level with JSON formatting, creates a StringIO stream at self.log_stream, and adds a StreamHandler using the existing formatter so subsequent log records are written to the in-memory stream for inspection.
        """
        reset_logging()
        configure_logging(LogLevel.DEBUG, LogFormat.JSON)
        # Capture log output via a string stream handler
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        formatter = logging.getLogger().handlers[0].formatter
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

    async def when_timed_async_operation_completes(self):
        """
        Runs a timed asynchronous operation named "test_operation" with extra_key "test_val" that completes after a short delay to exercise logging of start, completion, and duration.
        """
        async with timed_operation_async("test_operation", extra_key="test_val"):
            await asyncio.sleep(0.05)  # 50ms

    def then_log_output_should_contain_started_message(self):
        """
        Asserts that the captured log output contains the "test_operation started" message.

        Raises an AssertionError if the expected started message is not present in the log stream.
        """
        output = self.log_stream.getvalue()
        assert "test_operation started" in output

    def and_log_output_should_contain_completed_message(self):
        output = self.log_stream.getvalue()
        assert "test_operation completed" in output

    def and_log_output_should_contain_duration(self):
        """
        Asserts that the captured log output contains the `duration_seconds` field.

        Checks the in-memory log stream and fails the test if `duration_seconds` is not present.
        """
        output = self.log_stream.getvalue()
        assert "duration_seconds" in output

    def do_cleanup(self):
        """
        Reset global logging configuration to its default state.

        This is intended for test cleanup to remove any handlers, formatters, or level changes applied during a scenario.
        """
        reset_logging()


class Scenario2(vedro.Scenario):
    subject = "timed_operation_async logs failure on exception"

    def given_logging_configured_and_log_capture(self):
        """
        Prepare logging for tests and attach an in-memory stream handler to capture emitted log records.

        This resets existing logging configuration, sets logging level to DEBUG with JSON formatting, creates an in-memory StringIO at `self.log_stream`, and adds a StreamHandler that uses the existing formatter so subsequent logs produced during the test are written to `self.log_stream`.
        """
        reset_logging()
        configure_logging(LogLevel.DEBUG, LogFormat.JSON)
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        formatter = logging.getLogger().handlers[0].formatter
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

    async def when_timed_async_operation_fails(self):
        """
        Executes a timed asynchronous operation that intentionally raises a RuntimeError and records that the error was caught.

        Attempts an async timed operation named "failing_op"; when a RuntimeError is raised it is caught and self.error_caught is set to True.
        """
        self.error_caught = False
        try:
            async with timed_operation_async("failing_op"):
                raise RuntimeError("Intentional failure")
        except RuntimeError:
            self.error_caught = True

    def then_error_should_have_been_caught(self):
        """
        Asserts that the expected exception was caught during the scenario.

        Raises:
            AssertionError: If the exception was not caught (i.e., `self.error_caught` is not True).
        """
        assert self.error_caught is True

    def and_log_output_should_contain_failed_message(self):
        """
        Asserts that the captured log output contains the failure message for the failing operation.

        Checks the in-memory log stream for the substring "failing_op failed" and fails the test if it is not present.
        """
        output = self.log_stream.getvalue()
        assert "failing_op failed" in output

    def and_log_output_should_contain_duration(self):
        """
        Asserts that the captured log output contains the `duration_seconds` field.

        Checks the in-memory log stream and fails the test if `duration_seconds` is not present.
        """
        output = self.log_stream.getvalue()
        assert "duration_seconds" in output

    def do_cleanup(self):
        """
        Reset global logging configuration to its default state.

        This is intended for test cleanup to remove any handlers, formatters, or level changes applied during a scenario.
        """
        reset_logging()
