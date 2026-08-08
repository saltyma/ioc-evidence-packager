"""Deterministic evidence timeline with direct/context/undated filters."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.domain.analysis import AnalysisSnapshot
from ioc_evidence_packager.domain.evidence import EvidenceRecord


class TimelineView(QWidget):
    """Chronological source facts; undated events are never assigned invented times."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: tuple[EvidenceRecord, ...] = ()
        self._visible: list[EvidenceRecord] = []
        self._analysis: AnalysisSnapshot | None = None
        self._build_ui()

    @property
    def row_count(self) -> int:
        return self._table.rowCount()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(15)
        eyebrow = QLabel("DETERMINISTIC TIMELINE")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Chronology without invented time")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Events are ordered by normalized UTC time, source identity, and physical "
            "position. Records without a trustworthy timestamp stay in the Undated lane."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        filters = QHBoxLayout()
        self._class_filter = QComboBox()
        self._class_filter.addItems(("All evidence", "Direct matches", "Context", "Undated"))
        self._class_filter.currentIndexChanged.connect(self._apply_filters)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter host, user, event, source, or category…")
        self._search.textChanged.connect(self._apply_filters)
        self._summary = QLabel("0 events")
        self._summary.setObjectName("Muted")
        filters.addWidget(self._class_filter)
        filters.addWidget(self._search, 1)
        filters.addWidget(self._summary)
        root.addLayout(filters)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            ["UTC time", "Class", "Category", "Action", "Host", "User", "Source", "Line"]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        for column in range(8):
            self._table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._selection_changed)
        root.addWidget(self._table, 1)

        detail_label = QLabel("SELECTED EVENT · SOURCE-LINKED DETAIL")
        detail_label.setObjectName("SectionEyebrow")
        root.addWidget(detail_label)
        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(150)
        root.addWidget(self._detail)

    def set_records(
        self,
        records: tuple[EvidenceRecord, ...],
        analysis: AnalysisSnapshot | None,
    ) -> None:
        self._records = records
        self._analysis = analysis
        self._apply_filters()

    def _apply_filters(self) -> None:
        direct = self._analysis.direct_evidence_ids if self._analysis else frozenset()
        mode = self._class_filter.currentText()
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
            haystack = " ".join(
                (
                    record.event_id,
                    record.category,
                    record.action,
                    record.host_name or "",
                    record.user_name or "",
                    record.source_name,
                )
            ).casefold()
            if query and query not in haystack:
                continue
            visible.append(record)
        self._visible = visible
        self._populate(direct)

    def _populate(self, direct: frozenset[object]) -> None:
        self._table.setRowCount(0)
        for row, record in enumerate(self._visible):
            self._table.insertRow(row)
            values = (
                record.occurred_at.isoformat() if record.occurred_at else "Undated",
                "DIRECT" if record.evidence_id in direct else "CONTEXT",
                record.category,
                record.action,
                record.host_name or "—",
                record.user_name or "—",
                record.source_name,
                str(record.line_number),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self._table.setItem(row, column, item)
        undated = sum(record.occurred_at is None for record in self._records)
        self._summary.setText(f"{len(self._visible)} shown · {undated} undated")

    def _selection_changed(self) -> None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            self._detail.clear()
            return
        record = self._visible[selected[0].row()]
        self._detail.setPlainText(
            f"Evidence ID: {record.evidence_id}\n"
            f"Event ID: {record.event_id}\n"
            f"Source: {record.source_path}\n"
            f"SHA-256: {record.source_sha256 or 'Unavailable'}\n"
            f"Position: line {record.line_number}\n\n"
            f"Raw canonical JSON:\n{record.raw_json}"
        )
