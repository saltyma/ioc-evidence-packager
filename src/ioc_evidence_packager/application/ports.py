"""Application-facing interfaces implemented by infrastructure adapters."""

from datetime import datetime
from typing import Protocol

from ioc_evidence_packager.domain.models import Case, CaseId
from ioc_evidence_packager.domain.observables import Observable, ObservableId
from ioc_evidence_packager.domain.sources import SourcePreview


class CaseRepository(Protocol):
    """Persistence operations required by case use cases."""

    def add(self, case: Case) -> None: ...

    def get(self, case_id: CaseId) -> Case | None: ...

    def list_recent(self, limit: int) -> list[Case]: ...

    def update_last_opened(self, case_id: CaseId, opened_at: datetime) -> Case | None: ...

    def add_investigation(
        self,
        case: Case,
        lead: Observable,
        source_previews: tuple[SourcePreview, ...],
    ) -> None: ...

    def get_lead(self, case_id: CaseId) -> Observable | None: ...

    def list_source_previews(self, case_id: CaseId) -> list[SourcePreview]: ...


class Clock(Protocol):
    """Clock seam that makes timestamps deterministic in tests."""

    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    """Identifier seam that makes case creation deterministic in tests."""

    def new_case_id(self) -> CaseId: ...

    def new_observable_id(self) -> ObservableId: ...
