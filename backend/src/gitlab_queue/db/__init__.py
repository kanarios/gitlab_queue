"""Database module for GitLab Merge Queue Bot.

Provides async SQLite database access with SQLAlchemy, including:
- Async engine with WAL mode for concurrent reads
- Session factory for database operations
- Transaction helper for atomic operations
- Health check endpoints
- Graceful shutdown handling
- Custom exception hierarchy
- ORM models for Alembic migrations
- Repository pattern for data access

Example:
    >>> from gitlab_queue.db import Database
    >>> async with Database("sqlite+aiosqlite:///data/queue.db") as db:
    ...     async with db.session() as session:
    ...         # Perform database operations
    ...         await session.commit()

    # For atomic operations:
    >>> async with db.transaction() as session:
    ...     # Automatic commit on success, rollback on exception
    ...     session.add(user)

    # Using repositories with Unit of Work:
    >>> from gitlab_queue.db import UnitOfWork
    >>> async with UnitOfWork(db, auto_commit=True) as uow:
    ...     mr = await uow.merge_requests.get_by_iid(42)
    ...     await uow.merge_requests.complete_mr(42, "merged")
"""

from gitlab_queue.db.database import (
    Database,
    DatabaseAlreadyInitializedError,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    DatabaseNotInitializedError,
    DatabaseStatus,
    create_database,
)
from gitlab_queue.db.migrations import (
    ensure_migrations,
    get_current_revision,
    get_pending_migrations,
    run_migrations,
)
from gitlab_queue.db.models import (
    AnalyticsDailyModel,
    AnalyticsHourlyModel,
    Base,
    MergeRequestHistoryModel,
    MergeRequestModel,
    WebhookDLQModel,
    WebhookRetryModel,
)
from gitlab_queue.db.repositories import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    AnalyticsRepository,
    CompleteMRResult,
    DashboardMetrics,
    DuplicateRecordError,
    HistoryRepository,
    MergeRequestNotFoundError,
    MergeRequestRepository,
    ModelConverter,
    PaginatedResult,
    PeriodStats,
    RepositoryError,
    UnitOfWork,
)

__all__: list[str] = [
    # Constants
    "ACTIVE_STATES",
    "TERMINAL_STATES",
    # ORM Models
    "AnalyticsDailyModel",
    "AnalyticsHourlyModel",
    # Repositories
    "AnalyticsRepository",
    # Database core
    "Base",
    # Data classes
    "CompleteMRResult",
    "DashboardMetrics",
    "Database",
    "DatabaseAlreadyInitializedError",
    "DatabaseConfigurationError",
    "DatabaseConnectionError",
    "DatabaseError",
    "DatabaseNotInitializedError",
    "DatabaseStatus",
    # Exceptions
    "DuplicateRecordError",
    "HistoryRepository",
    "MergeRequestHistoryModel",
    "MergeRequestModel",
    "MergeRequestNotFoundError",
    "MergeRequestRepository",
    # Converters
    "ModelConverter",
    "PaginatedResult",
    "PeriodStats",
    "RepositoryError",
    # Unit of Work
    "UnitOfWork",
    "WebhookDLQModel",
    "WebhookRetryModel",
    "create_database",
    # Migrations
    "ensure_migrations",
    "get_current_revision",
    "get_pending_migrations",
    "run_migrations",
]
