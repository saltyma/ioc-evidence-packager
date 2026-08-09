"""Streaming canonical JSONL conversion with bounded structured rejections."""

import hashlib
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from ioc_evidence_packager.domain.evidence import (
    EvidenceId,
    EvidenceObservable,
    EvidenceRecord,
    ImportRejection,
    RejectionId,
)
from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import SourcePreview
from ioc_evidence_packager.ingestion.adapters.common import (
    CANONICAL_SCHEMA_ID,
    MAX_LINE_BYTES,
)
from ioc_evidence_packager.ingestion.base import ImportItem

SCHEMA_ID = CANONICAL_SCHEMA_ID
REQUIRED_TOP_LEVEL = ("event_id", "source", "time", "event", "observables", "adapter")


def source_sha256(path: Path) -> str:
    """Hash one selected source immediately before import."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_canonical_items(
    case_id: CaseId,
    preview: SourcePreview,
    imported_at: datetime,
) -> Iterator[ImportItem]:
    """Yield accepted records or explicit rejections without loading the file."""

    try:
        stream = preview.path.open("rb")
    except OSError as error:
        yield _rejection(case_id, preview, 0, "source_read_error", str(error), "", imported_at)
        return

    with stream:
        line_number = 0
        while True:
            raw_line = stream.readline(MAX_LINE_BYTES + 1)
            if not raw_line:
                return
            line_number += 1
            if not raw_line.strip():
                continue
            if len(raw_line) > MAX_LINE_BYTES:
                yield _rejection(
                    case_id,
                    preview,
                    line_number,
                    "line_too_large",
                    f"Line exceeds the {MAX_LINE_BYTES}-byte import limit.",
                    _bytes_excerpt(raw_line),
                    imported_at,
                )
                continue
            try:
                text = raw_line.decode("utf-8-sig").rstrip("\r\n")
            except UnicodeDecodeError:
                yield _rejection(
                    case_id,
                    preview,
                    line_number,
                    "invalid_utf8",
                    "Line is not valid UTF-8.",
                    _bytes_excerpt(raw_line),
                    imported_at,
                )
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as error:
                yield _rejection(
                    case_id,
                    preview,
                    line_number,
                    "invalid_json",
                    f"Invalid JSON at column {error.colno}.",
                    _text_excerpt(text),
                    imported_at,
                )
                continue
            yield convert_canonical_record(case_id, preview, line_number, text, value, imported_at)


def convert_canonical_record(
    case_id: CaseId,
    preview: SourcePreview,
    line_number: int,
    raw_json: str,
    value: Any,
    imported_at: datetime,
) -> ImportItem:
    if not isinstance(value, dict):
        return _rejection(
            case_id,
            preview,
            line_number,
            "invalid_shape",
            "Canonical event must be a JSON object.",
            _text_excerpt(raw_json),
            imported_at,
        )
    if value.get("schema") != SCHEMA_ID:
        return _rejection(
            case_id,
            preview,
            line_number,
            "invalid_schema",
            f"Record does not declare {SCHEMA_ID}.",
            _text_excerpt(raw_json),
            imported_at,
        )
    missing = [field for field in REQUIRED_TOP_LEVEL if field not in value]
    if missing:
        return _rejection(
            case_id,
            preview,
            line_number,
            "missing_required_field",
            f"Missing required field(s): {', '.join(missing)}.",
            _text_excerpt(raw_json),
            imported_at,
        )

    event_id = value["event_id"]
    source = value["source"]
    time_value = value["time"]
    event = value["event"]
    observables = value["observables"]
    if not isinstance(event_id, str) or not event_id.strip():
        return _shape_rejection(case_id, preview, line_number, "event_id", raw_json, imported_at)
    if not isinstance(source, dict) or not isinstance(source.get("source_id"), str):
        return _shape_rejection(case_id, preview, line_number, "source", raw_json, imported_at)
    position = source.get("position")
    if not isinstance(position, dict) or not isinstance(position.get("kind"), str):
        return _shape_rejection(
            case_id, preview, line_number, "source.position", raw_json, imported_at
        )
    if "value" not in position:
        return _shape_rejection(
            case_id, preview, line_number, "source.position.value", raw_json, imported_at
        )
    if not isinstance(time_value, dict) or not isinstance(time_value.get("original"), str):
        return _shape_rejection(case_id, preview, line_number, "time", raw_json, imported_at)
    if not isinstance(event, dict) or not isinstance(event.get("category"), str):
        return _shape_rejection(
            case_id, preview, line_number, "event.category", raw_json, imported_at
        )
    if not isinstance(event.get("action"), str):
        return _shape_rejection(
            case_id, preview, line_number, "event.action", raw_json, imported_at
        )
    parsed_observables = _observables(observables)
    if parsed_observables is None:
        return _shape_rejection(case_id, preview, line_number, "observables", raw_json, imported_at)
    occurred_at = _timestamp(time_value.get("utc"))
    if time_value.get("utc") is not None and occurred_at is None:
        return _rejection(
            case_id,
            preview,
            line_number,
            "invalid_timestamp",
            "time.utc must be an ISO-8601 timestamp with a timezone.",
            _text_excerpt(raw_json),
            imported_at,
        )

    host = value.get("host")
    user = value.get("user")
    warnings = value.get("warnings", [])
    warning_values = tuple(str(item) for item in warnings) if isinstance(warnings, list) else ()
    return EvidenceRecord(
        evidence_id=EvidenceId(_stable_id("evidence", case_id, preview, line_number)),
        case_id=case_id,
        source_preview_id=preview.preview_id,
        source_name=preview.display_name,
        source_path=preview.path,
        source_sha256=preview.sha256,
        line_number=line_number,
        event_id=event_id,
        occurred_at=occurred_at,
        category=event["category"],
        action=event["action"],
        host_name=_optional_name(host),
        user_name=_optional_name(user),
        observables=parsed_observables,
        declared_source_id=source["source_id"],
        declared_position_kind=position["kind"],
        declared_position_value=str(position["value"]),
        warnings=warning_values,
        raw_json=raw_json,
        imported_at=imported_at,
    )


def _observables(value: Any) -> tuple[EvidenceObservable, ...] | None:
    if not isinstance(value, list):
        return None
    result: list[EvidenceObservable] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        kind = item.get("kind")
        field_path = item.get("field_path")
        original = item.get("original")
        canonical = item.get("canonical")
        if (
            not isinstance(kind, str)
            or not isinstance(field_path, str)
            or not isinstance(original, str)
            or not isinstance(canonical, str)
        ):
            return None
        result.append(EvidenceObservable(kind, field_path, original, canonical))
    return tuple(result)


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _optional_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    return name if isinstance(name, str) else None


def _shape_rejection(
    case_id: CaseId,
    preview: SourcePreview,
    line_number: int,
    field: str,
    raw_json: str,
    imported_at: datetime,
) -> ImportRejection:
    return _rejection(
        case_id,
        preview,
        line_number,
        "invalid_shape",
        f"Field {field} has an invalid canonical-event shape.",
        _text_excerpt(raw_json),
        imported_at,
    )


def _rejection(
    case_id: CaseId,
    preview: SourcePreview,
    line_number: int,
    code: str,
    message: str,
    excerpt: str,
    created_at: datetime,
) -> ImportRejection:
    return ImportRejection(
        rejection_id=RejectionId(_stable_id(f"rejection:{code}", case_id, preview, line_number)),
        case_id=case_id,
        source_preview_id=preview.preview_id,
        source_name=preview.display_name,
        line_number=line_number,
        code=code,
        message=message,
        raw_excerpt=excerpt,
        created_at=created_at,
    )


def source_rejection(
    case_id: CaseId,
    preview: SourcePreview,
    code: str,
    message: str,
    created_at: datetime,
) -> ImportRejection:
    """Build a deterministic source-level rejection at synthetic line zero."""

    return _rejection(case_id, preview, 0, code, message, "", created_at)


def record_rejection(
    case_id: CaseId,
    preview: SourcePreview,
    line_number: int,
    code: str,
    message: str,
    raw_value: str,
    created_at: datetime,
) -> ImportRejection:
    """Build a deterministic record-level rejection for a non-canonical adapter."""

    return _rejection(
        case_id,
        preview,
        line_number,
        code,
        message,
        _text_excerpt(raw_value),
        created_at,
    )


def _stable_id(prefix: str, case_id: CaseId, preview: SourcePreview, line_number: int) -> str:
    source_identity = preview.sha256 or str(preview.path)
    value = f"{case_id}\0{source_identity}\0{line_number}\0{prefix}"
    return f"{prefix.split(':', maxsplit=1)[0]}-{hashlib.sha256(value.encode()).hexdigest()[:32]}"


def _text_excerpt(value: str) -> str:
    return value[:240].replace("\x00", "�")


def _bytes_excerpt(value: bytes) -> str:
    return repr(value[:120])
