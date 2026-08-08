"""Immutable report, export-history, and verification values."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import NewType

from ioc_evidence_packager.domain.analysis import AnalysisSnapshot
from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import Case, CaseId
from ioc_evidence_packager.domain.observables import Observable
from ioc_evidence_packager.domain.sources import SourcePreview

ExportId = NewType("ExportId", str)


class ExportProfile(StrEnum):
    """Filesystem capsule projections implemented by the desktop."""

    FULL_INTERNAL = "full-internal"
    REDACTED_SHAREABLE = "redacted-shareable"


@dataclass(frozen=True, slots=True)
class CaseReport:
    """Shared immutable semantic input for every capsule renderer."""

    case: Case
    lead: Observable | None
    source_previews: tuple[SourcePreview, ...]
    evidence: tuple[EvidenceRecord, ...]
    rejections: tuple[ImportRejection, ...]
    analysis: AnalysisSnapshot


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """Finalized artifact integrity metadata."""

    path: str
    media_type: str
    role: str
    byte_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CapsuleResult:
    """Successfully published and re-verified Case Capsule."""

    export_id: ExportId
    case_id: CaseId
    profile: ExportProfile
    destination: Path
    created_at: datetime
    manifest_sha256: str
    artifacts: tuple[ArtifactDigest, ...]


@dataclass(frozen=True, slots=True)
class ExportRecord:
    """Durable history of a successfully published capsule."""

    export_id: ExportId
    case_id: CaseId
    profile: ExportProfile
    destination: Path
    created_at: datetime
    manifest_sha256: str
    artifact_count: int


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Integrity verifier outcome safe to present in the GUI."""

    capsule_path: Path
    valid: bool
    checked_artifacts: int
    messages: tuple[str, ...]
