"""SQLite migration and repository integration tests."""

import sqlite3
from pathlib import Path

import pytest

from ioc_evidence_packager.application.services import (
    CaseService,
    NewCaseRequest,
    NewInvestigationRequest,
)
from ioc_evidence_packager.domain.errors import SchemaVersionError
from ioc_evidence_packager.domain.observables import ObservableType
from ioc_evidence_packager.ingestion.inspection import SourceInspectionService
from ioc_evidence_packager.storage.sqlite import SQLiteCaseRepository, SQLiteDatabase


def test_initial_migration_is_idempotent(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "cases.sqlite3")

    database.initialize()
    database.initialize()

    with database.connection() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        migration_count = connection.execute("SELECT count(*) FROM schema_migration").fetchone()[0]
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'case_record'"
        ).fetchone()
    assert version == 2
    assert migration_count == 2
    assert table is not None


def test_case_survives_repository_recreation(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "cases.sqlite3")
    database.initialize()
    first_service = CaseService(SQLiteCaseRepository(database))
    created = first_service.create_case(
        NewCaseRequest(
            title="Persistent case",
            external_reference="IR-2026-001",
            summary="Stored in the portable local case database.",
        )
    )

    second_service = CaseService(SQLiteCaseRepository(database))
    cases = second_service.list_recent_cases()

    assert [case.case_id for case in cases] == [created.case_id]
    assert cases[0].title == "Persistent case"
    assert cases[0].external_reference == "IR-2026-001"


def test_investigation_setup_survives_repository_recreation(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "cases.sqlite3")
    database.initialize()
    source = Path(__file__).parents[2] / "samples" / "input" / "canonical-demo.jsonl"
    preview = SourceInspectionService().inspect(source)
    first_service = CaseService(SQLiteCaseRepository(database))
    created = first_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Suspicious infrastructure"),
            lead_value="Example.TEST.",
            source_previews=(preview,),
        )
    )

    reopened = CaseService(SQLiteCaseRepository(database)).open_investigation(created.case.case_id)

    assert reopened.case.case_id == created.case.case_id
    assert reopened.lead is not None
    assert reopened.lead.observable_type is ObservableType.DOMAIN
    assert reopened.lead.original_value == "Example.TEST."
    assert reopened.lead.canonical_value == "example.test"
    assert reopened.source_previews == (preview,)


def test_newer_schema_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "newer.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 999")

    with pytest.raises(SchemaVersionError, match="newer version"):
        SQLiteDatabase(path).initialize()
