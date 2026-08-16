"""Coverage-aware case orientation dashboard."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
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
from ioc_evidence_packager.domain.timezones import UTC_DISPLAY, format_case_datetime


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


class CasePulseWidget(QWidget):
    """Small, readable investigation pulse without a charting dependency."""

    def __init__(self) -> None:
        super().__init__()
        self._values = (0, 0, 0, 0)
        self.setMinimumSize(230, 90)
        self.setToolTip(
            "A visual summary of imported evidence, direct sightings, searched coverage, "
            "and limitations. It is orientation, not a risk score."
        )

    def set_values(self, evidence: int, sightings: int, matched: int, limitations: int) -> None:
        self._values = (evidence, sightings, matched, limitations)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = ("#31D6C4", "#A98BFF", "#66A3FF", "#FFB84D")
        labels = ("Evidence", "Sightings", "Matched", "Limits")
        maximum = max(max(self._values), 1)
        left = 10
        top = 3
        width = max(self.width() - 112, 80)
        for index, (label, value, color) in enumerate(
            zip(labels, self._values, palette, strict=True)
        ):
            y = top + index * 22
            painter.setPen(QColor("#CFC5E7"))
            painter.drawText(left, y + 12, label)
            bar_x = left + 72
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2A2437"))
            painter.drawRoundedRect(bar_x, y + 2, width, 10, 5, 5)
            fill = int(width * (value / maximum)) if value else 0
            if fill:
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(bar_x, y + 2, max(fill, 5), 10, 5, 5)
            painter.setPen(QPen(QColor(color)))
            painter.drawText(bar_x + width + 10, y + 12, str(value))


class MissionStep(QLabel):
    """A compact investigation-stage marker used as a progress trail."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setObjectName("MissionStep")
        self.setProperty("state", "waiting")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_state(self, state: str) -> None:
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class DashboardView(QWidget):
    """Case-level findings, evidence volume, coverage limits, and time bounds."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._display_timezone = UTC_DISPLAY
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
        self._status = QLabel("DRAFT")
        self._status.setObjectName("StatusPill")
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(self._title)
        title_row.addWidget(self._status)
        title_row.addStretch(1)
        heading_text.addWidget(eyebrow)
        heading_text.addLayout(title_row)
        heading_text.addWidget(self._subtitle)
        heading.addLayout(heading_text, 1)
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

        orientation = QHBoxLayout()
        orientation.setSpacing(14)

        pulse = QFrame()
        pulse.setObjectName("Panel")
        pulse_layout = QVBoxLayout(pulse)
        pulse_layout.setContentsMargins(20, 18, 20, 18)
        pulse_heading = QLabel("INVESTIGATION PULSE")
        pulse_heading.setObjectName("SectionEyebrow")
        pulse_copy = QLabel("Evidence volume and analytical reach at a glance")
        pulse_copy.setObjectName("Muted")
        self._pulse = CasePulseWidget()
        pulse_layout.addWidget(pulse_heading)
        pulse_layout.addWidget(pulse_copy)
        pulse_layout.addWidget(self._pulse, 1)
        orientation.addWidget(pulse, 2)

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
        trail = QHBoxLayout()
        trail.setSpacing(7)
        self._mission_steps = {
            name: MissionStep(label)
            for name, label in (
                ("preview", "1  Preview"),
                ("import", "2  Import"),
                ("analyze", "3  Analyze"),
                ("explain", "4  Explain"),
                ("package", "5  Package"),
            )
        }
        for step in self._mission_steps.values():
            trail.addWidget(step, 1)
        next_layout.addWidget(next_eyebrow)
        next_layout.addWidget(self._next_title)
        next_layout.addWidget(self._next_copy)
        next_layout.addLayout(trail)
        next_layout.addWidget(self._timeline_summary)
        orientation.addWidget(next_step, 5)
        root.addLayout(orientation)

        details = QFrame()
        details.setObjectName("Panel")
        details_layout = QGridLayout(details)
        details_layout.setContentsMargins(20, 18, 20, 18)
        details_layout.setHorizontalSpacing(24)
        details_layout.setVerticalSpacing(10)
        details_layout.addWidget(_muted_label("CASE ID"), 0, 0)
        self._case_id = QLabel("Not available")
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
        self._display_timezone = case.display_timezone
        self._title.setText(case.title)
        self._subtitle.setText(
            "Opened "
            + format_case_datetime(
                case.last_opened_at, self._display_timezone, "%Y-%m-%d at %H:%M %Z"
            )
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
        self._pulse.set_values(0, 0, 0, 0)
        self._set_mission_progress("import" if source_count else "preview")
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
                "observables, preserved source records, and bounded rejection diagnostics."
            )
            self._pulse.set_values(evidence, 0, 0, rejections)
            self._set_mission_progress("analyze")
        else:
            self._evidence_metric.set_content("0", "No evidence imported yet")
            self._pulse.set_values(0, 0, 0, rejections)

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
            self._pulse.set_values(len(records), 0, 0, len(rejections))
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
        self._pulse.set_values(
            len(records), len(analysis.sightings), matched, limited + len(rejections)
        )
        self._set_mission_progress("explain")
        timestamps = [record.occurred_at for record in records if record.occurred_at is not None]
        hosts = {record.host_name for record in records if record.host_name}
        users = {record.user_name for record in records if record.user_name}
        if timestamps:
            first = format_case_datetime(min(timestamps), self._display_timezone)
            last = format_case_datetime(max(timestamps), self._display_timezone)
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
                "Verify exact-match provenance in Evidence, review Coverage limits, then "
                "package a defensible handoff."
            )
        else:
            self._next_title.setText("No exact lead match: review coverage before concluding")
            self._next_copy.setText(
                "The implemented recipe found no direct sighting. Coverage shows whether each "
                "expected telemetry step was actually searched, partial, missing, or failed."
            )

    def _set_mission_progress(self, current: str) -> None:
        order = tuple(self._mission_steps)
        current_index = order.index(current)
        for index, (name, step) in enumerate(self._mission_steps.items()):
            if index < current_index:
                state = "done"
            elif name == current:
                state = "current"
            else:
                state = "waiting"
            step.set_state(state)


def _muted_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionEyebrow")
    return label
