"""Adapter probe contracts used before any source is ingested."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


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
    """Minimal contract for identifying one evidence format safely."""

    adapter_id: str
    version: str

    def probe(self, path: Path) -> ProbeResult: ...
