"""Inspectable six-state Evidence Coverage Matrix."""

from collections import Counter

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.domain.analysis import AnalysisSnapshot, CoverageState
from ioc_evidence_packager.presentation.desktop.views.detail_dialog import DetailDialog

STATE_COLORS = {
    CoverageState.MATCH_FOUND: "#67D7A4",
    CoverageState.SEARCHED_NO_MATCH: "#AFA6BF",
    CoverageState.PARTIAL_COVERAGE: "#F2B84B",
    CoverageState.SOURCE_NOT_PROVIDED: "#D8A65A",
    CoverageState.SOURCE_FAILED: "#FF8A8A",
    CoverageState.FORMAT_UNSUPPORTED: "#C795FF",
}


class CoverageView(QWidget):
    """Shows every coverage state with its inputs, reason, and recovery action."""

    analysis_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analysis: AnalysisSnapshot | None = None
        self._detail_dialog: DetailDialog | None = None
        self._build_ui()

    @property
    def row_count(self) -> int:
        return self._table.rowCount()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(15)

        heading = QHBoxLayout()
        heading_text = QVBoxLayout()
        eyebrow = QLabel("EVIDENCE COVERAGE MATRIX")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("What was searched and what was not")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Coverage is calculated from declared source capabilities, import outcomes, "
            "rejected lines, and exact recipe results. A no-match is never labeled clean."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        heading_text.addWidget(eyebrow)
        heading_text.addWidget(title)
        heading_text.addWidget(subtitle)
        heading.addLayout(heading_text, 1)
        self._rerun_button = QPushButton("Re-run analysis")
        self._rerun_button.setObjectName("PrimaryButton")
        self._rerun_button.clicked.connect(self.analysis_requested)
        self._rerun_button.setEnabled(False)
        root.addLayout(heading)

        notice = QFrame()
        notice.setObjectName("NoticeCard")
        notice_layout = QHBoxLayout(notice)
        notice_layout.setContentsMargins(16, 12, 16, 12)
        self._summary = QLabel("Import evidence to calculate coverage.")
        self._summary.setObjectName("Muted")
        self._summary.setWordWrap(True)
        notice_layout.addWidget(self._summary, 1)
        notice_layout.addWidget(self._rerun_button)
        root.addWidget(notice)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Recipe step", "Telemetry", "State", "Matches", "Sources", "Reason"]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        for column in range(5):
            self._table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.cellClicked.connect(self._open_detail)
        root.addWidget(self._table, 1)

    def set_analysis(self, analysis: AnalysisSnapshot | None) -> None:
        self._analysis = analysis
        self._table.setRowCount(0)
        if self._detail_dialog is not None:
            self._detail_dialog.close()
        self._rerun_button.setEnabled(analysis is not None)
        if analysis is None:
            self._summary.setText("Import evidence to calculate coverage.")
            return
        counts = Counter(cell.state for cell in analysis.coverage)
        self._summary.setText(
            f"Recipe {analysis.recipe_id}/{analysis.recipe_version} · "
            f"{len(analysis.sightings)} direct sighting(s) · "
            f"{counts[CoverageState.MATCH_FOUND]} matched · "
            f"{analysis.warning_count} limitation(s)."
        )
        for row, cell in enumerate(analysis.coverage):
            self._table.insertRow(row)
            values = (
                cell.step_label,
                cell.telemetry,
                cell.state.value.replace("_", " "),
                str(cell.match_count),
                str(len(cell.source_preview_ids)),
                cell.reason.message,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 2:
                    item.setForeground(QColor(STATE_COLORS[cell.state]))
                    item.setData(Qt.ItemDataRole.UserRole, cell.state.value)
                self._table.setItem(row, column, item)

    def _open_detail(self, row: int, _column: int) -> None:
        if self._analysis is None or not 0 <= row < len(self._analysis.coverage):
            return
        cell = self._analysis.coverage[row]
        sources = ", ".join(str(value) for value in cell.source_preview_ids) or "None"
        evidence = ", ".join(str(value) for value in cell.evidence_ids) or "None"
        if self._detail_dialog is None:
            self._detail_dialog = DetailDialog(self)
        self._detail_dialog.present(
            window_title="Coverage calculation details",
            eyebrow="INSPECTABLE COVERAGE CALCULATION",
            title=f"{cell.step_label} · {cell.state.value.replace('_', ' ')}",
            text=(
                f"Coverage cell: {cell.cell_id}\n"
                f"Recipe step: {cell.step_label} ({cell.step_id})\n"
                f"Telemetry: {cell.telemetry}\n"
                f"State: {cell.state.value}\n"
                f"Matches: {cell.match_count}\n"
                f"Reason code: {cell.reason.code}\n"
                f"Calculation: {cell.reason.message}\n"
                f"Recovery: {cell.reason.recovery or 'No recovery action required.'}\n"
                f"Supporting sources: {sources}\n"
                f"Supporting evidence: {evidence}"
            ),
        )
