"""SQLite Case Capsule export-history persistence."""

from datetime import datetime
from pathlib import Path

from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.reporting.models import ExportId, ExportProfile, ExportRecord
from ioc_evidence_packager.storage.sqlite.connection import SQLiteDatabase


class SQLiteExportRepository:
    """Stores only successfully published and verified capsule records."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def add_export(self, record: ExportRecord) -> None:
        with self._database.connection() as connection:
            connection.execute(
                """
                INSERT INTO export_record (
                    export_id, case_id, profile, destination, created_at,
                    manifest_sha256, artifact_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.export_id),
                    str(record.case_id),
                    record.profile.value,
                    str(record.destination),
                    record.created_at.isoformat(),
                    record.manifest_sha256,
                    record.artifact_count,
                ),
            )
            connection.commit()

    def list_exports(self, case_id: CaseId, limit: int) -> list[ExportRecord]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM export_record
                WHERE case_id = ?
                ORDER BY created_at DESC, export_id DESC
                LIMIT ?
                """,
                (str(case_id), limit),
            ).fetchall()
        return [
            ExportRecord(
                export_id=ExportId(row["export_id"]),
                case_id=CaseId(row["case_id"]),
                profile=ExportProfile(row["profile"]),
                destination=Path(row["destination"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                manifest_sha256=row["manifest_sha256"],
                artifact_count=int(row["artifact_count"]),
            )
            for row in rows
        ]
