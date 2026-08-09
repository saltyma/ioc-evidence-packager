"""Application-facing interfaces implemented by infrastructure adapters."""

from datetime import datetime
from typing import Protocol

from ioc_evidence_packager.domain.analysis import AnalysisSnapshot
from ioc_evidence_packager.domain.evidence import (
    EvidenceCounts,
    EvidenceRecord,
    ImportRejection,
    ImportRun,
    ImportRunId,
    ImportStatus,
)
from ioc_evidence_packager.domain.models import Case, CaseId, PrivacyMode
from ioc_evidence_packager.domain.observables import Observable, ObservableId
from ioc_evidence_packager.domain.sources import SourcePreview
from ioc_evidence_packager.domain.workspace import (
    AssertionId,
    IntelligenceAssertion,
    RecommendationId,
    RecommendationStatus,
)
from ioc_evidence_packager.reporting.models import ExportRecord


class CaseRepository(Protocol):
    """Persistence operations required by case use cases."""

    def add(self, case: Case) -> None: ...

    def get(self, case_id: CaseId) -> Case | None: ...

    def list_recent(self, limit: int) -> list[Case]: ...

    def update_last_opened(self, case_id: CaseId, opened_at: datetime) -> Case | None: ...

    def update_preferences(
        self,
        case_id: CaseId,
        *,
        display_timezone: str,
        privacy_mode: PrivacyMode,
        updated_at: datetime,
    ) -> Case | None: ...

    def add_investigation(
        self,
        case: Case,
        lead: Observable,
        source_previews: tuple[SourcePreview, ...],
    ) -> None: ...

    def get_lead(self, case_id: CaseId) -> Observable | None: ...

    def list_source_previews(self, case_id: CaseId) -> list[SourcePreview]: ...


class EvidenceRepository(Protocol):
    """Persistence operations required by evidence import and ledger queries."""

    def begin_import(self, run: ImportRun) -> None: ...

    def append_batch(
        self,
        run_id: ImportRunId,
        records: tuple[EvidenceRecord, ...],
        rejections: tuple[ImportRejection, ...],
    ) -> None: ...

    def finish_import(
        self,
        run_id: ImportRunId,
        status: ImportStatus,
        finished_at: datetime,
        processed_sources: int,
        accepted_records: int,
        rejected_records: int,
        error_message: str | None,
    ) -> None: ...

    def list_evidence(self, case_id: CaseId, limit: int) -> list[EvidenceRecord]: ...

    def list_rejections(self, case_id: CaseId, limit: int) -> list[ImportRejection]: ...

    def counts(self, case_id: CaseId) -> EvidenceCounts: ...


class AnalysisRepository(Protocol):
    """Persistence required by deterministic IOC analysis."""

    def save_analysis(self, snapshot: AnalysisSnapshot) -> None: ...

    def latest_analysis(self, case_id: CaseId) -> AnalysisSnapshot | None: ...


class ExportRepository(Protocol):
    """Persistence required for successful Case Capsule history."""

    def add_export(self, record: ExportRecord) -> None: ...

    def list_exports(self, case_id: CaseId, limit: int) -> list[ExportRecord]: ...


class WorkspaceRepository(Protocol):
    """Persistence for analyst decisions and attributed intelligence."""

    def recommendation_states(
        self, case_id: CaseId
    ) -> dict[RecommendationId, tuple[RecommendationStatus, str | None, datetime]]: ...

    def set_recommendation_state(
        self,
        case_id: CaseId,
        recommendation_id: RecommendationId,
        status: RecommendationStatus,
        note: str | None,
        updated_at: datetime,
    ) -> None: ...

    def add_assertion(self, assertion: IntelligenceAssertion) -> None: ...

    def list_assertions(
        self, case_id: CaseId, *, include_archived: bool = False
    ) -> tuple[IntelligenceAssertion, ...]: ...

    def archive_assertion(self, case_id: CaseId, assertion_id: AssertionId) -> None: ...


class Clock(Protocol):
    """Clock seam that makes timestamps deterministic in tests."""

    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    """Identifier seam that makes case creation deterministic in tests."""

    def new_case_id(self) -> CaseId: ...

    def new_observable_id(self) -> ObservableId: ...
