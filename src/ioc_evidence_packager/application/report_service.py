"""Case Capsule construction, publication, history, and verification use cases."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ioc_evidence_packager.application.ports import ExportRepository
from ioc_evidence_packager.application.services import InvestigationSetup
from ioc_evidence_packager.domain.analysis import AnalysisSnapshot
from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.evidence import EvidenceRecord, ImportRejection
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.workspace import (
    IntelligenceAssertion,
    Recommendation,
    RelationshipSnapshot,
)
from ioc_evidence_packager.reporting.capsule import export_capsule, verify_capsule
from ioc_evidence_packager.reporting.models import (
    CapsuleResult,
    CaseReport,
    ExportId,
    ExportProfile,
    ExportRecord,
    VerificationResult,
)


class ReportService:
    """Builds immutable report projections and records successful exports."""

    def __init__(self, repository: ExportRepository) -> None:
        self._repository = repository

    def export_case(
        self,
        setup: InvestigationSetup,
        evidence: tuple[EvidenceRecord, ...],
        rejections: tuple[ImportRejection, ...],
        analysis: AnalysisSnapshot | None,
        destination: Path,
        profile: ExportProfile,
        relationships: RelationshipSnapshot | None = None,
        recommendations: tuple[Recommendation, ...] = (),
        intelligence: tuple[IntelligenceAssertion, ...] = (),
    ) -> CapsuleResult:
        if analysis is None:
            raise ValidationError("Import evidence and run the IOC recipe before exporting.")
        report = CaseReport(
            setup.case,
            setup.lead,
            setup.source_previews,
            evidence,
            rejections,
            analysis,
            relationships or RelationshipSnapshot((), ()),
            recommendations,
            intelligence,
        )
        created_at = datetime.now(UTC)
        export_id = ExportId(f"export-{uuid4()}")
        result = export_capsule(report, destination, profile, export_id, created_at)
        self._repository.add_export(
            ExportRecord(
                export_id=result.export_id,
                case_id=result.case_id,
                profile=result.profile,
                destination=result.destination,
                created_at=result.created_at,
                manifest_sha256=result.manifest_sha256,
                artifact_count=len(result.artifacts),
            )
        )
        return result

    def verify(self, path: Path) -> VerificationResult:
        return verify_capsule(path)

    def list_exports(self, case_id: CaseId, limit: int = 50) -> list[ExportRecord]:
        return self._repository.list_exports(case_id, limit)
