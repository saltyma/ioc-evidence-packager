"""Case lifecycle and analyst review without changing source evidence."""

from datetime import UTC, datetime

from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.review import EvidenceReview
from ioc_evidence_packager.storage.sqlite.connection import SQLiteDatabase


class ReviewService:
    """Transactional local review metadata, separate from immutable evidence."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def rename(self, case_id: CaseId, title: str) -> None:
        title = " ".join(title.split())
        if not title or len(title) > 120:
            raise ValidationError("Case title must contain 1 to 120 characters.")
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE case_record SET title=?, updated_at=? WHERE case_id=?",
                (title, datetime.now(UTC).isoformat(), str(case_id)),
            )
            connection.commit()

    def archive(self, case_id: CaseId, archived: bool) -> None:
        with self.database.connection() as connection:
            connection.execute(
                "UPDATE case_record SET status=?, updated_at=? WHERE case_id=?",
                ("archived" if archived else "draft", datetime.now(UTC).isoformat(), str(case_id)),
            )
            connection.commit()

    def archived_cases(self) -> list[tuple[str, str]]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT case_id,title FROM case_record WHERE status='archived' ORDER BY title"
            ).fetchall()
        return [(str(row[0]), str(row[1])) for row in rows]

    def reviews(self, case_id: CaseId) -> dict[str, EvidenceReview]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT evidence_id,bookmarked,note,included FROM evidence_review WHERE case_id=?",
                (str(case_id),),
            ).fetchall()
        return {
            str(row[0]): EvidenceReview(bool(row[1]), str(row[2]), bool(row[3])) for row in rows
        }

    def save(self, case_id: CaseId, evidence_id: str, review: EvidenceReview) -> None:
        if len(review.note) > 8000:
            raise ValidationError("Evidence note must be 8000 characters or fewer.")
        with self.database.connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM evidence_record WHERE case_id=? AND evidence_id=?",
                (str(case_id), evidence_id),
            ).fetchone()
            if exists is None:
                raise ValidationError("Evidence does not belong to this case.")
            connection.execute(
                """INSERT INTO evidence_review VALUES (?,?,?,?,?,?)
                ON CONFLICT(case_id,evidence_id) DO UPDATE SET
                bookmarked=excluded.bookmarked,note=excluded.note,
                included=excluded.included,updated_at=excluded.updated_at""",
                (
                    str(case_id),
                    evidence_id,
                    int(review.bookmarked),
                    review.note,
                    int(review.included),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.commit()
