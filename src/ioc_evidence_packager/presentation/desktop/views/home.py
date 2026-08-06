"""Recent-case home screen."""

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.domain.models import Case


class HomeView(QWidget):
    """Landing page with a guided start and recent investigations."""

    create_requested = Signal()
    open_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(22)

        eyebrow = QLabel("LOCAL INVESTIGATION WORKSPACE")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Turn a lead into defensible evidence")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Create a case, bring the telemetry you are authorized to use, and preserve "
            "what was found—along with what could not be searched."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        hero = QFrame()
        hero.setObjectName("HeroPanel")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(24)

        hero_text = QVBoxLayout()
        hero_title = QLabel("Start an IOC-centered investigation")
        hero_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #F4FAFF;")
        hero_copy = QLabel(
            "The guided workflow records case context, previews every source, and keeps "
            "network access disabled unless you explicitly change policy."
        )
        hero_copy.setObjectName("Muted")
        hero_copy.setWordWrap(True)
        hero_text.addWidget(hero_title)
        hero_text.addWidget(hero_copy)
        hero_layout.addLayout(hero_text, 1)

        create_button = QPushButton("New investigation")
        create_button.setObjectName("PrimaryButton")
        create_button.setMinimumWidth(165)
        create_button.clicked.connect(self.create_requested.emit)
        hero_layout.addWidget(create_button, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(hero)

        recent_header = QHBoxLayout()
        recent_title = QLabel("Recent cases")
        recent_title.setStyleSheet("font-size: 17px; font-weight: 700;")
        recent_header.addWidget(recent_title)
        recent_header.addStretch(1)
        self._open_button = QPushButton("Open selected")
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(self._emit_selected_case)
        recent_header.addWidget(self._open_button)
        root.addLayout(recent_header)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Case", "Status", "Policy", "Last opened"])
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            self._table.horizontalHeader().setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        self._table.itemSelectionChanged.connect(self._selection_changed)
        self._table.cellDoubleClicked.connect(self._double_clicked)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._table, 1)

        self._empty_label = QLabel(
            "No local cases yet. Create the first investigation to establish the workspace."
        )
        self._empty_label.setObjectName("Muted")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._empty_label)

    def set_cases(self, cases: Sequence[Case]) -> None:
        self._table.setRowCount(len(cases))
        for row, case in enumerate(cases):
            title_item = QTableWidgetItem(case.title)
            title_item.setData(Qt.ItemDataRole.UserRole, str(case.case_id))
            if case.external_reference:
                title_item.setToolTip(f"External reference: {case.external_reference}")
            self._table.setItem(row, 0, title_item)
            self._table.setItem(row, 1, QTableWidgetItem(_display_enum(case.status.value)))
            self._table.setItem(row, 2, QTableWidgetItem(_display_enum(case.privacy_mode.value)))
            opened = case.last_opened_at.astimezone().strftime("%Y-%m-%d  %H:%M")
            self._table.setItem(row, 3, QTableWidgetItem(opened))
            self._table.setRowHeight(row, 42)
        has_cases = bool(cases)
        self._table.setVisible(has_cases)
        self._empty_label.setVisible(not has_cases)
        self._open_button.setEnabled(False)

    def _selection_changed(self) -> None:
        self._open_button.setEnabled(self._selected_case_id() is not None)

    def _double_clicked(self, _row: int, _column: int) -> None:
        self._emit_selected_case()

    def _emit_selected_case(self) -> None:
        case_id = self._selected_case_id()
        if case_id is not None:
            self.open_requested.emit(case_id)

    def _selected_case_id(self) -> str | None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self._table.item(selected[0].row(), 0)
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return str(value) if value else None


def _display_enum(value: str) -> str:
    return value.replace("_", " ").title()
