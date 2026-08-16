"""Focused offscreen tests for the real desktop composition root."""

import os
import time
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QSettings  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPlainTextEdit  # noqa: E402

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
from ioc_evidence_packager.presentation.desktop.settings_store import (  # noqa: E402
    DesktopSettingsStore,
)
from ioc_evidence_packager.presentation.desktop.views.new_case import (  # noqa: E402
    NewCaseDialog,
)

_QT_APP = create_qapplication(["ioc-evidence-packager-test"])


@pytest.fixture(autouse=True)
def _close_qt_windows_after_test() -> Iterator[None]:
    yield
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    _QT_APP.processEvents()


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

    dialog._open_source_detail(0, 0)  # noqa: SLF001
    app.processEvents()
    assert dialog._detail_dialog is not None  # noqa: SLF001
    assert dialog._detail_dialog.isVisible()  # noqa: SLF001
    assert "SHA-256:" in dialog._detail_dialog.detail_text  # noqa: SLF001

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


def test_corrupt_device_preferences_fall_back_to_safe_values(tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("appearance/density", "Microscopic")
    settings.setValue("privacy/default_mode", "send-everything")
    settings.sync()

    preferences = DesktopSettingsStore(settings).load()

    assert preferences.density == "Comfortable"
    assert preferences.default_privacy_mode == "offline"


def test_settings_and_collapsible_icon_sidebar_work_without_a_case(tmp_path: Path) -> None:
    app = create_qapplication(["ioc-evidence-packager-shell-test"])
    context = build_desktop(tmp_path / "shell.sqlite3")
    window = context.window
    window.show()
    app.processEvents()

    assert window._pages.contentsMargins().top() == 0  # noqa: SLF001
    assert window._nav_buttons["Settings"].isEnabled()  # noqa: SLF001
    assert not window._nav_buttons["Dashboard"].isEnabled()  # noqa: SLF001
    assert all(not button.icon().isNull() for button in window._nav_buttons.values())  # noqa: SLF001
    window.show_page("Settings")
    assert window._pages.currentWidget() is window.settings_view  # noqa: SLF001
    assert not window.settings_view._tabs.isTabEnabled(0)  # noqa: SLF001
    expanded_right = (
        window._floating_actions.mapTo(window, QPoint(0, 0)).x()  # noqa: SLF001
        + window._floating_actions.width()  # noqa: SLF001
    )

    window._sidebar_toggle.click()  # noqa: SLF001
    app.processEvents()
    assert window._sidebar.width() == 72  # noqa: SLF001
    assert window._sidebar_collapsed  # noqa: SLF001
    assert not window._sidebar_logo.isVisible()  # noqa: SLF001
    assert window._sidebar_toggle.iconSize().width() == 28  # noqa: SLF001
    assert all(button.text() == "" for button in window._nav_buttons.values())  # noqa: SLF001
    for button in window._nav_buttons.values():  # noqa: SLF001
        button_left = button.mapTo(window._sidebar, QPoint(0, 0)).x()  # noqa: SLF001
        assert abs(button_left + button.width() / 2 - window._sidebar.width() / 2) <= 1  # noqa: SLF001
    toggle_top = window._sidebar_toggle.mapTo(window._sidebar, QPoint(0, 0)).y()  # noqa: SLF001
    cases_top = (
        window._nav_buttons["Cases"]
        .mapTo(  # noqa: SLF001
            window._sidebar,
            QPoint(0, 0),  # noqa: SLF001
        )
        .y()
    )
    assert cases_top - (toggle_top + window._sidebar_toggle.height()) >= 16  # noqa: SLF001
    collapsed_right = (
        window._floating_actions.mapTo(window, QPoint(0, 0)).x()  # noqa: SLF001
        + window._floating_actions.width()  # noqa: SLF001
    )
    assert abs(collapsed_right - expanded_right) <= 1

    window._sidebar_toggle.click()  # noqa: SLF001
    app.processEvents()
    assert window._sidebar.width() == 226  # noqa: SLF001
    assert window._nav_buttons["Settings"].text() == "Settings"  # noqa: SLF001

    window.close()
    app.processEvents()


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
    context.window.show()

    context.window._start_import(setup.case.case_id, setup.source_previews)  # noqa: SLF001
    deadline = time.monotonic() + 5
    while context.window._import_worker is not None and time.monotonic() < deadline:  # noqa: SLF001
        app.processEvents()

    assert context.window._import_worker is None  # noqa: SLF001
    assert context.window._jobs_button.text() == "Idle"  # noqa: SLF001
    assert context.window.evidence_view.evidence_row_count == 1
    assert context.window.evidence_view.rejection_row_count == 1
    assert context.window.timeline_view.row_count == 1
    assert context.window.coverage_view.row_count >= 3
    assert context.window.sources_view.row_count == 1
    assert context.window.relationships_view.row_count > 0
    assert context.window.relationships_view.graph_node_count > 0
    assert context.window.relationships_view.graph_edge_count > 0
    assert context.window.relationships_view.findChild(QFrame, "GraphLegendPanel") is not None
    assert context.window.relationships_view.findChild(QLabel, "GraphSelectionStatus") is None
    assert context.window._case_badge.text().endswith("Background import")  # noqa: SLF001
    assert context.window.recommendations_view.row_count > 0
    recommendations = context.window.recommendations_view
    recommendations._open_detail(0, 0)  # noqa: SLF001
    assert recommendations._accepted.isEnabled()  # noqa: SLF001
    recommendations.set_recommendations(recommendations._items)  # noqa: SLF001
    assert not recommendations._accepted.isEnabled()  # noqa: SLF001
    assert not recommendations._pivot.isEnabled()  # noqa: SLF001
    context.window._save_settings(  # noqa: SLF001
        "offline",
        "Local system time",
        context.window._preferences,  # noqa: SLF001
    )
    assert context.window.current_case is not None
    assert context.window.current_case.display_timezone == "Local system time"
    assert (
        context.window.timeline_view._table.horizontalHeaderItem(0).text()  # noqa: SLF001
        == "Time · Local system time"
    )
    original_run = context.window._analysis  # noqa: SLF001
    assert original_run is not None
    context.window.coverage_view._rerun_button.click()  # noqa: SLF001
    app.processEvents()
    first_rerun = context.window._analysis  # noqa: SLF001
    assert first_rerun is not None and first_rerun.run_id != original_run.run_id
    context.window.coverage_view._rerun_button.click()  # noqa: SLF001
    app.processEvents()
    second_rerun = context.window._analysis  # noqa: SLF001
    assert second_rerun is not None and second_rerun.run_id != first_rerun.run_id
    evidence_id = str(context.window._records[0].evidence_id)  # noqa: SLF001
    context.window.evidence_view.set_search_filter(evidence_id)
    assert context.window.evidence_view.evidence_row_count == 1
    assert not context.window.evidence_view.findChildren(QPlainTextEdit)
    assert not context.window.timeline_view.findChildren(QPlainTextEdit)
    assert not context.window.coverage_view.findChildren(QPlainTextEdit)

    context.window.evidence_view._open_evidence_detail(0, 0)  # noqa: SLF001
    app.processEvents()
    evidence_dialog = context.window.evidence_view._detail_dialog  # noqa: SLF001
    assert evidence_dialog is not None and evidence_dialog.isVisible()
    assert "Evidence ID:" in evidence_dialog.detail_text

    context.window.evidence_view._open_rejection_detail(0, 0)  # noqa: SLF001
    context.window.timeline_view._open_detail(0, 0)  # noqa: SLF001
    context.window.coverage_view._open_detail(0, 0)  # noqa: SLF001
    app.processEvents()
    timeline_dialog = context.window.timeline_view._detail_dialog  # noqa: SLF001
    coverage_dialog = context.window.coverage_view._detail_dialog  # noqa: SLF001
    assert "Bounded source excerpt:" in evidence_dialog.detail_text
    assert timeline_dialog is not None and timeline_dialog.isVisible()
    assert "Preserved source record:" in timeline_dialog.detail_text
    assert coverage_dialog is not None and coverage_dialog.isVisible()
    assert "Reason code:" in coverage_dialog.detail_text

    context.window.sources_view._open_detail(0, 0)  # noqa: SLF001
    app.processEvents()
    source_dialog = context.window.sources_view._detail_dialog  # noqa: SLF001
    assert source_dialog is not None and source_dialog.isVisible()
    assert "SHA-256:" in source_dialog.detail_text
    assert "Mapped/searchable fields:" in source_dialog.detail_text

    relationships = context.window.relationships_view
    relationships._graph_canvas.background_double_clicked.emit()  # noqa: SLF001
    app.processEvents()
    graph_window = relationships.graph_window
    assert graph_window is not None and graph_window.isVisible()
    assert graph_window.canvas.node_count > 0
    assert graph_window.canvas.edge_count > 0
    graph_window.canvas.reset_zoom()
    assert graph_window.canvas.zoom_percent == 100
    graph_window.canvas.zoom_in()
    assert graph_window.canvas.zoom_percent > 100
    relationship_id = str(relationships._visible[0].relationship_id)  # noqa: SLF001
    relationships._open_graph_edge(relationship_id)  # noqa: SLF001
    app.processEvents()
    relationship_dialog = relationships._detail_dialog  # noqa: SLF001
    assert relationship_dialog is not None and relationship_dialog.isVisible()
    assert "Supporting evidence IDs:" in relationship_dialog.detail_text
    graph_window.close()

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
    assert context.window._jobs_button.text() == "Idle"  # noqa: SLF001
    assert (destination / "manifest.json").is_file()
    assert context.report_service.verify(destination).valid
    assert context.window.exports_view.history_row_count == 1

    context.window.show()
    context.window.exports_view._open_history_detail(0, 0)  # noqa: SLF001
    app.processEvents()
    export_dialog = context.window.exports_view._detail_dialog  # noqa: SLF001
    assert export_dialog is not None and export_dialog.isVisible()
    assert "Manifest SHA-256:" in export_dialog.detail_text

    context.window.close()
    app.processEvents()
