"""Bounded generic JSON-array adapter with conservative built-in field aliases."""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.domain.observables import ObservableType
from ioc_evidence_packager.domain.sources import SourcePreview
from ioc_evidence_packager.ingestion.adapters.common import (
    MAX_SAMPLE_RECORDS,
    build_envelope,
    envelope_warnings,
    observable,
    preview_profile,
)
from ioc_evidence_packager.ingestion.base import ImportItem, ProbeResult
from ioc_evidence_packager.ingestion.canonical_import import (
    convert_canonical_record,
    record_rejection,
    source_rejection,
)

MAX_JSON_ARRAY_BYTES = 16 * 1_048_576


class GenericJsonArrayAdapter:
    """Maps common flat export fields only when their meaning is unambiguous."""

    adapter_id = "generic-json-array"
    version = "1.0.0"
    format_name = "Generic mapped JSON array"

    def probe(self, path: Path) -> ProbeResult:
        if path.stat().st_size > MAX_JSON_ARRAY_BYTES:
            return ProbeResult(recognized=False)
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return ProbeResult(recognized=False)
        if not isinstance(value, list) or not value:
            return ProbeResult(recognized=False)
        sample = value[:MAX_SAMPLE_RECORDS]
        if not all(isinstance(record, dict) for record in sample):
            return ProbeResult(recognized=False)
        typed_sample = [record for record in sample if isinstance(record, dict)]
        if not typed_sample or not all(_recognizes(record) for record in typed_sample):
            return ProbeResult(recognized=False)
        envelopes = [
            _map_record(record, index, path.name)
            for index, record in enumerate(typed_sample, start=1)
        ]
        fields, capabilities, earliest, latest = preview_profile(envelopes)
        return ProbeResult(
            recognized=True,
            format_name=self.format_name,
            sample_records=len(envelopes),
            fields=fields,
            capabilities=capabilities,
            warnings=envelope_warnings(envelopes),
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
            if preview.path.stat().st_size > MAX_JSON_ARRAY_BYTES:
                yield source_rejection(
                    case_id,
                    preview,
                    "source_too_large",
                    f"Generic JSON arrays are limited to {MAX_JSON_ARRAY_BYTES} bytes.",
                    imported_at,
                )
                return
            value = json.loads(preview.path.read_text(encoding="utf-8-sig"))
        except OSError as error:
            yield source_rejection(case_id, preview, "source_read_error", str(error), imported_at)
            return
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            yield source_rejection(
                case_id,
                preview,
                "invalid_json",
                f"JSON array could not be decoded: {error.__class__.__name__}.",
                imported_at,
            )
            return
        if not isinstance(value, list):
            yield source_rejection(
                case_id,
                preview,
                "adapter_schema_drift",
                "Source is no longer a JSON array.",
                imported_at,
            )
            return
        for index, record in enumerate(value, start=1):
            raw_text = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            if not isinstance(record, dict) or not _recognizes(record):
                yield record_rejection(
                    case_id,
                    preview,
                    index,
                    "mapping_invalid",
                    "Array record does not contain the recognized generic mapping fields.",
                    raw_text,
                    imported_at,
                )
                continue
            envelope = _map_record(record, index, preview.display_name)
            yield convert_canonical_record(
                case_id,
                preview,
                index,
                raw_text,
                envelope,
                imported_at,
            )


def _recognizes(record: dict[str, Any]) -> bool:
    has_time = _first(record, "timestamp", "time", "@timestamp") is not None
    has_semantic_field = any(
        _first(record, *aliases) is not None
        for aliases in (
            ("event_id", "id"),
            ("action", "event_action", "event"),
            ("category", "event_category", "type"),
            ("destination_ip", "dest_ip", "dst_ip"),
            ("source_ip", "src_ip"),
            ("domain", "query_name", "dns_query"),
            ("sha256", "file_hash"),
        )
    )
    return has_time and has_semantic_field


def _map_record(
    record: dict[str, Any],
    index: int,
    source_name: str,
) -> dict[str, Any]:
    observations = tuple(
        value
        for value in (
            observable(
                _first(record, "source_ip", "src_ip"),
                "network.source_ip",
                ObservableType.IPV4,
            ),
            observable(
                _first(record, "destination_ip", "dest_ip", "dst_ip"),
                "network.destination_ip",
                ObservableType.IPV4,
            ),
            observable(
                _first(record, "domain", "query_name", "dns_query"),
                "dns.question",
                ObservableType.DOMAIN,
            ),
            observable(
                _first(record, "sha256", "file_hash"),
                "file.sha256",
                ObservableType.SHA256,
            ),
        )
        if value is not None
    )
    category = str(_first(record, "category", "event_category", "type") or "event")
    action = str(_first(record, "action", "event_action", "event") or "observed")
    identity = _first(record, "event_id", "id") or index
    return build_envelope(
        adapter_id="generic-json-array",
        adapter_version="1.0.0",
        source_id=f"generic-json:{source_name}",
        position_kind="record",
        position_value=index,
        event_id=f"generic-json-{identity}",
        timestamp=_first(record, "timestamp", "time", "@timestamp"),
        category=category,
        action=action,
        host=_first(record, "host", "hostname", "computer"),
        user=_first(record, "user", "username"),
        observables=observations,
    )


def _first(record: dict[str, Any], *names: str) -> object:
    for name in names:
        if record.get(name) not in (None, ""):
            return record[name]
    return None
