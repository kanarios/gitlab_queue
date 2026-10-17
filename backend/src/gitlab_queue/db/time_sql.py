"""Instant comparisons for the application's legacy TEXT date columns."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.functions import FunctionElement

_CALENDAR_DATE = r"([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{8})"
_CLOCK = r"([01][0-9]|2[0-3])(:?[0-5][0-9](:?[0-5][0-9]([.,][0-9]+)?)?)?"
_PORTABLE_TIMESTAMP = rf"^{_CALENDAR_DATE}([Tt ]{_CLOCK}(Z|[+-]{_CLOCK})?)?$"


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
        # PostgreSQL also accepts relative words, infinities, BC years and
        # normalized 24:00/leap-second clocks, which Python's ISO reader rejects.
        # Do not turn those raw unknown values into scheduling/retention times.
        return (
            f"CASE WHEN ({column}) ~ '{_PORTABLE_TIMESTAMP}' "
            f"AND pg_input_is_valid({column}, 'timestamp with time zone') "
            f"THEN CAST(EXTRACT(EPOCH FROM CAST({column} AS TIMESTAMP WITH TIME ZONE)) AS DOUBLE PRECISION) END"
        )
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
    return epoch_sql(compiler.process(element.clauses, **kwargs), "postgresql")
