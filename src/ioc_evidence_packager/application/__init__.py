"""Use cases shared by the desktop UI and future automation interfaces."""

from ioc_evidence_packager.application.analysis_service import AnalysisService
from ioc_evidence_packager.application.evidence_service import EvidenceService
from ioc_evidence_packager.application.report_service import ReportService
from ioc_evidence_packager.application.services import (
    CaseService,
    InvestigationSetup,
    NewCaseRequest,
    NewInvestigationRequest,
)

__all__ = [
    "AnalysisService",
    "CaseService",
    "EvidenceService",
    "InvestigationSetup",
    "NewCaseRequest",
    "NewInvestigationRequest",
    "ReportService",
]
