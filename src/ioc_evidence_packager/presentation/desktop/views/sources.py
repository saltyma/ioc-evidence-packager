"""Source inventory, adapter capability, and import-diagnostic workspace."""

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.application.services import InvestigationSetup
from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.sources import PreviewStatus, SourcePreview
from ioc_evidence_packager.domain.timezones import UTC_DISPLAY, format_case_datetime
from ioc_evidence_packager.presentation.desktop.views.detail_dialog import DetailDialog

STATUS_COLORS = {
    PreviewStatus.READY: "#67D7A4",
    PreviewStatus.WARNING: "#F2B84B",
    PreviewStatus.UNSUPPORTED: "#C795FF",
    PreviewStatus.FAILED: "#FF8A8A",
}


class SourcesView(QWidget):
    """Shows exactly what each supplied source contributes to the case."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._previews: tuple[SourcePreview, ...] = ()
        self._visible: list[SourcePreview] = []
        self._records: tuple[EvidenceRecord, ...] = ()
        self._rejections: tuple[ImportRejection, ...] = ()
        self._display_timezone = UTC_DISPLAY
        self._detail_dialog: DetailDialog | None = None
        self._build_ui()

    @property
    def row_count(self) -> int:
        return self._table.rowCount()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(15)

        eyebrow = QLabel("SOURCE INVENTORY")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Know what entered the investigation")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Every selected file keeps its complete digest, detected adapter and version, "
            "searchable capabilities, preview limits, accepted evidence, and diagnostics."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        notice = QFrame()
        notice.setObjectName("NoticeCard")
        notice_layout = QHBoxLayout(notice)
        notice_layout.setContentsMargins(16, 12, 16, 12)
        self._summary = QLabel("Open an investigation to inspect its supplied sources.")
        self._summary.setObjectName("Muted")
        self._summary.setWordWrap(True)
        notice_layout.addWidget(self._summary)
        root.addWidget(notice)

        filters = QHBoxLayout()
        self._status_filter = QComboBox()
        self._status_filter.addItems(("All sources", "Ready", "Warnings", "Unsupported", "Failed"))
        self._status_filter.currentIndexChanged.connect(self._apply_filters)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter source, adapter, format, field, or capability…")
        self._search.textChanged.connect(self._apply_filters)
        filters.addWidget(self._status_filter)
        filters.addWidget(self._search, 1)
        root.addLayout(filters)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            [
                "Source",
                "State",
                "Adapter",
                "Size",
                "Sampled",
                "Evidence",
                "Rejected",
                "Time range",
            ]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in (1, 3, 4, 5, 6, 7):
            self._table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.cellClicked.connect(self._open_detail)
        root.addWidget(self._table, 1)

    def set_investigation(
        self,
        setup: InvestigationSetup,
        records: tuple[EvidenceRecord, ...],
        rejections: tuple[ImportRejection, ...],
    ) -> None:
        if self._detail_dialog is not None:
            self._detail_dialog.close()
        self._previews = setup.source_previews
        self._display_timezone = setup.case.display_timezone
        self._records = records
        self._rejections = rejections
        supported = sum(
            preview.status in {PreviewStatus.READY, PreviewStatus.WARNING}
            for preview in self._previews
        )
        limited = sum(
            preview.status in {PreviewStatus.UNSUPPORTED, PreviewStatus.FAILED}
            for preview in self._previews
        )
        warning_count = sum(bool(preview.warnings) for preview in self._previews)
        self._summary.setText(
            f"{len(self._previews)} supplied source(s) · {supported} supported · "
            f"{len(records)} durable evidence record(s) · {len(rejections)} rejection(s) · "
            f"{limited} unavailable/unsupported · {warning_count} source(s) with limitations."
        )
        self._apply_filters()

    def _apply_filters(self) -> None:
        mode = self._status_filter.currentText()
        query = self._search.text().strip().casefold()
        visible: list[SourcePreview] = []
        for preview in self._previews:
            if mode == "Ready" and preview.status is not PreviewStatus.READY:
                continue
            if mode == "Warnings" and preview.status is not PreviewStatus.WARNING:
                continue
            if mode == "Unsupported" and preview.status is not PreviewStatus.UNSUPPORTED:
                continue
            if mode == "Failed" and preview.status is not PreviewStatus.FAILED:
                continue
            haystack = " ".join(
                (
                    preview.display_name,
                    preview.adapter_id or "",
                    preview.format_name or "",
                    " ".join(preview.fields),
                    " ".join(preview.capabilities),
                )
            ).casefold()
            if query and query not in haystack:
                continue
            visible.append(preview)
        self._visible = visible
        self._populate()

    def _populate(self) -> None:
        evidence_counts = Counter(record.source_preview_id for record in self._records)
        rejection_counts = Counter(item.source_preview_id for item in self._rejections)
        self._table.setRowCount(0)
        for row, preview in enumerate(self._visible):
            self._table.insertRow(row)
            values = (
                preview.display_name,
                preview.status.value.title(),
                _adapter_label(preview),
                _format_size(preview.byte_size),
                str(preview.sample_records),
                str(evidence_counts[preview.preview_id]),
                str(rejection_counts[preview.preview_id]),
                _time_range_short(preview, self._display_timezone),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 1:
                    item.setForeground(QColor(STATUS_COLORS[preview.status]))
                    item.setData(Qt.ItemDataRole.UserRole, preview.status.value)
                self._table.setItem(row, column, item)

    def _open_detail(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self._visible):
            return
        preview = self._visible[row]
        records = tuple(
            record for record in self._records if record.source_preview_id == preview.preview_id
        )
        rejections = tuple(
            item for item in self._rejections if item.source_preview_id == preview.preview_id
        )
        fields = "\n".join(f"  - {field}" for field in preview.fields) or "  - None"
        capabilities = "\n".join(f"  - {value}" for value in preview.capabilities) or "  - None"
        warnings = "\n".join(f"  - {value}" for value in preview.warnings) or "  - None"
        diagnostics = (
            "\n".join(
                f"  - {item.code} · position {item.line_number or 'source'} · {item.message}"
                for item in rejections
            )
            or "  - None"
        )
        if self._detail_dialog is None:
            self._detail_dialog = DetailDialog(self)
        self._detail_dialog.present(
            window_title="Source inventory details",
            eyebrow="SOURCE PROVENANCE AND CAPABILITY",
            title=f"{preview.display_name} · {preview.status.value.title()}",
            text=(
                f"Preview ID: {preview.preview_id}\n"
                f"Selected path: {preview.path}\n"
                f"SHA-256: {preview.sha256 or 'Unavailable'}\n"
                f"Size: {_format_size(preview.byte_size)} ({preview.byte_size} bytes)\n"
                f"Status: {preview.status.value}\n"
                f"Format: {preview.format_name or 'Unrecognized'}\n"
                f"Adapter: {_adapter_label(preview)}\n"
                f"Sampled records: {preview.sample_records}\n"
                f"Time range ({self._display_timezone}): "
                f"{_time_range(preview, self._display_timezone)}\n"
                f"Durable evidence: {len(records)}\n"
                f"Rejected records: {len(rejections)}\n"
                f"Capabilities:\n{capabilities}\n"
                f"Mapped/searchable fields:\n{fields}\n"
                f"Preview limitations:\n{warnings}\n"
                f"Import diagnostics:\n{diagnostics}"
            ),
        )


def _adapter_label(preview: SourcePreview) -> str:
    if preview.adapter_id is None:
        return "No installed adapter"
    return f"{preview.adapter_id}/{preview.adapter_version or 'unknown'}"


def _format_size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value / (1024 * 1024):.1f} MiB"


def _time_range(preview: SourcePreview, display_timezone: str) -> str:
    if preview.earliest_time is None and preview.latest_time is None:
        return "Undated / unavailable"
    earliest = (
        format_case_datetime(preview.earliest_time, display_timezone)
        if preview.earliest_time
        else "Unknown"
    )
    latest = (
        format_case_datetime(preview.latest_time, display_timezone)
        if preview.latest_time
        else "Unknown"
    )
    return f"{earliest} → {latest}"


def _time_range_short(preview: SourcePreview, display_timezone: str) -> str:
    earliest = preview.earliest_time
    latest = preview.latest_time
    if earliest is None and latest is None:
        return "Undated / unavailable"
    if earliest is None or latest is None:
        value = earliest or latest
        return format_case_datetime(value, display_timezone) if value is not None else "Unknown"
    return (
        f"{format_case_datetime(earliest, display_timezone)} → "
        f"{format_case_datetime(latest, display_timezone)}"
    )
