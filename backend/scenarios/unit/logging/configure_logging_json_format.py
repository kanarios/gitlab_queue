"""Test that configure_logging with JSON format sets up structlog correctly."""

from __future__ import annotations

import logging

import structlog
import vedro

from gitlab_queue.config import LogFormat, LogLevel
from gitlab_queue.utils.logging import configure_logging, reset_logging


class Scenario(vedro.Scenario):
    subject = "configure_logging with JSON format sets up structlog correctly"

    def given_logging_is_reset(self):
        """
        Reset global logging and structlog configuration to a clean default state for test isolation.
        
        Ensures subsequent logging configuration in the scenario starts from a known baseline.
        """
        reset_logging()

    def when_logging_is_configured_with_json_format(self):
        """
        Configure global logging to DEBUG level with JSON-formatted output.
        """
        configure_logging(LogLevel.DEBUG, LogFormat.JSON)

    def then_root_logger_should_have_handler(self):
        """
        Asserts that the root logger has at least one handler configured.
        
        Raises:
            AssertionError: If the root logger has no handlers.
        """
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

    def and_root_logger_level_should_match(self):
        """
        Asserts that the root logger's effective logging level is DEBUG.
        
        Raises:
            AssertionError: If the root logger's effective level is not logging.DEBUG.
        """
        root_logger = logging.getLogger()
        assert root_logger.getEffectiveLevel() == logging.DEBUG

    def and_structlog_should_be_configured(self):
        # Verify structlog can create loggers without error
        """
        Asserts that structlog is configured and can produce a stdlib logger.
        
        Obtains a structlog stdlib logger named "test_json_config" and fails the test if the logger cannot be created.
        """
        log = structlog.stdlib.get_logger("test_json_config")
        assert log is not None

    def and_app_logger_level_should_be_set(self):
        """
        Asserts that the logger named "gitlab_queue" has an effective logging level of DEBUG.
        
        Raises:
            AssertionError: If the logger's effective level is not DEBUG.
        """
        app_logger = logging.getLogger("gitlab_queue")
        assert app_logger.getEffectiveLevel() == logging.DEBUG

    def and_httpx_logger_should_be_suppressed(self):
        """
        Asserts that the 'httpx' logger's effective logging level is at least WARNING.
        
        This ensures noisy httpx output is suppressed during tests.
        """
        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.getEffectiveLevel() >= logging.WARNING

    def do_cleanup(self):
        """
        Restore the process-wide logging configuration to its default state by calling reset_logging().
        """
        reset_logging()


class Scenario2(vedro.Scenario):
    subject = "configure_logging is idempotent"

    def given_logging_is_reset(self):
        """
        Reset global logging and structlog configuration to a clean default state for test isolation.
        
        Ensures subsequent logging configuration in the scenario starts from a known baseline.
        """
        reset_logging()

    def when_logging_is_configured_twice(self):
        """
        Invoke the logging configuration twice with INFO level and JSON format to exercise idempotency.
        
        This step calls the logging setup two times to verify that repeated configuration does not add duplicate handlers or otherwise alter the intended logging state.
        """
        configure_logging(LogLevel.INFO, LogFormat.JSON)
        configure_logging(LogLevel.INFO, LogFormat.JSON)

    def then_root_logger_should_have_exactly_one_handler(self):
        """
        Asserts that the root logger has exactly one handler.
        
        Raises:
            AssertionError: If the root logger does not have exactly one handler.
        """
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1

    def do_cleanup(self):
        """
        Restore the process-wide logging configuration to its default state by calling reset_logging().
        """
        reset_logging()
