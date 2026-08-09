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
    Migration(
        version=3,
        name="add_evidence_import_ledger",
        statements=(
            """
            CREATE TABLE import_run (
                run_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                status TEXT NOT NULL CHECK (
                    status IN ('running', 'completed', 'cancelled', 'failed')
                ),
                started_at TEXT NOT NULL,
                finished_at TEXT,
                processed_sources INTEGER NOT NULL DEFAULT 0 CHECK (processed_sources >= 0),
                accepted_records INTEGER NOT NULL DEFAULT 0 CHECK (accepted_records >= 0),
                rejected_records INTEGER NOT NULL DEFAULT 0 CHECK (rejected_records >= 0),
                error_message TEXT
            )
            """,
            """
            CREATE INDEX idx_import_run_case_started
                ON import_run(case_id, started_at DESC)
            """,
            """
            CREATE TABLE evidence_record (
                evidence_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                source_preview_id TEXT NOT NULL
                    REFERENCES source_preview(preview_id) ON DELETE CASCADE,
                import_run_id TEXT NOT NULL REFERENCES import_run(run_id),
                line_number INTEGER NOT NULL CHECK (line_number > 0),
                event_id TEXT NOT NULL,
                occurred_at TEXT,
                category TEXT NOT NULL,
                action TEXT NOT NULL,
                host_name TEXT,
                user_name TEXT,
                observables_json TEXT NOT NULL,
                declared_source_id TEXT NOT NULL,
                declared_position_kind TEXT NOT NULL,
                declared_position_value TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                UNIQUE(case_id, source_preview_id, line_number)
            )
            """,
            """
            CREATE INDEX idx_evidence_case_time
                ON evidence_record(case_id, occurred_at, evidence_id)
            """,
            """
            CREATE INDEX idx_evidence_case_event
                ON evidence_record(case_id, event_id)
            """,
            """
            CREATE TABLE import_rejection (
                rejection_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                source_preview_id TEXT NOT NULL
                    REFERENCES source_preview(preview_id) ON DELETE CASCADE,
                import_run_id TEXT NOT NULL REFERENCES import_run(run_id),
                line_number INTEGER NOT NULL CHECK (line_number >= 0),
                code TEXT NOT NULL,
                message TEXT NOT NULL,
                raw_excerpt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(case_id, source_preview_id, line_number, code)
            )
            """,
            """
            CREATE INDEX idx_rejection_case_source
                ON import_rejection(case_id, source_preview_id, line_number)
            """,
        ),
    ),
    Migration(
        version=4,
        name="add_ioc_analysis_and_coverage",
        statements=(
            """
            CREATE TABLE analysis_run (
                analysis_run_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                recipe_id TEXT NOT NULL,
                recipe_version TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                completed_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX idx_analysis_run_case_completed
                ON analysis_run(case_id, completed_at DESC, analysis_run_id DESC)
            """,
            """
            CREATE TABLE sighting (
                sighting_id TEXT PRIMARY KEY,
                analysis_run_id TEXT NOT NULL
                    REFERENCES analysis_run(analysis_run_id) ON DELETE CASCADE,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                evidence_id TEXT NOT NULL
                    REFERENCES evidence_record(evidence_id) ON DELETE CASCADE,
                observable_id TEXT NOT NULL
                    REFERENCES case_observable(observable_id) ON DELETE CASCADE,
                observable_type TEXT NOT NULL,
                recipe_id TEXT NOT NULL,
                recipe_version TEXT NOT NULL,
                step_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                field_path TEXT NOT NULL,
                original_value TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                explanation_json TEXT NOT NULL,
                UNIQUE(analysis_run_id, evidence_id, observable_id, field_path, rule_id)
            )
            """,
            """
            CREATE INDEX idx_sighting_case_evidence
                ON sighting(case_id, evidence_id, analysis_run_id)
            """,
            """
            CREATE TABLE coverage_cell (
                coverage_cell_id TEXT PRIMARY KEY,
                analysis_run_id TEXT NOT NULL
                    REFERENCES analysis_run(analysis_run_id) ON DELETE CASCADE,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                recipe_id TEXT NOT NULL,
                recipe_version TEXT NOT NULL,
                step_id TEXT NOT NULL,
                step_label TEXT NOT NULL,
                telemetry TEXT NOT NULL,
                state TEXT NOT NULL CHECK (
                    state IN (
                        'MATCH_FOUND', 'SEARCHED_NO_MATCH', 'PARTIAL_COVERAGE',
                        'SOURCE_NOT_PROVIDED', 'SOURCE_FAILED', 'FORMAT_UNSUPPORTED'
                    )
                ),
                reason_json TEXT NOT NULL,
                source_preview_ids_json TEXT NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                match_count INTEGER NOT NULL CHECK (match_count >= 0),
                UNIQUE(analysis_run_id, step_id)
            )
            """,
            """
            CREATE INDEX idx_coverage_case_state
                ON coverage_cell(case_id, state, analysis_run_id)
            """,
        ),
    ),
    Migration(
        version=5,
        name="add_case_capsule_history",
        statements=(
            """
            CREATE TABLE export_record (
                export_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                profile TEXT NOT NULL CHECK (
                    profile IN ('full-internal', 'redacted-shareable')
                ),
                destination TEXT NOT NULL,
                created_at TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                artifact_count INTEGER NOT NULL CHECK (artifact_count >= 0)
            )
            """,
            """
            CREATE INDEX idx_export_record_case_created
                ON export_record(case_id, created_at DESC, export_id DESC)
            """,
        ),
    ),
    Migration(
        version=6,
        name="add_analyst_reasoning_workspace",
        statements=(
            """
            CREATE TABLE recommendation_state (
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                recommendation_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('Proposed', 'Accepted', 'Completed', 'Dismissed')
                ),
                analyst_note TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(case_id, recommendation_id)
            )
            """,
            """
            CREATE TABLE intelligence_assertion (
                assertion_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                provider_version TEXT NOT NULL,
                observable_type TEXT NOT NULL,
                observable_value TEXT NOT NULL,
                claim TEXT NOT NULL CHECK (
                    claim IN ('Malicious', 'Suspicious', 'Benign', 'Unknown', 'Context only')
                ),
                confidence_label TEXT NOT NULL,
                summary TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                data_timestamp TEXT,
                expires_at TEXT,
                source_reference TEXT,
                raw_response_sha256 TEXT,
                origin TEXT NOT NULL CHECK (origin IN ('manual', 'import', 'virustotal')),
                archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))
            )
            """,
            """
            CREATE INDEX idx_intelligence_case_observable
                ON intelligence_assertion(case_id, observable_type, observable_value, retrieved_at)
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
