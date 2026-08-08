"""Canonical JSONL import conversion and rejection tests."""

from datetime import UTC, datetime
from pathlib import Path

from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.ingestion.canonical_import import iter_canonical_items
from ioc_evidence_packager.ingestion.inspection import SourceInspectionService


def test_partial_fixture_yields_evidence_and_structured_rejection() -> None:
    path = (
        Path(__file__).parents[2]
        / "samples"
        / "input"
        / "demo-investigation"
        / "05-partial-with-warning.jsonl"
    )
    preview = SourceInspectionService().inspect(path)

    items = list(iter_canonical_items(CaseId("case-demo"), preview, datetime.now(UTC)))

    assert len(items) == 2
    assert isinstance(items[0], EvidenceRecord)
    assert items[0].line_number == 1
    assert items[0].source_sha256 == preview.sha256
    assert items[0].observables[0].canonical == "203.0.113.42"
    assert isinstance(items[1], ImportRejection)
    assert items[1].line_number == 2
    assert items[1].code == "invalid_json"
    assert len(items[1].raw_excerpt) <= 240


def test_wrong_schema_is_never_accepted_as_evidence(tmp_path: Path) -> None:
    path = tmp_path / "wrong-schema.jsonl"
    path.write_text('{"schema":"something-else"}\n', encoding="utf-8")
    preview = SourceInspectionService().inspect(path)

    items = list(iter_canonical_items(CaseId("case-demo"), preview, datetime.now(UTC)))

    assert len(items) == 1
    assert isinstance(items[0], ImportRejection)
    assert items[0].code == "invalid_schema"
