# GitLab Merge Queue Bot - Backend

Python backend for GitLab Merge Queue Bot.

## Development

```bash
# Install dependencies
uv sync

# Run linting
uv run ruff check .

# Run type checking
uv run mypy src/

# Run tests
uv run vedro run
```

### PostgreSQL queue verification

SQLite remains the default storage backend. The migration job also runs the
queue, retry, repository and migration scenarios against PostgreSQL 16 using `asyncpg`.
To repeat this check locally, set `GITLAB_QUEUE_TEST_POSTGRES_URL` to an isolated
PostgreSQL admin database whose disposable role has `CREATEDB`, then run:

```bash
uv run vedro run scenarios/core/hotfix_priority/ scenarios/core/database_migrations/ scenarios/core/storage_backends/ scenarios/integration/retry_manager/ scenarios/integration/repositories/ --verbose --fail-fast
```

Each context creates a uniquely named `gq_test_*` database, applies real Alembic
migrations, and drops only that database on exit. Restart scenarios reopen the
same database before cleanup. Without the variable these scenarios use temporary
SQLite files. Never point this verification setting at a production server.

The real database scenarios cover queue ordering and actual merge workflows,
webhook admission, notification/completion recovery, retry backoff and
acknowledgment, concurrent DLQ transfers, schema helpers, legacy stamping,
dashboard/analytics APIs, retention and scheduled maintenance. Pure model
conversion scenarios in the repository selector do not open a database. These
checks verify the exercised local/CI paths; deployment and production load
validation are separate.

Retry dispatch remains at least once. Concurrent delivery can call the handler
again; effective queue admission is idempotent, stale acknowledgment is benign,
and retry/DLQ transfers and attempt increments are atomic. No distributed
exactly-once delivery guarantee is introduced.

Timestamp comparisons accept ISO timestamps (including offsets and `Z`) and
legacy SQL dates with a space. Naive values represent UTC. Every PostgreSQL
connection uses UTC; SQLite uses a deterministic parser on every physical
connection, preserving microseconds at exact due/retention boundaries.
Migration `a7b8c9d0e1f2` fixes four timestamp defaults and repairs stored literal
`CURRENT_TIMESTAMP` values using one captured migration instant. Their original
age is unknown, so the repair conservatively retains them as recent. Missing DLQ
move dates use that same repair instant; valid dates and optional creation NULLs
remain unchanged. An unknown retry receipt date remains `null` when moved to DLQ
and returned by the API. Requeue records a new receipt date. Downgrade to the old
non-nullable original-date schema refuses before changes while unknown DLQ
original dates remain; explicitly requeue or delete those entries first.
SQLite identity high-water marks survive
rebuilds, including when the highest issued row has been deleted.

The migration scenarios cover populated previous revisions and legacy schema
markers, concurrent startup, full reversal and Alembic model consistency. Fresh
schema helpers create the complete model schema; existing tables are upgraded
through migrations.
