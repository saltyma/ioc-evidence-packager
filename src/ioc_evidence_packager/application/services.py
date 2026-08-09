"""Headless application services for local case management."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from ioc_evidence_packager.application.ports import CaseRepository, Clock, IdGenerator
from ioc_evidence_packager.domain.errors import CaseNotFoundError, ValidationError
from ioc_evidence_packager.domain.models import Case, CaseId, CaseStatus, PrivacyMode
from ioc_evidence_packager.domain.observables import Observable, ObservableId, parse_observable
from ioc_evidence_packager.domain.sources import PreviewStatus, SourcePreview
from ioc_evidence_packager.domain.timezones import normalize_display_timezone

MAX_TITLE_LENGTH = 120
MAX_REFERENCE_LENGTH = 120
MAX_SUMMARY_LENGTH = 2_000
MAX_TIMEZONE_LENGTH = 64


@dataclass(frozen=True, slots=True)
class NewCaseRequest:
    """Validated-at-the-boundary data used to create a case."""

    title: str
    external_reference: str | None = None
    summary: str | None = None
    display_timezone: str = "UTC"
    privacy_mode: PrivacyMode = PrivacyMode.OFFLINE


@dataclass(frozen=True, slots=True)
class NewInvestigationRequest:
    """Case metadata, validated lead input, and completed source previews."""

    case: NewCaseRequest
    lead_value: str
    source_previews: tuple[SourcePreview, ...]


@dataclass(frozen=True, slots=True)
class InvestigationSetup:
    """Durable case orientation data used by the desktop workspace."""

    case: Case
    lead: Observable | None
    source_previews: tuple[SourcePreview, ...]


class SystemClock:
    """Production UTC clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class UUIDGenerator:
    """Production case identifier generator."""

    def new_case_id(self) -> CaseId:
        return CaseId(f"case-{uuid4()}")

    def new_observable_id(self) -> ObservableId:
        return ObservableId(f"observable-{uuid4()}")


class CaseService:
    """Coordinates case creation and opening without depending on Qt."""

    def __init__(
        self,
        repository: CaseRepository,
        *,
        clock: Clock | None = None,
        id_generator: IdGenerator | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or SystemClock()
        self._id_generator = id_generator or UUIDGenerator()

    def create_case(self, request: NewCaseRequest) -> Case:
        case = self._build_case(request)
        self._repository.add(case)
        return case

    def create_investigation(self, request: NewInvestigationRequest) -> InvestigationSetup:
        parsed = parse_observable(request.lead_value)
        if not request.source_previews:
            raise ValidationError("Select and preview at least one evidence source.")
        if not any(
            preview.status in {PreviewStatus.READY, PreviewStatus.WARNING}
            for preview in request.source_previews
        ):
            raise ValidationError("At least one source must have a recognized adapter.")
        paths = [preview.path for preview in request.source_previews]
        if len(paths) != len(set(paths)):
            raise ValidationError("The same source path cannot be added twice.")

        case = self._build_case(request.case)
        lead = Observable(
            observable_id=self._id_generator.new_observable_id(),
            observable_type=parsed.observable_type,
            original_value=parsed.original_value,
            canonical_value=parsed.canonical_value,
        )
        self._repository.add_investigation(case, lead, request.source_previews)
        return InvestigationSetup(case=case, lead=lead, source_previews=request.source_previews)

    def _build_case(self, request: NewCaseRequest) -> Case:
        title = _required_text(request.title, "Case title", MAX_TITLE_LENGTH)
        external_reference = _optional_text(
            request.external_reference,
            "External reference",
            MAX_REFERENCE_LENGTH,
        )
        summary = _optional_text(request.summary, "Summary", MAX_SUMMARY_LENGTH)
        display_timezone = normalize_display_timezone(
            _required_text(request.display_timezone, "Display timezone", MAX_TIMEZONE_LENGTH)
        )
        now = self._clock.now()
        case = Case(
            case_id=self._id_generator.new_case_id(),
            title=title,
            external_reference=external_reference,
            summary=summary,
            status=CaseStatus.DRAFT,
            privacy_mode=request.privacy_mode,
            display_timezone=display_timezone,
            created_at=now,
            updated_at=now,
            last_opened_at=now,
        )
        return case

    def list_recent_cases(self, limit: int = 12) -> list[Case]:
        if limit < 1 or limit > 100:
            raise ValidationError("Recent case limit must be between 1 and 100.")
        return self._repository.list_recent(limit)

    def open_case(self, case_id: CaseId) -> Case:
        case = self._repository.update_last_opened(case_id, self._clock.now())
        if case is None:
            raise CaseNotFoundError(f"Case does not exist: {case_id}")
        return case

    def open_investigation(self, case_id: CaseId) -> InvestigationSetup:
        case = self.open_case(case_id)
        return InvestigationSetup(
            case=case,
            lead=self._repository.get_lead(case_id),
            source_previews=tuple(self._repository.list_source_previews(case_id)),
        )

    def update_preferences(
        self,
        case_id: CaseId,
        *,
        display_timezone: str,
        privacy_mode: PrivacyMode,
    ) -> Case:
        timezone = normalize_display_timezone(
            _required_text(display_timezone, "Display timezone", MAX_TIMEZONE_LENGTH)
        )
        case = self._repository.update_preferences(
            case_id,
            display_timezone=timezone,
            privacy_mode=privacy_mode,
            updated_at=self._clock.now(),
        )
        if case is None:
            raise CaseNotFoundError(f"Case does not exist: {case_id}")
        return case


def _required_text(value: str, label: str, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValidationError(f"{label} is required.")
    if len(normalized) > maximum:
        raise ValidationError(f"{label} must be {maximum} characters or fewer.")
    return normalized


def _optional_text(value: str | None, label: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise ValidationError(f"{label} must be {maximum} characters or fewer.")
    return normalized
