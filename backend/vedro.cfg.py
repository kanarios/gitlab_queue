"""Vedro configuration for GitLab Queue Bot tests."""

import vedro
import vedro.plugins.director.rich as rich_reporter


class Config(vedro.Config):
    """Vedro test framework configuration."""

    class Registry(vedro.Config.Registry):
        pass

    class Plugins(vedro.Config.Plugins):
        class RichReporter(rich_reporter.RichReporter):
            enabled = True
            show_scenario_spinner = True
