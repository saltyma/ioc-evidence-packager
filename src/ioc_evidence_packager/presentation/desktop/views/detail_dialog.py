# ruff: noqa: E501 - embedded rich-text CSS is intentionally kept readable
"""Reusable, width-bounded semantic detail window for table-backed views."""

import html
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class DetailDialog(QDialog):
    """Keeps complete row details available without shrinking the primary table."""

    _preferred_width = 760

    @classmethod
    def set_preferred_width(cls, width: int) -> None:
        cls._preferred_width = max(620, min(900, width))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailDialog")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setFixedWidth(self._preferred_width)
        self.resize(self._preferred_width, 590)
        self.setMinimumHeight(420)
        self.setMaximumHeight(760)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        self._eyebrow = QLabel()
        self._eyebrow.setObjectName("SectionEyebrow")
        root.addWidget(self._eyebrow)

        self._title = QLabel()
        self._title.setObjectName("DetailTitle")
        self._title.setWordWrap(True)
        self._title.setMaximumWidth(self._preferred_width - 80)
        root.addWidget(self._title)

        self._content = QTextBrowser()
        self._content.setObjectName("DetailContent")
        self._content.setReadOnly(True)
        self._content.setOpenExternalLinks(False)
        self._content.setOpenLinks(False)
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
        self._plain_text = ""

    @property
    def detail_text(self) -> str:
        """Return the currently presented text for focused UI verification."""

        return self._plain_text

    def present(self, *, window_title: str, eyebrow: str, title: str, text: str) -> None:
        """Update, show, and focus this reusable non-modal detail window."""

        self.setFixedWidth(self._preferred_width)
        self._title.setMaximumWidth(self._preferred_width - 80)
        self.setWindowTitle(window_title)
        self._eyebrow.setText(eyebrow)
        self._title.setText(title)
        self._plain_text = text
        self._content.setHtml(_semantic_document(text))
        self._content.moveCursor(self._content.textCursor().MoveOperation.Start)
        self.show()
        self.raise_()
        self.activateWindow()

    def _copy_details(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._plain_text)


_LABEL = re.compile(r"^([^:\n]{1,48}):(?:\s*)(.*)$")


def _semantic_document(text: str) -> str:
    """Turn established ``Label: value`` detail text into safe semantic HTML."""

    parts: list[str] = []
    raw_mode = False
    raw_lines: list[str] = []
    for line in text.splitlines():
        if raw_mode:
            raw_lines.append(line)
            continue
        match = _LABEL.match(line)
        if match:
            label, value = match.groups()
            if label.casefold() in {"preserved source record", "bounded source excerpt"}:
                parts.append(f"<h3>{html.escape(label)}</h3>")
                raw_mode = True
                if value:
                    raw_lines.append(value)
                continue
            if not value:
                parts.append(f"<h3>{html.escape(label)}</h3>")
                continue
            tone = _tone_for(label, value)
            parts.append(
                '<div class="field">'
                f'<div class="label">{html.escape(label)}</div>'
                f'<div class="value {tone}">{html.escape(value)}</div>'
                "</div>"
            )
        elif line.startswith(("  - ", "- ")):
            parts.append(f'<div class="bullet">• {html.escape(line.lstrip(" -"))}</div>')
        elif line.strip():
            parts.append(f"<p>{html.escape(line)}</p>")
        else:
            parts.append('<div class="space"></div>')
    if raw_lines:
        parts.append(f"<pre>{html.escape(chr(10).join(raw_lines))}</pre>")
    return (
        """<html><head><style>
body{color:#eeeaf6;background:#0e0b14;font:13px/1.5 'Segoe UI',sans-serif;margin:10px;max-width:650px}
.field{margin:0 0 12px}.label{color:#a49cb5;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px}
.value{color:#f5f1fa;font-size:14px;overflow-wrap:anywhere;word-break:break-word;white-space:pre-wrap}
.identifier{color:#c9b8ff;font-family:'Cascadia Mono','Consolas',monospace}.source{color:#70d6e8}.time{color:#78dcca}
.good{color:#67d7a4}.warn{color:#f2b84b}.danger{color:#ff7f9f}.type{color:#a78bfa}.neutral{color:#eeeaf6}
h3{color:#e3b760;font-size:12px;text-transform:uppercase;letter-spacing:.6px;margin:18px 0 8px;border-bottom:1px solid #352e44;padding-bottom:6px}
p,.bullet{margin:5px 0;overflow-wrap:anywhere}.bullet{color:#d9d2e3;padding-left:8px}.space{height:7px}
pre{color:#c7d0df;background:#09070d;border:1px solid #352e44;border-radius:6px;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-all;font:12px/1.45 'Cascadia Mono','Consolas',monospace}
</style></head><body>"""
        + "".join(parts)
        + "</body></html>"
    )


def _tone_for(label: str, value: str) -> str:
    key = label.casefold()
    lowered = value.casefold()
    if any(word in key for word in ("id", "sha-256", "hash", "rule", "recipe")):
        return "identifier"
    if any(word in key for word in ("source", "path", "provider", "reference", "adapter")):
        return "source"
    if any(word in key for word in ("time", "date", "retrieved", "updated", "expires")):
        return "time"
    if any(
        word in key for word in ("classification", "claim", "state", "status", "priority", "type")
    ):
        if any(word in lowered for word in ("failed", "malicious", "dismissed", "error")):
            return "danger"
        if any(
            word in lowered for word in ("warning", "partial", "suspicious", "immediate", "expired")
        ):
            return "warn"
        if any(word in lowered for word in ("completed", "accepted", "fresh", "benign", "match")):
            return "good"
        return "type"
    return "neutral"
