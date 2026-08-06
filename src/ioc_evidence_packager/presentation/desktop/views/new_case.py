"""Three-step New Investigation wizard for lead and source preview."""

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.application.services import (
    NewCaseRequest,
    NewInvestigationRequest,
)
from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.observables import ParsedObservable, parse_observable
from ioc_evidence_packager.domain.sources import PreviewStatus, SourcePreview
from ioc_evidence_packager.ingestion import SourceInspectionService
from ioc_evidence_packager.presentation.desktop.jobs import SourcePreviewWorker


class NewCaseDialog(QDialog):
    """Guides case metadata, lead validation, source preview, and review."""

    def __init__(
        self,
        source_inspection_service: SourceInspectionService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_inspection_service = source_inspection_service
        self._thread_pool = QThreadPool.globalInstance()
        self._parsed_observable: ParsedObservable | None = None
        self._previews: dict[str, SourcePreview] = {}
        self._pending_paths: set[str] = set()
        self._workers: dict[str, SourcePreviewWorker] = {}
        self.setWindowTitle("New investigation")
        self.setModal(True)
        self.resize(820, 640)
        self.setMinimumSize(720, 560)
        self._build_ui()
        self._update_controls()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        heading = QHBoxLayout()
        heading_text = QVBoxLayout()
        title = QLabel("Create an investigation")
        title.setStyleSheet("font-size: 21px; font-weight: 700;")
        self._step_text = QLabel()
        self._step_text.setObjectName("Muted")
        heading_text.addWidget(title)
        heading_text.addWidget(self._step_text)
        heading.addLayout(heading_text, 1)
        self._step_pill = QLabel()
        self._step_pill.setObjectName("StepPill")
        heading.addWidget(self._step_pill, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(heading)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._build_lead_page())
        self._pages.addWidget(self._build_sources_page())
        self._pages.addWidget(self._build_review_page())
        self._pages.currentChanged.connect(self._page_changed)
        root.addWidget(self._pages, 1)

        buttons = QHBoxLayout()
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        self._back_button = QPushButton("Back")
        self._back_button.clicked.connect(self._back)
        self._next_button = QPushButton("Next")
        self._next_button.setObjectName("PrimaryButton")
        self._next_button.clicked.connect(self._next)
        self._create_button = QPushButton("Create investigation")
        self._create_button.setObjectName("PrimaryButton")
        self._create_button.clicked.connect(self.accept)
        buttons.addWidget(self._cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(self._back_button)
        buttons.addWidget(self._next_button)
        buttons.addWidget(self._create_button)
        root.addLayout(buttons)

    def _build_lead_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(14)

        intro = QLabel(
            "Name the case and enter the observable that started the investigation. "
            "The original value is preserved beside its canonical comparison form."
        )
        intro.setObjectName("PageSubtitle")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form_card = QFrame()
        form_card.setObjectName("Panel")
        form = QFormLayout(form_card)
        form.setContentsMargins(20, 18, 20, 18)
        form.setSpacing(12)
        self._title = QLineEdit()
        self._title.setPlaceholderText("Example: Suspicious domain on finance workstations")
        self._title.setMaxLength(120)
        self._reference = QLineEdit()
        self._reference.setPlaceholderText("Optional ticket or incident ID")
        self._reference.setMaxLength(120)
        self._lead = QLineEdit()
        self._lead.setPlaceholderText("IPv4, fully qualified domain, or SHA-256")
        self._timezone = QComboBox()
        self._timezone.addItems(["UTC", "Local system time"])
        self._summary = QTextEdit()
        self._summary.setAcceptRichText(False)
        self._summary.setPlaceholderText("Optional reason for opening this case")
        self._summary.setMaximumHeight(76)
        form.addRow("Case title *", self._title)
        form.addRow("External reference", self._reference)
        form.addRow("Lead observable *", self._lead)
        form.addRow("Display time zone", self._timezone)
        form.addRow("Summary", self._summary)
        layout.addWidget(form_card)

        validation_card = QFrame()
        validation_card.setObjectName("NoticeCard")
        validation_layout = QVBoxLayout(validation_card)
        validation_layout.setContentsMargins(18, 14, 18, 14)
        self._lead_state = QLabel("Waiting for a lead observable")
        self._lead_state.setStyleSheet("font-weight: 700;")
        self._canonical_value = QLabel(
            "Supported in this slice: IPv4, fully qualified domain, and SHA-256."
        )
        self._canonical_value.setObjectName("Muted")
        self._canonical_value.setWordWrap(True)
        validation_layout.addWidget(self._lead_state)
        validation_layout.addWidget(self._canonical_value)
        layout.addWidget(validation_card)
        layout.addStretch(1)

        self._title.textChanged.connect(self._update_controls)
        self._lead.textChanged.connect(self._validate_lead)
        return page

    def _build_sources_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        intro = QLabel(
            "Add exported evidence. Each file is hashed completely, then only a bounded "
            "sample is used to detect its adapter, fields, capabilities, and time range."
        )
        intro.setObjectName("PageSubtitle")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        actions = QHBoxLayout()
        add_button = QPushButton("Add evidence files")
        add_button.setObjectName("PrimaryButton")
        add_button.clicked.connect(self._choose_sources)
        self._remove_button = QPushButton("Remove selected")
        self._remove_button.setEnabled(False)
        self._remove_button.clicked.connect(self._remove_selected_source)
        actions.addWidget(add_button)
        actions.addWidget(self._remove_button)
        actions.addStretch(1)
        self._source_summary = QLabel("No sources selected")
        self._source_summary.setObjectName("Muted")
        actions.addWidget(self._source_summary)
        layout.addLayout(actions)

        self._source_table = QTableWidget(0, 6)
        self._source_table.setHorizontalHeaderLabels(
            ["Source", "Size", "Format", "Capabilities", "State", "SHA-256"]
        )
        self._source_table.setAlternatingRowColors(True)
        self._source_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._source_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._source_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._source_table.verticalHeader().setVisible(False)
        self._source_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in range(1, 6):
            self._source_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._source_table.itemSelectionChanged.connect(self._source_selection_changed)
        layout.addWidget(self._source_table, 1)

        self._preview_detail = QLabel(
            "Select a completed source to see its adapter and preview limitations."
        )
        self._preview_detail.setObjectName("Muted")
        self._preview_detail.setWordWrap(True)
        layout.addWidget(self._preview_detail)
        return page

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(14)

        intro = QLabel(
            "Review what will be stored in the local case. "
            "No network requests are part of this run."
        )
        intro.setObjectName("PageSubtitle")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        review = QFrame()
        review.setObjectName("Panel")
        review_layout = QFormLayout(review)
        review_layout.setContentsMargins(20, 18, 20, 18)
        review_layout.setSpacing(13)
        self._review_title = QLabel()
        self._review_lead = QLabel()
        self._review_lead.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._review_sources = QLabel()
        self._review_policy = QLabel("Offline — no values leave this workstation")
        review_layout.addRow("Case", self._review_title)
        review_layout.addRow("Lead", self._review_lead)
        review_layout.addRow("Evidence sources", self._review_sources)
        review_layout.addRow("Privacy policy", self._review_policy)
        layout.addWidget(review)

        privacy = QFrame()
        privacy.setObjectName("NoticeCard")
        privacy_layout = QVBoxLayout(privacy)
        privacy_layout.setContentsMargins(18, 14, 18, 14)
        privacy_title = QLabel("SOURCE BYTES ARE NOT IMPORTED YET")
        privacy_title.setObjectName("SectionEyebrow")
        privacy_copy = QLabel(
            "This slice stores the selected path, SHA-256, format, capabilities, time bounds, "
            "and warnings. Full record ingestion begins in Slice 3."
        )
        privacy_copy.setObjectName("Muted")
        privacy_copy.setWordWrap(True)
        privacy_layout.addWidget(privacy_title)
        privacy_layout.addWidget(privacy_copy)
        layout.addWidget(privacy)
        layout.addStretch(1)
        return page

    def add_source_paths(self, paths: list[Path]) -> None:
        """Queue unique paths for background inspection; also used by UI tests."""

        existing = set(self._previews) | self._pending_paths
        for path in paths:
            path_key = str(path.expanduser().resolve(strict=False))
            if path_key in existing:
                continue
            existing.add(path_key)
            self._pending_paths.add(path_key)
            row = self._source_table.rowCount()
            self._source_table.insertRow(row)
            source_item = QTableWidgetItem(Path(path_key).name)
            source_item.setData(Qt.ItemDataRole.UserRole, path_key)
            source_item.setToolTip(path_key)
            self._source_table.setItem(row, 0, source_item)
            for column, value in enumerate(["—", "Detecting…", "—", "Hashing…", "—"], 1):
                self._source_table.setItem(row, column, QTableWidgetItem(value))
            self._source_table.setRowHeight(row, 42)

            worker = SourcePreviewWorker(self._source_inspection_service, Path(path_key))
            worker.signals.completed.connect(self._preview_completed)
            worker.signals.failed.connect(self._preview_failed)
            self._workers[path_key] = worker
            self._thread_pool.start(worker)
        self._update_controls()

    def request(self) -> NewInvestigationRequest:
        if self._parsed_observable is None:
            raise ValidationError("The lead observable has not been validated.")
        timezone = "UTC" if self._timezone.currentIndex() == 0 else "Local system time"
        return NewInvestigationRequest(
            case=NewCaseRequest(
                title=self._title.text(),
                external_reference=self._reference.text(),
                display_timezone=timezone,
                summary=self._summary.toPlainText(),
            ),
            lead_value=self._parsed_observable.original_value,
            source_previews=tuple(self._previews.values()),
        )

    def _validate_lead(self, value: str) -> None:
        try:
            parsed = parse_observable(value)
        except ValidationError as error:
            self._parsed_observable = None
            self._lead_state.setText("Lead needs attention")
            self._lead_state.setObjectName("ValidationError")
            self._canonical_value.setText(str(error))
        else:
            self._parsed_observable = parsed
            display_type = parsed.observable_type.value.upper()
            self._lead_state.setText(f"Valid {display_type} lead")
            self._lead_state.setObjectName("ValidationGood")
            self._canonical_value.setText(f"Canonical value: {parsed.canonical_value}")
        self._lead_state.style().unpolish(self._lead_state)
        self._lead_state.style().polish(self._lead_state)
        self._update_controls()

    def _choose_sources(self) -> None:
        names, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Select exported evidence",
            "",
            "Evidence files (*.jsonl *.json *.csv);;All files (*)",
        )
        self.add_source_paths([Path(name) for name in names])

    def _preview_completed(self, path_key: str, value: object) -> None:
        self._pending_paths.discard(path_key)
        self._workers.pop(path_key, None)
        if not isinstance(value, SourcePreview) or self._row_for_path(path_key) is None:
            self._update_controls()
            return
        self._previews[path_key] = value
        self._update_source_row(path_key, value)
        self._update_controls()

    def _preview_failed(self, path_key: str, message: str) -> None:
        self._pending_paths.discard(path_key)
        self._workers.pop(path_key, None)
        row = self._row_for_path(path_key)
        if row is not None:
            self._source_table.setItem(row, 4, QTableWidgetItem("Failed"))
            source_item = self._source_table.item(row, 0)
            if source_item is not None:
                source_item.setToolTip(message)
        self._update_controls()

    def _update_source_row(self, path_key: str, preview: SourcePreview) -> None:
        row = self._row_for_path(path_key)
        if row is None:
            return
        digest = f"{preview.sha256[:12]}…" if preview.sha256 else "Unavailable"
        values = (
            _format_size(preview.byte_size),
            preview.format_name or "Unsupported",
            ", ".join(preview.capabilities) or "None",
            preview.status.value.title(),
            digest,
        )
        for column, value in enumerate(values, 1):
            item = QTableWidgetItem(value)
            if column == 5 and preview.sha256:
                item.setToolTip(preview.sha256)
            self._source_table.setItem(row, column, item)

    def _source_selection_changed(self) -> None:
        selected = self._source_table.selectionModel().selectedRows()
        self._remove_button.setEnabled(bool(selected))
        if not selected:
            return
        source_item = self._source_table.item(selected[0].row(), 0)
        if source_item is None:
            return
        path_key = str(source_item.data(Qt.ItemDataRole.UserRole))
        preview = self._previews.get(path_key)
        if preview is None:
            self._preview_detail.setText("Hashing and adapter detection are still running.")
            return
        time_range = _preview_time_range(preview)
        warning = " ".join(preview.warnings) if preview.warnings else "No preview warnings."
        fields = f"{len(preview.fields)} distinct sampled field paths"
        self._preview_detail.setText(f"{time_range} · {fields} · {warning}")

    def _remove_selected_source(self) -> None:
        selected = self._source_table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        item = self._source_table.item(row, 0)
        if item is None:
            return
        path_key = str(item.data(Qt.ItemDataRole.UserRole))
        self._previews.pop(path_key, None)
        self._pending_paths.discard(path_key)
        self._source_table.removeRow(row)
        self._preview_detail.setText(
            "Select a completed source to see its adapter and preview limitations."
        )
        self._update_controls()

    def _row_for_path(self, path_key: str) -> int | None:
        for row in range(self._source_table.rowCount()):
            item = self._source_table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == path_key:
                return row
        return None

    def _next(self) -> None:
        self._pages.setCurrentIndex(min(self._pages.currentIndex() + 1, 2))

    def _back(self) -> None:
        self._pages.setCurrentIndex(max(self._pages.currentIndex() - 1, 0))

    def _page_changed(self, _index: int) -> None:
        if self._pages.currentIndex() == 2:
            self._refresh_review()
        self._update_controls()

    def _refresh_review(self) -> None:
        parsed = self._parsed_observable
        self._review_title.setText(self._title.text().strip())
        if parsed is not None:
            self._review_lead.setText(
                f"{parsed.observable_type.value.upper()} · {parsed.canonical_value}"
            )
        ready = sum(
            preview.status in {PreviewStatus.READY, PreviewStatus.WARNING}
            for preview in self._previews.values()
        )
        limited = len(self._previews) - ready
        self._review_sources.setText(
            f"{len(self._previews)} selected · {ready} recognized · {limited} limited"
        )

    def _update_controls(self) -> None:
        page = self._pages.currentIndex()
        lead_ready = bool(self._title.text().strip()) and self._parsed_observable is not None
        source_ready = (
            not self._pending_paths
            and bool(self._previews)
            and any(
                preview.status in {PreviewStatus.READY, PreviewStatus.WARNING}
                for preview in self._previews.values()
            )
        )
        self._back_button.setVisible(page > 0)
        self._next_button.setVisible(page < 2)
        self._create_button.setVisible(page == 2)
        self._next_button.setEnabled(lead_ready if page == 0 else source_ready)
        self._create_button.setEnabled(page == 2 and lead_ready and source_ready)
        step_names = ("Case and lead", "Evidence sources", "Review")
        self._step_text.setText(step_names[page])
        self._step_pill.setText(f"STEP {page + 1} OF 3")
        pending = len(self._pending_paths)
        if pending:
            self._source_summary.setText(f"Inspecting {pending} source(s)…")
        elif self._previews:
            self._source_summary.setText(f"{len(self._previews)} source(s) previewed")
        else:
            self._source_summary.setText("No sources selected")


def _format_size(byte_size: int) -> str:
    if byte_size < 1_024:
        return f"{byte_size} B"
    if byte_size < 1_048_576:
        return f"{byte_size / 1_024:.1f} KB"
    return f"{byte_size / 1_048_576:.1f} MB"


def _preview_time_range(preview: SourcePreview) -> str:
    if preview.earliest_time is None or preview.latest_time is None:
        return "No reliable sampled time range"
    start = preview.earliest_time.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    end = preview.latest_time.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return f"Sampled time range {start} to {end}"
