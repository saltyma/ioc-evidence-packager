"""Deterministic structured matching over normalized evidence observables."""

import hashlib

from ioc_evidence_packager.domain.analysis import (
    AnalysisRunId,
    MatchExplanation,
    Sighting,
    SightingId,
)
from ioc_evidence_packager.domain.evidence import EvidenceRecord
from ioc_evidence_packager.domain.observables import Observable
from ioc_evidence_packager.matching.recipes import SearchRecipe


def find_direct_sightings(
    run_id: AnalysisRunId,
    lead: Observable,
    evidence: tuple[EvidenceRecord, ...],
    recipe: SearchRecipe,
) -> tuple[Sighting, ...]:
    """Return exact, type-safe matches in recipe-compatible declared fields."""

    sightings: list[Sighting] = []
    for record in evidence:
        for observable in record.observables:
            if observable.kind != lead.observable_type.value:
                continue
            if observable.canonical != lead.canonical_value:
                continue
            step = recipe.step_for(observable.field_path)
            if step is None:
                continue
            identity = "|".join(
                (
                    str(run_id),
                    str(record.case_id),
                    str(record.evidence_id),
                    str(lead.observable_id),
                    recipe.recipe_id,
                    recipe.version,
                    recipe.rule_id,
                    observable.field_path,
                )
            )
            sighting_id = SightingId(f"sighting-{hashlib.sha256(identity.encode()).hexdigest()}")
            sightings.append(
                Sighting(
                    sighting_id=sighting_id,
                    run_id=run_id,
                    case_id=record.case_id,
                    evidence_id=record.evidence_id,
                    observable_id=lead.observable_id,
                    observable_type=lead.observable_type,
                    recipe_id=recipe.recipe_id,
                    recipe_version=recipe.version,
                    step_id=step.step_id,
                    rule_id=recipe.rule_id,
                    field_path=observable.field_path,
                    original_value=observable.original,
                    normalized_value=observable.canonical,
                    explanation=MatchExplanation(
                        template_id="direct_exact_match/1",
                        text=(
                            f"The normalized {lead.observable_type.value} value exactly matches "
                            f"the case lead in declared field {observable.field_path}."
                        ),
                        parameters=tuple(
                            sorted(
                                (
                                    ("lead", lead.canonical_value),
                                    ("field_path", observable.field_path),
                                    ("comparison", "exact-normalized"),
                                )
                            )
                        ),
                    ),
                )
            )
    return tuple(
        sorted(
            sightings,
            key=lambda item: (
                str(item.evidence_id),
                item.field_path,
                str(item.sighting_id),
            ),
        )
    )
