"""IOC recipe execution and durable coverage orchestration."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from ioc_evidence_packager.application.ports import AnalysisRepository
from ioc_evidence_packager.coverage import evaluate_coverage
from ioc_evidence_packager.domain.analysis import AnalysisRunId, AnalysisSnapshot
from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.observables import Observable
from ioc_evidence_packager.domain.sources import SourcePreview
from ioc_evidence_packager.matching import find_direct_sightings, recipe_for


class AnalysisService:
    """Runs or reuses deterministic matching and coverage analysis."""

    def __init__(self, repository: AnalysisRepository) -> None:
        self._repository = repository

    def ensure_analysis(
        self,
        case_id: CaseId,
        lead: Observable,
        previews: tuple[SourcePreview, ...],
        evidence: tuple[EvidenceRecord, ...],
        rejections: tuple[ImportRejection, ...],
        *,
        force: bool = False,
        requested_start: datetime | None = None,
        requested_end: datetime | None = None,
    ) -> AnalysisSnapshot:
        if requested_start or requested_end:
            evidence = tuple(
                record
                for record in evidence
                if record.occurred_at is not None
                and (requested_start is None or record.occurred_at >= requested_start)
                and (requested_end is None or record.occurred_at <= requested_end)
            )
            scope_warning = (
                f"Requested inclusive window: {requested_start} to {requested_end}. "
                "Undated records are excluded; source continuity is not established."
            )
            previews = tuple(
                replace(preview, warnings=preview.warnings + (scope_warning,))
                for preview in previews
            )
        recipe = recipe_for(lead.observable_type)
        fingerprint = _input_fingerprint(lead, previews, evidence, rejections)
        existing = self._repository.latest_analysis(case_id)
        if (
            not force
            and existing is not None
            and existing.recipe_id == recipe.recipe_id
            and existing.recipe_version == recipe.version
            and existing.input_fingerprint == fingerprint
        ):
            return existing

        run_id = AnalysisRunId(f"analysis-{uuid4()}")
        sightings = find_direct_sightings(run_id, lead, evidence, recipe)
        coverage = evaluate_coverage(
            run_id,
            case_id,
            recipe,
            previews,
            evidence,
            rejections,
            sightings,
        )
        snapshot = AnalysisSnapshot(
            run_id=run_id,
            case_id=case_id,
            recipe_id=recipe.recipe_id,
            recipe_version=recipe.version,
            input_fingerprint=fingerprint,
            completed_at=datetime.now(UTC),
            sightings=sightings,
            coverage=coverage,
        )
        self._repository.save_analysis(snapshot)
        return snapshot

    def latest_analysis(self, case_id: CaseId) -> AnalysisSnapshot | None:
        return self._repository.latest_analysis(case_id)


def _input_fingerprint(
    lead: Observable,
    previews: tuple[SourcePreview, ...],
    evidence: tuple[EvidenceRecord, ...],
    rejections: tuple[ImportRejection, ...],
) -> str:
    payload = {
        "lead": [
            str(lead.observable_id),
            lead.observable_type.value,
            lead.canonical_value,
        ],
        "sources": [
            [
                str(preview.preview_id),
                preview.sha256,
                preview.status.value,
                list(preview.fields),
                list(preview.warnings),
            ]
            for preview in sorted(previews, key=lambda item: str(item.preview_id))
        ],
        "evidence": [str(record.evidence_id) for record in evidence],
        "rejections": [str(rejection.rejection_id) for rejection in rejections],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
