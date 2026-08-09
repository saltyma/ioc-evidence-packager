"""Canonical JSONL import conversion and rejection tests."""

import json
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


def test_invalid_canonical_observable_and_adapter_are_rejected(tmp_path: Path) -> None:
    base = {
        "schema": "canonical-event/1.0.0",
        "event_id": "event-invalid",
        "source": {"source_id": "source", "position": {"kind": "line", "value": 1}},
        "time": {"original": "2026-08-06T09:12:03Z", "utc": "2026-08-06T09:12:03Z"},
        "event": {"category": "network", "action": "connection"},
        "observables": [
            {
                "kind": "domain",
                "field_path": "dns.question",
                "original": "Example.TEST.",
                "canonical": "Example.TEST.",
            }
        ],
        "adapter": {"id": "", "version": "1.0.0"},
    }
    path = tmp_path / "invalid-canonical.jsonl"
    path.write_text(json.dumps(base) + "\n", encoding="utf-8")
    preview = SourceInspectionService().inspect(path)

    items = list(iter_canonical_items(CaseId("case-demo"), preview, datetime.now(UTC)))

    assert len(items) == 1
    assert isinstance(items[0], ImportRejection)
    assert items[0].code == "invalid_shape"
