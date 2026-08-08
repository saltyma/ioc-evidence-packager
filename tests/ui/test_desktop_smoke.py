"""Focused offscreen tests for the real desktop composition root."""

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ioc_evidence_packager.application.services import (  # noqa: E402
    NewCaseRequest,
    NewInvestigationRequest,
)
from ioc_evidence_packager.presentation.desktop.app import (  # noqa: E402
    build_desktop,
    create_qapplication,
)
from ioc_evidence_packager.presentation.desktop.branding import (  # noqa: E402
    APP_ICON_PATH,
    application_icon,
)
from ioc_evidence_packager.presentation.desktop.views.new_case import (  # noqa: E402
    NewCaseDialog,
)


def test_desktop_shell_opens_a_persisted_case(tmp_path: Path) -> None:
    app = create_qapplication(["ioc-evidence-packager-test"])
    context = build_desktop(tmp_path / "cases.sqlite3")
    case = context.case_service.create_case(
        NewCaseRequest(
            title="UI smoke investigation",
            external_reference="TEST-001",
            summary="Synthetic metadata only.",
        )
    )

    context.window.show()
    context.window.open_case(case)
    app.processEvents()

    assert context.window.isVisible()
    assert context.window.windowTitle() == "IOC Evidence Packager"
    assert not app.windowIcon().isNull()
    assert not context.window.windowIcon().isNull()
    assert context.window.current_case == case
    assert context.window.page_count == 11
    assert context.window.home_view is not None

    context.window.close()
    app.processEvents()
    assert QApplication.topLevelWidgets() is not None


def test_new_investigation_dialog_builds_previewed_request(tmp_path: Path) -> None:
    app = create_qapplication(["ioc-evidence-packager-wizard-test"])
    context = build_desktop(tmp_path / "wizard.sqlite3")
    dialog = NewCaseDialog(context.source_inspection_service)
    source = Path(__file__).parents[2] / "samples" / "input" / "canonical-demo.jsonl"

    dialog._title.setText("Synthetic source preview")  # noqa: SLF001
    dialog._lead.setText("Example.TEST.")  # noqa: SLF001
    dialog.add_source_paths([source])
    deadline = time.monotonic() + 5
    while dialog._pending_paths and time.monotonic() < deadline:  # noqa: SLF001
        app.processEvents()

    request = dialog.request()
    assert request.case.title == "Synthetic source preview"
    assert request.lead_value == "Example.TEST."
    assert len(request.source_previews) == 1
    assert request.source_previews[0].adapter_id == "canonical-jsonl"

    dialog.close()
    context.window.close()
    app.processEvents()


def test_packaged_branding_uses_generated_raster_icon() -> None:
    image = QImage(str(APP_ICON_PATH))

    assert APP_ICON_PATH.name == "app-icon-256.png"
    assert not image.isNull()
    assert image.width() == 256
    assert image.height() == 256
    assert not application_icon().pixmap(32, 32).isNull()


def test_background_import_populates_evidence_and_rejections(tmp_path: Path) -> None:
    app = create_qapplication(["ioc-evidence-packager-import-test"])
    context = build_desktop(tmp_path / "import.sqlite3")
    source = (
        Path(__file__).parents[2]
        / "samples"
        / "input"
        / "demo-investigation"
        / "05-partial-with-warning.jsonl"
    )
    preview = context.source_inspection_service.inspect(source)
    setup = context.case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Background import"),
            lead_value="203.0.113.42",
            source_previews=(preview,),
        )
    )
    context.window.open_investigation(setup)

    context.window._start_import(setup.case.case_id, setup.source_previews)  # noqa: SLF001
    deadline = time.monotonic() + 5
    while context.window._import_worker is not None and time.monotonic() < deadline:  # noqa: SLF001
        app.processEvents()

    assert context.window._import_worker is None  # noqa: SLF001
    assert context.window.evidence_view.evidence_row_count == 1
    assert context.window.evidence_view.rejection_row_count == 1
    assert context.window.timeline_view.row_count == 1
    assert context.window.coverage_view.row_count >= 3

    context.window.close()
    app.processEvents()


def test_background_capsule_export_updates_verified_history(tmp_path: Path) -> None:
    app = create_qapplication(["ioc-evidence-packager-export-test"])
    context = build_desktop(tmp_path / "export.sqlite3")
    source = Path(__file__).parents[2] / "samples" / "input" / "canonical-demo.jsonl"
    preview = context.source_inspection_service.inspect(source)
    setup = context.case_service.create_investigation(
        NewInvestigationRequest(
            case=NewCaseRequest(title="Background export"),
            lead_value="203.0.113.42",
            source_previews=(preview,),
        )
    )
    context.evidence_service.import_sources(setup.case.case_id, setup.source_previews)
    context.window.open_investigation(setup)
    destination = tmp_path / "verified-capsule"

    context.window._start_export("full-internal", str(destination))  # noqa: SLF001
    deadline = time.monotonic() + 8
    while context.window._export_worker is not None and time.monotonic() < deadline:  # noqa: SLF001
        app.processEvents()

    assert context.window._export_worker is None  # noqa: SLF001
    assert (destination / "manifest.json").is_file()
    assert context.report_service.verify(destination).valid
    assert context.window.exports_view.history_row_count == 1

    context.window.close()
    app.processEvents()
