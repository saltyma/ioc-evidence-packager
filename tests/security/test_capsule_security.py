"""Hostile presentation values and capsule path-integrity boundaries."""

import csv
import json
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
from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.ingestion import SourceInspectionService
from ioc_evidence_packager.presentation.desktop.views.intelligence import _is_https_reference
from ioc_evidence_packager.reporting import ExportProfile, verify_capsule
from ioc_evidence_packager.storage.sqlite import (
    SQLiteAnalysisRepository,
    SQLiteCaseRepository,
    SQLiteDatabase,
    SQLiteEvidenceRepository,
    SQLiteExportRepository,
)


def test_capsule_escapes_html_protects_csv_and_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "hostile.jsonl"
    source.write_text(json.dumps(_hostile_event()) + "\n", encoding="utf-8")
    database = SQLiteDatabase(tmp_path / "hostile.sqlite3")
    database.initialize()
    case_service = CaseService(SQLiteCaseRepository(database))
    evidence_service = EvidenceService(SQLiteEvidenceRepository(database))
    analysis_service = AnalysisService(SQLiteAnalysisRepository(database))
    report_service = ReportService(SQLiteExportRepository(database))
    preview = SourceInspectionService().inspect(source)
    setup = case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="<script>alert('case')</script>"),
            lead_value="203.0.113.42",
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
        tmp_path / "safe-capsule",
        ExportProfile.FULL_INTERNAL,
    )

    html = (result.destination / "report.html").read_text(encoding="utf-8")
    with (result.destination / "timeline.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert "<script>alert('case')</script>" not in html
    assert "&lt;script&gt;" in html
    assert rows[0]["host"] == "'=2+2"
    assert rows[0]["user"] == "'@analyst"
    assert rows[0]["action"] == "'-launch"
    assert report_service.verify(result.destination).valid

    with pytest.raises(ValidationError, match="already exists"):
        report_service.export_case(
            setup,
            evidence,
            rejections,
            analysis,
            result.destination,
            ExportProfile.FULL_INTERNAL,
        )
    assert report_service.verify(result.destination).valid


def test_verifier_rejects_manifest_path_traversal(tmp_path: Path) -> None:
    capsule = tmp_path / "unsafe-capsule"
    capsule.mkdir()
    (capsule / "manifest.json").write_text(
        json.dumps(
            {
                "capsule_schema": "1.1.0",
                "artifacts": [
                    {
                        "path": "../outside.txt",
                        "byte_size": 0,
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = verify_capsule(capsule)

    assert not result.valid
    assert any("Unsafe artifact path" in message for message in result.messages)


def test_intelligence_reference_launcher_accepts_only_plain_https_urls() -> None:
    assert _is_https_reference("https://www.virustotal.com/gui/ip-address/203.0.113.42")
    assert not _is_https_reference("http://example.test/report")
    assert not _is_https_reference("file:///C:/evidence.txt")
    assert not _is_https_reference("https://user@example.test/report")
    assert not _is_https_reference("urn:synthetic:provider:assertion")


def _hostile_event() -> dict[str, object]:
    return {
        "schema": "canonical-event/1.0.0",
        "event_id": "hostile-001",
        "source": {
            "source_id": "hostile-safe-fixture",
            "position": {"kind": "line", "value": 1},
        },
        "time": {
            "original": "2026-08-06T09:12:03Z",
            "utc": "2026-08-06T09:12:03Z",
            "precision": "second",
            "assumptions": [],
        },
        "event": {"category": "network", "action": "-launch"},
        "host": {"name": "=2+2"},
        "user": {"name": "@analyst"},
        "network": {"destination_ip": "203.0.113.42"},
        "observables": [
            {
                "kind": "ipv4",
                "field_path": "network.destination_ip",
                "original": "203.0.113.42",
                "canonical": "203.0.113.42",
            }
        ],
        "adapter": {"id": "hostile-test", "version": "1.0.0"},
        "warnings": [],
    }
