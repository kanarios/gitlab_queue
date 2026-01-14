"""Unit tests for Settings validation."""

import vedro

from gitlab_queue.config import (
    ConfigurationError,
    LogFormat,
    LogLevel,
    Secret,
    Settings,
    _validate_settings,
)


def create_valid_settings(**overrides) -> Settings:
    """Create a valid Settings object with optional overrides."""
    defaults = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": Secret("glpat-test-token"),
        "gitlab_project_id": 12345,
        "target_branch": "master",
        "queue_label": "merge_queue",
        "hotfix_label": "hotfix",
        "poll_interval_seconds": 30,
        "pipeline_timeout_seconds": 7200,
        "rebase_timeout_seconds": 300,
        "pipeline_retry_count": 1,
        "api_max_retries": 5,
        "webhook_retry_max_attempts": 3,
        "webhook_retry_base_delay_seconds": 30,
        "webhook_retry_max_delay_seconds": 300,
        "webhook_retry_poll_interval_seconds": 10,
        "webhook_dlq_retention_days": 30,
        "database_url": "sqlite+aiosqlite:///data/queue.db",
        "oauth_client_id": None,
        "oauth_client_secret": None,
        "oauth_redirect_uri": None,
        "jwt_secret": Secret("a" * 64),
        "jwt_expiration_hours": 24,
        "webhook_enabled": True,
        "webhook_host": "127.0.0.1",
        "webhook_port": 8080,
        "webhook_secret": Secret("webhook-secret"),
        "dashboard_enabled": True,
        "cors_origins": ["http://localhost:5173"],
        "log_level": LogLevel.INFO,
        "log_format": LogFormat.JSON,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class Scenario(vedro.Scenario):
    subject = "validate correct settings passes"

    def given_valid_settings(self):
        self.settings = create_valid_settings()

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_validation_should_pass(self):
        assert self.error is None


class Scenario__invalid_gitlab_url(vedro.Scenario):
    subject = "validation fails for invalid gitlab URL"

    def given_settings_with_invalid_url(self):
        self.settings = create_valid_settings(gitlab_url="ftp://gitlab.com")

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "gitlab_url" in str(self.error)
        assert "http" in str(self.error)


class Scenario__negative_project_id(vedro.Scenario):
    subject = "validation fails for negative project ID"

    def given_settings_with_negative_project_id(self):
        self.settings = create_valid_settings(gitlab_project_id=-1)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "gitlab_project_id" in str(self.error)
        assert "positive" in str(self.error)


class Scenario__zero_poll_interval(vedro.Scenario):
    subject = "validation fails for zero poll interval"

    def given_settings_with_zero_poll_interval(self):
        self.settings = create_valid_settings(poll_interval_seconds=0)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "poll_interval_seconds" in str(self.error)


class Scenario__negative_pipeline_timeout(vedro.Scenario):
    subject = "validation fails for negative pipeline timeout"

    def given_settings_with_negative_timeout(self):
        self.settings = create_valid_settings(pipeline_timeout_seconds=-100)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "pipeline_timeout_seconds" in str(self.error)


class Scenario__negative_retry_count(vedro.Scenario):
    subject = "validation fails for negative retry count"

    def given_settings_with_negative_retry(self):
        self.settings = create_valid_settings(pipeline_retry_count=-1)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "pipeline_retry_count" in str(self.error)


class Scenario__invalid_webhook_port(vedro.Scenario):
    subject = "validation fails for invalid webhook port"

    def given_settings_with_invalid_port(self):
        self.settings = create_valid_settings(webhook_port=70000)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "webhook_port" in str(self.error)
        assert "65535" in str(self.error)


class Scenario__webhook_enabled_without_secret(vedro.Scenario):
    subject = "validation fails when webhook enabled without secret"

    def given_settings_without_webhook_secret(self):
        self.settings = create_valid_settings(
            webhook_enabled=True,
            webhook_secret=None,
        )

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "webhook_secret" in str(self.error)


class Scenario__webhook_disabled_without_secret_ok(vedro.Scenario):
    subject = "validation passes when webhook disabled without secret"

    def given_settings_with_webhook_disabled(self):
        self.settings = create_valid_settings(
            webhook_enabled=False,
            webhook_secret=None,
        )

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_validation_should_pass(self):
        assert self.error is None


class Scenario__jwt_secret_too_short(vedro.Scenario):
    subject = "validation fails for short JWT secret"

    def given_settings_with_short_jwt_secret(self):
        self.settings = create_valid_settings(jwt_secret=Secret("short"))

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "jwt_secret" in str(self.error)
        assert "64" in str(self.error)


class Scenario__wildcard_cors_origin(vedro.Scenario):
    subject = "validation fails for wildcard CORS origin"

    def given_settings_with_wildcard_cors(self):
        self.settings = create_valid_settings(cors_origins=["*"])

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "Wildcard" in str(self.error) or "CORS" in str(self.error)


class Scenario__invalid_cors_origin_protocol(vedro.Scenario):
    subject = "validation fails for invalid CORS origin protocol"

    def given_settings_with_invalid_cors_origin(self):
        self.settings = create_valid_settings(cors_origins=["ftp://example.com"])

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "CORS" in str(self.error) or "http" in str(self.error)


class Scenario__webhook_retry_delays_invalid(vedro.Scenario):
    subject = "validation fails when max delay less than base delay"

    def given_settings_with_invalid_delays(self):
        self.settings = create_valid_settings(
            webhook_retry_base_delay_seconds=300,
            webhook_retry_max_delay_seconds=100,
        )

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "webhook_retry_max_delay_seconds" in str(self.error)


class Scenario__multiple_validation_errors(vedro.Scenario):
    subject = "validation collects multiple errors"

    def given_settings_with_multiple_issues(self):
        self.settings = create_valid_settings(
            gitlab_project_id=-1,
            poll_interval_seconds=0,
            webhook_port=99999,
        )

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_report_all_errors(self):
        assert self.error is not None
        error_msg = str(self.error)
        assert "gitlab_project_id" in error_msg
        assert "poll_interval_seconds" in error_msg
        assert "webhook_port" in error_msg
