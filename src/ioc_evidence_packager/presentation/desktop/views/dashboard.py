"""Coverage-aware case orientation dashboard."""

from datetime import UTC

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ioc_evidence_packager.application.services import InvestigationSetup
from ioc_evidence_packager.domain.analysis import AnalysisSnapshot, CoverageState
from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import Case


class MetricCard(QFrame):
    """Compact summary tile used by the dashboard shell."""

    def __init__(self, label: str, value: str, note: str) -> None:
        super().__init__()
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)
        metric_label = QLabel(label)
        metric_label.setObjectName("MetricLabel")
        self._value = QLabel(value)
        self._value.setObjectName("MetricValue")
        self._note = QLabel(note)
        self._note.setObjectName("Muted")
        self._note.setWordWrap(True)
        layout.addWidget(metric_label)
        layout.addWidget(self._value)
        layout.addWidget(self._note)

    def set_content(self, value: str, note: str) -> None:
        self._value.setText(value)
        self._note.setText(note)


class DashboardView(QWidget):
    """Case-level findings, evidence volume, coverage limits, and time bounds."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(20)

        heading = QHBoxLayout()
        heading_text = QVBoxLayout()
        eyebrow = QLabel("CASE DASHBOARD")
        eyebrow.setObjectName("SectionEyebrow")
        self._title = QLabel("Investigation")
        self._title.setObjectName("PageTitle")
        self._subtitle = QLabel("Durable local case workspace")
        self._subtitle.setObjectName("PageSubtitle")
        heading_text.addWidget(eyebrow)
        heading_text.addWidget(self._title)
        heading_text.addWidget(self._subtitle)
        heading.addLayout(heading_text, 1)
        self._status = QLabel("DRAFT")
        self._status.setObjectName("StatusPill")
        heading.addWidget(self._status, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(heading)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(14)
        self._lead_metric = MetricCard("Lead observables", "0", "No lead stored")
        self._evidence_metric = MetricCard("Evidence records", "0", "No evidence imported yet")
        self._sighting_metric = MetricCard("Direct sightings", "0", "Recipe not run")
        self._coverage_metric = MetricCard("Coverage", "Pending", "Evaluated after ingestion")
        metrics.addWidget(self._lead_metric, 0, 0)
        metrics.addWidget(self._evidence_metric, 0, 1)
        metrics.addWidget(self._sighting_metric, 0, 2)
        metrics.addWidget(self._coverage_metric, 0, 3)
        root.addLayout(metrics)

        next_step = QFrame()
        next_step.setObjectName("HeroPanel")
        next_layout = QVBoxLayout(next_step)
        next_layout.setContentsMargins(22, 20, 22, 20)
        next_eyebrow = QLabel("NEXT INVESTIGATION STEP")
        next_eyebrow.setObjectName("SectionEyebrow")
        self._next_title = QLabel("Import previewed records into the evidence ledger")
        self._next_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        self._next_copy = QLabel(
            "Open Evidence to stream canonical records into SQLite, review rejection "
            "diagnostics, and trace every accepted fact to its original source line."
        )
        self._next_copy.setObjectName("Muted")
        self._next_copy.setWordWrap(True)
        self._timeline_summary = QLabel("Timeline bounds are available after import.")
        self._timeline_summary.setObjectName("Muted")
        self._timeline_summary.setWordWrap(True)
        next_layout.addWidget(next_eyebrow)
        next_layout.addWidget(self._next_title)
        next_layout.addWidget(self._next_copy)
        next_layout.addWidget(self._timeline_summary)
        root.addWidget(next_step)

        details = QFrame()
        details.setObjectName("Panel")
        details_layout = QGridLayout(details)
        details_layout.setContentsMargins(20, 18, 20, 18)
        details_layout.setHorizontalSpacing(24)
        details_layout.setVerticalSpacing(10)
        details_layout.addWidget(_muted_label("CASE ID"), 0, 0)
        self._case_id = QLabel("—")
        self._case_id.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self._case_id, 0, 1)
        details_layout.addWidget(_muted_label("EXTERNAL REFERENCE"), 1, 0)
        self._reference = QLabel("Not set")
        details_layout.addWidget(self._reference, 1, 1)
        details_layout.addWidget(_muted_label("DISPLAY TIME ZONE"), 2, 0)
        self._timezone = QLabel("UTC")
        details_layout.addWidget(self._timezone, 2, 1)
        details_layout.addWidget(_muted_label("CASE SUMMARY"), 3, 0)
        self._summary = QLabel("No summary provided.")
        self._summary.setWordWrap(True)
        details_layout.addWidget(self._summary, 3, 1)
        details_layout.addWidget(_muted_label("LEAD OBSERVABLE"), 4, 0)
        self._lead = QLabel("No lead stored")
        self._lead.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._lead.setWordWrap(True)
        details_layout.addWidget(self._lead, 4, 1)
        details_layout.setColumnStretch(1, 1)
        root.addWidget(details)
        root.addStretch(1)

    def set_case(self, case: Case) -> None:
        self.set_investigation(InvestigationSetup(case=case, lead=None, source_previews=()))

    def set_investigation(self, setup: InvestigationSetup) -> None:
        case = setup.case
        self._title.setText(case.title)
        self._subtitle.setText(
            f"Opened {case.last_opened_at.astimezone().strftime('%Y-%m-%d at %H:%M')}"
        )
        self._status.setText(case.status.value.replace("_", " ").upper())
        self._case_id.setText(str(case.case_id))
        self._reference.setText(case.external_reference or "Not set")
        self._timezone.setText(case.display_timezone)
        self._summary.setText(case.summary or "No summary provided.")
        if setup.lead is None:
            self._lead.setText("No lead stored")
            self._lead_metric.set_content("0", "Legacy case without a lead")
        else:
            self._lead.setText(
                f"{setup.lead.observable_type.value.upper()} · {setup.lead.canonical_value}"
            )
            self._lead_metric.set_content("1", setup.lead.observable_type.value.upper())
        source_count = len(setup.source_previews)
        self._evidence_metric.set_content(
            "0",
            f"{source_count} source(s) previewed; ready for import",
        )
        self._sighting_metric.set_content("0", "Recipe not run")
        self._coverage_metric.set_content("Pending", "Evaluated after ingestion")
        self._timeline_summary.setText("Timeline bounds are available after import.")

    def set_evidence_counts(self, evidence: int, rejections: int) -> None:
        """Refresh import state without rebuilding the case orientation."""

        if evidence:
            note = f"{rejections} structured rejection(s)" if rejections else "No rejected lines"
            self._evidence_metric.set_content(str(evidence), note)
            self._next_title.setText("Review provenance and rejected source lines")
            self._next_copy.setText(
                "Open Evidence to inspect physical source lines, declared positions, "
                "observables, untouched canonical JSON, and bounded rejection diagnostics."
            )
        else:
            self._evidence_metric.set_content("0", "No evidence imported yet")

    def set_analysis(
        self,
        analysis: AnalysisSnapshot | None,
        records: tuple[EvidenceRecord, ...],
        rejections: tuple[ImportRejection, ...],
    ) -> None:
        """Refresh findings and limitations from the shared analysis projection."""

        if analysis is None:
            self._sighting_metric.set_content("0", "Import evidence to run the recipe")
            self._coverage_metric.set_content("Pending", "No completed recipe run")
            return
        self._sighting_metric.set_content(
            str(len(analysis.sightings)),
            f"Exact {analysis.recipe_id.upper()} matches",
        )
        limited = analysis.warning_count
        matched = sum(cell.state is CoverageState.MATCH_FOUND for cell in analysis.coverage)
        self._coverage_metric.set_content(
            f"{matched} matched",
            f"{limited} limitation(s) require review",
        )
        timestamps = [record.occurred_at for record in records if record.occurred_at is not None]
        hosts = {record.host_name for record in records if record.host_name}
        users = {record.user_name for record in records if record.user_name}
        if timestamps:
            first = min(timestamps).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            last = max(timestamps).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            bounds = f"Timeline {first} → {last}"
        else:
            bounds = "All imported records are undated"
        self._timeline_summary.setText(
            f"{bounds} · {len(hosts)} host(s) · {len(users)} user(s) · "
            f"{len(rejections)} rejected line(s)."
        )
        if analysis.sightings:
            self._next_title.setText("Review direct sightings beside coverage limitations")
            self._next_copy.setText(
                "Use Evidence for match explanations and raw provenance, Coverage for the "
                "meaning of missing or partial telemetry, then export a verified capsule."
            )
        else:
            self._next_title.setText("No exact lead match—review coverage before concluding")
            self._next_copy.setText(
                "The implemented recipe found no direct sighting. Coverage shows whether each "
                "expected telemetry step was actually searched, partial, missing, or failed."
            )


def _muted_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionEyebrow")
    return label
