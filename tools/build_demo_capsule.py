"""Build the checked, safe synthetic Case Capsule from repository fixtures."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from ioc_evidence_packager.application.analysis_service import AnalysisService
from ioc_evidence_packager.application.evidence_service import EvidenceService
from ioc_evidence_packager.application.report_service import ReportService
from ioc_evidence_packager.application.services import (
    CaseService,
    NewCaseRequest,
    NewInvestigationRequest,
)
from ioc_evidence_packager.application.workspace_service import WorkspaceService
from ioc_evidence_packager.ingestion import SourceInspectionService
from ioc_evidence_packager.reporting.models import ExportProfile
from ioc_evidence_packager.storage.sqlite import (
    SQLiteAnalysisRepository,
    SQLiteCaseRepository,
    SQLiteDatabase,
    SQLiteEvidenceRepository,
    SQLiteExportRepository,
    SQLiteWorkspaceRepository,
)

DEMO_NAMES = (
    "01-dns-events.jsonl",
    "02-endpoint-events.jsonl",
    "03-network-events.jsonl",
    "04-authentication-events.jsonl",
    "05-partial-with-warning.jsonl",
    "06-unsupported-siem-export.csv",
    "07-suricata-eve.jsonl",
    "08-wazuh-alerts.jsonl",
    "09-hayabusa-results.jsonl",
    "10-generic-array.json",
    "11-mapped-proxy.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--profile",
        choices=tuple(profile.value for profile in ExportProfile),
        default=ExportProfile.REDACTED_SHAREABLE.value,
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    demo = root / "samples" / "input" / "demo-investigation"
    previews = tuple(SourceInspectionService().inspect(demo / name) for name in DEMO_NAMES)

    with TemporaryDirectory(prefix="ioc-packager-demo-") as temporary:
        database = SQLiteDatabase(Path(temporary) / "demo.sqlite3")
        database.initialize()
        case_service = CaseService(SQLiteCaseRepository(database))
        evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
        analysis_service = AnalysisService(SQLiteAnalysisRepository(database))
        report_service = ReportService(SQLiteExportRepository(database))
        workspace_service = WorkspaceService(SQLiteWorkspaceRepository(database))
        setup = case_service.create_investigation(
            NewInvestigationRequest(
                case=NewCaseRequest(
                    title="Suspicious download on FIN-WS-014",
                    external_reference="DEMO-IR-2026-001",
                    summary=("Synthetic triage of a suspicious download and follow-on connection."),
                ),
                lead_value="203.0.113.42",
                source_previews=previews,
            )
        )
        evidence_service.import_sources(setup.case.case_id, setup.source_previews)
        evidence = tuple(evidence_service.list_evidence(setup.case.case_id))
        rejections = tuple(evidence_service.list_rejections(setup.case.case_id))
        if setup.lead is None:
            raise RuntimeError("The synthetic investigation did not retain its lead.")
        analysis = analysis_service.ensure_analysis(
            setup.case.case_id,
            setup.lead,
            setup.source_previews,
            evidence,
            rejections,
        )
        workspace_service.import_assertions(
            setup.case.case_id, demo / "12-intelligence-assertions.json"
        )
        relationships = workspace_service.relationships(evidence)
        recommendations = workspace_service.recommendations(
            setup.case.case_id, analysis, relationships
        )
        result = report_service.export_case(
            setup,
            evidence,
            rejections,
            analysis,
            args.destination,
            ExportProfile(args.profile),
            relationships,
            recommendations,
            workspace_service.assertions(setup.case.case_id),
        )
    print(f"Verified demo capsule: {result.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
