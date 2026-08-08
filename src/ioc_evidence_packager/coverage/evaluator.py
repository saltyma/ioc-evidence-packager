"""Deterministic six-state evidence coverage evaluator."""

import hashlib
from collections import Counter

from ioc_evidence_packager.domain.analysis import (
    AnalysisRunId,
    CoverageCell,
    CoverageCellId,
    CoverageReason,
    CoverageState,
    Sighting,
)
from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import PreviewStatus, SourcePreview
from ioc_evidence_packager.matching.recipes import RecipeStep, SearchRecipe


def evaluate_coverage(
    run_id: AnalysisRunId,
    case_id: CaseId,
    recipe: SearchRecipe,
    previews: tuple[SourcePreview, ...],
    evidence: tuple[EvidenceRecord, ...],
    rejections: tuple[ImportRejection, ...],
    sightings: tuple[Sighting, ...],
) -> tuple[CoverageCell, ...]:
    """Evaluate recipe steps and supplied-source diagnostics using fixed precedence."""

    cells = [
        _step_cell(run_id, case_id, recipe, step, previews, evidence, rejections, sightings)
        for step in recipe.steps
    ]
    cells.extend(_diagnostic_cells(run_id, case_id, recipe, previews))
    return tuple(cells)


def _step_cell(
    run_id: AnalysisRunId,
    case_id: CaseId,
    recipe: SearchRecipe,
    step: RecipeStep,
    previews: tuple[SourcePreview, ...],
    evidence: tuple[EvidenceRecord, ...],
    rejections: tuple[ImportRejection, ...],
    sightings: tuple[Sighting, ...],
) -> CoverageCell:
    compatible = tuple(preview for preview in previews if _preview_supports(preview, step))
    evidence_for_sources = tuple(
        record
        for record in evidence
        if record.source_preview_id in {preview.preview_id for preview in compatible}
    )
    rejections_for_sources = tuple(
        rejection
        for rejection in rejections
        if rejection.source_preview_id in {preview.preview_id for preview in compatible}
    )
    matches = tuple(sighting for sighting in sightings if sighting.step_id == step.step_id)

    if not compatible:
        state = CoverageState.SOURCE_NOT_PROVIDED
        reason = CoverageReason(
            code="compatible_source_missing",
            message=f"No supplied source declares fields compatible with {step.label}.",
            recovery=f"Add a supported {step.telemetry.lower()} export and preview it again.",
        )
    elif any(preview.status is PreviewStatus.FAILED for preview in compatible):
        state = CoverageState.SOURCE_FAILED
        reason = CoverageReason(
            code="compatible_source_failed",
            message=f"A supplied source for {step.label} could not be read reliably.",
            recovery="Repair or re-export the failed source, then preview and import it again.",
        )
    elif _is_partial(compatible, evidence_for_sources, rejections_for_sources):
        state = CoverageState.PARTIAL_COVERAGE
        reason = CoverageReason(
            code="compatible_search_partial",
            message=(
                f"{step.label} has incomplete coverage: {len(evidence_for_sources)} accepted "
                f"record(s), {len(rejections_for_sources)} rejected line(s), or a source warning."
            ),
            recovery=(
                "Review source warnings and rejected lines before drawing a no-match conclusion."
            ),
        )
    elif matches:
        state = CoverageState.MATCH_FOUND
        reason = CoverageReason(
            code="exact_match_found",
            message=f"{len(matches)} exact normalized match(es) were found for {step.label}.",
        )
    else:
        state = CoverageState.SEARCHED_NO_MATCH
        reason = CoverageReason(
            code="complete_search_no_match",
            message=(
                f"Compatible {step.telemetry.lower()} evidence was searched completely and "
                "produced no exact match; this is not a safety conclusion."
            ),
        )

    return CoverageCell(
        cell_id=_cell_id(run_id, step.step_id),
        run_id=run_id,
        case_id=case_id,
        recipe_id=recipe.recipe_id,
        recipe_version=recipe.version,
        step_id=step.step_id,
        step_label=step.label,
        telemetry=step.telemetry,
        state=state,
        reason=reason,
        source_preview_ids=tuple(preview.preview_id for preview in compatible),
        evidence_ids=tuple(record.evidence_id for record in evidence_for_sources),
        match_count=len(matches),
    )


def _diagnostic_cells(
    run_id: AnalysisRunId,
    case_id: CaseId,
    recipe: SearchRecipe,
    previews: tuple[SourcePreview, ...],
) -> list[CoverageCell]:
    cells: list[CoverageCell] = []
    for preview in previews:
        if preview.status not in {PreviewStatus.UNSUPPORTED, PreviewStatus.FAILED}:
            continue
        state = (
            CoverageState.FORMAT_UNSUPPORTED
            if preview.status is PreviewStatus.UNSUPPORTED
            else CoverageState.SOURCE_FAILED
        )
        code = (
            "supplied_format_unsupported"
            if state is CoverageState.FORMAT_UNSUPPORTED
            else "supplied_source_failed"
        )
        recovery = (
            "Add a mapping-capable adapter or convert this source to canonical JSONL."
            if state is CoverageState.FORMAT_UNSUPPORTED
            else "Restore read access or replace the failed source, then preview it again."
        )
        step_id = f"source_diagnostic:{preview.preview_id}"
        cells.append(
            CoverageCell(
                cell_id=_cell_id(run_id, step_id),
                run_id=run_id,
                case_id=case_id,
                recipe_id=recipe.recipe_id,
                recipe_version=recipe.version,
                step_id=step_id,
                step_label=preview.display_name,
                telemetry="Supplied source",
                state=state,
                reason=CoverageReason(
                    code=code,
                    message=(preview.warnings[0] if preview.warnings else state.value),
                    recovery=recovery,
                ),
                source_preview_ids=(preview.preview_id,),
                evidence_ids=(),
                match_count=0,
            )
        )
    return cells


def _preview_supports(preview: SourcePreview, step: RecipeStep) -> bool:
    return any(step.supports(path) for path in preview.fields)


def _is_partial(
    previews: tuple[SourcePreview, ...],
    evidence: tuple[EvidenceRecord, ...],
    rejections: tuple[ImportRejection, ...],
) -> bool:
    accepted_by_source = Counter(record.source_preview_id for record in evidence)
    rejected_by_source = Counter(rejection.source_preview_id for rejection in rejections)
    return any(
        preview.status is PreviewStatus.WARNING
        or bool(preview.warnings)
        or rejected_by_source[preview.preview_id] > 0
        or (
            preview.sample_records > 0
            and accepted_by_source[preview.preview_id] == 0
            and rejected_by_source[preview.preview_id] == 0
        )
        for preview in previews
    )


def _cell_id(run_id: AnalysisRunId, step_id: str) -> CoverageCellId:
    identity = f"{run_id}|{step_id}".encode()
    return CoverageCellId(f"coverage-{hashlib.sha256(identity).hexdigest()}")
