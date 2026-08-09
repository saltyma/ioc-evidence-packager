"""Reusable non-modal detail window for table-backed desktop views."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DetailDialog(QDialog):
    """Keeps complete row details available without shrinking the primary table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailDialog")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(780, 560)
        self.setMinimumSize(600, 400)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        self._eyebrow = QLabel()
        self._eyebrow.setObjectName("SectionEyebrow")
        root.addWidget(self._eyebrow)

        self._title = QLabel()
        self._title.setObjectName("DetailTitle")
        self._title.setWordWrap(True)
        root.addWidget(self._title)

        self._content = QPlainTextEdit()
        self._content.setObjectName("DetailContent")
        self._content.setReadOnly(True)
        self._content.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self._content, 1)

        actions = QHBoxLayout()
        self._copy_button = QPushButton("Copy details")
        self._copy_button.clicked.connect(self._copy_details)
        close_button = QPushButton("Close")
        close_button.setObjectName("PrimaryButton")
        close_button.clicked.connect(self.close)
        actions.addStretch(1)
        actions.addWidget(self._copy_button)
        actions.addWidget(close_button)
        root.addLayout(actions)

    @property
    def detail_text(self) -> str:
        """Return the currently presented text for focused UI verification."""

        return self._content.toPlainText()

    def present(self, *, window_title: str, eyebrow: str, title: str, text: str) -> None:
        """Update, show, and focus this reusable non-modal detail window."""

        self.setWindowTitle(window_title)
        self._eyebrow.setText(eyebrow)
        self._title.setText(title)
        self._content.setPlainText(text)
        self._content.moveCursor(self._content.textCursor().MoveOperation.Start)
        self.show()
        self.raise_()
        self.activateWindow()

    def _copy_details(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._content.toPlainText())
