"""Focused offscreen tests for the real desktop composition root."""

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from ioc_evidence_packager.application.services import NewCaseRequest  # noqa: E402
from ioc_evidence_packager.presentation.desktop.app import (  # noqa: E402
    build_desktop,
    create_qapplication,
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
