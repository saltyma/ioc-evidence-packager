"""Native desktop shell and navigation coordination."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
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

from ioc_evidence_packager.application.services import CaseService, InvestigationSetup
from ioc_evidence_packager.domain.errors import IOCEvidencePackagerError
from ioc_evidence_packager.domain.models import Case, CaseId
from ioc_evidence_packager.ingestion import SourceInspectionService
from ioc_evidence_packager.presentation.desktop.branding import application_icon
from ioc_evidence_packager.presentation.desktop.views.dashboard import DashboardView
from ioc_evidence_packager.presentation.desktop.views.home import HomeView
from ioc_evidence_packager.presentation.desktop.views.new_case import NewCaseDialog
from ioc_evidence_packager.presentation.desktop.views.placeholder import PlaceholderView

NAVIGATION = (
    ("Dashboard", "Case summary, findings, limitations, and next actions.", "Slice 1"),
    ("Evidence", "Source-linked facts, provenance, review state, and raw records.", "Slice 3"),
    ("Timeline", "A deterministic chronology with direct, context, and undated lanes.", "Slice 4"),
    ("Relationships", "Bounded typed relationships with evidence-backed edges.", "Phase 6"),
    (
        "Coverage",
        "Matched, searched, partial, missing, failed, and unsupported evidence.",
        "Slice 4",
    ),
    ("Intelligence", "Attributed provider assertions under the active privacy policy.", "Phase 7"),
    ("Recommendations", "Deterministic next actions citing evidence and coverage gaps.", "Phase 6"),
    ("Sources", "Input inventory, hashes, adapters, jobs, and diagnostics.", "Slice 2"),
    ("Exports", "Reviewed Case Capsule profiles and artifact verification.", "Slice 5"),
    ("Settings", "Case display, storage, privacy, and mapping preferences.", "Slice 2"),
)


class MainWindow(QMainWindow):
    """Coordinates presentation state while delegating work to services."""

    def __init__(
        self,
        case_service: CaseService,
        source_inspection_service: SourceInspectionService,
    ) -> None:
        super().__init__()
        self._case_service = case_service
        self._source_inspection_service = source_inspection_service
        self._current_case: Case | None = None
        self._page_indices: dict[str, int] = {}
        self._nav_buttons: dict[str, QPushButton] = {}
        self.setWindowTitle("IOC Evidence Packager")
        self.setWindowIcon(application_icon())
        self.resize(1280, 820)
        self.setMinimumSize(1024, 680)
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

        privacy = QLabel("●  Offline")
        privacy.setObjectName("PrivacyBadge")
        privacy.setToolTip("No network calls, telemetry, DNS resolution, or remote UI assets.")
        layout.addWidget(privacy)

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
        version = QLabel("v0.2.0  ·  Source preview")
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
        for name, description, milestone in NAVIGATION[1:]:
            self._page_indices[name] = self._pages.addWidget(
                PlaceholderView(name, description, milestone)
            )

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
        schema = QLabel("Schema 2")
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
        try:
            setup = self._case_service.open_investigation(CaseId(case_id))
        except IOCEvidencePackagerError as error:
            self._show_error("Could not open case", str(error))
            return
        self.open_investigation(setup)

    def open_case(self, case: Case) -> None:
        self.open_investigation(InvestigationSetup(case=case, lead=None, source_previews=()))

    def open_investigation(self, setup: InvestigationSetup) -> None:
        case = setup.case
        self._current_case = case
        self.dashboard_view.set_investigation(setup)
        self._case_context.setText(case.title)
        self._export_button.setEnabled(True)
        for name, button in self._nav_buttons.items():
            button.setEnabled(name == "Cases" or self._current_case is not None)
        self._status_text.setText("Ready · Case saved locally · Offline policy active")
        self.show_page("Dashboard")

    def _create_case(self) -> None:
        dialog = NewCaseDialog(self._source_inspection_service, self)
        if dialog.exec() != NewCaseDialog.DialogCode.Accepted:
            return
        try:
            setup = self._case_service.create_investigation(dialog.request())
        except IOCEvidencePackagerError as error:
            self._show_error("Could not create case", str(error))
            return
        self.refresh_cases()
        self.open_investigation(setup)

    def _show_error(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
