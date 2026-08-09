"""Durable analyst state and attributed intelligence assertions."""

from datetime import datetime

from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.workspace import (
    AssertionId,
    IntelligenceAssertion,
    IntelligenceClaim,
    RecommendationId,
    RecommendationStatus,
)
from ioc_evidence_packager.storage.sqlite.connection import SQLiteDatabase


class SQLiteWorkspaceRepository:
    """Stores analyst decisions separately from deterministic generated output."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def recommendation_states(
        self, case_id: CaseId
    ) -> dict[RecommendationId, tuple[RecommendationStatus, str | None, datetime]]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """SELECT recommendation_id, status, analyst_note, updated_at
                   FROM recommendation_state WHERE case_id = ?""",
                (str(case_id),),
            ).fetchall()
        return {
            RecommendationId(row["recommendation_id"]): (
                RecommendationStatus(row["status"]),
                row["analyst_note"],
                datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        }

    def set_recommendation_state(
        self,
        case_id: CaseId,
        recommendation_id: RecommendationId,
        status: RecommendationStatus,
        note: str | None,
        updated_at: datetime,
    ) -> None:
        with self._database.connection() as connection:
            connection.execute(
                """INSERT INTO recommendation_state(
                       case_id, recommendation_id, status, analyst_note, updated_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(case_id, recommendation_id) DO UPDATE SET
                       status=excluded.status,
                       analyst_note=excluded.analyst_note,
                       updated_at=excluded.updated_at""",
                (str(case_id), str(recommendation_id), status.value, note, updated_at.isoformat()),
            )
            connection.commit()

    def add_assertion(self, assertion: IntelligenceAssertion) -> None:
        with self._database.connection() as connection:
            connection.execute(
                """INSERT INTO intelligence_assertion(
                       assertion_id, case_id, provider, provider_version,
                       observable_type, observable_value, claim, confidence_label,
                       summary, retrieved_at, data_timestamp, expires_at,
                       source_reference, raw_response_sha256, origin, archived
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(assertion_id) DO NOTHING""",
                (
                    str(assertion.assertion_id),
                    str(assertion.case_id),
                    assertion.provider,
                    assertion.provider_version,
                    assertion.observable_type,
                    assertion.observable_value,
                    assertion.claim.value,
                    assertion.confidence_label,
                    assertion.summary,
                    assertion.retrieved_at.isoformat(),
                    assertion.data_timestamp.isoformat() if assertion.data_timestamp else None,
                    assertion.expires_at.isoformat() if assertion.expires_at else None,
                    assertion.source_reference,
                    assertion.raw_response_sha256,
                    assertion.origin,
                    int(assertion.archived),
                ),
            )
            connection.commit()

    def list_assertions(
        self, case_id: CaseId, *, include_archived: bool = False
    ) -> tuple[IntelligenceAssertion, ...]:
        where = "case_id = ?" if include_archived else "case_id = ? AND archived = 0"
        with self._database.connection() as connection:
            rows = connection.execute(
                f"""SELECT * FROM intelligence_assertion WHERE {where}
                    ORDER BY retrieved_at DESC, assertion_id""",  # noqa: S608 - static where
                (str(case_id),),
            ).fetchall()
        return tuple(
            IntelligenceAssertion(
                assertion_id=AssertionId(row["assertion_id"]),
                case_id=CaseId(row["case_id"]),
                provider=row["provider"],
                provider_version=row["provider_version"],
                observable_type=row["observable_type"],
                observable_value=row["observable_value"],
                claim=IntelligenceClaim(row["claim"]),
                confidence_label=row["confidence_label"],
                summary=row["summary"],
                retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
                data_timestamp=(
                    datetime.fromisoformat(row["data_timestamp"]) if row["data_timestamp"] else None
                ),
                expires_at=(
                    datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
                ),
                source_reference=row["source_reference"],
                raw_response_sha256=row["raw_response_sha256"],
                origin=row["origin"],
                archived=bool(row["archived"]),
            )
            for row in rows
        )

    def archive_assertion(self, case_id: CaseId, assertion_id: AssertionId) -> None:
        with self._database.connection() as connection:
            connection.execute(
                """UPDATE intelligence_assertion SET archived = 1
                   WHERE case_id = ? AND assertion_id = ?""",
                (str(case_id), str(assertion_id)),
            )
            connection.commit()
