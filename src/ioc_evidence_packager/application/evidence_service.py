"""Headless streaming evidence import and ledger query use cases."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from ioc_evidence_packager.application.ports import EvidenceRepository
from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.evidence import (
    EvidenceCounts,
    EvidenceRecord,
    ImportProgress,
    ImportRejection,
    ImportRun,
    ImportRunId,
    ImportStatus,
    ImportSummary,
)
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import PreviewStatus, SourcePreview
from ioc_evidence_packager.ingestion.canonical_import import source_rejection, source_sha256
from ioc_evidence_packager.ingestion.registry import AdapterRegistry

BATCH_SIZE = 250
ProgressCallback = Callable[[ImportProgress], None]
CancellationCheck = Callable[[], bool]


class EvidenceService:
    """Imports previewed supported sources and queries their durable ledger."""

    def __init__(
        self,
        repository: EvidenceRepository,
        registry: AdapterRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._registry = registry or AdapterRegistry()

    def import_sources(
        self,
        case_id: CaseId,
        previews: tuple[SourcePreview, ...],
        *,
        is_cancelled: CancellationCheck | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ImportSummary:
        eligible = tuple(
            preview
            for preview in previews
            if self._registry.adapter_for(preview.adapter_id) is not None
            and preview.status in {PreviewStatus.READY, PreviewStatus.WARNING}
        )
        if not eligible:
            raise ValidationError("No previewed source has an installed import adapter.")
        cancel = is_cancelled or (lambda: False)
        notify = on_progress or (lambda _progress: None)
        started_at = datetime.now(UTC)
        run = ImportRun(
            run_id=ImportRunId(f"run-{uuid4()}"),
            case_id=case_id,
            status=ImportStatus.RUNNING,
            started_at=started_at,
        )
        self._repository.begin_import(run)
        accepted = 0
        rejected = 0
        processed_sources = 0
        records: list[EvidenceRecord] = []
        rejections: list[ImportRejection] = []

        try:
            for preview in eligible:
                if cancel():
                    return self._finish(
                        run, ImportStatus.CANCELLED, processed_sources, accepted, rejected
                    )
                integrity_rejection = self._integrity_rejection(case_id, preview, started_at)
                if integrity_rejection is not None:
                    rejections.append(integrity_rejection)
                    rejected += 1
                else:
                    adapter = self._registry.adapter_for(preview.adapter_id)
                    if adapter is None:
                        rejections.append(
                            source_rejection(
                                case_id,
                                preview,
                                "adapter_unavailable",
                                "The adapter used during preview is no longer installed.",
                                started_at,
                            )
                        )
                        rejected += 1
                        continue
                    for item in adapter.iter_items(case_id, preview, started_at):
                        if cancel():
                            self._flush(run.run_id, records, rejections)
                            return self._finish(
                                run,
                                ImportStatus.CANCELLED,
                                processed_sources,
                                accepted,
                                rejected,
                            )
                        if isinstance(item, EvidenceRecord):
                            records.append(item)
                            accepted += 1
                        else:
                            rejections.append(item)
                            rejected += 1
                        if len(records) + len(rejections) >= BATCH_SIZE:
                            self._flush(run.run_id, records, rejections)
                            notify(
                                ImportProgress(
                                    current_source=preview.display_name,
                                    processed_sources=processed_sources,
                                    total_sources=len(eligible),
                                    accepted_records=accepted,
                                    rejected_records=rejected,
                                )
                            )
                self._flush(run.run_id, records, rejections)
                processed_sources += 1
                notify(
                    ImportProgress(
                        current_source=preview.display_name,
                        processed_sources=processed_sources,
                        total_sources=len(eligible),
                        accepted_records=accepted,
                        rejected_records=rejected,
                    )
                )
        except Exception as error:
            self._flush(run.run_id, records, rejections)
            self._repository.finish_import(
                run.run_id,
                ImportStatus.FAILED,
                datetime.now(UTC),
                processed_sources,
                accepted,
                rejected,
                str(error),
            )
            raise
        return self._finish(run, ImportStatus.COMPLETED, processed_sources, accepted, rejected)

    def list_evidence(self, case_id: CaseId, limit: int = 5_000) -> list[EvidenceRecord]:
        _validate_query_limit(limit)
        return self._repository.list_evidence(case_id, limit)

    def list_rejections(self, case_id: CaseId, limit: int = 5_000) -> list[ImportRejection]:
        _validate_query_limit(limit)
        return self._repository.list_rejections(case_id, limit)

    def counts(self, case_id: CaseId) -> EvidenceCounts:
        return self._repository.counts(case_id)

    def _integrity_rejection(
        self,
        case_id: CaseId,
        preview: SourcePreview,
        created_at: datetime,
    ) -> ImportRejection | None:
        if preview.sha256 is None:
            return source_rejection(
                case_id,
                preview,
                "source_digest_missing",
                "Source preview has no SHA-256 digest.",
                created_at,
            )
        try:
            actual = source_sha256(preview.path)
        except OSError as error:
            return source_rejection(case_id, preview, "source_read_error", str(error), created_at)
        if actual != preview.sha256:
            return source_rejection(
                case_id,
                preview,
                "source_hash_mismatch",
                "Source changed after preview; reselect it before importing.",
                created_at,
            )
        return None

    def _flush(
        self,
        run_id: ImportRunId,
        records: list[EvidenceRecord],
        rejections: list[ImportRejection],
    ) -> None:
        if not records and not rejections:
            return
        self._repository.append_batch(run_id, tuple(records), tuple(rejections))
        records.clear()
        rejections.clear()

    def _finish(
        self,
        run: ImportRun,
        status: ImportStatus,
        processed_sources: int,
        accepted: int,
        rejected: int,
    ) -> ImportSummary:
        self._repository.finish_import(
            run.run_id,
            status,
            datetime.now(UTC),
            processed_sources,
            accepted,
            rejected,
            None,
        )
        counts = self._repository.counts(run.case_id)
        return ImportSummary(
            run_id=run.run_id,
            status=status,
            processed_sources=processed_sources,
            accepted_records=accepted,
            rejected_records=rejected,
            stored_evidence_records=counts.evidence,
            stored_rejections=counts.rejections,
        )


def _validate_query_limit(limit: int) -> None:
    if not 1 <= limit <= 50_000:
        raise ValidationError("Evidence query limit must be between 1 and 50000.")
