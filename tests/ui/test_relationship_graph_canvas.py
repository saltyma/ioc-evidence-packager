"""Regression tests for the interactive relationship graph lifecycle."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from ioc_evidence_packager.domain.workspace import (  # noqa: E402
    EntityId,
    EntityType,
    EvidenceRelationship,
    RelationshipId,
    RelationshipNode,
)
from ioc_evidence_packager.presentation.desktop.app import create_qapplication  # noqa: E402
from ioc_evidence_packager.presentation.desktop.views.relationship_graph import (  # noqa: E402
    RelationshipGraphCanvas,
)


def _relationship_fixture(
    neighbor_count: int = 24,
) -> tuple[tuple[RelationshipNode, ...], tuple[EvidenceRelationship, ...], EntityId]:
    focus_id = EntityId("entity-focus")
    nodes = [
        RelationshipNode(
            entity_id=focus_id,
            entity_type=EntityType.HOST,
            value="FIN-WS-014",
            label="Host FIN-WS-014",
            evidence_ids=("evidence-focus",),
        )
    ]
    edges: list[EvidenceRelationship] = []
    types = (EntityType.IPV4, EntityType.DOMAIN, EntityType.EVENT, EntityType.SHA256)
    for index in range(neighbor_count):
        node_id = EntityId(f"entity-{index:02d}")
        entity_type = types[index % len(types)]
        nodes.append(
            RelationshipNode(
                entity_id=node_id,
                entity_type=entity_type,
                value=f"fixture-{entity_type.value}-{index:02d}",
                label=f"Fixture {index:02d}",
                evidence_ids=(f"evidence-{index:02d}",),
            )
        )
        edges.append(
            EvidenceRelationship(
                relationship_id=RelationshipId(f"relationship-{index:02d}"),
                source_id=focus_id if index % 2 else node_id,
                target_id=node_id if index % 2 else focus_id,
                relation="observed-with",
                rule_id="test.relationship",
                explanation="Synthetic graph-drag regression edge.",
                evidence_ids=(f"evidence-{index:02d}",),
            )
        )
    return tuple(nodes), tuple(edges), focus_id


def test_node_drag_updates_are_coalesced_and_survive_rerenders() -> None:
    app = create_qapplication(["ioc-relationship-graph-test"])
    nodes, edges, focus_id = _relationship_fixture()
    canvas = RelationshipGraphCanvas(max_neighbors=24, minimum_height=320)
    canvas.resize(980, 620)
    canvas.show()
    canvas.set_relationships(nodes, edges, str(focus_id))
    app.processEvents()

    for cycle in range(40):
        movable = next(
            item
            for node_id, item in canvas._node_items.items()
            if node_id != focus_id  # noqa: SLF001
        )
        movable.setPos(QPointF(260 + cycle * 3, -180 + (cycle % 9) * 42))

        # Rebuild while a deferred drag update is pending. This is the lifecycle
        # combination that previously left Python wrappers around deleted Qt items.
        if cycle % 4 == 0:
            canvas.set_relationships(nodes, edges, str(focus_id))
        app.processEvents()

    canvas._finish_node_move()  # noqa: SLF001 - simulate the drag release boundary

    assert canvas.node_count == 25
    assert canvas.edge_count == 24
    assert all(not edge.path().isEmpty() for edge in canvas._edge_items)  # noqa: SLF001
    assert all(edge.scene() is canvas._scene for edge in canvas._edge_items)  # noqa: SLF001
    assert not canvas._geometry_timer.isActive()  # noqa: SLF001

    # An external refresh can arrive while Qt still owns the dragged item as its
    # mouse grabber. The canvas must defer destruction until mouse release.
    canvas.set_relationships(nodes, edges, str(focus_id))
    app.processEvents()
    canvas.fit_graph()
    app.processEvents()
    dragged = next(
        item
        for node_id, item in canvas._node_items.items()
        if node_id != focus_id  # noqa: SLF001
    )
    start = canvas.view.mapFromScene(dragged.scenePos())
    assert canvas.view.itemAt(start) is dragged
    QTest.mousePress(
        canvas.view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        start,
    )
    QTest.mouseMove(canvas.view.viewport(), start + QPoint(55, 30), delay=1)
    canvas.set_relationships(nodes, edges, str(focus_id))
    assert canvas._rerender_timer.isActive()  # noqa: SLF001
    QTest.mouseRelease(
        canvas.view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        start + QPoint(55, 30),
    )
    QTest.qWait(25)
    app.processEvents()
    assert not canvas._rerender_timer.isActive()  # noqa: SLF001
    assert canvas.node_count == 25

    # A pending node update must also be harmless when the standalone canvas closes.
    movable = next(iter(canvas._node_items.values()))  # noqa: SLF001
    movable.setPos(movable.pos() + QPointF(75, 35))
    canvas.close()
    app.processEvents()
    assert not canvas.isVisible()
