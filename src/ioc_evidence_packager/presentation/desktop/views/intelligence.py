# ruff: noqa: E501 - complete provider disclosures stay close to their widgets
"""Attributed intelligence assertions with privacy and disclosure controls."""

import urllib.parse

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.domain.models import Case
from ioc_evidence_packager.domain.timezones import UTC_DISPLAY, format_case_datetime
from ioc_evidence_packager.domain.workspace import (
    IntelligenceAssertion,
    IntelligenceClaim,
    intelligence_conflicts,
)
from ioc_evidence_packager.presentation.desktop.views.detail_dialog import DetailDialog

CLAIM_COLORS = {
    "Malicious": "#FF7F9F",
    "Suspicious": "#F2B84B",
    "Benign": "#67D7A4",
    "Unknown": "#A49CB5",
    "Context only": "#70D6E8",
}


class IntelligenceView(QWidget):
    """Keeps provider claims separate from source-linked case facts."""

    add_requested = Signal(object)
    import_requested = Signal(str)
    archive_requested = Signal(str)
    query_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._case: Case | None = None
        self._assertions: tuple[IntelligenceAssertion, ...] = ()
        self._visible: list[IntelligenceAssertion] = []
        self._conflicts: frozenset[object] = frozenset()
        self._selected: IntelligenceAssertion | None = None
        self._detail_dialog: DetailDialog | None = None
        self._provider_enabled = False
        self._confirm_external_links = True
        self._display_timezone = UTC_DISPLAY
        self._build_ui()

    @property
    def row_count(self) -> int:
        return self._table.rowCount()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(14)
        eyebrow = QLabel("ATTRIBUTED PROVIDER ASSERTIONS")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Intelligence")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Intelligence is not evidence. Each assertion retains its provider, native confidence vocabulary, retrieval/data times, expiry, origin, reference, and response digest. Conflicts remain visible instead of being averaged away."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        provider = QHBoxLayout()
        self._observable = QComboBox()
        self._observable.setMinimumWidth(330)
        self._query = QPushButton("Query VirusTotal report")
        self._query.clicked.connect(self._request_query)
        manual = QPushButton("Add manual assertion")
        manual.clicked.connect(self._open_manual)
        import_button = QPushButton("Import assertion file")
        import_button.clicked.connect(self._choose_import)
        self._archive = QPushButton("Archive selected")
        self._archive.setEnabled(False)
        self._archive.clicked.connect(self._request_archive)
        self._open_reference = QPushButton("Open provider reference")
        self._open_reference.setEnabled(False)
        self._open_reference.clicked.connect(self._open_selected_reference)
        provider.addWidget(self._observable, 1)
        provider.addWidget(self._query)
        root.addLayout(provider)
        assertion_actions = QHBoxLayout()
        assertion_actions.addWidget(manual)
        assertion_actions.addWidget(import_button)
        assertion_actions.addWidget(self._archive)
        assertion_actions.addWidget(self._open_reference)
        assertion_actions.addStretch(1)
        root.addLayout(assertion_actions)

        self._policy = QLabel("Open a case to see its intelligence policy.")
        self._policy.setObjectName("Muted")
        self._policy.setWordWrap(True)
        root.addWidget(self._policy)

        filters = QHBoxLayout()
        self._claim = QComboBox()
        self._claim.addItems(("All claims", *[value.value for value in IntelligenceClaim]))
        self._claim.currentIndexChanged.connect(self._apply_filters)
        self._conflict = QComboBox()
        self._conflict.addItems(("All assertions", "Conflicts only", "No conflict"))
        self._conflict.currentIndexChanged.connect(self._apply_filters)
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Filter provider, observable, claim, summary, origin, or confidence…"
        )
        self._search.textChanged.connect(self._apply_filters)
        filters.addWidget(self._claim)
        filters.addWidget(self._conflict)
        filters.addWidget(self._search, 1)
        root.addLayout(filters)

        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            (
                "Provider",
                "Observable type",
                "Observable",
                "Claim",
                "Provider confidence",
                "Retrieved",
                "Cache",
                "Origin",
                "Conflict",
            )
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.cellClicked.connect(self._open_detail)
        root.addWidget(self._table, 1)

    def set_intelligence(
        self,
        case: Case,
        assertions: tuple[IntelligenceAssertion, ...],
        observables: tuple[tuple[str, str], ...],
        *,
        provider_enabled: bool,
        confirm_external_links: bool,
    ) -> None:
        if self._detail_dialog is not None:
            self._detail_dialog.close()
        self._selected = None
        self._archive.setEnabled(False)
        self._open_reference.setEnabled(False)
        self._case = case
        self._display_timezone = case.display_timezone
        self._assertions = assertions
        self._conflicts = intelligence_conflicts(assertions)
        self._provider_enabled = provider_enabled
        self._confirm_external_links = confirm_external_links
        current = self._observable.currentData()
        self._observable.clear()
        for kind, value in sorted(set(observables)):
            self._observable.addItem(f"{kind.upper()}  ·  {value}", (kind, value))
        index = self._observable.findData(current)
        self._observable.setCurrentIndex(max(0, index))
        remote_policy = case.privacy_mode.value in {"safe_enrichment", "enterprise"}
        self._query.setEnabled(bool(observables) and provider_enabled and remote_policy)
        self._policy.setText(
            f"Case policy: {case.privacy_mode.value.replace('_', ' ').title()} · Remote provider: {'enabled' if provider_enabled else 'disabled in Settings'} · {len(assertions)} active assertion(s) · {len(self._conflicts)} assertion(s) in explicit conflict. Remote lookup sends only the selected IOC; source records never leave the workstation."
        )
        self._apply_filters()

    def _apply_filters(self) -> None:
        claim = self._claim.currentText()
        conflict_filter = self._conflict.currentText()
        query = self._search.text().strip().casefold()
        visible: list[IntelligenceAssertion] = []
        for item in self._assertions:
            conflicted = item.assertion_id in self._conflicts
            if claim != "All claims" and item.claim.value != claim:
                continue
            if conflict_filter == "Conflicts only" and not conflicted:
                continue
            if conflict_filter == "No conflict" and conflicted:
                continue
            haystack = " ".join(
                (
                    item.provider,
                    item.observable_type,
                    item.observable_value,
                    item.claim.value,
                    item.confidence_label,
                    item.summary,
                    item.origin,
                )
            ).casefold()
            if query and query not in haystack:
                continue
            visible.append(item)
        self._visible = visible
        if self._selected not in visible:
            self._selected = None
            self._archive.setEnabled(False)
            self._open_reference.setEnabled(False)
        self._populate()

    def _populate(self) -> None:
        self._table.setRowCount(0)
        for row, item in enumerate(self._visible):
            self._table.insertRow(row)
            conflict = "CONFLICT" if item.assertion_id in self._conflicts else "—"
            values = (
                item.provider,
                item.observable_type.upper(),
                item.observable_value,
                item.claim.value,
                item.confidence_label,
                format_case_datetime(item.retrieved_at, self._display_timezone),
                item.cache_state,
                item.origin.upper(),
                conflict,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 3:
                    cell.setForeground(QBrush(QColor(CLAIM_COLORS[value])))
                elif column == 8 and conflict != "—":
                    cell.setForeground(QBrush(QColor("#FF7F9F")))
                elif column in {0, 2}:
                    cell.setForeground(QBrush(QColor("#70D6E8" if column == 0 else "#C9B8FF")))
                cell.setToolTip(value)
                self._table.setItem(row, column, cell)

    def _open_detail(self, row: int, _column: int) -> None:
        if not 0 <= row < len(self._visible):
            return
        item = self._visible[row]
        self._selected = item
        self._archive.setEnabled(True)
        self._open_reference.setEnabled(_is_https_reference(item.source_reference))
        conflict = item.assertion_id in self._conflicts
        text = (
            f"Assertion ID: {item.assertion_id}\nProvider: {item.provider}\nProvider version: {item.provider_version}\n"
            f"Origin: {item.origin.upper()}\nObservable type: {item.observable_type.upper()}\nObservable value: {item.observable_value}\n"
            f"Claim: {item.claim.value}\nProvider confidence: {item.confidence_label}\nConflict state: {'CONFLICT — inspect other assertions for this observable' if conflict else 'No active contradictory claim'}\n"
            f"Summary: {item.summary}\nRetrieved at ({self._display_timezone}): "
            f"{format_case_datetime(item.retrieved_at, self._display_timezone)}\n"
            f"Provider data timestamp ({self._display_timezone}): "
            f"{format_case_datetime(item.data_timestamp, self._display_timezone) if item.data_timestamp else 'Not supplied'}\n"
            f"Expires at ({self._display_timezone}): "
            f"{format_case_datetime(item.expires_at, self._display_timezone) if item.expires_at else 'Not supplied'}\n"
            f"Cache state: {item.cache_state}\n"
            f"Source reference: {item.source_reference or 'Not supplied'}\nRaw response SHA-256: {item.raw_response_sha256 or 'Not supplied'}\n"
            "Interpretation: This is an attributed provider/analyst assertion. It does not change evidence classification and is not proof of compromise."
        )
        if self._detail_dialog is None:
            self._detail_dialog = DetailDialog(self)
        self._detail_dialog.present(
            window_title="Intelligence assertion details",
            eyebrow="ATTRIBUTED — NOT SOURCE EVIDENCE",
            title=f"{item.provider} · {item.observable_value}",
            text=text,
        )

    def _open_manual(self) -> None:
        dialog = ManualAssertionDialog(self)
        data = self._observable.currentData()
        if isinstance(data, tuple) and len(data) == 2:
            dialog.set_observable(str(data[0]), str(data[1]))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.add_requested.emit(dialog.values())

    def _choose_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import intelligence assertion file", "", "JSON files (*.json)"
        )
        if path:
            self.import_requested.emit(path)

    def _request_archive(self) -> None:
        if self._selected is None:
            return
        answer = QMessageBox.question(
            self,
            "Archive assertion",
            "Archive this assertion? It remains in the case database for audit history but is removed from active views.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.archive_requested.emit(str(self._selected.assertion_id))

    def _request_query(self) -> None:
        if self._case is None:
            return
        data = self._observable.currentData()
        if not isinstance(data, tuple) or len(data) != 2:
            return
        kind, value = str(data[0]), str(data[1])
        message = (
            "Disclosure preview\n\n"
            f"Provider: VirusTotal API v3\nValue leaving this workstation: {kind.upper()} {value}\n"
            "Not sent: evidence records, source paths, case title, host names, user names, or raw logs.\n\n"
            "Proceed with this lookup?"
        )
        answer = QMessageBox.question(self, "Confirm remote intelligence lookup", message)
        if answer == QMessageBox.StandardButton.Yes:
            self.query_requested.emit(kind, value)

    def _open_selected_reference(self) -> None:
        if self._selected is None or not _is_https_reference(self._selected.source_reference):
            return
        reference = self._selected.source_reference or ""
        if self._confirm_external_links:
            answer = QMessageBox.question(
                self,
                "Open external provider reference",
                f"Open this HTTPS reference in the system browser?\n\n{reference}",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if not QDesktopServices.openUrl(QUrl(reference)):
            QMessageBox.warning(
                self,
                "Could not open provider reference",
                "The operating system did not accept the HTTPS URL.",
            )


class ManualAssertionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add attributed intelligence assertion")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Enter an assertion exactly as supplied by a trusted local source or analyst. Do not translate confidence into a universal score."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        layout.addWidget(note)
        form = QFormLayout()
        self._provider = QLineEdit()
        self._provider.setPlaceholderText("Example: Internal Threat Intelligence")
        self._type = QComboBox()
        self._type.addItems(("ipv4", "domain", "sha256"))
        self._value = QLineEdit()
        self._claim = QComboBox()
        self._claim.addItems(tuple(value.value for value in IntelligenceClaim))
        self._confidence = QLineEdit()
        self._confidence.setPlaceholderText("Provider-native wording, e.g. High confidence")
        self._summary = QTextEdit()
        self._summary.setMaximumHeight(110)
        self._reference = QLineEdit()
        form.addRow("Provider", self._provider)
        form.addRow("Observable type", self._type)
        form.addRow("Observable value", self._value)
        form.addRow("Provider claim", self._claim)
        form.addRow("Provider confidence", self._confidence)
        form.addRow("Summary", self._summary)
        form.addRow("Source reference (optional)", self._reference)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_observable(self, kind: str, value: str) -> None:
        index = self._type.findText(kind)
        self._type.setCurrentIndex(max(0, index))
        self._value.setText(value)

    def values(self) -> dict[str, str]:
        return {
            "provider": self._provider.text(),
            "observable_type": self._type.currentText(),
            "observable_value": self._value.text(),
            "claim": self._claim.currentText(),
            "confidence_label": self._confidence.text(),
            "summary": self._summary.toPlainText(),
            "source_reference": self._reference.text(),
        }


def _is_https_reference(value: str | None) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username
