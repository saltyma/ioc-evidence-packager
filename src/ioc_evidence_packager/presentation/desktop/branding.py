"""Packaged application identity assets."""

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon

ASSET_DIRECTORY = Path(__file__).resolve().parent / "assets"
APP_ICON_PATH = ASSET_DIRECTORY / "app-icon.svg"


@lru_cache(maxsize=1)
def application_icon() -> QIcon:
    """Load the canonical vector icon from packaged application data."""

    icon = QIcon(str(APP_ICON_PATH))
    if icon.isNull():
        raise RuntimeError(f"Could not load application icon: {APP_ICON_PATH}")
    return icon
