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
queue/history `CURRENT_TIMESTAMP` values using one captured migration instant.
Retry/DLQ raw dates are preserved instead: unknown receipt/move dates are returned
as JSON `null`, and an unknown retry due date is not automatically dispatched.
Unknown DLQ age is not automatically expired. A known due date remains actionable
even when its receipt date is unknown. Valid dates and offsets remain unchanged.
PostgreSQL comparison accepts portable calendar ISO/SQL date syntax, not its
relative/reserved words, infinities, BC years or normalized 24:00/leap-second
clocks. Those raw values remain unknown and cannot block a valid retry batch.
SQLite identity high-water marks survive rebuilds, including deleted highest IDs.

### Automatic retry/DLQ rollback archive

Use the new checkout for both directions of `a7b8c9d0e1f2` ↔ `f6a7b8c9d0e1`.
The backward-compatible hooks in a7 work even when a7 was already installed;
no visit to a new revision is required. Older checkouts do not contain these hooks.

Before migration, stop webhook intake, retry processors, scheduled jobs and
administrative writes. The common file/advisory gate serializes raw Alembic and
programmatic migrations; it does **not** serialize application writers. Migration
copy/delete, batch DDL, restore/acknowledgment and the revision marker share a real
database transaction, including an explicit physical SQLite transaction.
Administrative DDL outside that gate must also remain stopped during migration.

Downgrade moves incompatible retry/DLQ rows to three same-database typed tables:
`gq_retry_rollback_manifest_v1`, `gq_retry_rollback_rows_v1` and
`gq_dlq_rollback_rows_v1`. Unknown/unparseable dates are preserved as their exact
raw TEXT/NULL values, together with every original column, identity, project,
payload string, attempt count, limit, due time and error. These rows are absent
from the old runtime's live retry/DLQ tables, so they cannot be delivered there.
No requeue reset or invented date is used.
One permanent verified owner/format marker remains after batch acknowledgment.
Correctly-shaped empty tables without that marker are refused, never adopted.

Upgrade first captures incompatible new writes from the old runtime **before**
date repair, then restores all verified archive rows **after** schema repair.
Already completed historical a7 repairs cannot be reconstructed retroactively.
The versioned migration helper is independent of future application models.
Archive tables are excluded precisely from model autogeneration and are outside
managed drops and retention. They survive downgrade to `base`, but only captured
incompatible retry/DLQ rows are protected: compatible live rows and other managed
tables are still dropped by full reversal. This archive is not a full backup.

Restore verifies format/ownership, source schema, raw types, counts and digests
before writes. Batch digests bind the raw rows to all manifest context, including
both sequence high-water marks. A pending batch from an earlier helper with only
raw-row digests is refused intact rather than trusted or automatically signed;
the permanent empty owner marker remains compatible. Reconcile such an unbound
pending archive against a verified backup before attempting the return upgrade.
Any occupied table-global ID, including identical data or a row
from another project, stops the entire restoration without overwriting/remapping
or acknowledging the archive. Unsupported archive shapes, user triggers and
incoming foreign references on either live table or any of the three archive
tables also stop before mutations, including archive acknowledgment. PostgreSQL
incoming references are checked across schemas. Every row is verified after
insertion before any
archive acknowledgment. Sequences never rewind and include archived/deleted
high-water marks; PostgreSQL sequence advances can leave harmless gaps after a
rolled-back migration. Interrupted transactions can be retried after reopening.
SQLite REFERENCES names follow its ASCII case-insensitive identifier rules;
Unicode lookalikes remain distinct. PostgreSQL retains quoted-name/OID semantics.

The five mutation targets must resolve to the same ordinary permanent tables
that are inspected: SQLite `main`, or PostgreSQL's connection inspection
namespace. Same-name TEMP tables/views are refused on the actual supplied
connection, including when the permanent archive has not been created yet.
SQLite checks both main and TEMP trigger catalogs. PostgreSQL also refuses
rewrite rules and inheritance in either direction; temporary, unlogged, foreign,
view and partition targets are outside the supported profile. Durable identities
are resolved again after intentional migration DDL before restore/ACK, so a
legitimate rebuild need not retain its old OID or SQLite root page.

Operational order:

1. Stop all runtime writers and retain a verified full database backup. Use the
   checkout containing these updated a7 hooks for the migration commands.
2. With the intended database configured, run `uv run alembic downgrade
   f6a7b8c9d0e1`. Verify the revision and archive counts before starting an
   application version compatible with f6. Do not let an older copy of a7
   automatically perform the return upgrade.
3. For the return upgrade, stop writers again and use the updated checkout:
   `uv run alembic upgrade head` (or its normal startup migration runner).
4. If preflight reports an identity/schema/integrity conflict, leave writers
   stopped. The transaction preserves live rows and the archive. Reconcile the
   conflict explicitly against the retained backup; do not force acknowledgment,
   ignore duplicate IDs or fabricate dates. Rerun the migration after resolution.
5. Verify a7 is installed, restored rows match their original data and any
   existing archive tables have no pending batch/raw rows (the owner marker
   remains), then resume the new runtime.

The migration scenarios cover populated previous revisions and legacy schema
markers, concurrent startup, full reversal and Alembic model consistency. Fresh
schema helpers create the complete model schema; existing tables are upgraded
through migrations.
