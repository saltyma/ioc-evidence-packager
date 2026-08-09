"""Parameterized SQLite repositories for case metadata."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ioc_evidence_packager.domain.models import Case, CaseId, CaseStatus, PrivacyMode
from ioc_evidence_packager.domain.observables import Observable, ObservableId, ObservableType
from ioc_evidence_packager.domain.sources import (
    PreviewStatus,
    SourcePreview,
    SourcePreviewId,
)
from ioc_evidence_packager.storage.sqlite.connection import SQLiteDatabase

INSERT_CASE = """
    INSERT INTO case_record (
        case_id, title, external_reference, summary, status, privacy_mode,
        display_timezone, created_at, updated_at, last_opened_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_CASE = """
    SELECT
        case_id, title, external_reference, summary, status, privacy_mode,
        display_timezone, created_at, updated_at, last_opened_at
    FROM case_record
    WHERE case_id = ?
"""

LIST_RECENT_CASES = """
    SELECT
        case_id, title, external_reference, summary, status, privacy_mode,
        display_timezone, created_at, updated_at, last_opened_at
    FROM case_record
    WHERE status != ?
    ORDER BY last_opened_at DESC, case_id ASC
    LIMIT ?
"""

INSERT_OBSERVABLE = """
    INSERT INTO case_observable (
        observable_id, case_id, role, observable_type,
        original_value, canonical_value, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""

SELECT_LEAD = """
    SELECT observable_id, observable_type, original_value, canonical_value, role
    FROM case_observable
    WHERE case_id = ? AND role = 'lead'
"""

INSERT_SOURCE_PREVIEW = """
    INSERT INTO source_preview (
        preview_id, case_id, path, display_name, byte_size, sha256, status,
        adapter_id, adapter_version, format_name, sample_records,
        fields_json, capabilities_json, warnings_json,
        earliest_time, latest_time, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

LIST_SOURCE_PREVIEWS = """
    SELECT
        preview_id, path, display_name, byte_size, sha256, status,
        adapter_id, adapter_version, format_name, sample_records,
        fields_json, capabilities_json, warnings_json, earliest_time, latest_time
    FROM source_preview
    WHERE case_id = ?
    ORDER BY display_name ASC, preview_id ASC
"""


class SQLiteCaseRepository:
    """Durable implementation of the case repository port."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def add(self, case: Case) -> None:
        with self._database.connection() as connection:
            _insert_case(connection, case)
            connection.commit()

    def add_investigation(
        self,
        case: Case,
        lead: Observable,
        source_previews: tuple[SourcePreview, ...],
    ) -> None:
        with self._database.connection() as connection:
            _insert_case(connection, case)
            connection.execute(
                INSERT_OBSERVABLE,
                (
                    str(lead.observable_id),
                    str(case.case_id),
                    lead.role,
                    lead.observable_type.value,
                    lead.original_value,
                    lead.canonical_value,
                    case.created_at.isoformat(),
                ),
            )
            for preview in source_previews:
                connection.execute(
                    INSERT_SOURCE_PREVIEW,
                    _source_preview_parameters(case, preview),
                )
            connection.commit()

    def get(self, case_id: CaseId) -> Case | None:
        with self._database.connection() as connection:
            row = connection.execute(
                SELECT_CASE,
                (str(case_id),),
            ).fetchone()
        return _case_from_row(row) if row is not None else None

    def list_recent(self, limit: int) -> list[Case]:
        with self._database.connection() as connection:
            rows = connection.execute(
                LIST_RECENT_CASES,
                (CaseStatus.ARCHIVED.value, limit),
            ).fetchall()
        return [_case_from_row(row) for row in rows]

    def update_last_opened(self, case_id: CaseId, opened_at: datetime) -> Case | None:
        with self._database.connection() as connection:
            cursor = connection.execute(
                """
                    UPDATE case_record
                    SET last_opened_at = ?, updated_at = ?
                    WHERE case_id = ?
                """,
                (opened_at.isoformat(), opened_at.isoformat(), str(case_id)),
            )
            if cursor.rowcount == 0:
                connection.rollback()
                return None
            row = connection.execute(
                SELECT_CASE,
                (str(case_id),),
            ).fetchone()
            connection.commit()
        return _case_from_row(row)

    def update_preferences(
        self,
        case_id: CaseId,
        *,
        display_timezone: str,
        privacy_mode: PrivacyMode,
        updated_at: datetime,
    ) -> Case | None:
        with self._database.connection() as connection:
            cursor = connection.execute(
                """UPDATE case_record
                   SET display_timezone = ?, privacy_mode = ?, updated_at = ?
                   WHERE case_id = ?""",
                (display_timezone, privacy_mode.value, updated_at.isoformat(), str(case_id)),
            )
            if cursor.rowcount == 0:
                connection.rollback()
                return None
            row = connection.execute(SELECT_CASE, (str(case_id),)).fetchone()
            connection.commit()
        return _case_from_row(row)

    def get_lead(self, case_id: CaseId) -> Observable | None:
        with self._database.connection() as connection:
            row = connection.execute(SELECT_LEAD, (str(case_id),)).fetchone()
        if row is None:
            return None
        return Observable(
            observable_id=ObservableId(row["observable_id"]),
            observable_type=ObservableType(row["observable_type"]),
            original_value=row["original_value"],
            canonical_value=row["canonical_value"],
            role=row["role"],
        )

    def list_source_previews(self, case_id: CaseId) -> list[SourcePreview]:
        with self._database.connection() as connection:
            rows = connection.execute(LIST_SOURCE_PREVIEWS, (str(case_id),)).fetchall()
        return [_source_preview_from_row(row) for row in rows]


def _insert_case(connection: sqlite3.Connection, case: Case) -> None:
    connection.execute(INSERT_CASE, _case_parameters(case))


def _case_parameters(case: Case) -> tuple[str | None, ...]:
    return (
        str(case.case_id),
        case.title,
        case.external_reference,
        case.summary,
        case.status.value,
        case.privacy_mode.value,
        case.display_timezone,
        case.created_at.isoformat(),
        case.updated_at.isoformat(),
        case.last_opened_at.isoformat(),
    )


def _source_preview_parameters(
    case: Case,
    preview: SourcePreview,
) -> tuple[str | int | None, ...]:
    return (
        str(preview.preview_id),
        str(case.case_id),
        str(preview.path),
        preview.display_name,
        preview.byte_size,
        preview.sha256,
        preview.status.value,
        preview.adapter_id,
        preview.adapter_version,
        preview.format_name,
        preview.sample_records,
        json.dumps(preview.fields, separators=(",", ":")),
        json.dumps(preview.capabilities, separators=(",", ":")),
        json.dumps(preview.warnings, separators=(",", ":")),
        preview.earliest_time.isoformat() if preview.earliest_time else None,
        preview.latest_time.isoformat() if preview.latest_time else None,
        case.created_at.isoformat(),
    )


def _case_from_row(row: sqlite3.Row) -> Case:
    values: dict[str, Any] = dict(row)
    return Case(
        case_id=CaseId(values["case_id"]),
        title=values["title"],
        external_reference=values["external_reference"],
        summary=values["summary"],
        status=CaseStatus(values["status"]),
        privacy_mode=PrivacyMode(values["privacy_mode"]),
        display_timezone=values["display_timezone"],
        created_at=datetime.fromisoformat(values["created_at"]),
        updated_at=datetime.fromisoformat(values["updated_at"]),
        last_opened_at=datetime.fromisoformat(values["last_opened_at"]),
    )


def _source_preview_from_row(row: sqlite3.Row) -> SourcePreview:
    earliest = row["earliest_time"]
    latest = row["latest_time"]
    return SourcePreview(
        preview_id=SourcePreviewId(row["preview_id"]),
        path=Path(row["path"]),
        display_name=row["display_name"],
        byte_size=int(row["byte_size"]),
        sha256=row["sha256"],
        status=PreviewStatus(row["status"]),
        adapter_id=row["adapter_id"],
        adapter_version=row["adapter_version"],
        format_name=row["format_name"],
        sample_records=int(row["sample_records"]),
        fields=_string_tuple(row["fields_json"]),
        capabilities=_string_tuple(row["capabilities_json"]),
        warnings=_string_tuple(row["warnings_json"]),
        earliest_time=datetime.fromisoformat(earliest) if earliest else None,
        latest_time=datetime.fromisoformat(latest) if latest else None,
    )


def _string_tuple(serialized: str) -> tuple[str, ...]:
    value = json.loads(serialized)
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)
