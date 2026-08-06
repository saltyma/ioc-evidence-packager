"""Desktop composition root and executable smoke mode."""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QCoreApplication, QStandardPaths, Qt, QTimer
from PySide6.QtWidgets import QApplication

from ioc_evidence_packager.application.services import (
    CaseService,
    NewCaseRequest,
    NewInvestigationRequest,
)
from ioc_evidence_packager.ingestion import SourceInspectionService
from ioc_evidence_packager.presentation.desktop.branding import application_icon
from ioc_evidence_packager.presentation.desktop.main_window import MainWindow
from ioc_evidence_packager.presentation.desktop.theme import APP_STYLESHEET
from ioc_evidence_packager.storage.sqlite import SQLiteCaseRepository, SQLiteDatabase

APPLICATION_NAME = "IOC Evidence Packager"
ORGANIZATION_NAME = "saltyma"
SMOKE_EVENT = {
    "schema": "canonical-event/1.0.0",
    "event_id": "smoke-001",
    "source": {
        "source_id": "synthetic-smoke",
        "position": {"kind": "line", "value": 1},
    },
    "time": {
        "original": "2026-08-06T09:12:03Z",
        "utc": "2026-08-06T09:12:03Z",
        "precision": "second",
        "assumptions": [],
    },
    "event": {"category": "network", "action": "connection"},
    "host": {"name": "WS-DEMO"},
    "observables": [
        {
            "kind": "ipv4",
            "field_path": "network.destination_ip",
            "original": "203.0.113.42",
            "canonical": "203.0.113.42",
        }
    ],
    "adapter": {"id": "synthetic-smoke", "version": "1.0.0"},
    "warnings": [],
}


@dataclass(frozen=True, slots=True)
class DesktopContext:
    """Constructed adapters retained for tests and the desktop process."""

    database: SQLiteDatabase
    case_service: CaseService
    source_inspection_service: SourceInspectionService
    window: MainWindow


def build_desktop(database_path: Path) -> DesktopContext:
    """Compose infrastructure, application service, and main window."""

    database = SQLiteDatabase(database_path)
    database.initialize()
    repository = SQLiteCaseRepository(database)
    case_service = CaseService(repository)
    source_inspection_service = SourceInspectionService()
    window = MainWindow(case_service, source_inspection_service)
    return DesktopContext(
        database=database,
        case_service=case_service,
        source_inspection_service=source_inspection_service,
        window=window,
    )


def default_database_path() -> Path:
    """Return the OS-appropriate local application data path."""

    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    if not location:
        raise RuntimeError("The operating system did not provide a local application-data path.")
    return Path(location) / "cases.sqlite3"


def create_qapplication(arguments: list[str] | None = None) -> QApplication:
    """Create or reuse the process QApplication with stable metadata."""

    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setApplicationName(APPLICATION_NAME)
    QCoreApplication.setApplicationVersion("0.2.0")
    existing = QApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        raise RuntimeError("A non-GUI Qt application already exists in this process.")
    app = (
        existing
        if isinstance(existing, QApplication)
        else QApplication(arguments or [APPLICATION_NAME])
    )
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    app.setWindowIcon(application_icon())
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    return app


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open the IOC Evidence Packager desktop app.")
    parser.add_argument("--database", type=Path, help="Override the local case database path.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Open an isolated demo case briefly, then exit.",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="Save a screenshot during --smoke-test.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Launch the GUI, or execute its deterministic offscreen smoke path."""

    args = _parser().parse_args(argv)
    app = create_qapplication(sys.argv[:1])
    temporary_directory: TemporaryDirectory[str] | None = None
    smoke_source_directory: TemporaryDirectory[str] | None = None
    if args.smoke_test and args.database is None:
        temporary_directory = TemporaryDirectory(prefix="ioc-packager-smoke-")
        database_path = Path(temporary_directory.name) / "cases.sqlite3"
    else:
        database_path = args.database or default_database_path()

    try:
        context = build_desktop(database_path)
        if args.smoke_test:
            recent = context.case_service.list_recent_cases()
            if recent:
                setup = context.case_service.open_investigation(recent[0].case_id)
            else:
                smoke_source_directory = TemporaryDirectory(prefix="ioc-packager-source-")
                source_path = Path(smoke_source_directory.name) / "synthetic-source.jsonl"
                smoke_line = json.dumps(SMOKE_EVENT, separators=(",", ":")) + "\n"
                source_path.write_text(smoke_line, encoding="utf-8")
                preview = context.source_inspection_service.inspect(source_path)
                setup = context.case_service.create_investigation(
                    NewInvestigationRequest(
                        case=NewCaseRequest(
                            title="Synthetic triage demonstration",
                            external_reference="DEMO-001",
                            summary="Offline source-preview verification using synthetic data.",
                        ),
                        lead_value="203.0.113.42",
                        source_previews=(preview,),
                    )
                )
            context.window.open_investigation(setup)
        context.window.show()

        if args.smoke_test:
            app.processEvents()
            if args.screenshot is not None:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                if not context.window.grab().save(str(args.screenshot)):
                    return 1
            QTimer.singleShot(120, app.quit)
        return app.exec()
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()
        if smoke_source_directory is not None:
            smoke_source_directory.cleanup()
