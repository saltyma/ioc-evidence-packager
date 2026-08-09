"""SQLite migration and repository integration tests."""

import json
import sqlite3
from pathlib import Path

import pytest

from ioc_evidence_packager.application.analysis_service import AnalysisService
from ioc_evidence_packager.application.evidence_service import EvidenceService
from ioc_evidence_packager.application.report_service import ReportService
from ioc_evidence_packager.application.services import (
    CaseService,
    NewCaseRequest,
    NewInvestigationRequest,
)
from ioc_evidence_packager.domain.analysis import CoverageState
from ioc_evidence_packager.domain.errors import SchemaVersionError
from ioc_evidence_packager.domain.evidence import ImportStatus
from ioc_evidence_packager.domain.observables import ObservableType
from ioc_evidence_packager.ingestion.inspection import SourceInspectionService
from ioc_evidence_packager.reporting.models import ExportProfile
from ioc_evidence_packager.storage.sqlite import (
    SQLiteAnalysisRepository,
    SQLiteCaseRepository,
    SQLiteDatabase,
    SQLiteEvidenceRepository,
    SQLiteExportRepository,
)


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
    assert version == 6
    assert migration_count == 6
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


def test_demo_import_is_durable_and_idempotent(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "cases.sqlite3")
    database.initialize()
    case_service = CaseService(SQLiteCaseRepository(database))
    evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
    demo = Path(__file__).parents[2] / "samples" / "input" / "demo-investigation"
    previews = tuple(
        SourceInspectionService().inspect(demo / name)
        for name in (
            "01-dns-events.jsonl",
            "02-endpoint-events.jsonl",
            "03-network-events.jsonl",
            "04-authentication-events.jsonl",
            "05-partial-with-warning.jsonl",
        )
    )
    setup = case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Import demo"),
            lead_value="203.0.113.42",
            source_previews=previews,
        )
    )

    first = evidence_service.import_sources(setup.case.case_id, setup.source_previews)
    second = evidence_service.import_sources(setup.case.case_id, setup.source_previews)

    assert first.status is ImportStatus.COMPLETED
    assert first.accepted_records == 13
    assert first.rejected_records == 1
    assert first.stored_evidence_records == 13
    assert second.accepted_records == 13
    assert second.stored_evidence_records == 13
    assert len(evidence_service.list_evidence(setup.case.case_id)) == 13
    rejections = evidence_service.list_rejections(setup.case.case_id)
    assert len(rejections) == 1
    assert rejections[0].code == "invalid_json"


def test_changed_source_is_rejected_before_records_are_read(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    fixture = Path(__file__).parents[2] / "samples" / "input" / "canonical-demo.jsonl"
    source.write_bytes(fixture.read_bytes())
    preview = SourceInspectionService().inspect(source)
    database = SQLiteDatabase(tmp_path / "changed.sqlite3")
    database.initialize()
    case_service = CaseService(SQLiteCaseRepository(database))
    evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
    setup = case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Changed source"),
            lead_value="203.0.113.42",
            source_previews=(preview,),
        )
    )
    source.write_text("changed after preview", encoding="utf-8")

    summary = evidence_service.import_sources(setup.case.case_id, setup.source_previews)

    assert summary.accepted_records == 0
    assert summary.rejected_records == 1
    assert evidence_service.list_rejections(setup.case.case_id)[0].code == ("source_hash_mismatch")


def test_cancelled_import_stops_at_a_safe_boundary(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "cancelled.sqlite3")
    database.initialize()
    case_service = CaseService(SQLiteCaseRepository(database))
    evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
    source = Path(__file__).parents[2] / "samples" / "input" / "canonical-demo.jsonl"
    preview = SourceInspectionService().inspect(source)
    setup = case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Cancelled import"),
            lead_value="203.0.113.42",
            source_previews=(preview,),
        )
    )

    summary = evidence_service.import_sources(
        setup.case.case_id,
        setup.source_previews,
        is_cancelled=lambda: True,
    )

    assert summary.status is ImportStatus.CANCELLED
    assert summary.accepted_records == 0
    assert summary.stored_evidence_records == 0


def test_demo_analysis_is_exact_durable_and_coverage_aware(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "analysis.sqlite3")
    database.initialize()
    case_service = CaseService(SQLiteCaseRepository(database))
    evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
    analysis_service = AnalysisService(SQLiteAnalysisRepository(database))
    demo = Path(__file__).parents[2] / "samples" / "input" / "demo-investigation"
    names = (
        "01-dns-events.jsonl",
        "02-endpoint-events.jsonl",
        "03-network-events.jsonl",
        "04-authentication-events.jsonl",
        "05-partial-with-warning.jsonl",
        "06-unsupported-siem-export.csv",
    )
    previews = tuple(SourceInspectionService().inspect(demo / name) for name in names)
    setup = case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Exact match demo"),
            lead_value="203.0.113.42",
            source_previews=previews,
        )
    )
    evidence_service.import_sources(setup.case.case_id, previews)
    evidence = tuple(evidence_service.list_evidence(setup.case.case_id))
    rejections = tuple(evidence_service.list_rejections(setup.case.case_id))

    first = analysis_service.ensure_analysis(
        setup.case.case_id,
        setup.lead,
        previews,
        evidence,
        rejections,
    )
    second = analysis_service.ensure_analysis(
        setup.case.case_id,
        setup.lead,
        previews,
        evidence,
        rejections,
    )

    assert first.run_id == second.run_id
    assert len(first.sightings) == 4
    matched_event_ids = {
        record.event_id for record in evidence if record.evidence_id in first.direct_evidence_ids
    }
    assert matched_event_ids == {
        "demo-dns-002",
        "demo-network-001",
        "demo-network-002",
        "demo-partial-001",
    }
    assert "demo-network-003" not in matched_event_ids
    states = {cell.state for cell in first.coverage}
    assert CoverageState.MATCH_FOUND in states
    assert CoverageState.SEARCHED_NO_MATCH in states
    assert CoverageState.PARTIAL_COVERAGE in states
    assert CoverageState.FORMAT_UNSUPPORTED in states
    assert all(sighting.rule_id == "ipv4.direct.exact" for sighting in first.sightings)


def test_full_capsule_is_deterministic_verified_and_tamper_evident(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "capsule.sqlite3")
    database.initialize()
    case_service = CaseService(SQLiteCaseRepository(database))
    evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
    analysis_service = AnalysisService(SQLiteAnalysisRepository(database))
    report_service = ReportService(SQLiteExportRepository(database))
    demo = Path(__file__).parents[2] / "samples" / "input" / "demo-investigation"
    previews = tuple(
        SourceInspectionService().inspect(demo / name)
        for name in (
            "01-dns-events.jsonl",
            "03-network-events.jsonl",
            "11-mapped-proxy.csv",
        )
    )
    setup = case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Capsule demo", summary="Safe synthetic case."),
            lead_value="203.0.113.42",
            source_previews=previews,
        )
    )
    evidence_service.import_sources(setup.case.case_id, previews)
    evidence = tuple(evidence_service.list_evidence(setup.case.case_id))
    rejections = tuple(evidence_service.list_rejections(setup.case.case_id))
    analysis = analysis_service.ensure_analysis(
        setup.case.case_id,
        setup.lead,
        previews,
        evidence,
        rejections,
    )

    first = report_service.export_case(
        setup,
        evidence,
        rejections,
        analysis,
        tmp_path / "capsule-one",
        ExportProfile.FULL_INTERNAL,
    )
    second = report_service.export_case(
        setup,
        evidence,
        rejections,
        analysis,
        tmp_path / "capsule-two",
        ExportProfile.FULL_INTERNAL,
    )

    assert report_service.verify(first.destination).valid
    assert {item.path for item in first.artifacts} == {
        "report.html",
        "evidence.jsonl",
        "timeline.csv",
        "coverage.json",
        "source-inventory.json",
        "relationships.json",
        "recommendations.json",
        "intelligence.json",
    }
    assert {item.path: item.sha256 for item in first.artifacts} == {
        item.path: item.sha256 for item in second.artifacts
    }
    source_inventory = json.loads(
        (first.destination / "source-inventory.json").read_text(encoding="utf-8")
    )
    assert source_inventory["schema"] == "source-inventory/1.1.0"
    mapped_source = next(
        item for item in source_inventory["sources"] if item["adapter"] == "mapped-csv"
    )
    assert "mapping-sha256:" in mapped_source["format"]
    assert mapped_source["capabilities"] == [
        "observable.domain",
        "observable.ipv4",
        "timestamp.utc",
    ]
    assert "network.destination_ip" in mapped_source["mapped_fields"]
    assert len(report_service.list_exports(setup.case.case_id)) == 2
    with (first.destination / "evidence.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("tampered\n")
    verification = report_service.verify(first.destination)
    assert not verification.valid
    assert any("mismatch" in message for message in verification.messages)


def test_redacted_capsule_omits_paths_raw_json_and_identifiers(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "redacted.sqlite3")
    database.initialize()
    case_service = CaseService(SQLiteCaseRepository(database))
    evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
    analysis_service = AnalysisService(SQLiteAnalysisRepository(database))
    report_service = ReportService(SQLiteExportRepository(database))
    source = (
        Path(__file__).parents[2]
        / "samples"
        / "input"
        / "demo-investigation"
        / "02-endpoint-events.jsonl"
    )
    preview = SourceInspectionService().inspect(source)
    setup = case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Redacted demo"),
            lead_value="a" * 64,
            source_previews=(preview,),
        )
    )
    evidence_service.import_sources(setup.case.case_id, setup.source_previews)
    evidence = tuple(evidence_service.list_evidence(setup.case.case_id))
    rejections = tuple(evidence_service.list_rejections(setup.case.case_id))
    analysis = analysis_service.ensure_analysis(
        setup.case.case_id,
        setup.lead,
        setup.source_previews,
        evidence,
        rejections,
    )
    result = report_service.export_case(
        setup,
        evidence,
        rejections,
        analysis,
        tmp_path / "redacted-capsule",
        ExportProfile.REDACTED_SHAREABLE,
    )

    lines = [
        json.loads(line)
        for line in (result.destination / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert report_service.verify(result.destination).valid
    assert all("raw_json" not in line for line in lines)
    assert all(line["provenance"]["source_path"] is None for line in lines)
    assert all(line["host"].startswith("HOST-") for line in lines if line["host"])
    assert all(line["user"].startswith("USER-") for line in lines if line["user"])
