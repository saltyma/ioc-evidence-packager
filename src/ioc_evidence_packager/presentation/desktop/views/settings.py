# ruff: noqa: E501 - complete setting explanations stay close to their controls
"""Case and application settings with explicit scope and persistence."""

import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.domain.models import Case, PrivacyMode
from ioc_evidence_packager.presentation.desktop.settings_store import DesktopPreferences


class SettingsView(QWidget):
    """Separates case-durable policy from device-local UI preferences."""

    save_requested = Signal(str, str, object)
    reset_requested = Signal()

    def __init__(self, database_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._case: Case | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(14)
        eyebrow = QLabel("CASE POLICY AND DEVICE PREFERENCES")
        eyebrow.setObjectName("SectionEyebrow")
        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Case settings travel with the investigation database. Appearance and provider toggles apply only to this workstation. Secrets are never stored here."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._case_page(), "Case")
        tabs.addTab(self._appearance_page(), "Appearance")
        tabs.addTab(self._intelligence_page(), "Intelligence & privacy")
        tabs.addTab(self._storage_page(), "Storage & versions")
        root.addWidget(tabs, 1)

        self._feedback = QLabel("Changes have not been saved.")
        self._feedback.setObjectName("Muted")
        actions = QHBoxLayout()
        reset = QPushButton("Reset device preferences")
        reset.clicked.connect(self.reset_requested)
        save = QPushButton("Save settings")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._save)
        actions.addWidget(self._feedback, 1)
        actions.addWidget(reset)
        actions.addWidget(save)
        root.addLayout(actions)

    def _case_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "These values are durable case policy. Remote intelligence remains blocked unless the case mode and the device provider toggle both allow it."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self._timezone = QLineEdit("UTC")
        self._timezone.setPlaceholderText("IANA/UTC label used for display, e.g. UTC")
        self._privacy = QComboBox()
        for mode in PrivacyMode:
            self._privacy.addItem(mode.value.replace("_", " ").title(), mode.value)
        form.addRow("Display timezone", self._timezone)
        form.addRow("Case privacy mode", self._privacy)
        layout.addLayout(form)
        explanation = QLabel(
            "Offline: no provider calls. Local intelligence: manual/imported assertions only. Safe enrichment: selected IOC-only provider lookups after disclosure confirmation. Enterprise/Custom: organization-controlled policy; this build still applies the same explicit confirmation boundary."
        )
        explanation.setObjectName("Muted")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addStretch(1)
        return page

    def _appearance_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._density = QComboBox()
        self._density.addItems(("Comfortable", "Compact"))
        self._detail_width = QSpinBox()
        self._detail_width.setRange(620, 900)
        self._detail_width.setSingleStep(20)
        self._detail_width.setSuffix(" px")
        self._contrast = QCheckBox("Use stronger semantic value colors")
        form.addRow("Table/form density", self._density)
        form.addRow("Detail popup width", self._detail_width)
        form.addRow("Accessible semantics", self._contrast)
        help_label = QLabel(
            "Detail text always wraps inside a bounded reading column. Color reinforces labels and states; it never replaces text."
        )
        help_label.setObjectName("Muted")
        help_label.setWordWrap(True)
        form.addRow("", help_label)
        return page

    def _intelligence_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._vt = QCheckBox("Enable VirusTotal object-report connector")
        self._cache = QSpinBox()
        self._cache.setRange(1, 168)
        self._cache.setSuffix(" hours")
        self._external = QCheckBox("Confirm before opening external references")
        self._default_privacy = QComboBox()
        for mode in PrivacyMode:
            self._default_privacy.addItem(mode.value.replace("_", " ").title(), mode.value)
        self._key_state = QLabel()
        form.addRow("Provider", self._vt)
        form.addRow("Assertion freshness default", self._cache)
        form.addRow("External links", self._external)
        form.addRow("New-case privacy default", self._default_privacy)
        form.addRow("API key launch state", self._key_state)
        note = QLabel(
            "The API key is read only from IOC_PACKAGER_VT_API_KEY when the app starts; it is not written to SQLite, QSettings, logs, reports, or Case Capsules. Remote lookup sends one selected IOC and never uploads files."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        form.addRow("", note)
        return page

    def _storage_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        database = QLineEdit(str(self._database_path))
        database.setReadOnly(True)
        schema = QLabel("6 · analyst reasoning workspace")
        schema.setObjectName("SemanticInfo")
        app = QLabel("v0.7.0 · relationships, recommendations, intelligence, settings")
        app.setObjectName("SemanticGood")
        form.addRow("Case database", database)
        form.addRow("SQLite schema", schema)
        form.addRow("Application", app)
        note = QLabel(
            "Storage relocation is intentionally not performed in-place: copy and verify the database while the app is closed, then launch with --database. Case Capsule exports remain separate, immutable handoff directories."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        form.addRow("Safety", note)
        return page

    def set_settings(self, case: Case, preferences: DesktopPreferences) -> None:
        self._case = case
        self._timezone.setText(case.display_timezone)
        self._privacy.setCurrentIndex(max(0, self._privacy.findData(case.privacy_mode.value)))
        self._density.setCurrentText(preferences.density)
        self._detail_width.setValue(preferences.detail_width)
        self._contrast.setChecked(preferences.high_contrast)
        self._vt.setChecked(preferences.virustotal_enabled)
        self._cache.setValue(preferences.cache_hours)
        self._external.setChecked(preferences.confirm_external_links)
        self._default_privacy.setCurrentIndex(
            max(0, self._default_privacy.findData(preferences.default_privacy_mode))
        )
        configured = bool(os.environ.get("IOC_PACKAGER_VT_API_KEY", "").strip())
        self._key_state.setText(
            "Configured in launch environment" if configured else "Not configured"
        )
        self._key_state.setObjectName("SemanticGood" if configured else "SemanticWarn")
        self._feedback.setText("Loaded durable case policy and device preferences.")

    def mark_saved(self, message: str = "Settings saved and applied.") -> None:
        self._feedback.setText(message)
        self._feedback.setObjectName("SemanticGood")
        self._feedback.style().unpolish(self._feedback)
        self._feedback.style().polish(self._feedback)

    def _save(self) -> None:
        if self._case is None:
            return
        preferences = DesktopPreferences(
            density=self._density.currentText(),
            detail_width=self._detail_width.value(),
            high_contrast=self._contrast.isChecked(),
            virustotal_enabled=self._vt.isChecked(),
            cache_hours=self._cache.value(),
            confirm_external_links=self._external.isChecked(),
            default_privacy_mode=str(self._default_privacy.currentData()),
        )
        self.save_requested.emit(
            str(self._privacy.currentData()), self._timezone.text(), preferences
        )
