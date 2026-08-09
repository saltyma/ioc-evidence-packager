"""Bounded probe and import adapter for canonical event JSONL."""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.sources import SourcePreview
from ioc_evidence_packager.ingestion.adapters.common import (
    CANONICAL_SCHEMA_ID,
    MAX_LINE_BYTES,
    MAX_SAMPLE_RECORDS,
    preview_profile,
)
from ioc_evidence_packager.ingestion.base import ImportItem, ProbeResult

SCHEMA_ID = CANONICAL_SCHEMA_ID


class CanonicalJsonlAdapter:
    """Recognizes and imports the versioned reference envelope."""

    adapter_id = "canonical-jsonl"
    version = "1.0.0"

    def probe(self, path: Path) -> ProbeResult:
        recognized_records: list[dict[str, Any]] = []
        warnings: list[str] = []

        with path.open("rb") as stream:
            line_number = 0
            while len(recognized_records) < MAX_SAMPLE_RECORDS:
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
                if not isinstance(value, dict) or value.get("schema") != SCHEMA_ID:
                    if not recognized_records:
                        return ProbeResult(recognized=False)
                    warnings.append(
                        f"Line {line_number} does not declare the expected {SCHEMA_ID} schema."
                    )
                    continue
                recognized_records.append(value)

        if not recognized_records:
            return ProbeResult(recognized=False, warnings=tuple(warnings))

        fields, capabilities, earliest, latest = preview_profile(recognized_records)
        return ProbeResult(
            recognized=True,
            format_name="Canonical event JSONL v1",
            sample_records=len(recognized_records),
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
        from ioc_evidence_packager.ingestion.canonical_import import iter_canonical_items

        yield from iter_canonical_items(case_id, preview, imported_at)
