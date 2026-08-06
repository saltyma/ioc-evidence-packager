"""Core case value objects with no GUI or persistence dependencies."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

from ioc_evidence_packager.domain.errors import ValidationError

CaseId = NewType("CaseId", str)


class CaseStatus(StrEnum):
    """Lifecycle state of a local investigation case."""

    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    REVIEWED = "reviewed"
    EXPORTED = "exported"
    ARCHIVED = "archived"


class PrivacyMode(StrEnum):
    """Network disclosure policy attached to a case."""

    OFFLINE = "offline"
    LOCAL_INTELLIGENCE = "local_intelligence"
    SAFE_ENRICHMENT = "safe_enrichment"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class Case:
    """Durable metadata for one local investigation workspace."""

    case_id: CaseId
    title: str
    status: CaseStatus
    privacy_mode: PrivacyMode
    display_timezone: str
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime
    external_reference: str | None = None
    summary: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValidationError("Case ID cannot be empty.")
        if not self.title.strip():
            raise ValidationError("Case title cannot be empty.")
        if any(value.tzinfo is None for value in self._timestamps()):
            raise ValidationError("Case timestamps must include a timezone.")

    def _timestamps(self) -> tuple[datetime, datetime, datetime]:
        return self.created_at, self.updated_at, self.last_opened_at
