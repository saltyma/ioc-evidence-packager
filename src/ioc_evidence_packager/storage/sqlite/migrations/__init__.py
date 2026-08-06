"""Small explicit SQLite migration runner."""

import sqlite3
from dataclasses import dataclass

from ioc_evidence_packager.domain.errors import SchemaVersionError


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


MIGRATIONS = (
    Migration(
        version=1,
        name="create_case_foundation",
        statements=(
            """
            CREATE TABLE schema_migration (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE case_record (
                case_id TEXT PRIMARY KEY,
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                external_reference TEXT,
                summary TEXT,
                status TEXT NOT NULL CHECK (
                    status IN ('draft', 'ready_for_review', 'reviewed', 'exported', 'archived')
                ),
                privacy_mode TEXT NOT NULL CHECK (
                    privacy_mode IN (
                        'offline',
                        'local_intelligence',
                        'safe_enrichment',
                        'enterprise',
                        'custom'
                    )
                ),
                display_timezone TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_opened_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX idx_case_record_last_opened
                ON case_record(last_opened_at DESC, case_id ASC)
            """,
        ),
    ),
    Migration(
        version=2,
        name="add_investigation_setup",
        statements=(
            """
            CREATE TABLE case_observable (
                observable_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('lead', 'pivot')),
                observable_type TEXT NOT NULL CHECK (
                    observable_type IN ('ipv4', 'domain', 'sha256')
                ),
                original_value TEXT NOT NULL,
                canonical_value TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE UNIQUE INDEX idx_case_observable_one_lead
                ON case_observable(case_id)
                WHERE role = 'lead'
            """,
            """
            CREATE INDEX idx_case_observable_lookup
                ON case_observable(observable_type, canonical_value)
            """,
            """
            CREATE TABLE source_preview (
                preview_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                path TEXT NOT NULL,
                display_name TEXT NOT NULL,
                byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
                sha256 TEXT,
                status TEXT NOT NULL CHECK (
                    status IN ('ready', 'warning', 'unsupported', 'failed')
                ),
                adapter_id TEXT,
                adapter_version TEXT,
                format_name TEXT,
                sample_records INTEGER NOT NULL CHECK (sample_records >= 0),
                fields_json TEXT NOT NULL,
                capabilities_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                earliest_time TEXT,
                latest_time TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(case_id, path)
            )
            """,
            """
            CREATE INDEX idx_source_preview_case
                ON source_preview(case_id, status, display_name)
            """,
        ),
    ),
)

LATEST_SCHEMA_VERSION = MIGRATIONS[-1].version


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply all pending migrations, one atomic transaction at a time."""

    current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if current_version > LATEST_SCHEMA_VERSION:
        raise SchemaVersionError(
            "This case database was created by a newer version of the application "
            f"(schema {current_version}; supported {LATEST_SCHEMA_VERSION})."
        )

    for migration in MIGRATIONS:
        if migration.version <= current_version:
            continue
        _apply_one(connection, migration)
        current_version = migration.version


def _apply_one(connection: sqlite3.Connection, migration: Migration) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in migration.statements:
            connection.execute(statement)
        connection.execute(
            """
                INSERT INTO schema_migration(version, name, applied_at)
                VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (migration.version, migration.name),
        )
        connection.execute(
            f"PRAGMA user_version = {migration.version}"  # noqa: S608 - trusted migration metadata
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
