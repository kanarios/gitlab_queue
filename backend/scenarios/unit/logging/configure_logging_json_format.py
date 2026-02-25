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
        reset_logging()

    def when_logging_is_configured_with_json_format(self):
        configure_logging(LogLevel.DEBUG, LogFormat.JSON)

    def then_root_logger_should_have_handler(self):
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

    def and_root_logger_level_should_match(self):
        root_logger = logging.getLogger()
        assert root_logger.getEffectiveLevel() == logging.DEBUG

    def and_structlog_should_be_configured(self):
        # Verify structlog can create loggers without error
        log = structlog.stdlib.get_logger("test_json_config")
        assert log is not None

    def and_app_logger_level_should_be_set(self):
        app_logger = logging.getLogger("gitlab_queue")
        assert app_logger.getEffectiveLevel() == logging.DEBUG

    def and_httpx_logger_should_be_suppressed(self):
        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.getEffectiveLevel() >= logging.WARNING

    def do_cleanup(self):
        reset_logging()


class Scenario2(vedro.Scenario):
    subject = "configure_logging is idempotent"

    def given_logging_is_reset(self):
        reset_logging()

    def when_logging_is_configured_twice(self):
        configure_logging(LogLevel.INFO, LogFormat.JSON)
        configure_logging(LogLevel.INFO, LogFormat.JSON)

    def then_root_logger_should_have_exactly_one_handler(self):
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1

    def do_cleanup(self):
        reset_logging()
