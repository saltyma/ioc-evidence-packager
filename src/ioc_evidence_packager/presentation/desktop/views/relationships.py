# ruff: noqa: E501 - complete analyst-facing explanations stay close to widgets
"""Bounded evidence-backed relationship graph and edge ledger."""

import math

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGraphicsScene,
    QGraphicsView,
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

TYPE_COLORS = {
    "source": "#70D6E8",
    "event": "#C9B8FF",
    "host": "#67D7A4",
    "user": "#F2B84B",
    "ipv4": "#FF9F7A",
    "domain": "#A78BFA",
    "sha256": "#FF7F9F",
    "observable": "#D9D2E3",
}


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
        self._build_ui()

    @property
    def row_count(self) -> int:
        return self._table.rowCount()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(14)
        eyebrow = QLabel("EVIDENCE GRAPH")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Relationships")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Every edge is deterministic, typed, bounded to this case, and cites the exact supporting evidence. A relationship is context—not proof of causation."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        controls = QHBoxLayout()
        self._type = QComboBox()
        self._type.addItem("All entity types", "")
        for value in TYPE_COLORS:
            self._type.addItem(value.upper(), value)
        self._type.currentIndexChanged.connect(self._apply_filters)
        self._relation = QComboBox()
        self._relation.addItem("All relationship types", "")
        self._relation.currentIndexChanged.connect(self._apply_filters)
        self._focus = QComboBox()
        self._focus.setMinimumWidth(230)
        self._focus.addItem("Automatic one-hop focus", "")
        self._focus.currentIndexChanged.connect(self._draw_graph)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter entity value, relationship, rule, or evidence ID…")
        self._search.textChanged.connect(self._apply_filters)
        self._pivot = QPushButton("Pivot to Evidence")
        self._pivot.setEnabled(False)
        self._pivot.clicked.connect(self._emit_pivot)
        controls.addWidget(self._type)
        controls.addWidget(self._relation)
        controls.addWidget(self._focus)
        controls.addWidget(self._search, 1)
        controls.addWidget(self._pivot)
        root.addLayout(controls)

        self._summary = QLabel("No evidence graph is available yet.")
        self._summary.setObjectName("Muted")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        tabs = QTabWidget()
        graph_page = QWidget()
        graph_layout = QVBoxLayout(graph_page)
        graph_layout.setContentsMargins(0, 10, 0, 0)
        legend = QLabel(
            "COLOR KEY  ·  SOURCE cyan  ·  EVENT violet  ·  HOST green  ·  USER amber  ·  IPv4 coral  ·  DOMAIN purple  ·  SHA-256 pink"
        )
        legend.setObjectName("Muted")
        legend.setWordWrap(True)
        graph_layout.addWidget(legend)
        self._scene = QGraphicsScene(self)
        self._graph = QGraphicsView(self._scene)
        self._graph.setRenderHint(self._graph.renderHints())
        self._graph.setMinimumHeight(300)
        graph_layout.addWidget(self._graph, 1)
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
            f"{len(snapshot.nodes)} typed entity node(s) · {len(snapshot.edges)} evidence-backed edge(s) · click a table row for citations and rule provenance."
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
        self._scene.clear()
        available = {value for edge in self._visible for value in (edge.source_id, edge.target_id)}
        if not available:
            self._scene.addText("No relationships match the current filters.").setDefaultTextColor(
                QColor("#A49CB5")
            )
            return
        requested = str(self._focus.currentData() or "")
        requested_id = next((value for value in available if str(value) == requested), None)
        degrees = {
            node_id: sum(node_id in {edge.source_id, edge.target_id} for edge in self._visible)
            for node_id in available
        }
        focus = requested_id or max(available, key=lambda value: (degrees[value], str(value)))
        neighbor_ids = sorted(
            {
                edge.target_id if edge.source_id == focus else edge.source_id
                for edge in self._visible
                if focus in {edge.source_id, edge.target_id}
            },
            key=lambda value: (-degrees[value], str(value)),
        )[:16]
        node_ids = [focus, *neighbor_ids]
        positions: dict[object, tuple[float, float]] = {focus: (0.0, 0.0)}
        radius = max(170.0, len(neighbor_ids) * 12.0)
        for index, node_id in enumerate(neighbor_ids):
            angle = (2 * math.pi * index / max(1, len(neighbor_ids))) - math.pi / 2
            positions[node_id] = (math.cos(angle) * radius, math.sin(angle) * radius)
        pen = QPen(QColor("#554869"), 1.2)
        for edge in self._visible:
            if edge.source_id in positions and edge.target_id in positions:
                x1, y1 = positions[edge.source_id]
                x2, y2 = positions[edge.target_id]
                self._scene.addLine(x1, y1, x2, y2, pen)
        for node_id in node_ids:
            node = self._nodes[node_id]
            x, y = positions[node_id]
            color = QColor(TYPE_COLORS[node.entity_type.value])
            size = 30 if node_id == focus else 20
            self._scene.addEllipse(
                x - size / 2,
                y - size / 2,
                size,
                size,
                QPen(color, 2 if node_id == focus else 1),
                QBrush(color.darker(220)),
            )
            text = self._scene.addText(
                f"{'FOCUS · ' if node_id == focus else ''}{node.entity_type.value.upper()}\n"
                f"{_short(node.value)}"
            )
            text.setDefaultTextColor(color)
            text.setPos(x + 13, y - 16)
            text.setToolTip(node.value)
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-30, -30, 30, 30))

    def _open_detail(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self._visible):
            return
        edge = self._visible[row]
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
