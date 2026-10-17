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
hotfix queue and migration scenarios against PostgreSQL 16 using `asyncpg`.
To repeat this check locally, set `GITLAB_QUEUE_TEST_POSTGRES_URL` to an isolated
PostgreSQL admin database whose disposable role has `CREATEDB`, then run:

```bash
uv run vedro run scenarios/core/hotfix_priority/ scenarios/core/database_migrations/ --verbose --fail-fast
```

Each context creates a uniquely named `gq_test_*` database, applies real Alembic
migrations, and drops only that database on exit. Restart scenarios reopen the
same database before cleanup. Without the variable these scenarios use temporary
SQLite files. Never point this verification setting at a production server.

This verifies queue ordering, webhook admission, notification/completion
recovery and schema upgrades. It does not establish general PostgreSQL support
for unrelated legacy SQLite SQL in retry storage, schema helpers or dashboard
statistics. The migration scenarios compare populated records across the
`c3d7f1a8b902`, `d4e5f6a7b8c9` and `e5f6a7b8c9d0` schemas, verify full reversal,
and check Alembic model consistency.
