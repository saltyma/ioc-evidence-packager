"""Release regressions for IPv6, scope, review, lifecycle and handoff projections."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest

from ioc_evidence_packager.application.review_service import ReviewService
from ioc_evidence_packager.application.services import NewCaseRequest, NewInvestigationRequest
from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.observables import ObservableType, parse_observable
from ioc_evidence_packager.domain.review import EvidenceReview
from ioc_evidence_packager.presentation.desktop.app import (
    SMOKE_EVENT,
    build_desktop,
    create_qapplication,
)
from ioc_evidence_packager.reporting.models import ExportProfile
from ioc_evidence_packager.reporting.projections import project_capsule


def test_ipv6_canonicalization_and_ambiguous_addresses() -> None:
    parsed = parse_observable("2001:0DB8:0000:0:0:0:0:1")
    assert parsed.observable_type is ObservableType.IPV6
    assert parsed.canonical_value == "2001:db8::1"
    for invalid in ("2001:db8::zz", "fe80::1%12", "[2001:db8::1]"):
        with pytest.raises(ValidationError):
            parse_observable(invalid)


def test_case_lifecycle_scope_review_and_selected_exports(tmp_path: Path) -> None:
    app = create_qapplication(["closeout-regression"])
    context = build_desktop(tmp_path / "cases.sqlite3")
    source = Path(__file__).parents[2] / "samples/input/canonical-demo.jsonl"
    preview = context.source_inspection_service.inspect(source)
    setup = context.case_service.create_investigation(
        NewInvestigationRequest(
            NewCaseRequest(
                title="Scoped case",
                requested_start=datetime(2026, 8, 6, tzinfo=UTC),
                requested_end=datetime(2026, 8, 7, tzinfo=UTC),
            ),
            "203.0.113.42",
            (preview,),
        )
    )
    context.evidence_service.import_sources(setup.case.case_id, setup.source_previews)
    context.window.open_investigation(setup)
    records = context.window._records  # noqa: SLF001
    review = ReviewService(context.database)
    note = "<script>private analyst note</script>"
    review.save(setup.case.case_id, str(records[0].evidence_id), EvidenceReview(True, note))
    review.save(setup.case.case_id, str(records[1].evidence_id), EvidenceReview(False, "", False))
    restored = ReviewService(context.database).reviews(setup.case.case_id)
    assert restored[str(records[0].evidence_id)].note == note
    assert not restored[str(records[1].evidence_id)].included
    assert (
        context.case_service.open_investigation(setup.case.case_id).case.requested_start
        == setup.case.requested_start
    )
    for profile in ExportProfile:
        result = context.report_service.export_case(
            setup,
            records,
            (),
            context.window._analysis,
            tmp_path / profile.value,
            profile,
            context.window._relationships,
        )  # noqa: SLF001
        assert context.report_service.verify(result.destination).valid
        rows = [
            json.loads(line)
            for line in (result.destination / "evidence.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert len(rows) == len(records) - 1
        assert str(records[1].evidence_id) not in {row["evidence_id"] for row in rows}
        combined = "".join(p.read_text(encoding="utf-8") for p in result.destination.iterdir())
        if profile is ExportProfile.REDACTED_SHAREABLE:
            assert note not in combined
        else:
            assert rows[0]["analyst_review"]["note"] == note
        pdf = project_capsule(result.destination, tmp_path / (profile.value + ".pdf"), "pdf")
        assert pdf.read_bytes().startswith(b"%PDF-")
        archive = project_capsule(result.destination, tmp_path / (profile.value + ".zip"), "zip")
        with ZipFile(archive) as zipped:
            assert len(zipped.namelist()) == 9
            assert zipped.testzip() is None
        with pytest.raises(ValidationError):
            project_capsule(result.destination, archive, "zip")
    review.rename(setup.case.case_id, "Updated title")
    assert context.case_service.open_case(setup.case.case_id).title == "Updated title"
    review.archive(setup.case.case_id, True)
    assert not context.case_service.list_recent_cases()
    assert review.archived_cases()[0][0] == str(setup.case.case_id)
    review.archive(setup.case.case_id, False)
    assert len(context.case_service.list_recent_cases()) == 1
    with context.database.connection() as connection:
        before = connection.execute("SELECT count(*) FROM sighting").fetchone()[0]
        assert before > 0
        connection.execute("DROP TABLE evidence_review")
        connection.execute("ALTER TABLE case_record DROP COLUMN requested_start")
        connection.execute("ALTER TABLE case_record DROP COLUMN requested_end")
        connection.execute("DELETE FROM schema_migration WHERE version=7")
        connection.execute("PRAGMA user_version=6")
        connection.commit()
    context.database.initialize()
    with context.database.connection() as connection:
        assert connection.execute("SELECT count(*) FROM sighting").fetchone()[0] == before
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    context.window.close()
    app.processEvents()


def test_inverted_or_naive_scope_is_rejected(tmp_path: Path) -> None:
    app = create_qapplication(["closeout-scope"])
    context = build_desktop(tmp_path / "scope.sqlite3")
    with pytest.raises(ValidationError):
        context.case_service.create_case(
            NewCaseRequest(title="Bad", requested_start=datetime(2026, 1, 1))
        )
    with pytest.raises(ValidationError):
        context.case_service.create_case(
            NewCaseRequest(
                title="Bad",
                requested_start=datetime(2026, 2, 1, tzinfo=UTC),
                requested_end=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    context.window.close()
    app.processEvents()


def test_ipv6_import_scope_and_exact_recipe(tmp_path: Path) -> None:
    app = create_qapplication(["ipv6-workflow"])
    context = build_desktop(tmp_path / "ipv6.sqlite3")
    first = deepcopy(SMOKE_EVENT)
    first["observables"][0].update(kind="ipv6", original="2001:0DB8::1", canonical="2001:db8::1")
    second = deepcopy(first)
    second["event_id"] = "outside-window"
    second["time"]["original"] = "2026-08-06T09:12:04Z"
    second["time"]["utc"] = "2026-08-06T09:12:04Z"
    source = tmp_path / "ipv6.jsonl"
    source.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8")
    preview = context.source_inspection_service.inspect(source)
    bound = datetime(2026, 8, 6, 9, 12, 3, tzinfo=UTC)
    setup = context.case_service.create_investigation(
        NewInvestigationRequest(
            NewCaseRequest(title="IPv6 window", requested_start=bound, requested_end=bound),
            "2001:db8::1",
            (preview,),
        )
    )
    context.evidence_service.import_sources(setup.case.case_id, setup.source_previews)
    context.window.open_investigation(setup)
    assert len(context.evidence_service.list_evidence(setup.case.case_id)) == 2
    assert len(context.window._records) == 1  # noqa: SLF001
    analysis = context.window._analysis  # noqa: SLF001
    assert analysis is not None and len(analysis.sightings) == 1
    assert analysis.recipe_id == "ipv6"
    assert context.case_service.open_investigation(setup.case.case_id).lead == setup.lead
    assert any(node.entity_type.value == "ipv6" for node in context.window._relationships.nodes)  # noqa: SLF001
    context.window.close()
    app.processEvents()
