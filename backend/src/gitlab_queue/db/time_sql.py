"""Instant comparisons for the application's legacy TEXT date columns."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.functions import FunctionElement


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_epoch(value: str | None) -> float | None:
    """Parse supported ISO/SQL timestamps without SQLite's millisecond rounding."""
    if value is None:
        return None
    try:
        instant = datetime.fromisoformat(value)
    except ValueError:
        return None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    return instant.timestamp()


def epoch_sql(column: str, backend: str) -> str:
    """Return Unix seconds for a trusted SQL column/expression, including offsets."""
    if backend == "postgresql":
        return f"CAST(EXTRACT(EPOCH FROM CAST({column} AS TIMESTAMP WITH TIME ZONE)) AS DOUBLE PRECISION)"
    return f"queue_epoch({column})"


class TimestampEpoch(FunctionElement[float]):
    """Dialect-compiled equivalent of epoch_sql for ORM timestamp predicates."""

    type = Float()
    inherit_cache = True


@compiles(TimestampEpoch)
def _sqlite_epoch(element: TimestampEpoch, compiler: SQLCompiler, **kwargs: Any) -> str:
    return f"queue_epoch({compiler.process(element.clauses, **kwargs)})"


@compiles(TimestampEpoch, "postgresql")
def _postgres_epoch(element: TimestampEpoch, compiler: SQLCompiler, **kwargs: Any) -> str:
    return f"CAST(EXTRACT(EPOCH FROM CAST({compiler.process(element.clauses, **kwargs)} AS TIMESTAMP WITH TIME ZONE)) AS DOUBLE PRECISION)"
