# ruff: noqa: E501 - complete analyst-facing explanations stay close to widgets
"""Transparent deterministic next actions with an analyst-owned lifecycle."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.domain.workspace import Recommendation, RecommendationStatus
from ioc_evidence_packager.presentation.desktop.views.detail_dialog import DetailDialog

PRIORITY_COLORS = {"Immediate": "#FF7F9F", "Useful": "#F2B84B", "Optional": "#70D6E8"}
STATUS_COLORS = {
    "Proposed": "#C9B8FF",
    "Accepted": "#70D6E8",
    "Completed": "#67D7A4",
    "Dismissed": "#A49CB5",
}


class RecommendationsView(QWidget):
    """Explains every rule output and persists only the analyst decision overlay."""

    state_requested = Signal(str, str, object)
    evidence_pivot_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: tuple[Recommendation, ...] = ()
        self._visible: list[Recommendation] = []
        self._selected: Recommendation | None = None
        self._detail_dialog: DetailDialog | None = None
        self._build_ui()

    @property
    def row_count(self) -> int:
        return self._table.rowCount()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(14)
        eyebrow = QLabel("DETERMINISTIC ANALYST ASSISTANCE")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Recommendations")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Actions come from versioned rules over coverage, sightings, and relationships. They are not autonomous conclusions; each action exposes its rationale, expected value, safety note, and citations."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        self._summary = QLabel("No recommendation set is available.")
        self._summary.setObjectName("Muted")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        filters = QHBoxLayout()
        self._priority = QComboBox()
        self._priority.addItems(("All priorities", "Immediate", "Useful", "Optional"))
        self._priority.currentIndexChanged.connect(self._apply_filters)
        self._status = QComboBox()
        self._status.addItems(("All states", "Proposed", "Accepted", "Completed", "Dismissed"))
        self._status.currentIndexChanged.connect(self._apply_filters)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter action, category, rationale, rule, or citation…")
        self._search.textChanged.connect(self._apply_filters)
        filters.addWidget(self._priority)
        filters.addWidget(self._status)
        filters.addWidget(self._search, 1)
        root.addLayout(filters)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ("Priority", "State", "Category", "Recommended action", "Evidence", "Coverage", "Rule")
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.cellClicked.connect(self._open_detail)
        root.addWidget(self._table, 1)

        actions = QHBoxLayout()
        self._accepted = QPushButton("Accept")
        self._completed = QPushButton("Mark completed")
        self._dismissed = QPushButton("Dismiss with reason")
        self._reset = QPushButton("Reset to proposed")
        self._pivot = QPushButton("Open cited evidence")
        self._accepted.clicked.connect(lambda: self._set_state(RecommendationStatus.ACCEPTED))
        self._completed.clicked.connect(lambda: self._set_state(RecommendationStatus.COMPLETED))
        self._dismissed.clicked.connect(lambda: self._set_state(RecommendationStatus.DISMISSED))
        self._reset.clicked.connect(lambda: self._set_state(RecommendationStatus.PROPOSED))
        self._pivot.clicked.connect(self._pivot_evidence)
        for button in (self._accepted, self._completed, self._dismissed, self._reset, self._pivot):
            button.setEnabled(False)
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)

    def set_recommendations(self, items: tuple[Recommendation, ...]) -> None:
        if self._detail_dialog is not None:
            self._detail_dialog.close()
        self._items = items
        self._selected = None
        counts = {
            status.value: sum(item.status is status for item in items)
            for status in RecommendationStatus
        }
        self._summary.setText(
            f"{len(items)} current action(s) · {counts['Proposed']} proposed · {counts['Accepted']} accepted · {counts['Completed']} completed · {counts['Dismissed']} dismissed. Generated actions may change when evidence changes; analyst states are durable."
        )
        self._apply_filters()

    def _apply_filters(self) -> None:
        priority = self._priority.currentText()
        status = self._status.currentText()
        query = self._search.text().strip().casefold()
        visible: list[Recommendation] = []
        for item in self._items:
            if priority != "All priorities" and item.priority.value != priority:
                continue
            if status != "All states" and item.status.value != status:
                continue
            haystack = " ".join(
                (
                    item.title,
                    item.category,
                    item.rationale,
                    item.action,
                    item.rule_id,
                    *item.evidence_ids,
                    *item.coverage_cell_ids,
                    *item.relationship_ids,
                )
            ).casefold()
            if query and query not in haystack:
                continue
            visible.append(item)
        self._visible = visible
        self._populate()

    def _populate(self) -> None:
        self._table.setRowCount(0)
        for row, item in enumerate(self._visible):
            self._table.insertRow(row)
            values = (
                item.priority.value,
                item.status.value,
                item.category,
                item.title,
                str(len(item.evidence_ids)),
                str(len(item.coverage_cell_ids)),
                f"{item.rule_id}/{item.rule_version}",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setForeground(QBrush(QColor(PRIORITY_COLORS[value])))
                if column == 1:
                    cell.setForeground(QBrush(QColor(STATUS_COLORS[value])))
                cell.setToolTip(value)
                self._table.setItem(row, column, cell)

    def _open_detail(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self._visible):
            return
        item = self._visible[row]
        self._selected = item
        for button in (self._accepted, self._completed, self._dismissed, self._reset):
            button.setEnabled(True)
        self._pivot.setEnabled(bool(item.evidence_ids))
        text = (
            f"Recommendation ID: {item.recommendation_id}\nRule ID: {item.rule_id}/{item.rule_version}\n"
            f"Priority: {item.priority.value}\nState: {item.status.value}\nCategory: {item.category}\n"
            f"Rationale: {item.rationale}\nExpected value: {item.expected_value}\nSafety note: {item.safety_note}\n"
            f"Suggested action: {item.action}\nAnalyst note: {item.analyst_note or 'None'}\n"
            f"Updated at: {item.updated_at.isoformat() if item.updated_at else 'Not yet changed by an analyst'}\n"
            "Evidence citations:\n"
            + ("\n".join(f"  - {value}" for value in item.evidence_ids) or "  - None")
            + "\n"
            "Coverage citations:\n"
            + ("\n".join(f"  - {value}" for value in item.coverage_cell_ids) or "  - None")
            + "\n"
            "Relationship citations:\n"
            + ("\n".join(f"  - {value}" for value in item.relationship_ids) or "  - None")
        )
        if self._detail_dialog is None:
            self._detail_dialog = DetailDialog(self)
        self._detail_dialog.present(
            window_title="Recommendation details",
            eyebrow="RULE-EXPLAINED NEXT ACTION",
            title=item.title,
            text=text,
        )

    def _set_state(self, status: RecommendationStatus) -> None:
        if self._selected is None:
            return
        note: str | None = None
        if status is RecommendationStatus.DISMISSED:
            value, accepted = QInputDialog.getMultiLineText(
                self, "Dismiss recommendation", "Analyst reason (required):"
            )
            if not accepted or not value.strip():
                return
            note = value.strip()
        self.state_requested.emit(str(self._selected.recommendation_id), status.value, note)

    def _pivot_evidence(self) -> None:
        if self._selected is not None and self._selected.evidence_ids:
            self.evidence_pivot_requested.emit(self._selected.evidence_ids[0])
