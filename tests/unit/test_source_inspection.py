"""Bounded source hashing and adapter-preview tests."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from ioc_evidence_packager.domain.sources import PreviewStatus
from ioc_evidence_packager.ingestion.inspection import SourceInspectionService


def test_canonical_fixture_is_hashed_and_explained() -> None:
    fixture = Path(__file__).parents[2] / "samples" / "input" / "canonical-demo.jsonl"

    preview = SourceInspectionService().inspect(fixture)

    assert preview.status is PreviewStatus.READY
    assert preview.adapter_id == "canonical-jsonl"
    assert preview.adapter_version == "1.0.0"
    assert preview.format_name == "Canonical event JSONL v1"
    assert preview.sample_records == 3
    assert preview.sha256 == hashlib.sha256(fixture.read_bytes()).hexdigest()
    assert preview.capabilities == (
        "observable.domain",
        "observable.ipv4",
        "observable.sha256",
        "timestamp.utc",
    )
    assert preview.earliest_time == datetime(2026, 8, 6, 9, 12, 3, tzinfo=UTC)
    assert preview.latest_time == datetime(2026, 8, 6, 9, 12, 8, tzinfo=UTC)


def test_recognized_file_with_bad_record_returns_safe_warning(tmp_path: Path) -> None:
    source = tmp_path / "partial.jsonl"
    source.write_text(
        '{"schema":"canonical-event/1.0.0","event_id":"one"}\nnot-json\n',
        encoding="utf-8",
    )

    preview = SourceInspectionService().inspect(source)

    assert preview.status is PreviewStatus.WARNING
    assert preview.sample_records == 1
    assert preview.sha256 is not None
    assert preview.warnings == ("Line 2 is not valid UTF-8 JSON.",)


def test_unknown_format_is_hashed_but_not_claimed_as_evidence(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("analyst notes only", encoding="utf-8")

    preview = SourceInspectionService().inspect(source)

    assert preview.status is PreviewStatus.UNSUPPORTED
    assert preview.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert preview.adapter_id is None
    assert preview.sample_records == 0


def test_missing_file_returns_failed_preview_without_digest(tmp_path: Path) -> None:
    preview = SourceInspectionService().inspect(tmp_path / "missing.jsonl")

    assert preview.status is PreviewStatus.FAILED
    assert preview.sha256 is None
    assert preview.warnings
