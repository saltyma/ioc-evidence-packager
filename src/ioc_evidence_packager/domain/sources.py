"""Safe source-preview values produced before evidence ingestion."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import NewType

SourcePreviewId = NewType("SourcePreviewId", str)


class PreviewStatus(StrEnum):
    """Pre-ingestion interpretation of a selected source."""

    READY = "ready"
    WARNING = "warning"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SourcePreview:
    """Hash, adapter, capabilities, and limitations known before import."""

    preview_id: SourcePreviewId
    path: Path
    display_name: str
    byte_size: int
    sha256: str | None
    status: PreviewStatus
    adapter_id: str | None
    adapter_version: str | None
    format_name: str | None
    sample_records: int
    fields: tuple[str, ...]
    capabilities: tuple[str, ...]
    warnings: tuple[str, ...]
    earliest_time: datetime | None = None
    latest_time: datetime | None = None
