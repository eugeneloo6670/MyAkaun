"""Lightweight SQLite migration helper.

Why this exists:
    SQLAlchemy's `Base.metadata.create_all()` creates missing tables but does
    NOT alter existing tables that are missing columns. When the schema gains
    new columns between releases (e.g. the v8 addition of `status`, `voided_by`,
    `voided_at`, `void_reason` on `entries`), users with a pre-existing dev DB
    get cryptic `OperationalError: no such column` failures.

    A full migration framework (Alembic) would be the right answer for a
    production system. For a single-table-family prototype it's overkill. This
    module is the pragmatic middle: declare the expected columns, check what's
    on disk via PRAGMA, and ALTER TABLE in the gaps.

How to extend:
    Add an entry to EXPECTED_COLUMNS keyed by table name. Each value is a list
    of (column_name, column_definition_sql) tuples. column_definition_sql is the
    fragment SQLite needs after `ADD COLUMN name`, e.g. "VARCHAR DEFAULT 'posted'".
    Run this on every startup; columns already present are left alone.

What this does NOT do:
    - Drop columns (SQLite ALTER TABLE doesn't support DROP COLUMN cleanly)
    - Change column types (would need table rebuild)
    - Rename columns
    - Anything involving foreign keys

    Those operations need a proper migration; when one becomes necessary, that's
    the moment to bring in Alembic.
"""
from __future__ import annotations
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
import logging

log = logging.getLogger(__name__)


# (table_name, [(column_name, column_definition_sql)])
# Column definitions must include the SQLite type and any DEFAULT / NOT NULL
# clauses. Keep these in sync with the SQLAlchemy model definitions.
EXPECTED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "entries": [
        # v8 soft-delete columns
        ("status",       "VARCHAR DEFAULT 'posted' NOT NULL"),
        ("voided_by",    "VARCHAR"),
        ("voided_at",    "DATETIME"),
        ("void_reason",  "TEXT"),
        # Idempotent POST /api/entries/ support
        ("idempotency_key",  "VARCHAR"),
        ("idempotency_hash", "VARCHAR"),
        # FX audit metadata
        ("rate_source",      "VARCHAR"),
        ("rate_locked_at",   "DATETIME"),
    ],
}


def run_migrations(engine: Engine) -> None:
    """Add any columns listed in EXPECTED_COLUMNS that are missing from the
    actual database. Idempotent — safe to call on every startup.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, expected_cols in EXPECTED_COLUMNS.items():
            if table not in existing_tables:
                # Table doesn't exist yet — create_all() will handle it with the
                # full, current schema. Nothing to migrate.
                continue

            actual_col_names = {c["name"] for c in inspector.get_columns(table)}
            for col_name, col_def in expected_cols:
                if col_name in actual_col_names:
                    continue
                log.info("migrations: adding %s.%s (%s)", table, col_name, col_def)
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))

            # Backfill: any row with NULL status (added before this migration)
            # should be treated as 'posted'. SQLite's ALTER TABLE ... DEFAULT only
            # applies to new rows, not existing ones.
            if any(c[0] == "status" for c in expected_cols):
                conn.execute(text(
                    "UPDATE entries SET status = 'posted' WHERE status IS NULL"
                ))

        if "entries" in existing_tables:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_entries_idempotency_key "
                "ON entries (idempotency_key) "
                "WHERE idempotency_key IS NOT NULL"
            ))

        if engine.dialect.name == "sqlite" and "audit_log" in existing_tables:
            conn.execute(text(
                """
                CREATE TRIGGER IF NOT EXISTS audit_log_no_update
                BEFORE UPDATE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'audit_log is append-only');
                END
                """
            ))
            conn.execute(text(
                """
                CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
                BEFORE DELETE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'audit_log is append-only');
                END
                """
            ))
