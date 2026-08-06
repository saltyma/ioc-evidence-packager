"""Honest placeholder pages for planned workspace areas."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class PlaceholderView(QWidget):
    """Explains a planned view without pretending the capability exists."""

    def __init__(self, title: str, description: str, milestone: str) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(12)

        eyebrow = QLabel(milestone.upper())
        eyebrow.setObjectName("SectionEyebrow")
        page_title = QLabel(title)
        page_title.setObjectName("PageTitle")
        copy = QLabel(description)
        copy.setObjectName("PageSubtitle")
        copy.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(page_title)
        root.addWidget(copy)

        card = QFrame()
        card.setObjectName("NoticeCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_title = QLabel("Workspace reserved")
        card_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        card_copy = QLabel(
            "The navigation is established now so later slices can attach tested application "
            "services without restructuring the desktop shell."
        )
        card_copy.setObjectName("Muted")
        card_copy.setWordWrap(True)
        card_layout.addWidget(card_title)
        card_layout.addWidget(card_copy)
        root.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
        root.addStretch(1)
