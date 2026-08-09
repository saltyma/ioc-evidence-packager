"""Interactive vector canvas for evidence-backed relationship graphs."""

import math
from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.domain.workspace import (
    EntityId,
    EvidenceRelationship,
    RelationshipNode,
)

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

_CARD_WIDTH = 218.0
_CARD_HEIGHT = 58.0
_FOCUS_WIDTH = 236.0
_FOCUS_HEIGHT = 64.0


class InteractiveGraphicsView(QGraphicsView):
    """A high-quality graphics view with bounded cursor-centred zoom and panning."""

    zoom_changed = Signal(int)

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setObjectName("RelationshipGraphCanvas")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(QBrush(QColor("#0C0911")))
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setToolTip(
            "Mouse wheel: zoom · drag background: pan · drag node: rearrange · "
            "double-click node: focus · double-click edge: inspect"
        )

    @property
    def zoom_percent(self) -> int:
        return round(self.transform().m11() * 100)

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.zoom_by(1.18 if event.angleDelta().y() > 0 else 1 / 1.18)
        event.accept()

    def zoom_by(self, factor: float) -> None:
        current = self.transform().m11()
        target = max(0.12, min(5.0, current * factor))
        if math.isclose(target, current):
            return
        applied = target / current
        self.scale(applied, applied)
        self.zoom_changed.emit(self.zoom_percent)

    def reset_zoom(self) -> None:
        self.resetTransform()
        self.centerOn(self.scene().itemsBoundingRect().center())
        self.zoom_changed.emit(100)

    def fit_graph(self) -> None:
        bounds = self.scene().itemsBoundingRect()
        if bounds.isEmpty():
            self.resetTransform()
            self.zoom_changed.emit(100)
            return
        self.fitInView(bounds.adjusted(-54, -54, 54, 54), Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 1.15:
            self.resetTransform()
            self.centerOn(bounds.center())
        self.zoom_changed.emit(self.zoom_percent)


class GraphNodeItem(QGraphicsObject):
    """Movable, selectable node card that exposes its full value on hover."""

    def __init__(
        self,
        node: RelationshipNode,
        *,
        is_focus: bool,
        activated: Callable[[str], None],
        moved: Callable[[], None],
    ) -> None:
        super().__init__()
        self.node = node
        self.is_focus = is_focus
        self._activated = activated
        self._moved = moved
        self._hovered = False
        self._width = _FOCUS_WIDTH if is_focus else _CARD_WIDTH
        self._height = _FOCUS_HEIGHT if is_focus else _CARD_HEIGHT
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(
            f"{node.entity_type.value.upper()}\n{node.value}\n"
            f"Supported by {len(node.evidence_ids)} evidence record(s)\n"
            "Drag to rearrange · double-click to focus"
        )
        self.setZValue(10 if is_focus else 5)

    def boundingRect(self) -> QRectF:
        return QRectF(-self._width / 2, -self._height / 2, self._width, self._height)

    def paint(
        self,
        painter: QPainter,
        _option: QStyleOptionGraphicsItem,
        _widget: QWidget | None = None,
    ) -> None:
        bounds = self.boundingRect()
        color = QColor(TYPE_COLORS.get(self.node.entity_type.value, "#D9D2E3"))
        border = color.lighter(125) if self.isSelected() or self._hovered else color
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(border, 2.4 if self.isSelected() or self.is_focus else 1.4))
        painter.setBrush(QBrush(QColor("#1A1523" if self.is_focus else "#14101C")))
        painter.drawRoundedRect(bounds, 10, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(
            QRectF(bounds.left(), bounds.top(), 5, bounds.height()),
            2.5,
            2.5,
        )

        painter.setPen(QPen(color))
        type_font = QFont(painter.font())
        type_font.setPixelSize(10)
        type_font.setBold(True)
        type_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.7)
        painter.setFont(type_font)
        prefix = "FOCUS · " if self.is_focus else ""
        painter.drawText(
            QRectF(bounds.left() + 15, bounds.top() + 8, bounds.width() - 25, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{prefix}{self.node.entity_type.value.upper()}",
        )

        painter.setPen(QPen(QColor("#F5F0FC")))
        value_font = QFont(painter.font())
        value_font.setPixelSize(12 if self.is_focus else 11)
        value_font.setBold(self.is_focus)
        painter.setFont(value_font)
        painter.drawText(
            QRectF(bounds.left() + 15, bounds.top() + 26, bounds.width() - 25, 22),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            _short(self.node.value, 34 if self.is_focus else 31),
        )

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._moved()
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update()
        return result

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._hovered = True
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._hovered = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self._activated(str(self.node.entity_id))
        event.accept()


class GraphEdgeItem(QGraphicsPathItem):
    """Broad-hit-target curved edge with selection, hover, arrow, and provenance tooltip."""

    def __init__(
        self,
        edge: EvidenceRelationship,
        source: GraphNodeItem,
        target: GraphNodeItem,
        *,
        curve_offset: float,
        activated: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.edge = edge
        self.source = source
        self.target = target
        self.curve_offset = curve_offset
        self._activated = activated
        self._hovered = False
        self._arrow = QPolygonF()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(-5)
        self.setToolTip(
            f"{edge.relation}\n{source.node.value} → {target.node.value}\n"
            f"{len(edge.evidence_ids)} supporting evidence record(s)\n"
            "Double-click to inspect citations and rule provenance"
        )
        self.update_path()

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(14)
        return stroker.createStroke(self.path())

    def paint(
        self,
        painter: QPainter,
        _option: QStyleOptionGraphicsItem,
        _widget: QWidget | None = None,
    ) -> None:
        if self.isSelected():
            color, width = QColor("#F2B84B"), 2.8
        elif self._hovered:
            color, width = QColor("#C9B8FF"), 2.4
        else:
            color, width = QColor("#77658F"), 1.5
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(self.path())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPolygon(self._arrow)

    def update_path(self) -> None:
        source_center = self.source.scenePos()
        target_center = self.target.scenePos()
        start = _card_port(self.source, target_center)
        end = _card_port(self.target, source_center)
        delta = end - start
        length = max(1.0, math.hypot(delta.x(), delta.y()))
        normal = QPointF(-delta.y() / length, delta.x() / length) * self.curve_offset
        control_a = start + delta * 0.42 + normal
        control_b = start + delta * 0.58 + normal
        path = QPainterPath(start)
        path.cubicTo(control_a, control_b, end)
        self.setPath(path)

        arrow_base = path.pointAtPercent(0.94)
        arrow_tip = path.pointAtPercent(0.985)
        arrow_delta = arrow_tip - arrow_base
        arrow_angle = math.atan2(arrow_delta.y(), arrow_delta.x())
        wing = 8.0
        self._arrow = QPolygonF(
            [
                arrow_tip,
                arrow_tip
                - QPointF(
                    math.cos(arrow_angle - math.pi / 5) * wing,
                    math.sin(arrow_angle - math.pi / 5) * wing,
                ),
                arrow_tip
                - QPointF(
                    math.cos(arrow_angle + math.pi / 5) * wing,
                    math.sin(arrow_angle + math.pi / 5) * wing,
                ),
            ]
        )
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update()
        return result

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self._activated(str(self.edge.relationship_id))
        event.accept()


class RelationshipGraphCanvas(QWidget):
    """Graph toolbar and canvas shared by embedded and standalone presentations."""

    focus_requested = Signal(str)
    edge_activated = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        max_neighbors: int = 12,
        minimum_height: int = 390,
        neighbor_limits: tuple[int, ...] = (),
    ) -> None:
        super().__init__(parent)
        self._max_neighbors = max_neighbors
        self._nodes: dict[EntityId, RelationshipNode] = {}
        self._edges: tuple[EvidenceRelationship, ...] = ()
        self._focus_id: EntityId | None = None
        self._node_items: dict[EntityId, GraphNodeItem] = {}
        self._edge_items: list[GraphEdgeItem] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        tools = QHBoxLayout()
        tools.setSpacing(7)
        self._graph_count = QLabel("No graph")
        self._graph_count.setObjectName("Muted")
        tools.addWidget(self._graph_count)
        tools.addStretch(1)
        self._neighbor_limit: QComboBox | None = None
        if neighbor_limits:
            self._neighbor_limit = QComboBox()
            self._neighbor_limit.setToolTip(
                "Choose how many of the highest-connected one-hop neighbors to display."
            )
            for limit in neighbor_limits:
                self._neighbor_limit.addItem(f"Up to {limit} neighbors", limit)
            index = self._neighbor_limit.findData(max_neighbors)
            self._neighbor_limit.setCurrentIndex(max(0, index))
            self._neighbor_limit.currentIndexChanged.connect(self._set_neighbor_limit)
            tools.addWidget(self._neighbor_limit)
        self._cross_links = QCheckBox("Include cross-links")
        self._cross_links.setToolTip(
            "Also draw relationships between the displayed neighbors. Disabled by default "
            "to keep the one-hop view readable."
        )
        self._cross_links.toggled.connect(self._render)
        tools.addWidget(self._cross_links)
        fit = _tool_button("Fit", "Fit the whole bounded graph in the viewport")
        minus = _tool_button("−", "Zoom out")
        reset = _tool_button("100%", "Reset to actual size")
        plus = _tool_button("+", "Zoom in")
        fit.clicked.connect(self.fit_graph)
        minus.clicked.connect(self.zoom_out)
        reset.clicked.connect(self.reset_zoom)
        plus.clicked.connect(self.zoom_in)
        tools.addWidget(fit)
        tools.addWidget(minus)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setObjectName("GraphZoomLabel")
        self._zoom_label.setMinimumWidth(43)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tools.addWidget(self._zoom_label)
        tools.addWidget(reset)
        tools.addWidget(plus)
        root.addLayout(tools)

        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor("#0C0911")))
        self._scene.selectionChanged.connect(self._describe_selection)
        self.view = InteractiveGraphicsView(self._scene, self)
        self.view.setMinimumHeight(minimum_height)
        self.view.zoom_changed.connect(lambda value: self._zoom_label.setText(f"{value}%"))
        root.addWidget(self.view, 1)

        self._selection = QLabel(
            "Wheel: zoom · drag: pan or rearrange · double-click: focus or inspect"
        )
        self._selection.setObjectName("GraphSelectionStatus")
        self._selection.setWordWrap(True)
        root.addWidget(self._selection)

    @property
    def node_count(self) -> int:
        return len(self._node_items)

    @property
    def edge_count(self) -> int:
        return len(self._edge_items)

    @property
    def zoom_percent(self) -> int:
        return self.view.zoom_percent

    def set_relationships(
        self,
        nodes: Iterable[RelationshipNode],
        edges: Iterable[EvidenceRelationship],
        requested_focus: str,
    ) -> None:
        self._nodes = {node.entity_id: node for node in nodes}
        self._edges = tuple(edges)
        available = {value for edge in self._edges for value in (edge.source_id, edge.target_id)}
        requested_id = next(
            (value for value in available if str(value) == requested_focus),
            None,
        )
        degrees = {
            node_id: sum(node_id in {edge.source_id, edge.target_id} for edge in self._edges)
            for node_id in available
        }
        self._focus_id = (
            requested_id
            if requested_id is not None
            else max(available, key=lambda value: (degrees[value], str(value)), default=None)
        )
        self._render()

    def fit_graph(self) -> None:
        self.view.fit_graph()

    def reset_zoom(self) -> None:
        self.view.reset_zoom()

    def zoom_in(self) -> None:
        self.view.zoom_by(1.22)

    def zoom_out(self) -> None:
        self.view.zoom_by(1 / 1.22)

    def _set_neighbor_limit(self, _index: int) -> None:
        if self._neighbor_limit is not None:
            self._max_neighbors = int(self._neighbor_limit.currentData())
            self._render()

    def _render(self, _checked: bool = False) -> None:
        self._scene.clear()
        self._node_items = {}
        self._edge_items = []
        focus = self._focus_id
        if focus is None or focus not in self._nodes:
            empty = self._scene.addText("No relationships match the current filters.")
            empty.setDefaultTextColor(QColor("#A49CB5"))
            self._graph_count.setText("No graph")
            self._selection.setText("Adjust the entity, relationship, or search filters.")
            QTimer.singleShot(0, self.fit_graph)
            return

        adjacent = [edge for edge in self._edges if focus in {edge.source_id, edge.target_id}]
        degree: dict[EntityId, int] = {}
        for edge in self._edges:
            degree[edge.source_id] = degree.get(edge.source_id, 0) + 1
            degree[edge.target_id] = degree.get(edge.target_id, 0) + 1
        neighbors = sorted(
            {edge.target_id if edge.source_id == focus else edge.source_id for edge in adjacent},
            key=lambda value: (
                -degree.get(value, 0),
                self._nodes[value].entity_type.value,
                self._nodes[value].value,
            ),
        )
        total_neighbors = len(neighbors)
        neighbors = neighbors[: self._max_neighbors]
        selected_ids = {focus, *neighbors}
        displayed = [
            edge
            for edge in adjacent
            if edge.source_id in selected_ids and edge.target_id in selected_ids
        ]
        if self._cross_links.isChecked():
            displayed = [
                edge
                for edge in self._edges
                if edge.source_id in selected_ids and edge.target_id in selected_ids
            ]

        incoming: list[EntityId] = []
        outgoing: list[EntityId] = []
        for node_id in neighbors:
            incoming_count = sum(
                edge.source_id == node_id and edge.target_id == focus for edge in adjacent
            )
            outgoing_count = sum(
                edge.source_id == focus and edge.target_id == node_id for edge in adjacent
            )
            if incoming_count > outgoing_count:
                incoming.append(node_id)
            elif outgoing_count > incoming_count:
                outgoing.append(node_id)
            elif len(incoming) <= len(outgoing):
                incoming.append(node_id)
            else:
                outgoing.append(node_id)

        positions: dict[EntityId, QPointF] = {focus: QPointF(0, 0)}
        positions.update(_column_positions(incoming, -390.0))
        positions.update(_column_positions(outgoing, 390.0))
        for node_id in [focus, *neighbors]:
            node_item = GraphNodeItem(
                self._nodes[node_id],
                is_focus=node_id == focus,
                activated=self.focus_requested.emit,
                moved=self._update_edge_paths,
            )
            self._scene.addItem(node_item)
            node_item.setPos(positions[node_id])
            self._node_items[node_id] = node_item

        pair_counts: dict[frozenset[EntityId], int] = {}
        for edge in displayed:
            key = frozenset((edge.source_id, edge.target_id))
            pair_counts[key] = pair_counts.get(key, 0) + 1
        pair_seen: dict[frozenset[EntityId], int] = {}
        for edge in displayed:
            key = frozenset((edge.source_id, edge.target_id))
            index = pair_seen.get(key, 0)
            pair_seen[key] = index + 1
            curve_offset = (index - (pair_counts[key] - 1) / 2) * 22.0
            edge_item = GraphEdgeItem(
                edge,
                self._node_items[edge.source_id],
                self._node_items[edge.target_id],
                curve_offset=curve_offset,
                activated=self.edge_activated.emit,
            )
            self._scene.addItem(edge_item)
            self._edge_items.append(edge_item)

        bounds = self._scene.itemsBoundingRect().adjusted(-70, -70, 70, 70)
        self._scene.setSceneRect(bounds)
        omitted = total_neighbors - len(neighbors)
        suffix = f" · {omitted} more available by changing focus" if omitted else ""
        cross_link_text = (
            "with cross-links" if self._cross_links.isChecked() else "focus edges only"
        )
        self._graph_count.setText(
            f"{len(self._node_items)} nodes · {len(self._edge_items)} edges · "
            f"{cross_link_text}{suffix}"
        )
        self._selection.setText(
            "Wheel: zoom · drag: pan or rearrange · double-click: focus or inspect"
        )
        QTimer.singleShot(0, self.fit_graph)

    def _update_edge_paths(self) -> None:
        for edge in self._edge_items:
            edge.update_path()
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-70, -70, 70, 70))

    def _describe_selection(self) -> None:
        selected = self._scene.selectedItems()
        if not selected:
            return
        item = selected[0]
        if isinstance(item, GraphNodeItem):
            node = item.node
            self._selection.setText(
                f"NODE · {node.entity_type.value.upper()} · {node.value} · "
                f"{len(node.evidence_ids)} evidence record(s) · double-click to focus"
            )
        elif isinstance(item, GraphEdgeItem):
            edge = item.edge
            self._selection.setText(
                f"EDGE · {item.source.node.value} → {item.target.node.value} · "
                f"{edge.relation} · {len(edge.evidence_ids)} citation(s) · "
                "double-click for provenance"
            )


class RelationshipGraphWindow(QDialog):
    """Non-modal, resizable home for the expanded interactive graph canvas."""

    focus_requested = Signal(str)
    edge_activated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RelationshipGraphWindow")
        self.setWindowTitle("Interactive relationship graph · IOC Evidence Packager")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
        self.setMinimumSize(860, 560)
        self.resize(1180, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)
        heading = QLabel("Interactive relationship graph")
        heading.setObjectName("PageTitle")
        root.addWidget(heading)
        explanation = QLabel(
            "Explore the current filtered evidence graph without losing your place in the case. "
            "Selection is explanatory; every edge still comes from deterministic rules and cites "
            "supporting evidence."
        )
        explanation.setObjectName("PageSubtitle")
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        self.canvas = RelationshipGraphCanvas(
            self,
            max_neighbors=10,
            minimum_height=440,
            neighbor_limits=(10, 20, 30),
        )
        self.canvas.focus_requested.connect(self.focus_requested.emit)
        self.canvas.edge_activated.connect(self.edge_activated.emit)
        root.addWidget(self.canvas, 1)

    def present(
        self,
        nodes: Iterable[RelationshipNode],
        edges: Iterable[EvidenceRelationship],
        requested_focus: str,
    ) -> None:
        self.canvas.set_relationships(nodes, edges, requested_focus)
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self.canvas.fit_graph)


def _column_positions(node_ids: list[EntityId], x: float) -> dict[EntityId, QPointF]:
    spacing = 82.0
    centre = (len(node_ids) - 1) / 2
    return {
        node_id: QPointF(x, (index - centre) * spacing) for index, node_id in enumerate(node_ids)
    }


def _card_port(item: GraphNodeItem, toward: QPointF) -> QPointF:
    center = item.scenePos()
    delta = toward - center
    if math.isclose(delta.x(), 0.0) and math.isclose(delta.y(), 0.0):
        return center
    half_width = item.boundingRect().width() / 2
    half_height = item.boundingRect().height() / 2
    x_scale = half_width / abs(delta.x()) if not math.isclose(delta.x(), 0.0) else math.inf
    y_scale = half_height / abs(delta.y()) if not math.isclose(delta.y(), 0.0) else math.inf
    scale = min(x_scale, y_scale)
    return center + delta * scale


def _tool_button(text: str, tooltip: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("GraphToolButton")
    button.setToolTip(tooltip)
    button.setMinimumWidth(38)
    return button


def _short(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"
