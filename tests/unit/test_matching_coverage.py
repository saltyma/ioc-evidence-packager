"""Exact-match recipe and six-state coverage behavior."""

from datetime import UTC, datetime
from pathlib import Path

from ioc_evidence_packager.coverage import evaluate_coverage
from ioc_evidence_packager.domain.analysis import AnalysisRunId, CoverageState
from ioc_evidence_packager.domain.evidence import (
    EvidenceId,
    EvidenceObservable,
    EvidenceRecord,
)
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.observables import Observable, ObservableId, ObservableType
from ioc_evidence_packager.domain.sources import (
    PreviewStatus,
    SourcePreview,
    SourcePreviewId,
)
from ioc_evidence_packager.matching import find_direct_sightings, recipe_for

NOW = datetime(2026, 8, 6, 9, 12, tzinfo=UTC)
CASE_ID = CaseId("case-test")
RUN_ID = AnalysisRunId("analysis-test")
LEAD = Observable(
    observable_id=ObservableId("observable-test"),
    observable_type=ObservableType.IPV4,
    original_value="203.0.113.42",
    canonical_value="203.0.113.42",
)


def test_direct_matching_is_exact_and_recipe_field_scoped() -> None:
    recipe = recipe_for(LEAD.observable_type)
    evidence = (
        _record("exact", "203.0.113.42", "network.destination_ip", "network"),
        _record("lookalike", "203.0.113.43", "network.destination_ip", "network"),
        _record("unknown-field", "203.0.113.42", "custom.note", "custom"),
    )

    sightings = find_direct_sightings(RUN_ID, LEAD, evidence, recipe)

    assert len(sightings) == 1
    assert sightings[0].evidence_id == EvidenceId("evidence-exact")
    assert sightings[0].rule_id == "ipv4.direct.exact"
    assert sightings[0].explanation.template_id == "direct_exact_match/1"


def test_coverage_evaluator_exercises_all_six_normative_states() -> None:
    recipe = recipe_for(LEAD.observable_type)
    dns = _preview("dns", PreviewStatus.READY, ("dns.answers[]",))
    network = _preview("network", PreviewStatus.READY, ("network.destination_ip",))
    complete_evidence = (
        _record("dns-match", "203.0.113.42", "dns.answers[0]", "dns"),
        _record("network-no-match", "198.51.100.25", "network.destination_ip", "network"),
    )
    complete_sightings = find_direct_sightings(RUN_ID, LEAD, complete_evidence, recipe)
    complete = evaluate_coverage(
        RUN_ID,
        CASE_ID,
        recipe,
        (dns, network),
        complete_evidence,
        (),
        complete_sightings,
    )

    partial = _preview(
        "partial",
        PreviewStatus.WARNING,
        ("network.destination_ip",),
        warnings=("One line was malformed.",),
    )
    unsupported = _preview("unsupported", PreviewStatus.UNSUPPORTED, ())
    failed = _preview("failed", PreviewStatus.FAILED, (), warnings=("Unreadable.",))
    partial_evidence = (
        _record(
            "partial-match",
            "203.0.113.42",
            "network.destination_ip",
            "partial",
        ),
    )
    partial_sightings = find_direct_sightings(RUN_ID, LEAD, partial_evidence, recipe)
    limited = evaluate_coverage(
        RUN_ID,
        CASE_ID,
        recipe,
        (partial, unsupported, failed),
        partial_evidence,
        (),
        partial_sightings,
    )

    states = {cell.state for cell in complete + limited}
    assert states == set(CoverageState)


def _record(
    identity: str,
    canonical: str,
    field_path: str,
    source: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=EvidenceId(f"evidence-{identity}"),
        case_id=CASE_ID,
        source_preview_id=SourcePreviewId(f"preview-{source}"),
        source_name=f"{source}.jsonl",
        source_path=Path(f"{source}.jsonl"),
        source_sha256="a" * 64,
        line_number=1,
        event_id=f"event-{identity}",
        occurred_at=NOW,
        category="network",
        action="connection",
        host_name="WS-TEST",
        user_name=None,
        observables=(
            EvidenceObservable(
                kind="ipv4",
                field_path=field_path,
                original=canonical,
                canonical=canonical,
            ),
        ),
        declared_source_id=source,
        declared_position_kind="line",
        declared_position_value="1",
        warnings=(),
        raw_json="{}",
        imported_at=NOW,
    )


def _preview(
    identity: str,
    status: PreviewStatus,
    fields: tuple[str, ...],
    *,
    warnings: tuple[str, ...] = (),
) -> SourcePreview:
    return SourcePreview(
        preview_id=SourcePreviewId(f"preview-{identity}"),
        path=Path(f"{identity}.jsonl"),
        display_name=f"{identity}.jsonl",
        byte_size=100,
        sha256="b" * 64,
        status=status,
        adapter_id="canonical-jsonl" if status is not PreviewStatus.UNSUPPORTED else None,
        adapter_version="1.0.0" if status is not PreviewStatus.UNSUPPORTED else None,
        format_name="Canonical event JSONL v1" if fields else None,
        sample_records=1 if fields else 0,
        fields=fields,
        capabilities=("observable.ipv4",) if fields else (),
        warnings=warnings,
        earliest_time=NOW if fields else None,
        latest_time=NOW if fields else None,
    )
