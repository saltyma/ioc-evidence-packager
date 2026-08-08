"""Immutable IOC matching and evidence-coverage values."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

from ioc_evidence_packager.domain.evidence import EvidenceId
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.observables import ObservableId, ObservableType
from ioc_evidence_packager.domain.sources import SourcePreviewId

AnalysisRunId = NewType("AnalysisRunId", str)
SightingId = NewType("SightingId", str)
CoverageCellId = NewType("CoverageCellId", str)


class CoverageState(StrEnum):
    """Normative coverage states; no state implies that a case is safe."""

    MATCH_FOUND = "MATCH_FOUND"
    SEARCHED_NO_MATCH = "SEARCHED_NO_MATCH"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    SOURCE_NOT_PROVIDED = "SOURCE_NOT_PROVIDED"
    SOURCE_FAILED = "SOURCE_FAILED"
    FORMAT_UNSUPPORTED = "FORMAT_UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class MatchExplanation:
    """Versioned, structured explanation for one direct exact match."""

    template_id: str
    text: str
    parameters: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class Sighting:
    """A direct linkage between the case lead and one evidence observable."""

    sighting_id: SightingId
    run_id: AnalysisRunId
    case_id: CaseId
    evidence_id: EvidenceId
    observable_id: ObservableId
    observable_type: ObservableType
    recipe_id: str
    recipe_version: str
    step_id: str
    rule_id: str
    field_path: str
    original_value: str
    normalized_value: str
    explanation: MatchExplanation


@dataclass(frozen=True, slots=True)
class CoverageReason:
    """Machine-stable reason plus analyst-facing explanation and recovery action."""

    code: str
    message: str
    recovery: str | None = None


@dataclass(frozen=True, slots=True)
class CoverageCell:
    """One inspectable recipe-step or source-diagnostic coverage result."""

    cell_id: CoverageCellId
    run_id: AnalysisRunId
    case_id: CaseId
    recipe_id: str
    recipe_version: str
    step_id: str
    step_label: str
    telemetry: str
    state: CoverageState
    reason: CoverageReason
    source_preview_ids: tuple[SourcePreviewId, ...]
    evidence_ids: tuple[EvidenceId, ...]
    match_count: int


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    """Durable output of one deterministic recipe and coverage evaluation."""

    run_id: AnalysisRunId
    case_id: CaseId
    recipe_id: str
    recipe_version: str
    input_fingerprint: str
    completed_at: datetime
    sightings: tuple[Sighting, ...]
    coverage: tuple[CoverageCell, ...]

    @property
    def direct_evidence_ids(self) -> frozenset[EvidenceId]:
        return frozenset(sighting.evidence_id for sighting in self.sightings)

    @property
    def warning_count(self) -> int:
        warning_states = {
            CoverageState.PARTIAL_COVERAGE,
            CoverageState.SOURCE_NOT_PROVIDED,
            CoverageState.SOURCE_FAILED,
            CoverageState.FORMAT_UNSUPPORTED,
        }
        return sum(cell.state in warning_states for cell in self.coverage)
