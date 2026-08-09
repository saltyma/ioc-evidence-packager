"""Detection and mapping tests for the Phase 5 practical adapters."""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import PreviewStatus
from ioc_evidence_packager.ingestion.inspection import SourceInspectionService
from ioc_evidence_packager.ingestion.registry import AdapterRegistry

DEMO = Path(__file__).parents[2] / "samples" / "input" / "demo-investigation"
PRACTICAL_FIXTURES = (
    ("07-suricata-eve.jsonl", "suricata-eve-jsonl", "dns.answers[0]"),
    ("08-wazuh-alerts.jsonl", "wazuh-alert-jsonl", "network.destination_ip"),
    ("09-hayabusa-results.jsonl", "hayabusa-jsonl", "file.sha256"),
    ("10-generic-array.json", "generic-json-array", "network.destination_ip"),
    ("11-mapped-proxy.csv", "mapped-csv", "network.domain"),
)


@pytest.mark.parametrize(("name", "adapter_id", "mapped_field"), PRACTICAL_FIXTURES)
def test_practical_fixture_is_detected_with_searchable_fields(
    name: str,
    adapter_id: str,
    mapped_field: str,
) -> None:
    preview = SourceInspectionService().inspect(DEMO / name)

    assert preview.status is PreviewStatus.READY
    assert preview.adapter_id == adapter_id
    assert preview.sample_records == 2
    assert mapped_field in preview.fields
    assert preview.earliest_time is not None
    assert preview.latest_time is not None


@pytest.mark.parametrize(("name", "adapter_id", "_mapped_field"), PRACTICAL_FIXTURES)
def test_practical_adapter_yields_source_linked_evidence(
    name: str,
    adapter_id: str,
    _mapped_field: str,
) -> None:
    registry = AdapterRegistry()
    preview = SourceInspectionService(registry).inspect(DEMO / name)
    adapter = registry.adapter_for(adapter_id)

    assert adapter is not None
    items = list(adapter.iter_items(CaseId("case-phase5"), preview, datetime.now(UTC)))
    assert len(items) == 2
    assert all(isinstance(item, EvidenceRecord) for item in items)
    assert all(item.source_sha256 == preview.sha256 for item in items)
    assert all(item.raw_json for item in items)
    assert all(item.occurred_at is not None for item in items)


def test_unmapped_csv_remains_explicitly_unsupported() -> None:
    preview = SourceInspectionService().inspect(DEMO / "06-unsupported-siem-export.csv")

    assert preview.status is PreviewStatus.UNSUPPORTED
    assert preview.adapter_id is None


def test_mapped_csv_uses_physical_csv_line_numbers() -> None:
    registry = AdapterRegistry()
    preview = SourceInspectionService(registry).inspect(DEMO / "11-mapped-proxy.csv")
    adapter = registry.adapter_for(preview.adapter_id)

    assert adapter is not None
    records = list(adapter.iter_items(CaseId("case-phase5"), preview, datetime.now(UTC)))
    assert isinstance(records[0], EvidenceRecord)
    assert records[0].line_number == 2
    assert records[0].declared_position_kind == "line"
    assert records[0].observables[0].canonical == "203.0.113.42"


def test_offset_timestamp_is_normalized_and_naive_timestamp_stays_undated(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mixed-timezones.json"
    source.write_text(
        "["
        '{"id":"aware","timestamp":"2026-08-06T10:12:00+01:00",'
        '"action":"connection","destination_ip":"203.0.113.42"},'
        '{"id":"naive","timestamp":"2026-08-06T09:13:00",'
        '"action":"connection","destination_ip":"198.51.100.25"}'
        "]",
        encoding="utf-8",
    )
    registry = AdapterRegistry()
    preview = SourceInspectionService(registry).inspect(source)
    adapter = registry.adapter_for(preview.adapter_id)

    assert preview.status is PreviewStatus.WARNING
    assert preview.earliest_time == datetime(2026, 8, 6, 9, 12, tzinfo=UTC)
    assert "Mapped timestamp has no timezone; event remains undated." in preview.warnings
    assert adapter is not None
    records = list(adapter.iter_items(CaseId("case-time"), preview, datetime.now(UTC)))
    assert isinstance(records[0], EvidenceRecord) and records[0].occurred_at is not None
    assert isinstance(records[1], EvidenceRecord) and records[1].occurred_at is None


def test_detected_jsonl_schema_drift_becomes_a_structured_rejection(tmp_path: Path) -> None:
    source = tmp_path / "suricata-drift.jsonl"
    source.write_text(
        '{"timestamp":"2026-08-06T09:12:10Z","event_type":"flow",'
        '"flow_id":1,"dest_ip":"203.0.113.42"}\n'
        '{"timestamp":"2026-08-06T09:12:11Z","unexpected":true}\n',
        encoding="utf-8",
    )
    registry = AdapterRegistry()
    preview = SourceInspectionService(registry).inspect(source)
    adapter = registry.adapter_for(preview.adapter_id)

    assert preview.status is PreviewStatus.WARNING
    assert adapter is not None
    items = list(adapter.iter_items(CaseId("case-drift"), preview, datetime.now(UTC)))
    assert isinstance(items[0], EvidenceRecord)
    assert isinstance(items[1], ImportRejection)
    assert items[1].code == "adapter_schema_drift"


def test_changed_csv_mapping_profile_is_rejected_after_preview(tmp_path: Path) -> None:
    source = tmp_path / "mapped.csv"
    sidecar = tmp_path / "mapped.csv.ioc-map.json"
    shutil.copyfile(DEMO / "11-mapped-proxy.csv", source)
    shutil.copyfile(DEMO / "11-mapped-proxy.csv.ioc-map.json", sidecar)
    registry = AdapterRegistry()
    preview = SourceInspectionService(registry).inspect(source)
    adapter = registry.adapter_for(preview.adapter_id)
    sidecar.write_text(
        sidecar.read_text(encoding="utf-8").replace(
            '"synthetic-proxy/1.0.0"', '"synthetic-proxy/1.0.1"'
        ),
        encoding="utf-8",
    )

    assert adapter is not None
    items = list(adapter.iter_items(CaseId("case-map-change"), preview, datetime.now(UTC)))
    assert len(items) == 1
    assert isinstance(items[0], ImportRejection)
    assert items[0].code == "mapping_profile_changed"
