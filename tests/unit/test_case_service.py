"""Unit tests for framework-independent case use cases."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from ioc_evidence_packager.application.services import CaseService, NewCaseRequest
from ioc_evidence_packager.domain.errors import CaseNotFoundError, ValidationError
from ioc_evidence_packager.domain.models import Case, CaseId, PrivacyMode


class MemoryCaseRepository:
    def __init__(self) -> None:
        self.cases: dict[CaseId, Case] = {}

    def add(self, case: Case) -> None:
        self.cases[case.case_id] = case

    def get(self, case_id: CaseId) -> Case | None:
        return self.cases.get(case_id)

    def list_recent(self, limit: int) -> list[Case]:
        return sorted(
            self.cases.values(),
            key=lambda case: (case.last_opened_at, str(case.case_id)),
            reverse=True,
        )[:limit]

    def update_last_opened(self, case_id: CaseId, opened_at: datetime) -> Case | None:
        case = self.cases.get(case_id)
        if case is None:
            return None
        updated = replace(case, updated_at=opened_at, last_opened_at=opened_at)
        self.cases[case_id] = updated
        return updated


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class FixedIds:
    def new_case_id(self) -> CaseId:
        return CaseId("case-fixed")


def test_create_case_normalizes_metadata_and_defaults_offline() -> None:
    moment = datetime(2026, 8, 6, 14, 0, tzinfo=UTC)
    repository = MemoryCaseRepository()
    service = CaseService(repository, clock=FixedClock(moment), id_generator=FixedIds())

    case = service.create_case(
        NewCaseRequest(
            title="  Suspicious   hash investigation ",
            external_reference="  INC-1042  ",
            summary="  Initial triage only.  ",
        )
    )

    assert case.case_id == CaseId("case-fixed")
    assert case.title == "Suspicious hash investigation"
    assert case.external_reference == "INC-1042"
    assert case.summary == "Initial triage only."
    assert case.privacy_mode is PrivacyMode.OFFLINE
    assert case.created_at == moment
    assert repository.get(case.case_id) == case


@pytest.mark.parametrize("title", ["", "   ", "\n\t"])
def test_create_case_rejects_an_empty_title(title: str) -> None:
    service = CaseService(MemoryCaseRepository())

    with pytest.raises(ValidationError, match="Case title is required"):
        service.create_case(NewCaseRequest(title=title))


def test_open_case_updates_last_opened_time() -> None:
    initial = datetime(2026, 8, 6, 14, 0, tzinfo=UTC)
    clock = FixedClock(initial)
    repository = MemoryCaseRepository()
    service = CaseService(repository, clock=clock, id_generator=FixedIds())
    created = service.create_case(NewCaseRequest(title="Case"))

    clock.value = initial + timedelta(minutes=5)
    opened = service.open_case(created.case_id)

    assert opened.last_opened_at == clock.value
    assert opened.updated_at == clock.value


def test_open_case_reports_missing_identifier() -> None:
    service = CaseService(MemoryCaseRepository())

    with pytest.raises(CaseNotFoundError, match="case-missing"):
        service.open_case(CaseId("case-missing"))


def test_recent_case_limit_is_bounded() -> None:
    service = CaseService(MemoryCaseRepository())

    with pytest.raises(ValidationError, match="between 1 and 100"):
        service.list_recent_cases(0)
