"""End-to-end durable import across every Phase 5 practical adapter."""

from pathlib import Path

from ioc_evidence_packager.application.evidence_service import EvidenceService
from ioc_evidence_packager.application.services import (
    CaseService,
    NewCaseRequest,
    NewInvestigationRequest,
)
from ioc_evidence_packager.ingestion.inspection import SourceInspectionService
from ioc_evidence_packager.ingestion.registry import AdapterRegistry
from ioc_evidence_packager.storage.sqlite import (
    SQLiteCaseRepository,
    SQLiteDatabase,
    SQLiteEvidenceRepository,
)

DEMO = Path(__file__).parents[2] / "samples" / "input" / "demo-investigation"
NAMES = (
    "07-suricata-eve.jsonl",
    "08-wazuh-alerts.jsonl",
    "09-hayabusa-results.jsonl",
    "10-generic-array.json",
    "11-mapped-proxy.csv",
)


def test_practical_adapters_share_one_durable_ledger(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "phase5.sqlite3")
    database.initialize()
    registry = AdapterRegistry()
    previews = tuple(SourceInspectionService(registry).inspect(DEMO / name) for name in NAMES)
    case_service = CaseService(SQLiteCaseRepository(database))
    setup = case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Phase 5 multi-adapter import"),
            lead_value="203.0.113.42",
            source_previews=previews,
        )
    )
    evidence_service = EvidenceService(SQLiteEvidenceRepository(database), registry)

    summary = evidence_service.import_sources(setup.case.case_id, setup.source_previews)
    records = evidence_service.list_evidence(setup.case.case_id)

    assert summary.accepted_records == 10
    assert summary.rejected_records == 0
    assert len(records) == 10
    assert {record.source_name for record in records} == set(NAMES)
    assert (
        sum(
            observable.canonical == "203.0.113.42"
            for record in records
            for observable in record.observables
        )
        == 4
    )
