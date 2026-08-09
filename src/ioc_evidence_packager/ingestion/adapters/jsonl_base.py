"""Reusable bounded JSONL adapter mechanics with structured diagnostics."""

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import SourcePreview
from ioc_evidence_packager.ingestion.adapters.common import (
    MAX_LINE_BYTES,
    MAX_SAMPLE_RECORDS,
    envelope_warnings,
    preview_profile,
)
from ioc_evidence_packager.ingestion.base import ImportItem, ProbeResult
from ioc_evidence_packager.ingestion.canonical_import import (
    convert_canonical_record,
    record_rejection,
)


class MappingError(ValueError):
    """Safe adapter mapping error containing no raw record data."""


class JsonlRecordAdapter(ABC):
    """Base for explicitly recognized, line-oriented JSON exports."""

    adapter_id: str
    version: str
    format_name: str

    @abstractmethod
    def matches(self, record: dict[str, Any]) -> bool:
        """Return whether this adapter owns the record shape."""

    @abstractmethod
    def map_record(
        self,
        record: dict[str, Any],
        line_number: int,
        source_name: str,
    ) -> dict[str, Any]:
        """Map an owned source record to a canonical envelope."""

    def probe(self, path: Path) -> ProbeResult:
        envelopes: list[dict[str, Any]] = []
        warnings: list[str] = []
        matched_shape = False
        with path.open("rb") as stream:
            line_number = 0
            while len(envelopes) < MAX_SAMPLE_RECORDS:
                raw_line = stream.readline(MAX_LINE_BYTES + 1)
                if not raw_line:
                    break
                line_number += 1
                if len(raw_line) > MAX_LINE_BYTES:
                    warnings.append(
                        f"Line {line_number} exceeds the {MAX_LINE_BYTES}-byte preview limit."
                    )
                    break
                if not raw_line.strip():
                    continue
                try:
                    value = json.loads(raw_line.decode("utf-8-sig"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    warnings.append(f"Line {line_number} is not valid UTF-8 JSON.")
                    continue
                if not isinstance(value, dict) or not self.matches(value):
                    if not matched_shape:
                        return ProbeResult(recognized=False)
                    warnings.append(f"Line {line_number} does not match the detected schema.")
                    continue
                matched_shape = True
                try:
                    envelopes.append(self.map_record(value, line_number, path.name))
                except MappingError as error:
                    warnings.append(f"Line {line_number} mapping failed: {error}")

        if not matched_shape:
            return ProbeResult(recognized=False)
        fields, capabilities, earliest, latest = preview_profile(envelopes)
        warnings.extend(value for value in envelope_warnings(envelopes) if value not in warnings)
        return ProbeResult(
            recognized=True,
            format_name=self.format_name,
            sample_records=len(envelopes),
            fields=fields,
            capabilities=capabilities,
            warnings=tuple(warnings),
            earliest_time=earliest,
            latest_time=latest,
        )

    def iter_items(
        self,
        case_id: CaseId,
        preview: SourcePreview,
        imported_at: datetime,
    ) -> Iterator[ImportItem]:
        try:
            stream = preview.path.open("rb")
        except OSError as error:
            yield record_rejection(
                case_id, preview, 0, "source_read_error", str(error), "", imported_at
            )
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
                    yield record_rejection(
                        case_id,
                        preview,
                        line_number,
                        "line_too_large",
                        f"Line exceeds the {MAX_LINE_BYTES}-byte import limit.",
                        repr(raw_line[:120]),
                        imported_at,
                    )
                    continue
                try:
                    raw_text = raw_line.decode("utf-8-sig").rstrip("\r\n")
                except UnicodeDecodeError:
                    yield record_rejection(
                        case_id,
                        preview,
                        line_number,
                        "invalid_utf8",
                        "Line is not valid UTF-8.",
                        repr(raw_line[:120]),
                        imported_at,
                    )
                    continue
                try:
                    value = json.loads(raw_text)
                except json.JSONDecodeError as error:
                    yield record_rejection(
                        case_id,
                        preview,
                        line_number,
                        "invalid_json",
                        f"Invalid JSON at column {error.colno}.",
                        raw_text,
                        imported_at,
                    )
                    continue
                if not isinstance(value, dict) or not self.matches(value):
                    yield record_rejection(
                        case_id,
                        preview,
                        line_number,
                        "adapter_schema_drift",
                        f"Record no longer matches the detected {self.adapter_id} schema.",
                        raw_text,
                        imported_at,
                    )
                    continue
                try:
                    envelope = self.map_record(value, line_number, preview.display_name)
                except MappingError as error:
                    yield record_rejection(
                        case_id,
                        preview,
                        line_number,
                        "mapping_invalid",
                        str(error),
                        raw_text,
                        imported_at,
                    )
                    continue
                yield convert_canonical_record(
                    case_id,
                    preview,
                    line_number,
                    raw_text,
                    envelope,
                    imported_at,
                )
