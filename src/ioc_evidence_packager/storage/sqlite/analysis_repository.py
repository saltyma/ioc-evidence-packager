"""SQLite persistence for matching sightings and coverage snapshots."""

import json
import sqlite3
from datetime import datetime
from typing import Any

from ioc_evidence_packager.domain.analysis import (
    AnalysisRunId,
    AnalysisSnapshot,
    CoverageCell,
    CoverageCellId,
    CoverageReason,
    CoverageState,
    MatchExplanation,
    Sighting,
    SightingId,
)
from ioc_evidence_packager.domain.evidence import EvidenceId
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.observables import ObservableId, ObservableType
from ioc_evidence_packager.domain.sources import SourcePreviewId
from ioc_evidence_packager.storage.sqlite.connection import SQLiteDatabase


class SQLiteAnalysisRepository:
    """Stores immutable analysis runs and retrieves the newest snapshot."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def save_analysis(self, snapshot: AnalysisSnapshot) -> None:
        with self._database.connection() as connection:
            connection.execute(
                """
                INSERT INTO analysis_run (
                    analysis_run_id, case_id, recipe_id, recipe_version,
                    input_fingerprint, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(snapshot.run_id),
                    str(snapshot.case_id),
                    snapshot.recipe_id,
                    snapshot.recipe_version,
                    snapshot.input_fingerprint,
                    snapshot.completed_at.isoformat(),
                ),
            )
            connection.executemany(
                """
                INSERT INTO sighting (
                    sighting_id, analysis_run_id, case_id, evidence_id, observable_id,
                    observable_type, recipe_id, recipe_version, step_id, rule_id,
                    field_path, original_value, normalized_value, explanation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (_sighting_parameters(item) for item in snapshot.sightings),
            )
            connection.executemany(
                """
                INSERT INTO coverage_cell (
                    coverage_cell_id, analysis_run_id, case_id, recipe_id, recipe_version,
                    step_id, step_label, telemetry, state, reason_json,
                    source_preview_ids_json, evidence_ids_json, match_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (_coverage_parameters(item) for item in snapshot.coverage),
            )
            connection.commit()

    def latest_analysis(self, case_id: CaseId) -> AnalysisSnapshot | None:
        with self._database.connection() as connection:
            run = connection.execute(
                """
                SELECT * FROM analysis_run
                WHERE case_id = ?
                ORDER BY completed_at DESC, analysis_run_id DESC
                LIMIT 1
                """,
                (str(case_id),),
            ).fetchone()
            if run is None:
                return None
            sightings = connection.execute(
                """
                SELECT * FROM sighting WHERE analysis_run_id = ?
                ORDER BY evidence_id, field_path, sighting_id
                """,
                (run["analysis_run_id"],),
            ).fetchall()
            coverage = connection.execute(
                """
                SELECT * FROM coverage_cell WHERE analysis_run_id = ?
                ORDER BY rowid
                """,
                (run["analysis_run_id"],),
            ).fetchall()
        return AnalysisSnapshot(
            run_id=AnalysisRunId(run["analysis_run_id"]),
            case_id=CaseId(run["case_id"]),
            recipe_id=run["recipe_id"],
            recipe_version=run["recipe_version"],
            input_fingerprint=run["input_fingerprint"],
            completed_at=datetime.fromisoformat(run["completed_at"]),
            sightings=tuple(_sighting_from_row(row) for row in sightings),
            coverage=tuple(_coverage_from_row(row) for row in coverage),
        )


def _sighting_parameters(item: Sighting) -> tuple[str, ...]:
    explanation = {
        "template_id": item.explanation.template_id,
        "text": item.explanation.text,
        "parameters": dict(item.explanation.parameters),
    }
    return (
        str(item.sighting_id),
        str(item.run_id),
        str(item.case_id),
        str(item.evidence_id),
        str(item.observable_id),
        item.observable_type.value,
        item.recipe_id,
        item.recipe_version,
        item.step_id,
        item.rule_id,
        item.field_path,
        item.original_value,
        item.normalized_value,
        json.dumps(explanation, sort_keys=True, separators=(",", ":")),
    )


def _coverage_parameters(item: CoverageCell) -> tuple[str | int, ...]:
    reason = {
        "code": item.reason.code,
        "message": item.reason.message,
        "recovery": item.reason.recovery,
    }
    return (
        str(item.cell_id),
        str(item.run_id),
        str(item.case_id),
        item.recipe_id,
        item.recipe_version,
        item.step_id,
        item.step_label,
        item.telemetry,
        item.state.value,
        json.dumps(reason, sort_keys=True, separators=(",", ":")),
        json.dumps([str(value) for value in item.source_preview_ids], separators=(",", ":")),
        json.dumps([str(value) for value in item.evidence_ids], separators=(",", ":")),
        item.match_count,
    )


def _sighting_from_row(row: sqlite3.Row) -> Sighting:
    explanation: dict[str, Any] = json.loads(row["explanation_json"])
    parameters = explanation.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}
    return Sighting(
        sighting_id=SightingId(row["sighting_id"]),
        run_id=AnalysisRunId(row["analysis_run_id"]),
        case_id=CaseId(row["case_id"]),
        evidence_id=EvidenceId(row["evidence_id"]),
        observable_id=ObservableId(row["observable_id"]),
        observable_type=ObservableType(row["observable_type"]),
        recipe_id=row["recipe_id"],
        recipe_version=row["recipe_version"],
        step_id=row["step_id"],
        rule_id=row["rule_id"],
        field_path=row["field_path"],
        original_value=row["original_value"],
        normalized_value=row["normalized_value"],
        explanation=MatchExplanation(
            template_id=str(explanation["template_id"]),
            text=str(explanation["text"]),
            parameters=tuple(sorted((str(key), str(value)) for key, value in parameters.items())),
        ),
    )


def _coverage_from_row(row: sqlite3.Row) -> CoverageCell:
    reason: dict[str, Any] = json.loads(row["reason_json"])
    return CoverageCell(
        cell_id=CoverageCellId(row["coverage_cell_id"]),
        run_id=AnalysisRunId(row["analysis_run_id"]),
        case_id=CaseId(row["case_id"]),
        recipe_id=row["recipe_id"],
        recipe_version=row["recipe_version"],
        step_id=row["step_id"],
        step_label=row["step_label"],
        telemetry=row["telemetry"],
        state=CoverageState(row["state"]),
        reason=CoverageReason(
            code=str(reason["code"]),
            message=str(reason["message"]),
            recovery=str(reason["recovery"]) if reason.get("recovery") is not None else None,
        ),
        source_preview_ids=tuple(
            SourcePreviewId(value) for value in json.loads(row["source_preview_ids_json"])
        ),
        evidence_ids=tuple(EvidenceId(value) for value in json.loads(row["evidence_ids_json"])),
        match_count=int(row["match_count"]),
    )
