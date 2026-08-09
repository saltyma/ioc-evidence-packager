"""Qt worker adapters for source preview and cancellable evidence import."""

from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ioc_evidence_packager.application.evidence_service import EvidenceService
from ioc_evidence_packager.application.report_service import ReportService
from ioc_evidence_packager.application.services import InvestigationSetup
from ioc_evidence_packager.application.workspace_service import WorkspaceService
from ioc_evidence_packager.domain.analysis import AnalysisSnapshot
from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import Case, CaseId
from ioc_evidence_packager.domain.sources import SourcePreview
from ioc_evidence_packager.domain.workspace import (
    IntelligenceAssertion,
    Recommendation,
    RelationshipSnapshot,
)
from ioc_evidence_packager.ingestion import SourceInspectionService
from ioc_evidence_packager.reporting.models import ExportProfile


class SourcePreviewSignals(QObject):
    """Queued worker outcomes delivered safely to the GUI thread."""

    completed = Signal(str, object)
    failed = Signal(str, str)


class SourcePreviewWorker(QRunnable):
    """Hash and probe one source away from the Qt event loop."""

    def __init__(self, service: SourceInspectionService, path: Path) -> None:
        super().__init__()
        self._service = service
        self._path = path
        self.signals = SourcePreviewSignals()

    @Slot()
    def run(self) -> None:
        try:
            preview = self._service.inspect(self._path)
        except Exception as error:  # noqa: BLE001 - keep worker failures out of the Qt loop
            self.signals.failed.emit(str(self._path), str(error))
            return
        self.signals.completed.emit(str(self._path), preview)


class EvidenceImportSignals(QObject):
    """Queued progress and outcomes for one evidence import."""

    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)


class EvidenceImportWorker(QRunnable):
    """Run integrity checks and streaming import away from the GUI thread."""

    def __init__(
        self,
        service: EvidenceService,
        case_id: CaseId,
        previews: tuple[SourcePreview, ...],
    ) -> None:
        super().__init__()
        self._service = service
        self._case_id = case_id
        self._previews = previews
        self._cancelled = Event()
        self.signals = EvidenceImportSignals()

    def cancel(self) -> None:
        self._cancelled.set()

    @Slot()
    def run(self) -> None:
        try:
            summary = self._service.import_sources(
                self._case_id,
                self._previews,
                is_cancelled=self._cancelled.is_set,
                on_progress=self.signals.progress.emit,
            )
        except Exception as error:  # noqa: BLE001 - worker must not unwind into Qt
            self.signals.failed.emit(str(error))
            return
        self.signals.completed.emit(summary)


class CapsuleExportSignals(QObject):
    """Queued outcomes for one Case Capsule publication."""

    completed = Signal(object)
    failed = Signal(str)


class CapsuleExportWorker(QRunnable):
    """Render, hash, verify, and publish a capsule away from the GUI thread."""

    def __init__(
        self,
        service: ReportService,
        setup: InvestigationSetup,
        evidence: tuple[EvidenceRecord, ...],
        rejections: tuple[ImportRejection, ...],
        analysis: AnalysisSnapshot | None,
        destination: Path,
        profile: ExportProfile,
        relationships: RelationshipSnapshot,
        recommendations: tuple[Recommendation, ...],
        intelligence: tuple[IntelligenceAssertion, ...],
    ) -> None:
        super().__init__()
        self._service = service
        self._setup = setup
        self._evidence = evidence
        self._rejections = rejections
        self._analysis = analysis
        self._destination = destination
        self._profile = profile
        self._relationships = relationships
        self._recommendations = recommendations
        self._intelligence = intelligence
        self.signals = CapsuleExportSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.export_case(
                self._setup,
                self._evidence,
                self._rejections,
                self._analysis,
                self._destination,
                self._profile,
                self._relationships,
                self._recommendations,
                self._intelligence,
            )
        except Exception as error:  # noqa: BLE001 - worker must not unwind into Qt
            self.signals.failed.emit(str(error))
            return
        self.signals.completed.emit(result)


class IntelligenceLookupSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class IntelligenceLookupWorker(QRunnable):
    """Run a confirmed provider object lookup away from the Qt event loop."""

    def __init__(
        self,
        service: WorkspaceService,
        case: Case,
        observable_type: str,
        value: str,
        cache_hours: int,
    ) -> None:
        super().__init__()
        self._service = service
        self._case = case
        self._observable_type = observable_type
        self._value = value
        self._cache_hours = cache_hours
        self.signals = IntelligenceLookupSignals()

    @Slot()
    def run(self) -> None:
        try:
            assertion = self._service.query_virustotal(
                self._case,
                self._observable_type,
                self._value,
                cache_hours=self._cache_hours,
            )
        except Exception as error:  # noqa: BLE001 - worker must not unwind into Qt
            self.signals.failed.emit(str(error))
            return
        self.signals.completed.emit(assertion)
