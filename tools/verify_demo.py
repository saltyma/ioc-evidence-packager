"""Verify every bundled demo fixture and expected end-to-end result offline."""

import hashlib
from collections import Counter
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
from ioc_evidence_packager.domain.workspace import intelligence_conflicts
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

EXPECTED_FILES = {
    "01-dns-events.jsonl": "e20a70beb42d5b009e2707aa728a12e61ecd7e6ef0c3ae0fb98f9d006f231661",
    "02-endpoint-events.jsonl": "af71027aa8e1af38a27242a2e968c83eefa3c7cd1314b7e040ead6078bc64c00",
    "03-network-events.jsonl": "82a0dfdbe4c5a18ae155c0aa3647fbc9d8fa518f51f155a631e60c219699fa44",
    "04-authentication-events.jsonl": (
        "978ebc4d3a396c2018c21178917718ddcacaf8390c96dd8f1108c5ad67b3f74e"
    ),
    "05-partial-with-warning.jsonl": (
        "8fce4bfbb3167ba323260c878825e63154506ac4e0e2243c5b90c2e11c270229"
    ),
    "06-unsupported-siem-export.csv": (
        "ebd7c3fe81e5653e078082b29435fa27a3b37f08f9ead7fbbf94241a457144ce"
    ),
    "07-suricata-eve.jsonl": "b806f2db3a98d92725304025de4c296e91ee639f713f0440ce4af6a14aabbd5a",
    "08-wazuh-alerts.jsonl": "687a9b080f2c32e0751ec91a4656aef86a6ab417bf21348899216d0526026482",
    "09-hayabusa-results.jsonl": "a9d96d6703916cca37be202babeb35b30506357689313c39de297430f8e33089",
    "10-generic-array.json": "c1ce90cd8aeabfc3d57f819b755648dc06cf4c71a7a02c71ce5b585bae68bbb5",
    "11-mapped-proxy.csv": "74fef217e0bd3a47bcdf95eaa6ff8bdc0104005137eaf0368b9ff5cbfdf0c931",
    "11-mapped-proxy.csv.ioc-map.json": (
        "7ce87df151b448606bb9bd93b1d35dc42aa249cbc77461f7e67134525fdcb977"
    ),
    "12-intelligence-assertions.json": (
        "dc0f0c11ac253e6c7b19a15c64a77b79c9d5b4bdce36e1c0b5cf72fe3441f4b8"
    ),
}

EVIDENCE_NAMES = tuple(
    name
    for name in EXPECTED_FILES
    if name[:2].isdigit()
    and 1 <= int(name[:2]) <= 11
    and name != "11-mapped-proxy.csv.ioc-map.json"
)

EXPECTED_PREVIEWS = {
    "01-dns-events.jsonl": ("ready", 3, "canonical-jsonl"),
    "02-endpoint-events.jsonl": ("ready", 4, "canonical-jsonl"),
    "03-network-events.jsonl": ("ready", 3, "canonical-jsonl"),
    "04-authentication-events.jsonl": ("ready", 2, "canonical-jsonl"),
    "05-partial-with-warning.jsonl": ("warning", 1, "canonical-jsonl"),
    "06-unsupported-siem-export.csv": ("unsupported", 0, None),
    "07-suricata-eve.jsonl": ("ready", 2, "suricata-eve-jsonl"),
    "08-wazuh-alerts.jsonl": ("ready", 2, "wazuh-alert-jsonl"),
    "09-hayabusa-results.jsonl": ("ready", 2, "hayabusa-jsonl"),
    "10-generic-array.json": ("ready", 2, "generic-json-array"),
    "11-mapped-proxy.csv": ("ready", 2, "mapped-csv"),
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    demo = root / "samples" / "input" / "demo-investigation"
    _verify_bytes(demo)

    inspector = SourceInspectionService()
    previews = tuple(inspector.inspect(demo / name) for name in EVIDENCE_NAMES)
    preview_values = {
        preview.display_name: (
            preview.status.value,
            preview.sample_records,
            preview.adapter_id,
        )
        for preview in previews
    }
    _expect("preview states", preview_values, EXPECTED_PREVIEWS)

    with TemporaryDirectory(prefix="ioc-packager-demo-verify-") as temporary:
        database = SQLiteDatabase(Path(temporary) / "demo.sqlite3")
        database.initialize()
        cases = CaseService(SQLiteCaseRepository(database))
        evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
        analysis_service = AnalysisService(SQLiteAnalysisRepository(database))
        workspace = WorkspaceService(SQLiteWorkspaceRepository(database))
        reports = ReportService(SQLiteExportRepository(database))
        setup = cases.create_investigation(
            NewInvestigationRequest(
                case=NewCaseRequest(
                    title="Suspicious download on FIN-WS-014",
                    external_reference="DEMO-IR-2026-001",
                ),
                lead_value="203.0.113.42",
                source_previews=previews,
            )
        )
        if setup.lead is None:
            raise RuntimeError("Demo lead was not retained.")

        first = evidence_service.import_sources(setup.case.case_id, previews)
        retry = evidence_service.import_sources(setup.case.case_id, previews)
        _expect("durable evidence", first.stored_evidence_records, 23)
        _expect("durable rejections", first.stored_rejections, 1)
        _expect("retry durable evidence", retry.stored_evidence_records, 23)
        _expect("retry durable rejections", retry.stored_rejections, 1)

        records = tuple(evidence_service.list_evidence(setup.case.case_id))
        rejections = tuple(evidence_service.list_rejections(setup.case.case_id))
        analysis = analysis_service.ensure_analysis(
            setup.case.case_id,
            setup.lead,
            previews,
            records,
            rejections,
        )
        _expect("direct sightings", len(analysis.sightings), 8)
        states = Counter(cell.state.value for cell in analysis.coverage)
        _expect(
            "coverage states",
            states,
            Counter(
                {
                    "MATCH_FOUND": 1,
                    "PARTIAL_COVERAGE": 1,
                    "SEARCHED_NO_MATCH": 1,
                    "FORMAT_UNSUPPORTED": 1,
                }
            ),
        )

        graph = workspace.relationships(records)
        _expect("relationship nodes", len(graph.nodes), 47)
        _expect("relationship edges", len(graph.edges), 113)
        recommendations = workspace.recommendations(setup.case.case_id, analysis, graph)
        _expect("recommendations", len(recommendations), 4)
        _expect(
            "recommendation priorities",
            Counter(item.priority.value for item in recommendations),
            Counter({"Immediate": 2, "Useful": 2}),
        )

        imported = workspace.import_assertions(
            setup.case.case_id,
            demo / "12-intelligence-assertions.json",
        )
        assertions = workspace.assertions(setup.case.case_id)
        _expect("imported assertions", imported, 2)
        _expect("active assertions", len(assertions), 2)
        _expect("conflicting assertions", len(intelligence_conflicts(assertions)), 2)

        result = reports.export_case(
            setup,
            records,
            rejections,
            analysis,
            Path(temporary) / "capsule",
            ExportProfile.REDACTED_SHAREABLE,
            graph,
            recommendations,
            assertions,
        )
        verification = reports.verify(result.destination)
        _expect("capsule verification", verification.valid, True)
        _expect("capsule artifacts", len(result.artifacts), 8)
        _expect("checked capsule artifacts", verification.checked_artifacts, 8)

    print("Demo verification passed.")
    print("  13 fixture hashes · 11 evidence previews · 23 evidence / 1 rejection")
    print("  8 sightings · 47 nodes / 113 edges · 4 recommendations")
    print("  2 conflicting assertions · 8 verified capsule artifacts")
    return 0


def _verify_bytes(demo: Path) -> None:
    for name, expected in EXPECTED_FILES.items():
        path = demo / name
        if not path.is_file():
            raise RuntimeError(f"Demo fixture is missing: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        _expect(f"SHA-256 for {name}", actual, expected)


def _expect(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise RuntimeError(f"{label} mismatch: expected {expected!r}, received {actual!r}")


if __name__ == "__main__":
    raise SystemExit(main())
