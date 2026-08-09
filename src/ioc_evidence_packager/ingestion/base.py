"""Adapter probe contracts used before any source is ingested."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import SourcePreview

ImportItem = EvidenceRecord | ImportRejection


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Bounded evidence-format probe result."""

    recognized: bool
    format_name: str | None = None
    sample_records: int = 0
    fields: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    earliest_time: datetime | None = None
    latest_time: datetime | None = None


class EvidenceAdapter(Protocol):
    """Contract for bounded detection and source-linked record conversion."""

    adapter_id: str
    version: str

    def probe(self, path: Path) -> ProbeResult: ...

    def iter_items(
        self,
        case_id: CaseId,
        preview: SourcePreview,
        imported_at: datetime,
    ) -> Iterator[ImportItem]: ...
