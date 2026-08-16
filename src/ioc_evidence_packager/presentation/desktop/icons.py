"""Small code-native vector icon set for the desktop navigation."""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "cases": "M3 5h7l2 2h9v12H3z M3 8h18",
    "dashboard": "M3 3h7v7H3z M14 3h7v4h-7z M14 11h7v10h-7z M3 14h7v7H3z",
    "evidence": "M6 2h9l4 4v16H6z M15 2v5h5 M9 11h7 M9 15h7 M9 19h5",
    "timeline": "M12 3a9 9 0 1 0 9 9 M12 7v6l4 2 M18 3v5h-5",
    "relationships": (
        "M5 4a2 2 0 1 0 0 4a2 2 0 0 0 0-4 M19 4a2 2 0 1 0 0 4a2 2 0 0 0 0-4 "
        "M12 16a2 2 0 1 0 0 4a2 2 0 0 0 0-4 M7 7l4 9 M17 7l-4 9 M7 6h10"
    ),
    "coverage": "M12 2l8 3v6c0 5-3.3 9-8 11c-4.7-2-8-6-8-11V5z M8 12l2.5 2.5L16 9",
    "intelligence": (
        "M9 18h6 M10 22h4 M8 14c-1.3-1.1-2-2.8-2-5a6 6 0 0 1 12 0c0 2.2-.7 3.9-2 5l-1 1H9z"
    ),
    "recommendations": "M12 2l3 7l7 3l-7 3l-3 7l-3-7l-7-3l7-3z M12 9v6 M9 12h6",
    "sources": "M4 6c0-2 16-2 16 0v12c0 2-16 2-16 0z M4 6c0 2 16 2 16 0 M4 12c0 2 16 2 16 0",
    "exports": "M4 4h10v5h6v11H4z M14 2v7h7 M11 14h6 M14 11l3 3l-3 3",
    "settings": (
        "M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8 M12 2v3 M12 19v3 M4.9 4.9L7 7 "
        "M17 17l2.1 2.1 M2 12h3 M19 12h3 M4.9 19.1L7 17 M17 7l2.1-2.1"
    ),
    "collapse": "M15 5l-7 7l7 7 M5 3v18",
    "expand": "M9 5l7 7l-7 7 M19 3v18",
}


def navigation_icon(name: str, size: int = 20) -> QIcon:
    """Return a two-state theme-matched SVG icon."""

    path = _PATHS.get(name, _PATHS["evidence"])
    icon = QIcon()
    icon.addPixmap(_pixmap(path, "#AAA1BA", size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_pixmap(path, "#F4E9FF", size), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(_pixmap(path, "#70D6E8", size), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(_pixmap(path, "#70D6E8", size), QIcon.Mode.Active, QIcon.State.On)
    return icon


def _pixmap(path: str, color: str, size: int) -> QPixmap:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter)
    painter.end()
    return pixmap
