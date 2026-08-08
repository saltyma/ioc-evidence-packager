"""Packaged application identity assets."""

from pathlib import Path

from PySide6.QtGui import QIcon

ASSET_DIRECTORY = Path(__file__).resolve().parent / "assets"
APP_ICON_PATH = ASSET_DIRECTORY / "app-icon-256.png"
WINDOWS_ICON_PATH = ASSET_DIRECTORY / "app-icon.ico"


def application_icon() -> QIcon:
    """Load the generated application icon from packaged application data."""

    icon = QIcon(str(APP_ICON_PATH))
    if WINDOWS_ICON_PATH.is_file():
        icon.addFile(str(WINDOWS_ICON_PATH))
    if icon.isNull():
        raise RuntimeError(f"Could not load application icon: {APP_ICON_PATH}")
    return icon
