# ruff: noqa: E501 - complete analyst-facing explanations stay close to widgets
"""Bounded evidence-backed relationship graph and edge ledger."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.domain.workspace import (
    EvidenceRelationship,
    RelationshipNode,
    RelationshipSnapshot,
)
from ioc_evidence_packager.presentation.desktop.views.detail_dialog import DetailDialog
from ioc_evidence_packager.presentation.desktop.views.relationship_graph import (
    TYPE_COLORS,
    RelationshipGraphCanvas,
    RelationshipGraphWindow,
)


class RelationshipsView(QWidget):
    """Shows only relationships that can be traced back to evidence IDs."""

    pivot_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snapshot = RelationshipSnapshot((), ())
        self._visible: list[EvidenceRelationship] = []
        self._nodes: dict[object, RelationshipNode] = {}
        self._selected: EvidenceRelationship | None = None
        self._detail_dialog: DetailDialog | None = None
        self._graph_window: RelationshipGraphWindow | None = None
        self._build_ui()

    @property
    def row_count(self) -> int:
        return self._table.rowCount()

    @property
    def graph_node_count(self) -> int:
        return self._graph_canvas.node_count

    @property
    def graph_edge_count(self) -> int:
        return self._graph_canvas.edge_count

    @property
    def graph_window(self) -> RelationshipGraphWindow | None:
        return self._graph_window

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(10)
        eyebrow = QLabel("EVIDENCE GRAPH")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Relationships")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Every edge is deterministic, typed, bounded to this case, and cites the exact "
            "supporting evidence. A relationship is context, not proof of causation."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        self._type = QComboBox()
        self._type.setMinimumWidth(135)
        self._type.addItem("All entity types", "")
        for value in TYPE_COLORS:
            self._type.addItem(value.upper(), value)
        self._type.currentIndexChanged.connect(self._apply_filters)
        self._relation = QComboBox()
        self._relation.setMinimumWidth(170)
        self._relation.addItem("All relationship types", "")
        self._relation.currentIndexChanged.connect(self._apply_filters)
        self._focus = QComboBox()
        self._focus.setMinimumWidth(270)
        self._focus.addItem("Automatic one-hop focus", "")
        self._focus.currentIndexChanged.connect(self._draw_graph)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter entity value, relationship, rule, or evidence ID…")
        self._search.textChanged.connect(self._apply_filters)
        self._pivot = QPushButton("Pivot to Evidence")
        self._pivot.setEnabled(False)
        self._pivot.clicked.connect(self._emit_pivot)
        filters.addWidget(self._type)
        filters.addWidget(self._relation)
        filters.addWidget(self._focus, 1)
        root.addLayout(filters)

        search_actions = QHBoxLayout()
        search_actions.setSpacing(10)
        search_actions.addWidget(self._search, 1)
        search_actions.addWidget(self._pivot)
        root.addLayout(search_actions)

        self._summary = QLabel("No evidence graph is available yet.")
        self._summary.setObjectName("Muted")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        tabs = QTabWidget()
        tabs.setObjectName("RelationshipTabs")
        graph_page = QWidget()
        graph_page.setObjectName("RelationshipGraphPage")
        graph_layout = QVBoxLayout(graph_page)
        graph_layout.setContentsMargins(0, 12, 0, 0)
        graph_layout.setSpacing(0)
        graph_body = QHBoxLayout()
        graph_body.setContentsMargins(0, 0, 0, 0)
        graph_body.setSpacing(12)
        self._graph_canvas = RelationshipGraphCanvas(
            self,
            max_neighbors=6,
            minimum_height=410,
            allow_expand=True,
        )
        self._graph_canvas.focus_requested.connect(self._select_graph_focus)
        self._graph_canvas.edge_activated.connect(self._open_graph_edge)
        self._graph_canvas.background_double_clicked.connect(self.open_graph_window)
        self._graph_canvas.expand_requested.connect(self.open_graph_window)
        graph_body.addWidget(self._graph_canvas, 1)
        graph_body.addWidget(_graph_legend())
        graph_layout.addLayout(graph_body, 1)
        tabs.addTab(graph_page, "Graph")

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ("From", "Type", "Relationship", "To", "Type", "Evidence", "Rule")
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.cellClicked.connect(self._open_detail)
        tabs.addTab(self._table, "Evidence-backed edges")
        root.addWidget(tabs, 1)

    def set_relationships(self, snapshot: RelationshipSnapshot) -> None:
        if self._detail_dialog is not None:
            self._detail_dialog.close()
        self._snapshot = snapshot
        self._nodes = {node.entity_id: node for node in snapshot.nodes}
        current = self._relation.currentData()
        relations = sorted({edge.relation for edge in snapshot.edges})
        self._relation.blockSignals(True)
        self._relation.clear()
        self._relation.addItem("All relationship types", "")
        for relation in relations:
            self._relation.addItem(relation, relation)
        index = self._relation.findData(current)
        self._relation.setCurrentIndex(max(0, index))
        self._relation.blockSignals(False)
        focus_value = self._focus.currentData()
        self._focus.blockSignals(True)
        self._focus.clear()
        self._focus.addItem("Automatic one-hop focus", "")
        for node in sorted(
            snapshot.nodes, key=lambda value: (value.entity_type.value, value.value)
        ):
            self._focus.addItem(
                f"{node.entity_type.value.upper()} · {_short(node.value, 40)}",
                str(node.entity_id),
            )
        focus_index = self._focus.findData(focus_value)
        self._focus.setCurrentIndex(max(0, focus_index))
        self._focus.blockSignals(False)
        self._summary.setText(
            f"{len(snapshot.nodes)} typed entity node(s) · {len(snapshot.edges)} evidence-backed edge(s) · graph objects are selectable and every edge exposes citations and rule provenance."
        )
        self._apply_filters()

    def _apply_filters(self) -> None:
        selected_type = str(self._type.currentData() or "")
        selected_relation = str(self._relation.currentData() or "")
        query = self._search.text().strip().casefold()
        visible: list[EvidenceRelationship] = []
        for edge in self._snapshot.edges:
            left = self._nodes[edge.source_id]
            right = self._nodes[edge.target_id]
            if selected_type and selected_type not in {
                left.entity_type.value,
                right.entity_type.value,
            }:
                continue
            if selected_relation and edge.relation != selected_relation:
                continue
            haystack = " ".join(
                (left.value, right.value, edge.relation, edge.rule_id, *edge.evidence_ids)
            ).casefold()
            if query and query not in haystack:
                continue
            visible.append(edge)
        self._visible = visible
        if self._selected not in visible:
            self._selected = None
            self._pivot.setEnabled(False)
        self._populate_table()
        self._draw_graph()

    def _populate_table(self) -> None:
        self._table.setRowCount(0)
        for row, edge in enumerate(self._visible):
            left = self._nodes[edge.source_id]
            right = self._nodes[edge.target_id]
            self._table.insertRow(row)
            values = (
                left.value,
                left.entity_type.value.upper(),
                edge.relation,
                right.value,
                right.entity_type.value.upper(),
                str(len(edge.evidence_ids)),
                edge.rule_id,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 1:
                    item.setForeground(QBrush(QColor(TYPE_COLORS[left.entity_type.value])))
                elif column == 4:
                    item.setForeground(QBrush(QColor(TYPE_COLORS[right.entity_type.value])))
                elif column == 2:
                    item.setForeground(QBrush(QColor("#F2B84B")))
                item.setToolTip(value)
                self._table.setItem(row, column, item)

    def _draw_graph(self) -> None:
        requested = str(self._focus.currentData() or "")
        nodes = tuple(self._nodes.values())
        edges = tuple(self._visible)
        self._graph_canvas.set_relationships(nodes, edges, requested)
        if self._graph_window is not None and self._graph_window.isVisible():
            self._graph_window.canvas.set_relationships(nodes, edges, requested)

    def _open_detail(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self._visible):
            return
        self._present_edge(self._visible[row])

    def _present_edge(self, edge: EvidenceRelationship) -> None:
        self._selected = edge
        self._pivot.setEnabled(True)
        left = self._nodes[edge.source_id]
        right = self._nodes[edge.target_id]
        text = (
            f"Relationship ID: {edge.relationship_id}\n"
            f"From type: {left.entity_type.value.upper()}\nFrom value: {left.value}\n"
            f"Relationship: {edge.relation}\n"
            f"To type: {right.entity_type.value.upper()}\nTo value: {right.value}\n"
            f"Rule ID: {edge.rule_id}\nExplanation: {edge.explanation}\n"
            "Supporting evidence IDs:\n" + "\n".join(f"  - {value}" for value in edge.evidence_ids)
        )
        if self._detail_dialog is None:
            self._detail_dialog = DetailDialog(self)
        self._detail_dialog.present(
            window_title="Relationship details",
            eyebrow="EVIDENCE-BACKED EDGE",
            title=f"{left.value}  →  {right.value}",
            text=text,
        )

    def open_graph_window(self) -> None:
        """Show the filtered graph in a resizable, non-modal interactive window."""

        if self._graph_window is None:
            self._graph_window = RelationshipGraphWindow(self)
            self._graph_window.focus_requested.connect(self._select_graph_focus)
            self._graph_window.edge_activated.connect(self._open_graph_edge)
        self._graph_window.present(
            tuple(self._nodes.values()),
            tuple(self._visible),
            str(self._focus.currentData() or ""),
        )

    def _select_graph_focus(self, node_id: str) -> None:
        index = self._focus.findData(node_id)
        if index >= 0:
            self._focus.setCurrentIndex(index)

    def _open_graph_edge(self, relationship_id: str) -> None:
        edge = next(
            (item for item in self._snapshot.edges if str(item.relationship_id) == relationship_id),
            None,
        )
        if edge is not None:
            self._present_edge(edge)

    def _emit_pivot(self) -> None:
        if self._selected is not None:
            left = self._nodes[self._selected.source_id]
            right = self._nodes[self._selected.target_id]
            value = (
                right.value if right.entity_type.value not in {"event", "source"} else left.value
            )
            self.pivot_requested.emit(value)


def _short(value: str, limit: int = 30) -> str:
    return value if len(value) <= limit else value[:27] + "…"


def _legend_chip(entity_type: str) -> QLabel:
    label = QLabel(
        f'<span style="color:{TYPE_COLORS[entity_type]};">●</span>&nbsp;{entity_type.upper()}'
    )
    label.setObjectName("GraphLegendChip")
    label.setToolTip(f"{entity_type.upper()} entities use this color in the graph")
    return label


def _graph_legend() -> QFrame:
    legend = QFrame()
    legend.setObjectName("GraphLegendPanel")
    legend.setFixedWidth(112)
    layout = QVBoxLayout(legend)
    layout.setContentsMargins(10, 12, 10, 12)
    layout.setSpacing(7)
    title = QLabel("ENTITY\nCOLORS")
    title.setObjectName("SectionEyebrow")
    layout.addWidget(title)
    for entity_type in ("source", "event", "host", "user", "ipv4", "domain", "sha256"):
        layout.addWidget(_legend_chip(entity_type))
    layout.addStretch(1)
    return legend
