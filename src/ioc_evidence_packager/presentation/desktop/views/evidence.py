"""Source-linked evidence ledger and structured import diagnostics."""

from datetime import UTC

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.application.services import InvestigationSetup
from ioc_evidence_packager.domain.analysis import AnalysisSnapshot, Sighting
from ioc_evidence_packager.domain.evidence import (
    EvidenceRecord,
    ImportProgress,
    ImportRejection,
    ImportSummary,
)
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import PreviewStatus, SourcePreview
from ioc_evidence_packager.presentation.desktop.views.detail_dialog import DetailDialog


class EvidenceView(QWidget):
    """Imports previewed sources and exposes every accepted/rejected source line."""

    import_requested = Signal(object, object)
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._case_id: CaseId | None = None
        self._previews: tuple[SourcePreview, ...] = ()
        self._records: list[EvidenceRecord] = []
        self._visible_records: list[EvidenceRecord] = []
        self._rejections: list[ImportRejection] = []
        self._analysis: AnalysisSnapshot | None = None
        self._detail_dialog: DetailDialog | None = None
        self._build_ui()

    @property
    def evidence_row_count(self) -> int:
        return self._evidence_table.rowCount()

    @property
    def rejection_row_count(self) -> int:
        return self._rejection_table.rowCount()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(15)

        heading = QHBoxLayout()
        heading_text = QVBoxLayout()
        eyebrow = QLabel("EVIDENCE LEDGER")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Imported source records")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Accepted events retain the selected-file digest, physical line, declared "
            "source position, observables, warnings, and the preserved source record."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        heading_text.addWidget(eyebrow)
        heading_text.addWidget(title)
        heading_text.addWidget(subtitle)
        heading.addLayout(heading_text, 1)
        self._import_button = QPushButton("Import previewed sources")
        self._import_button.setObjectName("PrimaryButton")
        self._import_button.clicked.connect(self._request_import)
        self._cancel_button = QPushButton("Cancel import")
        self._cancel_button.clicked.connect(self.cancel_requested)
        self._cancel_button.setVisible(False)
        heading.addWidget(self._cancel_button, 0, Qt.AlignmentFlag.AlignTop)
        heading.addWidget(self._import_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(heading)

        summary = QFrame()
        summary.setObjectName("NoticeCard")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        self._summary = QLabel("Open a case to load its evidence state.")
        self._summary.setWordWrap(True)
        self._summary.setObjectName("Muted")
        summary_layout.addWidget(self._summary, 1)
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setMinimumWidth(240)
        self._progress.setVisible(False)
        summary_layout.addWidget(self._progress)
        root.addWidget(summary)

        filters = QHBoxLayout()
        self._classification_filter = QComboBox()
        self._classification_filter.addItems(
            ("All evidence", "Direct matches", "Context", "Undated")
        )
        self._classification_filter.currentIndexChanged.connect(self._apply_evidence_filters)
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Filter observable, host, user, source, category, action, or event ID…"
        )
        self._search.textChanged.connect(self._apply_evidence_filters)
        filters.addWidget(self._classification_filter)
        filters.addWidget(self._search, 1)
        root.addLayout(filters)

        self._tabs = QTabWidget()
        self._evidence_table = self._build_evidence_table()
        evidence_page = QWidget()
        evidence_layout = QVBoxLayout(evidence_page)
        evidence_layout.setContentsMargins(0, 10, 0, 0)
        evidence_layout.addWidget(self._evidence_table, 1)
        self._tabs.addTab(evidence_page, "Evidence · 0")

        self._rejection_table = self._build_rejection_table()
        rejection_page = QWidget()
        rejection_layout = QVBoxLayout(rejection_page)
        rejection_layout.setContentsMargins(0, 10, 0, 0)
        rejection_copy = QLabel(
            "Rejected lines stay separate from evidence and carry a stable code, safe "
            "message, source line, and bounded excerpt."
        )
        rejection_copy.setObjectName("Muted")
        rejection_copy.setWordWrap(True)
        rejection_layout.addWidget(rejection_copy)
        rejection_layout.addWidget(self._rejection_table, 1)
        self._tabs.addTab(rejection_page, "Rejections · 0")
        root.addWidget(self._tabs, 1)

    def _build_evidence_table(self) -> QTableWidget:
        table = QTableWidget(0, 10)
        table.setHorizontalHeaderLabels(
            [
                "Time",
                "Class",
                "Category",
                "Action",
                "Host",
                "User",
                "Observables",
                "Match explanation",
                "Source",
                "Position",
            ]
        )
        _configure_table(table)
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        table.cellClicked.connect(self._open_evidence_detail)
        return table

    def _build_rejection_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Source", "Position", "Code", "Message", "Excerpt"])
        _configure_table(table)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table.cellClicked.connect(self._open_rejection_detail)
        return table

    def set_investigation(
        self,
        setup: InvestigationSetup,
        records: list[EvidenceRecord],
        rejections: list[ImportRejection],
    ) -> None:
        if self._detail_dialog is not None:
            self._detail_dialog.close()
        self._case_id = setup.case.case_id
        self._previews = setup.source_previews
        self._analysis = None
        self.set_records(records, rejections)

    def set_records(
        self,
        records: list[EvidenceRecord],
        rejections: list[ImportRejection],
    ) -> None:
        self._records = records
        self._rejections = rejections
        self._apply_evidence_filters()
        self._populate_rejections()
        recognized = sum(
            preview.status in {PreviewStatus.READY, PreviewStatus.WARNING}
            and preview.adapter_id is not None
            for preview in self._previews
        )
        self._summary.setText(
            f"{len(records)} durable evidence record(s) · {len(rejections)} rejection(s) · "
            f"{recognized} supported source(s) available for idempotent import/retry."
        )
        self._import_button.setEnabled(self._case_id is not None and recognized > 0)
        self._tabs.setTabText(0, f"Evidence · {len(records)}")
        self._tabs.setTabText(1, f"Rejections · {len(rejections)}")

    def set_analysis(self, analysis: AnalysisSnapshot | None) -> None:
        self._analysis = analysis
        self._apply_evidence_filters()

    def set_import_running(self) -> None:
        self._import_button.setEnabled(False)
        self._cancel_button.setVisible(True)
        self._progress.setVisible(True)
        self._progress.setRange(0, max(1, len(self._previews)))
        self._progress.setValue(0)
        self._progress.setFormat("Verifying source digests…")

    def set_import_progress(self, progress: ImportProgress) -> None:
        self._progress.setMaximum(max(1, progress.total_sources))
        self._progress.setValue(progress.processed_sources)
        self._progress.setFormat(
            f"{progress.current_source} · {progress.accepted_records} accepted · "
            f"{progress.rejected_records} rejected"
        )

    def set_import_finished(self, summary: ImportSummary | None = None) -> None:
        self._cancel_button.setVisible(False)
        self._progress.setVisible(False)
        self._import_button.setEnabled(True)
        if summary is not None:
            self._summary.setText(
                f"Import {summary.status.value} · {summary.accepted_records} accepted this run · "
                f"{summary.rejected_records} rejected · {summary.stored_evidence_records} "
                "unique durable evidence record(s)."
            )

    def _request_import(self) -> None:
        if self._case_id is not None:
            self.import_requested.emit(self._case_id, self._previews)

    def _apply_evidence_filters(self) -> None:
        direct = self._analysis.direct_evidence_ids if self._analysis else frozenset()
        mode = self._classification_filter.currentText()
        query = self._search.text().strip().casefold()
        visible: list[EvidenceRecord] = []
        for record in self._records:
            is_direct = record.evidence_id in direct
            if mode == "Direct matches" and not is_direct:
                continue
            if mode == "Context" and is_direct:
                continue
            if mode == "Undated" and record.occurred_at is not None:
                continue
            observable_text = " ".join(item.canonical for item in record.observables)
            haystack = " ".join(
                (
                    record.event_id,
                    record.category,
                    record.action,
                    record.host_name or "",
                    record.user_name or "",
                    record.source_name,
                    observable_text,
                )
            ).casefold()
            if query and query not in haystack:
                continue
            visible.append(record)
        self._visible_records = visible
        self._populate_evidence()

    def _populate_evidence(self) -> None:
        self._evidence_table.setRowCount(0)
        direct = self._analysis.direct_evidence_ids if self._analysis else frozenset()
        sightings = _sightings_by_evidence(self._analysis)
        for row, record in enumerate(self._visible_records):
            self._evidence_table.insertRow(row)
            timestamp = (
                record.occurred_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
                if record.occurred_at
                else "Undated"
            )
            observable_text = (
                ", ".join(
                    f"{observable.kind}:{observable.canonical}" for observable in record.observables
                )
                or "None declared"
            )
            values = (
                timestamp,
                "DIRECT" if record.evidence_id in direct else "CONTEXT",
                record.category,
                record.action,
                record.host_name or "—",
                record.user_name or "—",
                observable_text,
                sightings.get(record.evidence_id, "—"),
                record.source_name,
                f"{record.declared_position_kind} {record.declared_position_value}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self._evidence_table.setItem(row, column, item)

    def _populate_rejections(self) -> None:
        self._rejection_table.setRowCount(0)
        for row, rejection in enumerate(self._rejections):
            self._rejection_table.insertRow(row)
            values = (
                rejection.source_name,
                str(rejection.line_number) if rejection.line_number else "Source",
                rejection.code,
                rejection.message,
                rejection.raw_excerpt or "—",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self._rejection_table.setItem(row, column, item)

    def _open_evidence_detail(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self._visible_records):
            return
        record = self._visible_records[row]
        matching = tuple(
            sighting
            for sighting in (self._analysis.sightings if self._analysis else ())
            if sighting.evidence_id == record.evidence_id
        )
        observable_lines = (
            "\n".join(
                f"  - {item.kind} · {item.field_path} · {item.canonical}"
                for item in record.observables
            )
            or "  - None declared"
        )
        match_lines = _match_detail(matching)
        self._show_detail(
            window_title="Evidence record details",
            eyebrow="SOURCE-LINKED EVIDENCE",
            title=f"{record.event_id} · {record.source_name}:{record.line_number}",
            text=(
                f"Evidence ID: {record.evidence_id}\n"
                f"Classification: {'DIRECT MATCH' if matching else 'CONTEXT'}\n"
                f"Event ID: {record.event_id}\n"
                f"Selected source: {record.source_path}\n"
                f"Selected source SHA-256: {record.source_sha256 or 'Unavailable'}\n"
                f"Adapter record index: {record.line_number}\n"
                f"Declared source: {record.declared_source_id}\n"
                f"Declared position: {record.declared_position_kind} "
                f"{record.declared_position_value}\n"
                f"Observables:\n{observable_lines}\n"
                f"Match explanation:\n{match_lines}\n\n"
                f"Preserved source record:\n{record.raw_json}"
            ),
        )

    def _open_rejection_detail(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self._rejections):
            return
        rejection = self._rejections[row]
        position = f"line {rejection.line_number}" if rejection.line_number else "source level"
        self._show_detail(
            window_title="Rejected source line details",
            eyebrow="STRUCTURED IMPORT DIAGNOSTIC",
            title=f"{rejection.code} · {rejection.source_name}",
            text=(
                f"Source: {rejection.source_name}\n"
                f"Position: {position}\n"
                f"Code: {rejection.code}\n"
                f"Message: {rejection.message}\n\n"
                f"Bounded source excerpt:\n{rejection.raw_excerpt or 'Unavailable'}"
            ),
        )

    def _show_detail(
        self,
        *,
        window_title: str,
        eyebrow: str,
        title: str,
        text: str,
    ) -> None:
        if self._detail_dialog is None:
            self._detail_dialog = DetailDialog(self)
        self._detail_dialog.present(
            window_title=window_title,
            eyebrow=eyebrow,
            title=title,
            text=text,
        )


def _configure_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    for column in range(table.columnCount()):
        table.horizontalHeader().setSectionResizeMode(
            column, QHeaderView.ResizeMode.ResizeToContents
        )


def _sightings_by_evidence(analysis: AnalysisSnapshot | None) -> dict[object, str]:
    values: dict[object, list[str]] = {}
    if analysis is None:
        return {}
    for sighting in analysis.sightings:
        values.setdefault(sighting.evidence_id, []).append(
            f"{sighting.rule_id} · {sighting.field_path}"
        )
    return {key: "; ".join(items) for key, items in values.items()}


def _match_detail(sightings: tuple[Sighting, ...]) -> str:
    if not sightings:
        return "  - No direct lead match; retained as source context."
    return "\n".join(
        f"  - {item.recipe_id}/{item.recipe_version} · {item.rule_id} · {item.explanation.text}"
        for item in sightings
    )
