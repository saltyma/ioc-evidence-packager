"""Case Capsule export, verification, and history workspace."""

import re
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.application.services import InvestigationSetup
from ioc_evidence_packager.domain.analysis import AnalysisSnapshot
from ioc_evidence_packager.domain.timezones import UTC_DISPLAY, format_case_datetime
from ioc_evidence_packager.presentation.desktop.views.detail_dialog import DetailDialog
from ioc_evidence_packager.reporting.models import (
    CapsuleResult,
    ExportProfile,
    ExportRecord,
    VerificationResult,
)


class ExportsView(QWidget):
    """Creates new capsule directories and verifies existing handoffs."""

    export_requested = Signal(str, str)
    verify_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup: InvestigationSetup | None = None
        self._history_records: list[ExportRecord] = []
        self._display_timezone = UTC_DISPLAY
        self._detail_dialog: DetailDialog | None = None
        self._build_ui()

    @property
    def history_row_count(self) -> int:
        return self._history.rowCount()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(15)
        eyebrow = QLabel("PORTABLE CASE CAPSULE")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Export a handoff that verifies itself")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "The desktop and report share one immutable analysis model. Artifacts are "
            "written offline, hashed, indexed in manifest.json, re-read, and only then published."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        panel = QFrame()
        panel.setObjectName("Panel")
        form = QGridLayout(panel)
        form.setContentsMargins(20, 18, 20, 18)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.addWidget(_label("EXPORT PROFILE"), 0, 0)
        self._profile = QComboBox()
        self._profile.addItem("Full Internal", ExportProfile.FULL_INTERNAL.value)
        self._profile.addItem("Redacted Shareable", ExportProfile.REDACTED_SHAREABLE.value)
        self._profile.currentIndexChanged.connect(self._profile_changed)
        form.addWidget(self._profile, 0, 1, 1, 2)
        form.addWidget(_label("NEW CAPSULE DIRECTORY"), 1, 0)
        self._destination = QLineEdit()
        self._destination.setPlaceholderText("Choose a new directory; existing paths are blocked")
        form.addWidget(self._destination, 1, 1)
        browse = QPushButton("Browse parent…")
        browse.clicked.connect(self._browse_destination)
        form.addWidget(browse, 1, 2)
        self._profile_note = QLabel()
        self._profile_note.setObjectName("Muted")
        self._profile_note.setWordWrap(True)
        form.addWidget(self._profile_note, 2, 1, 1, 2)
        actions = QHBoxLayout()
        self._export_button = QPushButton("Build and verify capsule")
        self._export_button.setObjectName("PrimaryButton")
        self._export_button.clicked.connect(self._request_export)
        self._export_button.setEnabled(False)
        self._verify_button = QPushButton("Verify existing capsule…")
        self._verify_button.clicked.connect(self._browse_verify)
        actions.addWidget(self._export_button)
        actions.addWidget(self._verify_button)
        actions.addStretch(1)
        form.addLayout(actions, 3, 1, 1, 2)
        root.addWidget(panel)
        self._profile_changed()

        notice = QFrame()
        notice.setObjectName("NoticeCard")
        notice_layout = QHBoxLayout(notice)
        notice_layout.setContentsMargins(16, 12, 16, 12)
        self._status = QLabel("Import and analyze evidence before exporting.")
        self._status.setObjectName("Muted")
        self._status.setWordWrap(True)
        notice_layout.addWidget(self._status)
        root.addWidget(notice)

        history_label = QLabel("SUCCESSFUL EXPORT HISTORY")
        history_label.setObjectName("SectionEyebrow")
        root.addWidget(history_label)
        self._history = QTableWidget(0, 5)
        self._history.setHorizontalHeaderLabels(
            ["Created", "Profile", "Artifacts", "Destination", "Manifest SHA-256"]
        )
        self._history.setAlternatingRowColors(True)
        self._history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._history.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._history.verticalHeader().setVisible(False)
        for column in (0, 1, 2):
            self._history.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        for column in (3, 4):
            self._history.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.Stretch
            )
        self._history.cellClicked.connect(self._open_history_detail)
        root.addWidget(self._history, 1)

    def set_investigation(
        self,
        setup: InvestigationSetup,
        analysis: AnalysisSnapshot | None,
        history: list[ExportRecord],
    ) -> None:
        self._setup = setup
        self._display_timezone = setup.case.display_timezone
        self._export_button.setEnabled(analysis is not None)
        if not self._destination.text().strip():
            self._destination.setText(str(_default_destination(setup.case.title)))
        if analysis is None:
            self._status.setText("Import and analyze evidence before exporting.")
        else:
            self._status.setText(
                f"Ready · {analysis.recipe_id}/{analysis.recipe_version} · "
                f"{len(analysis.sightings)} direct sighting(s) · manifest verification enabled."
            )
        self.set_history(history)

    def set_history(self, history: list[ExportRecord]) -> None:
        if self._detail_dialog is not None:
            self._detail_dialog.close()
        self._history_records = history
        self._history.setRowCount(0)
        for row, record in enumerate(history):
            self._history.insertRow(row)
            values = (
                format_case_datetime(record.created_at, self._display_timezone),
                record.profile.value,
                str(record.artifact_count),
                str(record.destination),
                record.manifest_sha256,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self._history.setItem(row, column, item)

    def _open_history_detail(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self._history_records):
            return
        record = self._history_records[row]
        if self._detail_dialog is None:
            self._detail_dialog = DetailDialog(self)
        self._detail_dialog.present(
            window_title="Export history details",
            eyebrow="VERIFIED CASE CAPSULE",
            title=(
                f"{record.profile.value} · "
                f"{format_case_datetime(record.created_at, self._display_timezone)}"
            ),
            text=(
                f"Export ID: {record.export_id}\n"
                f"Case ID: {record.case_id}\n"
                f"Profile: {record.profile.value}\n"
                f"Created ({self._display_timezone}): "
                f"{format_case_datetime(record.created_at, self._display_timezone)}\n"
                f"Destination: {record.destination}\n"
                f"Artifacts: {record.artifact_count}\n"
                f"Manifest SHA-256: {record.manifest_sha256}"
            ),
        )

    def set_export_running(self) -> None:
        self._export_button.setEnabled(False)
        self._status.setText("Rendering artifacts, hashing files, and verifying the manifest…")

    def set_export_result(self, result: CapsuleResult) -> None:
        self._export_button.setEnabled(True)
        self._status.setText(
            f"Verified capsule published to {result.destination} · "
            f"{len(result.artifacts)} artifact(s) · manifest {result.manifest_sha256[:16]}…"
        )
        self._destination.setText(str(_next_destination(result.destination)))

    def set_export_failed(self, message: str) -> None:
        self._export_button.setEnabled(True)
        self._status.setText(f"Export failed safely; no completed capsule was published. {message}")

    def set_verification(self, result: VerificationResult) -> None:
        verdict = "VERIFIED" if result.valid else "FAILED"
        self._status.setText(
            f"{verdict} · {result.capsule_path} · {result.checked_artifacts} artifact(s) · "
            + " ".join(result.messages)
        )

    def _request_export(self) -> None:
        profile = self._profile.currentData()
        destination = self._destination.text().strip()
        if isinstance(profile, str) and destination:
            self.export_requested.emit(profile, destination)

    def _profile_changed(self) -> None:
        if self._profile.currentData() == ExportProfile.REDACTED_SHAREABLE.value:
            self._profile_note.setText(
                "Case-identifying metadata is omitted; host and user names receive capsule-local "
                "pseudonyms; source paths and raw JSON are omitted. Evidence IDs and source "
                "digests remain verifiable."
            )
        else:
            self._profile_note.setText(
                "Includes source paths and preserved raw canonical JSON. Original source files "
                "are not copied into the capsule."
            )

    def _browse_destination(self) -> None:
        parent = QFileDialog.getExistingDirectory(self, "Choose capsule parent directory")
        if parent:
            name = _capsule_name(self._setup.case.title if self._setup else "investigation")
            self._destination.setText(str(_next_destination(Path(parent) / name)))

    def _browse_verify(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose Case Capsule directory")
        if directory:
            self.verify_requested.emit(directory)


def _label(text: str) -> QLabel:
    value = QLabel(text)
    value.setObjectName("SectionEyebrow")
    value.setAlignment(Qt.AlignmentFlag.AlignTop)
    return value


def _default_destination(title: str) -> Path:
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    parent = Path(documents) if documents else Path.cwd()
    return _next_destination(parent / _capsule_name(title))


def _capsule_name(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:60]
    return f"{slug or 'investigation'}-capsule"


def _next_destination(path: Path) -> Path:
    candidate = path
    counter = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.name}-{counter}")
        counter += 1
    return candidate
