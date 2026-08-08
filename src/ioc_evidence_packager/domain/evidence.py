"""Immutable evidence, provenance, import-run, and rejection values."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import NewType

from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import SourcePreviewId

EvidenceId = NewType("EvidenceId", str)
ImportRunId = NewType("ImportRunId", str)
RejectionId = NewType("RejectionId", str)


class ImportStatus(StrEnum):
    """Terminal-safe state of one evidence import attempt."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EvidenceObservable:
    """Observable exactly as declared by one canonical source record."""

    kind: str
    field_path: str
    original: str
    canonical: str


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Accepted canonical event with direct file and source provenance."""

    evidence_id: EvidenceId
    case_id: CaseId
    source_preview_id: SourcePreviewId
    source_name: str
    source_path: Path
    source_sha256: str | None
    line_number: int
    event_id: str
    occurred_at: datetime | None
    category: str
    action: str
    host_name: str | None
    user_name: str | None
    observables: tuple[EvidenceObservable, ...]
    declared_source_id: str
    declared_position_kind: str
    declared_position_value: str
    warnings: tuple[str, ...]
    raw_json: str
    imported_at: datetime


@dataclass(frozen=True, slots=True)
class ImportRejection:
    """Structured reason one source line could not become evidence."""

    rejection_id: RejectionId
    case_id: CaseId
    source_preview_id: SourcePreviewId
    source_name: str
    line_number: int
    code: str
    message: str
    raw_excerpt: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ImportRun:
    """One auditable import attempt."""

    run_id: ImportRunId
    case_id: CaseId
    status: ImportStatus
    started_at: datetime


@dataclass(frozen=True, slots=True)
class ImportProgress:
    """Monotonic progress snapshot safe to send across a worker boundary."""

    current_source: str
    processed_sources: int
    total_sources: int
    accepted_records: int
    rejected_records: int


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """Terminal import result plus current case-level durable totals."""

    run_id: ImportRunId
    status: ImportStatus
    processed_sources: int
    accepted_records: int
    rejected_records: int
    stored_evidence_records: int
    stored_rejections: int


@dataclass(frozen=True, slots=True)
class EvidenceCounts:
    """Current durable evidence/rejection counts for a case."""

    evidence: int
    rejections: int
