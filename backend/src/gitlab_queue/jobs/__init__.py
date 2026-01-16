"""Scheduled Jobs for GitLab Merge Queue Bot.

Provides background job processors for:
- Analytics data collection (hourly snapshots, daily aggregation)
- Data retention (cleanup old records)

Example:
    >>> from gitlab_queue.jobs import create_analytics_processor
    >>> processor = create_analytics_processor(database, settings)
    >>> await processor.run()
"""

from gitlab_queue.jobs.analytics import (
    AnalyticsJobProcessor,
    create_analytics_processor,
)

__all__: list[str] = [
    "AnalyticsJobProcessor",
    "create_analytics_processor",
]
