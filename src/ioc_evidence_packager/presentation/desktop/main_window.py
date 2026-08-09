"""Native desktop shell and navigation coordination."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.application.analysis_service import AnalysisService
from ioc_evidence_packager.application.evidence_service import EvidenceService
from ioc_evidence_packager.application.report_service import ReportService
from ioc_evidence_packager.application.services import CaseService, InvestigationSetup
from ioc_evidence_packager.application.workspace_service import WorkspaceService
from ioc_evidence_packager.domain.analysis import AnalysisSnapshot
from ioc_evidence_packager.domain.errors import IOCEvidencePackagerError
from ioc_evidence_packager.domain.evidence import (
    EvidenceRecord,
    ImportProgress,
    ImportRejection,
    ImportSummary,
)
from ioc_evidence_packager.domain.models import Case, CaseId, PrivacyMode
from ioc_evidence_packager.domain.sources import SourcePreview
from ioc_evidence_packager.domain.workspace import (
    AssertionId,
    IntelligenceClaim,
    RecommendationId,
    RecommendationStatus,
    RelationshipSnapshot,
)
from ioc_evidence_packager.ingestion import SourceInspectionService
from ioc_evidence_packager.presentation.desktop.branding import application_icon
from ioc_evidence_packager.presentation.desktop.jobs import (
    CapsuleExportWorker,
    EvidenceImportWorker,
    IntelligenceLookupWorker,
)
from ioc_evidence_packager.presentation.desktop.settings_store import (
    DesktopPreferences,
    DesktopSettingsStore,
)
from ioc_evidence_packager.presentation.desktop.theme import desktop_stylesheet
from ioc_evidence_packager.presentation.desktop.views.coverage import CoverageView
from ioc_evidence_packager.presentation.desktop.views.dashboard import DashboardView
from ioc_evidence_packager.presentation.desktop.views.detail_dialog import DetailDialog
from ioc_evidence_packager.presentation.desktop.views.evidence import EvidenceView
from ioc_evidence_packager.presentation.desktop.views.exports import ExportsView
from ioc_evidence_packager.presentation.desktop.views.home import HomeView
from ioc_evidence_packager.presentation.desktop.views.intelligence import IntelligenceView
from ioc_evidence_packager.presentation.desktop.views.new_case import NewCaseDialog
from ioc_evidence_packager.presentation.desktop.views.recommendations import RecommendationsView
from ioc_evidence_packager.presentation.desktop.views.relationships import RelationshipsView
from ioc_evidence_packager.presentation.desktop.views.settings import SettingsView
from ioc_evidence_packager.presentation.desktop.views.sources import SourcesView
from ioc_evidence_packager.presentation.desktop.views.timeline import TimelineView
from ioc_evidence_packager.reporting.models import (
    CapsuleResult,
    ExportProfile,
)

NAVIGATION = (
    ("Dashboard", "Case summary, findings, limitations, and next actions.", "Slice 1"),
    ("Evidence", "Source-linked facts, exact matches, provenance, and raw records.", "Slice 4"),
    ("Timeline", "A deterministic chronology with direct, context, and undated lanes.", "Slice 5"),
    ("Relationships", "Bounded typed relationships with evidence-backed edges.", "v0.7"),
    (
        "Coverage",
        "Matched, searched, partial, missing, failed, and unsupported evidence.",
        "Slice 4",
    ),
    ("Intelligence", "Attributed provider assertions under the active privacy policy.", "v0.7"),
    ("Recommendations", "Deterministic next actions citing evidence and coverage gaps.", "v0.7"),
    ("Sources", "Input inventory, hashes, adapters, jobs, and diagnostics.", "Phase 5"),
    ("Exports", "Reviewed Case Capsule profiles and artifact verification.", "Slice 5"),
    ("Settings", "Case display, storage, privacy, and mapping preferences.", "v0.7"),
)


class MainWindow(QMainWindow):
    """Coordinates presentation state while delegating work to services."""

    def __init__(
        self,
        case_service: CaseService,
        evidence_service: EvidenceService,
        analysis_service: AnalysisService,
        report_service: ReportService,
        workspace_service: WorkspaceService,
        settings_store: DesktopSettingsStore,
        source_inspection_service: SourceInspectionService,
        database_path: Path,
    ) -> None:
        super().__init__()
        self._case_service = case_service
        self._evidence_service = evidence_service
        self._analysis_service = analysis_service
        self._report_service = report_service
        self._workspace_service = workspace_service
        self._settings_store = settings_store
        self._preferences = settings_store.load()
        self._source_inspection_service = source_inspection_service
        self._database_path = database_path
        self._current_case: Case | None = None
        self._current_setup: InvestigationSetup | None = None
        self._import_worker: EvidenceImportWorker | None = None
        self._import_case_id: CaseId | None = None
        self._export_worker: CapsuleExportWorker | None = None
        self._export_case_id: CaseId | None = None
        self._intelligence_worker: IntelligenceLookupWorker | None = None
        self._intelligence_case_id: CaseId | None = None
        self._records: tuple[EvidenceRecord, ...] = ()
        self._rejections: tuple[ImportRejection, ...] = ()
        self._analysis: AnalysisSnapshot | None = None
        self._relationships = RelationshipSnapshot((), ())
        self._thread_pool = QThreadPool.globalInstance()
        self._page_indices: dict[str, int] = {}
        self._nav_buttons: dict[str, QPushButton] = {}
        self.setWindowTitle("IOC Evidence Packager")
        self.setWindowIcon(application_icon())
        self.resize(1280, 820)
        self.setMinimumSize(1024, 680)
        DetailDialog.set_preferred_width(self._preferences.detail_width)
        self._apply_device_preferences()
        self._build_ui()
        self.show_home()

    @property
    def current_case(self) -> Case | None:
        return self._current_case

    @property
    def page_count(self) -> int:
        return self._pages.count()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_top_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        self._pages = QStackedWidget()
        self._build_pages()
        body.addWidget(self._pages, 1)
        root.addLayout(body, 1)
        root.addWidget(self._build_status_bar())
        self.setCentralWidget(central)

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(66)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(12)

        mark = QLabel()
        mark.setObjectName("BrandIcon")
        mark.setFixedSize(42, 42)
        mark.setPixmap(application_icon().pixmap(QSize(42, 42)))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("IOC Evidence Packager")
        title.setObjectName("BrandTitle")
        layout.addWidget(mark)
        layout.addWidget(title)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("color: #3D334D;")
        layout.addWidget(divider)
        self._case_context = QLabel("No case open")
        self._case_context.setObjectName("Muted")
        layout.addWidget(self._case_context)
        layout.addStretch(1)

        self._privacy_badge = QLabel("●  Offline")
        self._privacy_badge.setObjectName("PrivacyBadge")
        self._privacy_badge.setToolTip("The active case policy controls remote disclosure.")
        layout.addWidget(self._privacy_badge)

        self._jobs_button = QPushButton("Jobs  0")
        self._jobs_button.setEnabled(False)
        layout.addWidget(self._jobs_button)
        self._export_button = QPushButton("Export")
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(lambda: self.show_page("Exports"))
        layout.addWidget(self._export_button)
        return bar

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(218)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(4)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        cases_button = self._make_nav_button("Cases")
        cases_button.clicked.connect(self.show_home)
        self._nav_group.addButton(cases_button)
        layout.addWidget(cases_button)
        self._nav_buttons["Cases"] = cases_button

        section = QLabel("INVESTIGATION")
        section.setObjectName("SectionEyebrow")
        section.setContentsMargins(10, 16, 0, 5)
        layout.addWidget(section)

        for name, _description, _milestone in NAVIGATION:
            button = self._make_nav_button(name)
            button.setEnabled(False)
            button.clicked.connect(lambda _checked=False, page=name: self.show_page(page))
            self._nav_group.addButton(button)
            self._nav_buttons[name] = button
            layout.addWidget(button)

        layout.addStretch(1)
        version = QLabel("v0.7.0  ·  Analyst reasoning")
        version.setObjectName("Muted")
        version.setContentsMargins(10, 0, 0, 2)
        layout.addWidget(version)
        return sidebar

    @staticmethod
    def _make_nav_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _build_pages(self) -> None:
        self.home_view = HomeView()
        self.home_view.create_requested.connect(self._create_case)
        self.home_view.open_requested.connect(self.open_case_by_id)
        self._page_indices["Cases"] = self._pages.addWidget(self.home_view)

        self.dashboard_view = DashboardView()
        self._page_indices["Dashboard"] = self._pages.addWidget(self.dashboard_view)
        self.evidence_view = EvidenceView()
        self.evidence_view.import_requested.connect(self._start_import)
        self.evidence_view.cancel_requested.connect(self._cancel_import)
        self._page_indices["Evidence"] = self._pages.addWidget(self.evidence_view)
        self.timeline_view = TimelineView()
        self._page_indices["Timeline"] = self._pages.addWidget(self.timeline_view)
        self.relationships_view = RelationshipsView()
        self.relationships_view.pivot_requested.connect(self._pivot_to_evidence)
        self._page_indices["Relationships"] = self._pages.addWidget(self.relationships_view)
        self.coverage_view = CoverageView()
        self.coverage_view.analysis_requested.connect(self._rerun_analysis)
        self._page_indices["Coverage"] = self._pages.addWidget(self.coverage_view)
        self.intelligence_view = IntelligenceView()
        self.intelligence_view.add_requested.connect(self._add_intelligence)
        self.intelligence_view.import_requested.connect(self._import_intelligence)
        self.intelligence_view.archive_requested.connect(self._archive_intelligence)
        self.intelligence_view.query_requested.connect(self._query_intelligence)
        self._page_indices["Intelligence"] = self._pages.addWidget(self.intelligence_view)
        self.recommendations_view = RecommendationsView()
        self.recommendations_view.state_requested.connect(self._set_recommendation_state)
        self.recommendations_view.evidence_pivot_requested.connect(self._pivot_to_evidence)
        self._page_indices["Recommendations"] = self._pages.addWidget(self.recommendations_view)
        self.sources_view = SourcesView()
        self._page_indices["Sources"] = self._pages.addWidget(self.sources_view)
        self.exports_view = ExportsView()
        self.exports_view.export_requested.connect(self._start_export)
        self.exports_view.verify_requested.connect(self._verify_capsule)
        self._page_indices["Exports"] = self._pages.addWidget(self.exports_view)
        self.settings_view = SettingsView(self._database_path)
        self.settings_view.save_requested.connect(self._save_settings)
        self.settings_view.reset_requested.connect(self._reset_settings)
        self._page_indices["Settings"] = self._pages.addWidget(self.settings_view)

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        self._status_text = QLabel("Ready · Local case store available")
        self._status_text.setObjectName("Muted")
        layout.addWidget(self._status_text)
        layout.addStretch(1)
        schema = QLabel("Schema 6")
        schema.setObjectName("Muted")
        layout.addWidget(schema)
        return bar

    def show_home(self) -> None:
        self.refresh_cases()
        self._pages.setCurrentIndex(self._page_indices["Cases"])
        self._nav_buttons["Cases"].setChecked(True)

    def show_page(self, name: str) -> None:
        if self._current_case is None or name not in self._page_indices:
            return
        self._pages.setCurrentIndex(self._page_indices[name])
        self._nav_buttons[name].setChecked(True)

    def refresh_cases(self) -> None:
        self.home_view.set_cases(self._case_service.list_recent_cases())

    def open_case_by_id(self, case_id: str) -> None:
        if self._background_job_count() and (
            self._current_case is None or str(self._current_case.case_id) != case_id
        ):
            self._show_error(
                "Work in progress",
                "Wait for the active import, lookup, or export before switching cases.",
            )
            return
        try:
            setup = self._case_service.open_investigation(CaseId(case_id))
        except IOCEvidencePackagerError as error:
            self._show_error("Could not open case", str(error))
            return
        self.open_investigation(setup)

    def open_case(self, case: Case) -> None:
        self.open_investigation(InvestigationSetup(case=case, lead=None, source_previews=()))

    def open_investigation(self, setup: InvestigationSetup) -> None:
        if self._background_job_count() and (
            self._current_case is None or self._current_case.case_id != setup.case.case_id
        ):
            self._show_error(
                "Work in progress",
                "Wait for the active import, lookup, or export before switching cases.",
            )
            return
        case = setup.case
        self._current_case = case
        self._current_setup = setup
        self.dashboard_view.set_investigation(setup)
        self._reload_evidence(setup)
        self._case_context.setText(case.title)
        self._update_privacy_badge(case)
        self._export_button.setEnabled(self._analysis is not None)
        for name, button in self._nav_buttons.items():
            button.setEnabled(name == "Cases" or self._current_case is not None)
        self._status_text.setText(
            "Ready · Case saved locally · "
            f"{case.privacy_mode.value.replace('_', ' ').title()} policy active"
        )
        self.show_page("Dashboard")

    def _create_case(self) -> None:
        if self._background_job_count():
            self._show_error(
                "Work in progress",
                "Wait for the active import, lookup, or export before creating another case.",
            )
            return
        dialog = NewCaseDialog(self._source_inspection_service, self)
        if dialog.exec() != NewCaseDialog.DialogCode.Accepted:
            return
        try:
            request = dialog.request()
            request = replace(
                request,
                case=replace(
                    request.case,
                    privacy_mode=PrivacyMode(self._preferences.default_privacy_mode),
                ),
            )
            setup = self._case_service.create_investigation(request)
        except IOCEvidencePackagerError as error:
            self._show_error("Could not create case", str(error))
            return
        self.refresh_cases()
        self.open_investigation(setup)

    def _reload_evidence(self, setup: InvestigationSetup | None = None) -> None:
        active = setup or self._current_setup
        if active is None:
            return
        records = tuple(self._evidence_service.list_evidence(active.case.case_id))
        rejections = tuple(self._evidence_service.list_rejections(active.case.case_id))
        analysis: AnalysisSnapshot | None = None
        if active.lead is not None and (records or rejections):
            analysis = self._analysis_service.ensure_analysis(
                active.case.case_id,
                active.lead,
                active.source_previews,
                records,
                rejections,
            )
        self._records = records
        self._rejections = rejections
        self._analysis = analysis
        self._relationships = self._workspace_service.relationships(records)
        self.evidence_view.set_investigation(active, list(records), list(rejections))
        self.evidence_view.set_analysis(analysis)
        self.coverage_view.set_analysis(analysis)
        self.timeline_view.set_records(records, analysis, active.case.display_timezone)
        self.sources_view.set_investigation(active, records, rejections)
        self.relationships_view.set_relationships(self._relationships)
        self.recommendations_view.set_display_timezone(active.case.display_timezone)
        self.recommendations_view.set_recommendations(
            self._workspace_service.recommendations(
                active.case.case_id, analysis, self._relationships
            )
        )
        self._reload_intelligence(active.case)
        self.settings_view.set_settings(active.case, self._preferences)
        self.dashboard_view.set_evidence_counts(len(records), len(rejections))
        self.dashboard_view.set_analysis(analysis, records, rejections)
        history = self._report_service.list_exports(active.case.case_id)
        self.exports_view.set_investigation(active, analysis, history)
        self._export_button.setEnabled(analysis is not None)

    def _start_import(self, case_value: object, previews_value: object) -> None:
        if self._background_job_count() or not isinstance(case_value, str):
            return
        if not isinstance(previews_value, tuple) or not all(
            isinstance(preview, SourcePreview) for preview in previews_value
        ):
            return
        case_id = CaseId(case_value)
        if self._current_case is None or self._current_case.case_id != case_id:
            self._show_error(
                "Could not import evidence", "The import request belongs to another case."
            )
            return
        worker = EvidenceImportWorker(self._evidence_service, case_id, previews_value)
        worker.signals.progress.connect(self._import_progress)
        worker.signals.completed.connect(self._import_completed)
        worker.signals.failed.connect(self._import_failed)
        self._import_worker = worker
        self._import_case_id = case_id
        self.evidence_view.set_import_running()
        self._sync_jobs()
        self._status_text.setText("Import running · Source integrity verification active")
        self._thread_pool.start(worker)

    def _cancel_import(self) -> None:
        if self._import_worker is not None:
            self._import_worker.cancel()
            self._status_text.setText("Cancelling import after the current safe boundary…")

    def _import_progress(self, value: object) -> None:
        if (
            isinstance(value, ImportProgress)
            and self._current_case is not None
            and self._current_case.case_id == self._import_case_id
        ):
            self.evidence_view.set_import_progress(value)

    def _import_completed(self, value: object) -> None:
        if not isinstance(value, ImportSummary):
            self._import_failed("Import worker returned an invalid result.")
            return
        imported_case = self._import_case_id
        self._import_worker = None
        self._import_case_id = None
        self._sync_jobs()
        if (
            imported_case is not None
            and self._current_setup is not None
            and imported_case == self._current_setup.case.case_id
        ):
            self.evidence_view.set_import_finished(value)
            self._reload_evidence()
            self.show_page("Evidence")
        self._status_text.setText(
            f"Import {value.status.value} · {value.stored_evidence_records} durable record(s)"
        )

    def _import_failed(self, message: str) -> None:
        imported_case = self._import_case_id
        self._import_worker = None
        self._import_case_id = None
        self._sync_jobs()
        if self._current_case is not None and self._current_case.case_id == imported_case:
            self.evidence_view.set_import_finished()
        self._status_text.setText("Import failed · Review diagnostics and retry")
        self._show_error("Evidence import failed", message)

    def _rerun_analysis(self) -> None:
        if self._background_job_count():
            self._status_text.setText(
                "Analysis not started · wait for the active background job to finish"
            )
            return
        setup = self._current_setup
        if setup is None or setup.lead is None or not (self._records or self._rejections):
            return
        try:
            self._analysis = self._analysis_service.ensure_analysis(
                setup.case.case_id,
                setup.lead,
                setup.source_previews,
                self._records,
                self._rejections,
                force=True,
            )
        except Exception as error:  # noqa: BLE001 - keep analysis failure inside the GUI
            self._show_error("IOC analysis failed", str(error))
            return
        self.evidence_view.set_analysis(self._analysis)
        self.coverage_view.set_analysis(self._analysis)
        self.timeline_view.set_records(self._records, self._analysis, setup.case.display_timezone)
        self.dashboard_view.set_analysis(self._analysis, self._records, self._rejections)
        self.exports_view.set_investigation(
            setup,
            self._analysis,
            self._report_service.list_exports(setup.case.case_id),
        )
        self._export_button.setEnabled(True)
        self._status_text.setText(
            f"Analysis complete · {len(self._analysis.sightings)} direct sighting(s)"
        )
        self._reload_reasoning()

    def _reload_reasoning(self) -> None:
        if self._current_setup is None:
            return
        self._relationships = self._workspace_service.relationships(self._records)
        self.relationships_view.set_relationships(self._relationships)
        self.recommendations_view.set_display_timezone(self._current_setup.case.display_timezone)
        self.recommendations_view.set_recommendations(
            self._workspace_service.recommendations(
                self._current_setup.case.case_id, self._analysis, self._relationships
            )
        )

    def _pivot_to_evidence(self, value: str) -> None:
        self.evidence_view.set_search_filter(value)
        self.show_page("Evidence")
        self._status_text.setText(f"Evidence pivot applied · {value}")

    def _set_recommendation_state(self, recommendation_id: str, status: str, note: object) -> None:
        if self._current_case is None:
            return
        try:
            self._workspace_service.set_recommendation_state(
                self._current_case.case_id,
                RecommendationId(recommendation_id),
                RecommendationStatus(status),
                str(note) if note is not None else None,
            )
        except (ValueError, IOCEvidencePackagerError) as error:
            self._show_error("Could not update recommendation", str(error))
            return
        self._reload_reasoning()
        self._status_text.setText(
            f"Recommendation marked {status.casefold()} · analyst state saved"
        )

    def _observable_inventory(self) -> tuple[tuple[str, str], ...]:
        values = {
            (item.kind, item.canonical)
            for record in self._records
            for item in record.observables
            if item.kind in {"ipv4", "domain", "sha256"}
        }
        if self._current_setup is not None and self._current_setup.lead is not None:
            lead = self._current_setup.lead
            values.add((lead.observable_type.value, lead.canonical_value))
        return tuple(sorted(values))

    def _reload_intelligence(self, case: Case | None = None) -> None:
        active = case or self._current_case
        if active is None:
            return
        self.intelligence_view.set_intelligence(
            active,
            self._workspace_service.assertions(active.case_id),
            self._observable_inventory(),
            provider_enabled=self._preferences.virustotal_enabled,
            confirm_external_links=self._preferences.confirm_external_links,
        )

    def _add_intelligence(self, value: object) -> None:
        if self._current_case is None or not isinstance(value, dict):
            return
        try:
            self._workspace_service.add_manual_assertion(
                self._current_case.case_id,
                provider=str(value.get("provider", "")),
                observable_type=str(value.get("observable_type", "")),
                observable_value=str(value.get("observable_value", "")),
                claim=IntelligenceClaim(str(value.get("claim", ""))),
                confidence_label=str(value.get("confidence_label", "")),
                summary=str(value.get("summary", "")),
                source_reference=str(value.get("source_reference", "")) or None,
            )
        except (ValueError, IOCEvidencePackagerError) as error:
            self._show_error("Could not add assertion", str(error))
            return
        self._reload_intelligence()
        self._status_text.setText("Attributed intelligence assertion saved locally")

    def _import_intelligence(self, path: str) -> None:
        if self._current_case is None:
            return
        try:
            count = self._workspace_service.import_assertions(
                self._current_case.case_id, Path(path)
            )
        except IOCEvidencePackagerError as error:
            self._show_error("Could not import intelligence", str(error))
            return
        self._reload_intelligence()
        self._status_text.setText(f"Imported {count} attributed intelligence assertion(s)")

    def _archive_intelligence(self, assertion_id: str) -> None:
        if self._current_case is None:
            return
        try:
            self._workspace_service.archive_assertion(
                self._current_case.case_id, AssertionId(assertion_id)
            )
        except IOCEvidencePackagerError as error:
            self._show_error("Could not archive assertion", str(error))
            return
        self._reload_intelligence()
        self._status_text.setText("Assertion archived · audit row retained in SQLite")

    def _query_intelligence(self, observable_type: str, value: str) -> None:
        if self._current_case is None or self._background_job_count():
            return
        worker = IntelligenceLookupWorker(
            self._workspace_service,
            self._current_case,
            observable_type,
            value,
            self._preferences.cache_hours,
        )
        worker.signals.completed.connect(self._intelligence_completed)
        worker.signals.failed.connect(self._intelligence_failed)
        self._intelligence_worker = worker
        self._intelligence_case_id = self._current_case.case_id
        self._sync_jobs()
        self._status_text.setText("VirusTotal object lookup running · selected IOC disclosed")
        self._thread_pool.start(worker)

    def _intelligence_completed(self, _value: object) -> None:
        queried_case = self._intelligence_case_id
        self._intelligence_worker = None
        self._intelligence_case_id = None
        self._sync_jobs()
        if self._current_case is not None and self._current_case.case_id == queried_case:
            self._reload_intelligence()
        self._status_text.setText(
            "Provider assertion saved · attribution and response digest retained"
        )

    def _intelligence_failed(self, message: str) -> None:
        self._intelligence_worker = None
        self._intelligence_case_id = None
        self._sync_jobs()
        self._status_text.setText("Provider lookup failed safely · no evidence changed")
        self._show_error("Intelligence lookup failed", message)

    def _save_settings(self, privacy_mode: str, timezone: str, preferences: object) -> None:
        if self._current_case is None or not isinstance(preferences, DesktopPreferences):
            return
        try:
            updated = self._case_service.update_preferences(
                self._current_case.case_id,
                display_timezone=timezone,
                privacy_mode=PrivacyMode(privacy_mode),
            )
        except (ValueError, IOCEvidencePackagerError) as error:
            self._show_error("Could not save settings", str(error))
            return
        self._settings_store.save(preferences)
        self._preferences = preferences
        DetailDialog.set_preferred_width(preferences.detail_width)
        self._apply_device_preferences()
        self._current_case = updated
        if self._current_setup is not None:
            self._current_setup = InvestigationSetup(
                case=updated,
                lead=self._current_setup.lead,
                source_previews=self._current_setup.source_previews,
            )
        self._update_privacy_badge(updated)
        if self._current_setup is not None:
            self.dashboard_view.set_investigation(self._current_setup)
            self._reload_evidence(self._current_setup)
        else:
            self._reload_intelligence(updated)
            self.settings_view.set_settings(updated, preferences)
        self.settings_view.mark_saved()
        self._status_text.setText("Settings saved · case policy and device preferences applied")

    def _reset_settings(self) -> None:
        self._preferences = self._settings_store.reset()
        DetailDialog.set_preferred_width(self._preferences.detail_width)
        self._apply_device_preferences()
        if self._current_case is not None:
            self.settings_view.set_settings(self._current_case, self._preferences)
            self._reload_intelligence()
        self.settings_view.mark_saved("Device preferences reset; case policy was not changed.")

    def _update_privacy_badge(self, case: Case) -> None:
        label = case.privacy_mode.value.replace("_", " ").title()
        self._privacy_badge.setText(f"●  {label}")

    def _apply_device_preferences(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(
                desktop_stylesheet(
                    compact=self._preferences.density == "Compact",
                    high_contrast=self._preferences.high_contrast,
                )
            )

    def _start_export(self, profile_value: str, destination_value: str) -> None:
        if self._background_job_count():
            return
        setup = self._current_setup
        if setup is None or self._analysis is None:
            self._show_error(
                "Could not export capsule", "Import and analyze evidence before exporting."
            )
            return
        try:
            profile = ExportProfile(profile_value)
        except ValueError:
            self._show_error("Could not export capsule", "Unknown export profile.")
            return
        worker = CapsuleExportWorker(
            self._report_service,
            setup,
            self._records,
            self._rejections,
            self._analysis,
            Path(destination_value),
            profile,
            self._relationships,
            self._workspace_service.recommendations(
                setup.case.case_id, self._analysis, self._relationships
            ),
            self._workspace_service.assertions(setup.case.case_id),
        )
        worker.signals.completed.connect(self._export_completed)
        worker.signals.failed.connect(self._export_failed)
        self._export_worker = worker
        self._export_case_id = setup.case.case_id
        self.exports_view.set_export_running()
        self._sync_jobs()
        self._status_text.setText("Building Case Capsule · Offline verification active")
        self._thread_pool.start(worker)

    def _export_completed(self, value: object) -> None:
        exported_case = self._export_case_id
        self._export_worker = None
        self._export_case_id = None
        self._sync_jobs()
        if not isinstance(value, CapsuleResult):
            self.exports_view.set_export_failed("Export worker returned an invalid result.")
            self._status_text.setText(
                "Capsule export failed safely · No completed handoff published"
            )
            self._show_error(
                "Case Capsule export failed", "Export worker returned an invalid result."
            )
            return
        if (
            self._current_setup is not None
            and exported_case == value.case_id == self._current_setup.case.case_id
        ):
            self.exports_view.set_export_result(value)
            self.exports_view.set_history(
                self._report_service.list_exports(self._current_setup.case.case_id)
            )
        self._status_text.setText(
            f"Capsule verified · {len(value.artifacts)} artifact(s) · {value.destination}"
        )

    def _export_failed(self, message: str) -> None:
        exported_case = self._export_case_id
        self._export_worker = None
        self._export_case_id = None
        self._sync_jobs()
        if self._current_case is not None and self._current_case.case_id == exported_case:
            self.exports_view.set_export_failed(message)
        self._status_text.setText("Capsule export failed safely · No completed handoff published")
        self._show_error("Case Capsule export failed", message)

    def _verify_capsule(self, path_value: str) -> None:
        try:
            result = self._report_service.verify(Path(path_value))
        except Exception as error:  # noqa: BLE001 - filesystem failures stay inside the GUI
            self._show_error("Could not verify capsule", str(error))
            return
        self.exports_view.set_verification(result)
        self._status_text.setText(
            f"Capsule {'verified' if result.valid else 'failed verification'} · "
            f"{result.checked_artifacts} artifact(s) checked"
        )

    def _background_job_count(self) -> int:
        return sum(
            worker is not None
            for worker in (
                self._import_worker,
                self._export_worker,
                self._intelligence_worker,
            )
        )

    def _sync_jobs(self) -> None:
        count = self._background_job_count()
        self._jobs_button.setText(f"Jobs  {count}")
        self._jobs_button.setEnabled(count > 0)

    def _show_error(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
