"""SQLite evidence import-run, ledger, and rejection persistence."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ioc_evidence_packager.domain.evidence import (
    EvidenceCounts,
    EvidenceId,
    EvidenceObservable,
    EvidenceRecord,
    ImportRejection,
    ImportRun,
    ImportRunId,
    ImportStatus,
    RejectionId,
)
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import SourcePreviewId
from ioc_evidence_packager.storage.sqlite.connection import SQLiteDatabase

INSERT_RUN = """
    INSERT INTO import_run (run_id, case_id, status, started_at)
    VALUES (?, ?, ?, ?)
"""

INSERT_EVIDENCE = """
    INSERT INTO evidence_record (
        evidence_id, case_id, source_preview_id, import_run_id, line_number,
        event_id, occurred_at, category, action, host_name, user_name,
        observables_json, declared_source_id, declared_position_kind,
        declared_position_value, warnings_json, raw_json, imported_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(case_id, source_preview_id, line_number) DO NOTHING
"""

INSERT_REJECTION = """
    INSERT INTO import_rejection (
        rejection_id, case_id, source_preview_id, import_run_id, line_number,
        code, message, raw_excerpt, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(case_id, source_preview_id, line_number, code) DO NOTHING
"""

LIST_EVIDENCE = """
    SELECT
        evidence_record.*, source_preview.display_name, source_preview.path,
        source_preview.sha256
    FROM evidence_record
    JOIN source_preview
        ON source_preview.preview_id = evidence_record.source_preview_id
    WHERE evidence_record.case_id = ?
    ORDER BY
        evidence_record.occurred_at IS NULL,
        evidence_record.occurred_at,
        source_preview.display_name,
        evidence_record.line_number
    LIMIT ?
"""

LIST_REJECTIONS = """
    SELECT import_rejection.*, source_preview.display_name
    FROM import_rejection
    JOIN source_preview
        ON source_preview.preview_id = import_rejection.source_preview_id
    WHERE import_rejection.case_id = ?
    ORDER BY source_preview.display_name, import_rejection.line_number,
        import_rejection.code
    LIMIT ?
"""


class SQLiteEvidenceRepository:
    """Transactional SQLite implementation of the evidence repository port."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def begin_import(self, run: ImportRun) -> None:
        with self._database.connection() as connection:
            connection.execute(
                INSERT_RUN,
                (str(run.run_id), str(run.case_id), run.status.value, run.started_at.isoformat()),
            )
            connection.commit()

    def append_batch(
        self,
        run_id: ImportRunId,
        records: tuple[EvidenceRecord, ...],
        rejections: tuple[ImportRejection, ...],
    ) -> None:
        with self._database.connection() as connection:
            connection.executemany(
                INSERT_EVIDENCE,
                (_evidence_parameters(run_id, record) for record in records),
            )
            connection.executemany(
                INSERT_REJECTION,
                (_rejection_parameters(run_id, rejection) for rejection in rejections),
            )
            connection.commit()

    def finish_import(
        self,
        run_id: ImportRunId,
        status: ImportStatus,
        finished_at: datetime,
        processed_sources: int,
        accepted_records: int,
        rejected_records: int,
        error_message: str | None,
    ) -> None:
        with self._database.connection() as connection:
            connection.execute(
                """
                    UPDATE import_run
                    SET status = ?, finished_at = ?, processed_sources = ?,
                        accepted_records = ?, rejected_records = ?, error_message = ?
                    WHERE run_id = ?
                """,
                (
                    status.value,
                    finished_at.isoformat(),
                    processed_sources,
                    accepted_records,
                    rejected_records,
                    error_message,
                    str(run_id),
                ),
            )
            connection.commit()

    def list_evidence(self, case_id: CaseId, limit: int) -> list[EvidenceRecord]:
        with self._database.connection() as connection:
            rows = connection.execute(LIST_EVIDENCE, (str(case_id), limit)).fetchall()
        return [_evidence_from_row(row) for row in rows]

    def list_rejections(self, case_id: CaseId, limit: int) -> list[ImportRejection]:
        with self._database.connection() as connection:
            rows = connection.execute(LIST_REJECTIONS, (str(case_id), limit)).fetchall()
        return [_rejection_from_row(row) for row in rows]

    def counts(self, case_id: CaseId) -> EvidenceCounts:
        with self._database.connection() as connection:
            evidence = connection.execute(
                "SELECT count(*) FROM evidence_record WHERE case_id = ?", (str(case_id),)
            ).fetchone()[0]
            rejections = connection.execute(
                "SELECT count(*) FROM import_rejection WHERE case_id = ?", (str(case_id),)
            ).fetchone()[0]
        return EvidenceCounts(evidence=int(evidence), rejections=int(rejections))


def _evidence_parameters(
    run_id: ImportRunId,
    record: EvidenceRecord,
) -> tuple[str | int | None, ...]:
    observables = [
        {
            "kind": observable.kind,
            "field_path": observable.field_path,
            "original": observable.original,
            "canonical": observable.canonical,
        }
        for observable in record.observables
    ]
    return (
        str(record.evidence_id),
        str(record.case_id),
        str(record.source_preview_id),
        str(run_id),
        record.line_number,
        record.event_id,
        record.occurred_at.isoformat() if record.occurred_at else None,
        record.category,
        record.action,
        record.host_name,
        record.user_name,
        json.dumps(observables, separators=(",", ":")),
        record.declared_source_id,
        record.declared_position_kind,
        record.declared_position_value,
        json.dumps(record.warnings, separators=(",", ":")),
        record.raw_json,
        record.imported_at.isoformat(),
    )


def _rejection_parameters(
    run_id: ImportRunId,
    rejection: ImportRejection,
) -> tuple[str | int, ...]:
    return (
        str(rejection.rejection_id),
        str(rejection.case_id),
        str(rejection.source_preview_id),
        str(run_id),
        rejection.line_number,
        rejection.code,
        rejection.message,
        rejection.raw_excerpt,
        rejection.created_at.isoformat(),
    )


def _evidence_from_row(row: sqlite3.Row) -> EvidenceRecord:
    values: dict[str, Any] = dict(row)
    observable_values = json.loads(values["observables_json"])
    observables = tuple(
        EvidenceObservable(
            kind=str(value["kind"]),
            field_path=str(value["field_path"]),
            original=str(value["original"]),
            canonical=str(value["canonical"]),
        )
        for value in observable_values
        if isinstance(value, dict)
    )
    occurred_at = values["occurred_at"]
    return EvidenceRecord(
        evidence_id=EvidenceId(values["evidence_id"]),
        case_id=CaseId(values["case_id"]),
        source_preview_id=SourcePreviewId(values["source_preview_id"]),
        source_name=values["display_name"],
        source_path=Path(values["path"]),
        source_sha256=values["sha256"],
        line_number=int(values["line_number"]),
        event_id=values["event_id"],
        occurred_at=datetime.fromisoformat(occurred_at) if occurred_at else None,
        category=values["category"],
        action=values["action"],
        host_name=values["host_name"],
        user_name=values["user_name"],
        observables=observables,
        declared_source_id=values["declared_source_id"],
        declared_position_kind=values["declared_position_kind"],
        declared_position_value=values["declared_position_value"],
        warnings=_string_tuple(values["warnings_json"]),
        raw_json=values["raw_json"],
        imported_at=datetime.fromisoformat(values["imported_at"]),
    )


def _rejection_from_row(row: sqlite3.Row) -> ImportRejection:
    return ImportRejection(
        rejection_id=RejectionId(row["rejection_id"]),
        case_id=CaseId(row["case_id"]),
        source_preview_id=SourcePreviewId(row["source_preview_id"]),
        source_name=row["display_name"],
        line_number=int(row["line_number"]),
        code=row["code"],
        message=row["message"],
        raw_excerpt=row["raw_excerpt"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _string_tuple(serialized: str) -> tuple[str, ...]:
    value = json.loads(serialized)
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)
