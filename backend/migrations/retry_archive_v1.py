"""Frozen, raw storage contract for the a7/f6 retry rollback boundary.

This module deliberately depends only on SQLAlchemy and the standard library.
Archive tables are not application models and must outlive managed table drops.
"""

import hashlib
import json
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa

HEAD = "a7b8c9d0e1f2"
PREVIOUS = "f6a7b8c9d0e1"
OWNER = "gitlab_queue.retry_rollback"
CONTROL_ID = "__contract_v1__"
MANIFEST = "gq_retry_rollback_manifest_v1"
RETRY_ARCHIVE = "gq_retry_rollback_rows_v1"
DLQ_ARCHIVE = "gq_dlq_rollback_rows_v1"
ARCHIVE_NAMES = (MANIFEST, RETRY_ARCHIVE, DLQ_ARCHIVE)
SOURCES = ("webhook_retry_queue", "webhook_dlq")
RAW_COLUMNS = {
    SOURCES[0]: (
        ("id", "integer", False),
        ("project_id", "integer", False),
        ("event_type", "text", False),
        ("payload", "text", False),
        ("attempt_count", "integer", False),
        ("max_attempts", "integer", False),
        ("next_attempt_at", "text", False),
        ("last_error", "text", True),
        ("created_at", "text", True),
    ),
    SOURCES[1]: (
        ("id", "integer", False),
        ("project_id", "integer", False),
        ("event_type", "text", False),
        ("payload", "text", False),
        ("attempt_count", "integer", False),
        ("last_error", "text", False),
        ("original_created_at", "text", True),
        ("moved_to_dlq_at", "text", True),
    ),
}
DATES = {SOURCES[0]: ("next_attempt_at", "created_at"), SOURCES[1]: ("original_created_at", "moved_to_dlq_at")}


def _metadata():
    metadata = sa.MetaData()
    sa.Table(
        MANIFEST,
        metadata,
        sa.Column("archive_id", sa.Text, primary_key=True),
        sa.Column("owner", sa.Text, nullable=False),
        sa.Column("format_version", sa.Integer, nullable=False),
        sa.Column("source_revision", sa.Text, nullable=False),
        sa.Column("target_revision", sa.Text, nullable=False),
        sa.Column("source_schema", sa.Text, nullable=False),
        *(
            sa.Column(f"{kind}_{field}", datatype, nullable=False)
            for kind in ("retry", "dlq")
            for field, datatype in (("count", sa.Integer), ("digest", sa.Text), ("high_water", sa.BigInteger))
        ),
    )
    for source, archive in zip(SOURCES, (RETRY_ARCHIVE, DLQ_ARCHIVE), strict=True):
        sa.Table(
            archive,
            metadata,
            sa.Column("archive_id", sa.Text, primary_key=True),
            *(
                sa.Column(
                    name, sa.Integer if kind == "integer" else sa.Text, primary_key=name == "id", nullable=nullable
                )
                for name, kind, nullable in RAW_COLUMNS[source]
            ),
            sa.Column("row_digest", sa.Text, nullable=False),
        )
    return metadata


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _digest(source, rows):
    columns = [column[0] for column in RAW_COLUMNS[source]]
    raw = [[row[column] for column in columns] for row in sorted(rows, key=lambda row: row["id"])]
    return hashlib.sha256(_json(raw).encode("utf-8")).hexdigest()


def _batch_digest(manifest, source, rows):
    # Bind both high-water marks and all other manifest context to the raw data.
    # The permanent empty owner marker keeps its original v1 representation;
    # pending batches without this binding are refused, never silently adopted.
    context = {key: manifest[key] for key in sorted(manifest) if key not in ("retry_digest", "dlq_digest")}
    raw = _json([context, source, _digest(source, rows)])
    return "bound-sha256-v1:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _schema(revision):
    result = {source: [list(column) for column in columns] for source, columns in RAW_COLUMNS.items()}
    if revision == PREVIOUS:
        result[SOURCES[1]][6][2] = False
    return result


def _control_manifest():
    """Permanent ownership proof, retained even when every batch is ACKed."""
    manifest = {
        "archive_id": CONTROL_ID,
        "owner": OWNER,
        "format_version": 1,
        "source_revision": HEAD,
        "target_revision": PREVIOUS,
        "source_schema": _json(_schema(HEAD)),
    }
    for kind, source in zip(("retry", "dlq"), SOURCES, strict=True):
        manifest.update({f"{kind}_count": 0, f"{kind}_digest": _digest(source, []), f"{kind}_high_water": 0})
    return manifest


def _check_shape(bind, name, columns, primary):
    inspector = sa.inspect(bind)
    actual = inspector.get_columns(name)
    expected = list(columns)
    if {column["name"] for column in actual} != {column[0] for column in expected}:
        raise RuntimeError(f"Rollback archive refuses unexpected columns in {name}")
    by_name = {column["name"]: column for column in actual}
    for column_name, kind, nullable in expected:
        actual_column = by_name[column_name]
        datatype = sa.Integer if kind == "integer" else sa.Text
        if not isinstance(actual_column["type"], datatype) or actual_column["nullable"] != nullable:
            raise RuntimeError(f"Rollback archive refuses unexpected type/nullability in {name}")
    if inspector.get_pk_constraint(name)["constrained_columns"] != list(primary):
        raise RuntimeError(f"Rollback archive refuses unexpected primary key in {name}")
    if inspector.get_foreign_keys(name):
        raise RuntimeError(f"Rollback archive refuses foreign keys in {name}")


def _check_relations(bind):
    """Bind the five inspected durable tables to actual DML name resolution."""
    targets = {f"target{index}": name for index, name in enumerate((*SOURCES, *ARCHIVE_NAMES))}
    if bind.dialect.name == "sqlite":
        shadows = (
            "SELECT name FROM temp.sqlite_master WHERE type IN ('table', 'view') AND lower(name) IN "
            f"({', '.join(':' + key for key in targets)})"
        )
        if bind.execute(sa.text(shadows), targets).first():
            raise RuntimeError("Rollback archive refuses TEMP shadows of persistent relations")
        for name in targets.values():
            relation = (
                bind.execute(
                    sa.text(
                        "SELECT name, type, sql FROM main.sqlite_master WHERE type IN ('table', 'view') AND lower(name) = :name"
                    ),
                    {"name": name},
                )
                .mappings()
                .one_or_none()
            )
            if relation is None and name in ARCHIVE_NAMES:
                continue
            if (
                relation is None
                or relation["name"] != name
                or relation["type"] != "table"
                or not relation["sql"]
                or relation["sql"].upper().startswith("CREATE VIRTUAL TABLE")
            ):
                raise RuntimeError("Rollback archive requires ordinary persistent relations in main")
        return targets
    schema = sa.inspect(bind).default_schema_name
    if (
        not schema
        or schema.startswith("pg_temp_")
        or bind.execute(sa.text("SELECT current_schema()")).scalar_one() != schema
    ):
        raise RuntimeError("Rollback archive refuses changed persistent relation namespace")
    identities = {}
    for key, name in targets.items():
        durable = (
            bind.execute(
                sa.text(
                    "SELECT c.oid, c.relkind::text AS relkind, c.relpersistence::text AS relpersistence "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = :schema AND c.relname = :name"
                ),
                {"schema": schema, "name": name},
            )
            .mappings()
            .one_or_none()
        )
        effective = bind.execute(sa.text("SELECT to_regclass(:name)::oid"), {"name": name}).scalar_one()
        if durable is None and effective is None and name in ARCHIVE_NAMES:
            identities[key] = None
            continue
        if (
            durable is None
            or durable["relkind"] != "r"
            or durable["relpersistence"] != "p"
            or durable["oid"] != effective
        ):
            raise RuntimeError("Rollback archive requires matching ordinary persistent relation identities")
        identities[key] = durable["oid"]
    placeholders = ", ".join(":" + key for key in identities)
    inheritance = f"SELECT 1 FROM pg_inherits WHERE inhparent IN ({placeholders}) OR inhrelid IN ({placeholders})"
    if bind.execute(sa.text(inheritance), identities).first():
        raise RuntimeError("Rollback archive refuses inheritance of persistent relations")
    return identities


def _check_mutation_safety(bind):
    targets = _check_relations(bind)
    if bind.dialect.name == "sqlite":
        trigger_sql = (
            "SELECT name FROM (SELECT name, tbl_name FROM main.sqlite_master WHERE type = 'trigger' "
            "UNION ALL SELECT name, tbl_name FROM temp.sqlite_master WHERE type = 'trigger') "
            "WHERE lower(tbl_name) IN "
            f"({', '.join(':' + key for key in targets)})"
        )
    else:
        trigger_sql = (
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN "
            f"({', '.join(':' + key for key in targets)})"
        )
    if bind.execute(sa.text(trigger_sql), targets).first():
        raise RuntimeError("Rollback archive refuses user triggers on mutation targets")
    if bind.dialect.name == "postgresql":
        rules_sql = f"SELECT rulename FROM pg_rewrite WHERE ev_class IN ({', '.join(':' + key for key in targets)})"
        if bind.execute(sa.text(rules_sql), targets).first():
            raise RuntimeError("Rollback archive refuses rewrite rules on mutation targets")
    if bind.dialect.name == "sqlite":
        inspector = sa.inspect(bind)
        referenced = any(
            key["referred_table"] in targets.values()
            for name in inspector.get_table_names()
            for key in inspector.get_foreign_keys(name)
        )
    else:
        # pg_constraint sees incoming ownership even from another schema. The
        # archive ACK is a deletion boundary just like source capture.
        references_sql = (
            "SELECT conname FROM pg_constraint WHERE contype = 'f' AND confrelid IN "
            f"({', '.join(':' + key for key in targets)})"
        )
        referenced = bind.execute(sa.text(references_sql), targets).first() is not None
    if referenced:
        raise RuntimeError("Rollback archive refuses references to mutation targets")


def _check_sources(bind, revision):
    _check_mutation_safety(bind)
    schema = _schema(revision)
    if revision == PREVIOUS:
        # Canonical create_all helpers can be legacy-stamped through f6 while
        # already having a7's nullable original-date column. This exact known
        # variant is supported; all other column/type/nullability checks remain.
        original = next(
            column for column in sa.inspect(bind).get_columns(SOURCES[1]) if column["name"] == "original_created_at"
        )
        schema[SOURCES[1]][6][2] = original["nullable"]
    for source, columns in schema.items():
        _check_shape(bind, source, columns, ("id",))
    return schema


def _archive_tables(bind, *, create=False):
    existing = set(sa.inspect(bind).get_table_names()) & set(ARCHIVE_NAMES)
    if existing and existing != set(ARCHIVE_NAMES):
        raise RuntimeError("Rollback archive is incomplete; no data was adopted")
    metadata = _metadata()
    if not existing:
        if not create:
            return None
        metadata.create_all(bind)
        bind.execute(metadata.tables[MANIFEST].insert(), _control_manifest())
    for table in metadata.tables.values():
        columns = [
            (column.name, "integer" if isinstance(column.type, sa.Integer) else "text", column.nullable)
            for column in table.columns
        ]
        _check_shape(bind, table.name, columns, tuple(column.name for column in table.primary_key))
        inspector = sa.inspect(bind)
        if (
            inspector.get_unique_constraints(table.name)
            or inspector.get_check_constraints(table.name)
            or inspector.get_indexes(table.name)
        ):
            raise RuntimeError("Rollback archive refuses unexpected constraints/indexes")
    control = (
        bind.execute(sa.select(metadata.tables[MANIFEST]).where(metadata.tables[MANIFEST].c.archive_id == CONTROL_ID))
        .mappings()
        .one_or_none()
    )
    if dict(control or {}) != _control_manifest():
        raise RuntimeError("Rollback archive has no valid durable owner/format marker")
    return metadata.tables


def _unknown(value):
    if value is None or value == "CURRENT_TIMESTAMP":
        return True
    try:
        datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return True
    return False


def _validate_rows(source, rows, columns=None):
    for row in rows:
        for name, kind, nullable in columns or RAW_COLUMNS[source]:
            value = row[name]
            if value is None and nullable:
                continue
            if type(value) is not (int if kind == "integer" else str):
                raise RuntimeError("Rollback archive contains incompatible raw values")
        for name in DATES[source]:
            _unknown(row[name])


def _read_archive(bind, tables):
    if tables is None:
        return []
    manifests = list(
        bind.execute(sa.select(tables[MANIFEST]).where(tables[MANIFEST].c.archive_id != CONTROL_ID)).mappings()
    )
    archive_ids = {manifest["archive_id"] for manifest in manifests}
    batches = []
    for archive in (RETRY_ARCHIVE, DLQ_ARCHIVE):
        if any(row[0] not in archive_ids for row in bind.execute(sa.select(tables[archive].c.archive_id))):
            raise RuntimeError("Rollback archive has orphan rows")
    for manifest in manifests:
        revision = manifest["source_revision"]
        known_schemas = {_json(_schema(revision))} if revision in (HEAD, PREVIOUS) else set()
        if revision == PREVIOUS:
            known_schemas.add(_json(_schema(HEAD)))
        if (
            manifest["owner"] != OWNER
            or manifest["format_version"] != 1
            or revision not in (HEAD, PREVIOUS)
            or manifest["target_revision"] != PREVIOUS
            or manifest["source_schema"] not in known_schemas
        ):
            raise RuntimeError("Rollback archive ownership/version/source schema is unsupported")
        source_schema = json.loads(manifest["source_schema"])
        rows_by_source = {}
        for kind, source, archive in zip(("retry", "dlq"), SOURCES, (RETRY_ARCHIVE, DLQ_ARCHIVE), strict=True):
            rows = list(
                bind.execute(
                    sa.select(tables[archive]).where(tables[archive].c.archive_id == manifest["archive_id"])
                ).mappings()
            )
            _validate_rows(source, rows, source_schema[source])
            if (
                len(rows) != manifest[f"{kind}_count"]
                or _batch_digest(manifest, source, rows) != manifest[f"{kind}_digest"]
                or any(_digest(source, [row]) != row["row_digest"] for row in rows)
                or manifest[f"{kind}_high_water"] < max((row["id"] for row in rows), default=0)
            ):
                raise RuntimeError("Rollback archive integrity verification failed")
            rows_by_source[source] = rows
        batches.append((manifest, rows_by_source))
    for source in SOURCES:
        ids = [row["id"] for _, rows in batches for row in rows[source]]
        if len(ids) != len(set(ids)):
            raise RuntimeError("Rollback archive contains repeated source identities")
        if ids:
            occupied = set(bind.execute(sa.text(f"SELECT id FROM {source}")).scalars())
            if occupied & set(ids):
                raise RuntimeError(f"Rollback archive restore identity collision in {source}")
    return batches


def _high_water(bind, source):
    maximum = bind.execute(sa.text(f"SELECT COALESCE(MAX(id), 0) FROM {source}")).scalar_one()
    if bind.dialect.name == "sqlite":
        issued = bind.execute(sa.text("SELECT seq FROM sqlite_sequence WHERE name = :name"), {"name": source}).scalar()
    else:
        sequence = bind.execute(sa.text("SELECT pg_get_serial_sequence(:name, 'id')"), {"name": source}).scalar_one()
        issued = bind.execute(sa.text(f"SELECT last_value FROM {sequence}")).scalar_one()
    return max(maximum, issued or 0)


def _advance(bind, source, high_water):
    value = max(_high_water(bind, source), high_water)
    if bind.dialect.name == "sqlite":
        bind.execute(
            sa.text(
                "INSERT INTO sqlite_sequence(name, seq) SELECT :name, :value WHERE NOT EXISTS "
                "(SELECT 1 FROM sqlite_sequence WHERE name = :name)"
            ),
            {"name": source, "value": value},
        )
        bind.execute(
            sa.text("UPDATE sqlite_sequence SET seq = MAX(seq, :value) WHERE name = :name"),
            {"name": source, "value": value},
        )
    elif value:
        bind.execute(
            sa.text("SELECT setval(pg_get_serial_sequence(:name, 'id'), :value, true)"),
            {"name": source, "value": value},
        )


def capture(bind, source_revision):
    """Copy/verify/delete incompatible raw rows inside the caller's DDL transaction."""
    source_schema = _check_sources(bind, source_revision)
    tables = _archive_tables(bind)
    _read_archive(bind, tables)
    captured = {}
    for source in SOURCES:
        rows = list(bind.execute(sa.text(f"SELECT * FROM {source} ORDER BY id")).mappings())
        _validate_rows(source, rows, source_schema[source])
        captured[source] = [row for row in rows if any(_unknown(row[name]) for name in DATES[source])]
    if not any(captured.values()):
        return
    tables = _archive_tables(bind, create=True)
    archive_id = str(uuid4())
    manifest = {
        "archive_id": archive_id,
        "owner": OWNER,
        "format_version": 1,
        "source_revision": source_revision,
        "target_revision": PREVIOUS,
        "source_schema": _json(source_schema),
    }
    for kind, source, archive in zip(("retry", "dlq"), SOURCES, (RETRY_ARCHIVE, DLQ_ARCHIVE), strict=True):
        rows = captured[source]
        manifest.update(
            {
                f"{kind}_count": len(rows),
                f"{kind}_digest": _digest(source, rows),
                f"{kind}_high_water": _high_water(bind, source),
            }
        )
        if rows:
            bind.execute(
                tables[archive].insert(),
                [{**dict(row), "archive_id": archive_id, "row_digest": _digest(source, [row])} for row in rows],
            )
            copied = list(
                bind.execute(sa.select(tables[archive]).where(tables[archive].c.archive_id == archive_id)).mappings()
            )
            if len(copied) != len(rows) or _digest(source, copied) != _digest(source, rows):
                raise RuntimeError("Rollback archive copy verification failed")
    for kind, source in zip(("retry", "dlq"), SOURCES, strict=True):
        manifest[f"{kind}_digest"] = _batch_digest(manifest, source, captured[source])
    bind.execute(tables[MANIFEST].insert(), manifest)
    for kind, source in zip(("retry", "dlq"), SOURCES, strict=True):
        for row in captured[source]:
            result = bind.execute(sa.text(f"DELETE FROM {source} WHERE id = :id"), {"id": row["id"]})
            if result.rowcount != 1:
                raise RuntimeError("Rollback archive source ownership changed")
        _advance(bind, source, manifest[f"{kind}_high_water"])


def restore(bind):
    """Restore every verified batch or none; acknowledge only after raw verification."""
    _check_sources(bind, HEAD)
    tables = _archive_tables(bind)
    batches = _read_archive(bind, tables)
    if not batches:
        return
    for manifest, rows_by_source in batches:
        for kind, source in zip(("retry", "dlq"), SOURCES, strict=True):
            columns = [column[0] for column in RAW_COLUMNS[source]]
            rows = [{column: row[column] for column in columns} for row in rows_by_source[source]]
            if rows:
                bind.execute(
                    sa.text(
                        f"INSERT INTO {source} ({', '.join(columns)}) VALUES ({', '.join(':' + name for name in columns)})"
                    ),
                    rows,
                )
                restored = [
                    bind.execute(sa.text(f"SELECT * FROM {source} WHERE id = :id"), {"id": row["id"]}).mappings().one()
                    for row in rows
                ]
                if _batch_digest(manifest, source, restored) != manifest[f"{kind}_digest"]:
                    raise RuntimeError("Rollback archive restoration verification failed")
            _advance(bind, source, manifest[f"{kind}_high_water"])
    for manifest, _ in batches:
        for archive in (RETRY_ARCHIVE, DLQ_ARCHIVE, MANIFEST):
            bind.execute(tables[archive].delete().where(tables[archive].c.archive_id == manifest["archive_id"]))
