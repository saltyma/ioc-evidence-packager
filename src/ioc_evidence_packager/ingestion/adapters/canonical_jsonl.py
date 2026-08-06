"""Bounded probe for the versioned canonical JSONL reference format."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ioc_evidence_packager.ingestion.base import ProbeResult

SCHEMA_ID = "canonical-event/1.0.0"
MAX_SAMPLE_RECORDS = 20
MAX_LINE_BYTES = 1_048_576


class CanonicalJsonlAdapter:
    """Recognizes canonical event envelopes without performing ingestion."""

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

        fields = sorted({field for record in recognized_records for field in _field_paths(record)})
        capabilities = sorted(
            {
                capability
                for record in recognized_records
                for capability in _record_capabilities(record)
            }
        )
        timestamps = [
            timestamp
            for record in recognized_records
            if (timestamp := _utc_timestamp(record)) is not None
        ]
        return ProbeResult(
            recognized=True,
            format_name="Canonical event JSONL v1",
            sample_records=len(recognized_records),
            fields=tuple(fields),
            capabilities=tuple(capabilities),
            warnings=tuple(warnings),
            earliest_time=min(timestamps) if timestamps else None,
            latest_time=max(timestamps) if timestamps else None,
        )


def _field_paths(value: Any, prefix: str = "", depth: int = 0) -> set[str]:
    if depth > 4:
        return set()
    if isinstance(value, dict):
        paths: set[str] = set()
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths.update(_field_paths(child, path, depth + 1))
        return paths
    if isinstance(value, list):
        paths = set()
        for child in value[:10]:
            paths.update(_field_paths(child, f"{prefix}[]", depth + 1))
        return paths
    return set()


def _record_capabilities(record: dict[str, Any]) -> set[str]:
    capabilities: set[str] = set()
    time_value = record.get("time")
    if isinstance(time_value, dict) and time_value.get("utc"):
        capabilities.add("timestamp.utc")
    observables = record.get("observables")
    if not isinstance(observables, list):
        return capabilities
    for observable in observables:
        if not isinstance(observable, dict):
            continue
        kind = observable.get("kind")
        if kind in {"ipv4", "domain", "sha256"}:
            capabilities.add(f"observable.{kind}")
    return capabilities


def _utc_timestamp(record: dict[str, Any]) -> datetime | None:
    time_value = record.get("time")
    if not isinstance(time_value, dict) or not isinstance(time_value.get("utc"), str):
        return None
    try:
        parsed = datetime.fromisoformat(time_value["utc"].replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None
