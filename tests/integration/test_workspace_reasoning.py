"""Integration coverage for durable analyst reasoning and local intelligence."""

import json
from pathlib import Path
from typing import Any

import pytest

from ioc_evidence_packager.application.services import NewCaseRequest, NewInvestigationRequest
from ioc_evidence_packager.domain.models import PrivacyMode
from ioc_evidence_packager.domain.workspace import (
    IntelligenceClaim,
    RecommendationStatus,
    intelligence_conflicts,
)
from ioc_evidence_packager.presentation.desktop.app import build_desktop, create_qapplication
from ioc_evidence_packager.reporting.models import ExportProfile


def _loaded_context(tmp_path: Path):  # type: ignore[no-untyped-def]
    create_qapplication(["workspace-reasoning-test"])
    context = build_desktop(tmp_path / "workspace.sqlite3")
    source = Path(__file__).parents[2] / "samples" / "input" / "canonical-demo.jsonl"
    preview = context.source_inspection_service.inspect(source)
    setup = context.case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Reasoning integration"),
            lead_value="203.0.113.42",
            source_previews=(preview,),
        )
    )
    context.evidence_service.import_sources(setup.case.case_id, setup.source_previews)
    context.window.open_investigation(setup)
    return context, setup


def test_relationships_and_recommendation_state_are_evidence_backed(tmp_path: Path) -> None:
    context, setup = _loaded_context(tmp_path)

    assert context.window.relationships_view.row_count > 0
    assert context.window.recommendations_view.row_count > 0
    relationships = context.workspace_service.relationships(context.window._records)  # noqa: SLF001
    assert all(edge.evidence_ids for edge in relationships.edges)

    recommendations = context.workspace_service.recommendations(
        setup.case.case_id,
        context.window._analysis,
        relationships,  # noqa: SLF001
    )
    selected = recommendations[0]
    context.workspace_service.set_recommendation_state(
        setup.case.case_id,
        selected.recommendation_id,
        RecommendationStatus.ACCEPTED,
        "Scoped for collection.",
    )
    reloaded = context.workspace_service.recommendations(
        setup.case.case_id,
        context.window._analysis,
        relationships,  # noqa: SLF001
    )
    updated = next(
        item for item in reloaded if item.recommendation_id == selected.recommendation_id
    )
    assert updated.status is RecommendationStatus.ACCEPTED
    assert updated.analyst_note == "Scoped for collection."
    context.window.close()


def test_imported_intelligence_preserves_conflict_and_attribution(tmp_path: Path) -> None:
    context, setup = _loaded_context(tmp_path)
    fixture = (
        Path(__file__).parents[2]
        / "samples"
        / "input"
        / "demo-investigation"
        / "12-intelligence-assertions.json"
    )

    assert context.workspace_service.import_assertions(setup.case.case_id, fixture) == 2
    assertions = context.workspace_service.assertions(setup.case.case_id)
    assert {item.claim for item in assertions} == {
        IntelligenceClaim.MALICIOUS,
        IntelligenceClaim.BENIGN,
    }
    assert len(intelligence_conflicts(assertions)) == 2
    assert all(item.provider.startswith("Synthetic TI") for item in assertions)
    context.window.close()


def test_virustotal_lookup_is_policy_gated_cached_and_does_not_store_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, setup = _loaded_context(tmp_path)
    with pytest.raises(Exception, match="Safe enrichment|Enterprise"):
        context.workspace_service.query_virustotal(setup.case, "ipv4", "203.0.113.42")

    case = context.case_service.update_preferences(
        setup.case.case_id,
        display_timezone="UTC",
        privacy_mode=PrivacyMode.SAFE_ENRICHMENT,
    )
    secret = "synthetic-api-key-that-must-not-persist"  # noqa: S105 - non-secret fixture
    monkeypatch.setenv("IOC_PACKAGER_VT_API_KEY", secret)
    response = json.dumps(
        {
            "data": {
                "attributes": {
                    "last_analysis_date": 1785984000,
                    "last_analysis_stats": {
                        "malicious": 2,
                        "suspicious": 1,
                        "harmless": 61,
                    },
                }
            }
        }
    ).encode()

    class _Response:
        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return response

    calls = [0]

    def fake_urlopen(_request: object, timeout: int):  # type: ignore[no-untyped-def]
        assert timeout == 12
        calls[0] += 1
        return _Response()

    monkeypatch.setattr(
        "ioc_evidence_packager.application.workspace_service.urllib.request.urlopen",
        fake_urlopen,
    )
    first = context.workspace_service.query_virustotal(case, "ipv4", "203.0.113.42", cache_hours=48)
    second = context.workspace_service.query_virustotal(
        case, "ipv4", "203.0.113.42", cache_hours=48
    )

    assert first == second
    assert calls == [1]
    assert first.claim is IntelligenceClaim.MALICIOUS
    assert first.raw_response_sha256 is not None
    assert secret.encode() not in (tmp_path / "workspace.sqlite3").read_bytes()
    context.window.close()


def test_schema_five_database_upgrades_to_reasoning_tables(tmp_path: Path) -> None:
    context, _setup = _loaded_context(tmp_path)
    context.window.close()
    with context.database.connection() as connection:
        connection.execute("DROP TABLE intelligence_assertion")
        connection.execute("DROP TABLE recommendation_state")
        connection.execute("DELETE FROM schema_migration WHERE version = 6")
        connection.execute("PRAGMA user_version = 5")
        connection.commit()

    context.database.initialize()

    with context.database.connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
        tables = {
            row[0]
            for row in connection.execute(
                """SELECT name FROM sqlite_master
                   WHERE type = 'table' AND name IN (
                       'recommendation_state', 'intelligence_assertion'
                   )"""
            ).fetchall()
        }
    assert tables == {"recommendation_state", "intelligence_assertion"}


def test_redacted_graph_remaps_sensitive_values_and_entity_ids(tmp_path: Path) -> None:
    context, setup = _loaded_context(tmp_path)
    records = context.window._records  # noqa: SLF001
    analysis = context.window._analysis  # noqa: SLF001
    assert analysis is not None
    graph = context.workspace_service.relationships(records)
    recommendations = context.workspace_service.recommendations(setup.case.case_id, analysis, graph)
    original_sensitive_ids = {
        str(node.entity_id) for node in graph.nodes if node.entity_type.value in {"host", "user"}
    }
    result = context.report_service.export_case(
        setup,
        records,
        context.window._rejections,  # noqa: SLF001
        analysis,
        tmp_path / "redacted-graph",
        ExportProfile.REDACTED_SHAREABLE,
        graph,
        recommendations,
        (),
    )
    exported = json.loads((result.destination / "relationships.json").read_text(encoding="utf-8"))
    exported_sensitive = {
        node["entity_id"] for node in exported["nodes"] if node["entity_type"] in {"host", "user"}
    }
    edge_endpoints = {value for edge in exported["edges"] for value in (edge["from"], edge["to"])}

    assert original_sensitive_ids.isdisjoint(exported_sensitive)
    assert exported_sensitive <= edge_endpoints
    serialized = json.dumps(exported)
    assert "FIN-WS-014" not in serialized
    assert "analyst-demo" not in serialized
    context.window.close()
