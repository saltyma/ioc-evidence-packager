"""Explicit sidecar-profile CSV adapter for safe analyst-controlled mappings."""

import csv
import hashlib
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
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
    source_rejection,
)

MAPPING_SCHEMA = "ioc-csv-mapping/1.0.0"
MAX_MAPPING_BYTES = 65_536


@dataclass(frozen=True, slots=True)
class ObservableMapping:
    column: str
    kind: ObservableType
    field_path: str


@dataclass(frozen=True, slots=True)
class CsvMappingProfile:
    profile_id: str
    delimiter: str
    columns: dict[str, str]
    defaults: dict[str, str]
    observables: tuple[ObservableMapping, ...]
    sha256: str


class MappingProfileError(ValueError):
    """Safe sidecar validation error containing no CSV data."""


class MappedCsvAdapter:
    """Imports a CSV only when an adjacent versioned mapping profile authorizes it."""

    adapter_id = "mapped-csv"
    version = "1.0.0"
    format_name = "CSV with IOC mapping profile"

    def probe(self, path: Path) -> ProbeResult:
        sidecar = mapping_path(path)
        if not sidecar.is_file():
            return ProbeResult(recognized=False)
        try:
            profile = _load_profile(sidecar)
        except MappingProfileError as error:
            return ProbeResult(
                recognized=True,
                format_name=self.format_name,
                warnings=(str(error),),
            )
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream, delimiter=profile.delimiter)
                header_error = _header_error(reader.fieldnames, profile)
                if header_error is not None:
                    return ProbeResult(
                        recognized=True,
                        format_name=self.format_name,
                        warnings=(header_error,),
                    )
                envelopes = [
                    _map_row(row, reader.line_num, path.name, profile)
                    for row in _take(reader, MAX_SAMPLE_RECORDS)
                ]
        except (OSError, UnicodeDecodeError, csv.Error) as error:
            return ProbeResult(
                recognized=True,
                format_name=self.format_name,
                warnings=(f"CSV preview failed safely: {error.__class__.__name__}.",),
            )
        fields, capabilities, earliest, latest = preview_profile(envelopes)
        return ProbeResult(
            recognized=True,
            format_name=_profile_format(profile),
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
            profile = _load_profile(mapping_path(preview.path))
        except MappingProfileError as error:
            yield source_rejection(case_id, preview, "mapping_invalid", str(error), imported_at)
            return
        if preview.format_name != _profile_format(profile):
            yield source_rejection(
                case_id,
                preview,
                "mapping_profile_changed",
                "CSV mapping profile changed after preview; preview the source again.",
                imported_at,
            )
            return
        try:
            stream = preview.path.open("r", encoding="utf-8-sig", newline="")
        except OSError as error:
            yield source_rejection(case_id, preview, "source_read_error", str(error), imported_at)
            return
        with stream:
            try:
                reader = csv.DictReader(stream, delimiter=profile.delimiter)
                header_error = _header_error(reader.fieldnames, profile)
                if header_error is not None:
                    yield source_rejection(
                        case_id,
                        preview,
                        "adapter_schema_drift",
                        header_error,
                        imported_at,
                    )
                    return
                for row in reader:
                    line_number = reader.line_num
                    raw_text = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                    envelope = _map_row(row, line_number, preview.display_name, profile)
                    yield convert_canonical_record(
                        case_id,
                        preview,
                        line_number,
                        raw_text,
                        envelope,
                        imported_at,
                    )
            except (UnicodeDecodeError, csv.Error) as error:
                yield source_rejection(
                    case_id,
                    preview,
                    "csv_parse_failed",
                    f"CSV import failed safely: {error.__class__.__name__}.",
                    imported_at,
                )


def mapping_path(source: Path) -> Path:
    return source.with_suffix(source.suffix + ".ioc-map.json")


def _load_profile(path: Path) -> CsvMappingProfile:
    try:
        if not path.is_file():
            raise MappingProfileError(f"Mapping profile is missing: {path.name}.")
        if path.stat().st_size > MAX_MAPPING_BYTES:
            raise MappingProfileError("Mapping profile exceeds the 65536-byte limit.")
        raw_bytes = path.read_bytes()
        value = json.loads(raw_bytes.decode("utf-8-sig"))
    except MappingProfileError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MappingProfileError(
            f"Mapping profile is not valid UTF-8 JSON: {error.__class__.__name__}."
        ) from error
    if not isinstance(value, dict) or value.get("schema") != MAPPING_SCHEMA:
        raise MappingProfileError(f"Mapping profile must declare {MAPPING_SCHEMA}.")
    profile_id = value.get("profile_id")
    delimiter = value.get("delimiter", ",")
    columns = value.get("columns", {})
    defaults = value.get("defaults", {})
    mappings = value.get("observables")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise MappingProfileError("Mapping profile_id must be a non-empty string.")
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise MappingProfileError("Mapping delimiter must be exactly one character.")
    if not isinstance(columns, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in columns.items()
    ):
        raise MappingProfileError("Mapping columns must contain string-to-string entries.")
    if not isinstance(defaults, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in defaults.items()
    ):
        raise MappingProfileError("Mapping defaults must contain string-to-string entries.")
    if not isinstance(mappings, list) or not mappings:
        raise MappingProfileError("Mapping profile must declare at least one observable.")
    observables: list[ObservableMapping] = []
    for item in mappings:
        if not isinstance(item, dict):
            raise MappingProfileError("Each observable mapping must be an object.")
        column = item.get("column")
        field_path = item.get("field_path")
        kind_value = item.get("kind")
        if not isinstance(kind_value, str):
            raise MappingProfileError("Observable mapping kind is unsupported.")
        try:
            kind = ObservableType(kind_value)
        except ValueError as error:
            raise MappingProfileError("Observable mapping kind is unsupported.") from error
        if not isinstance(column, str) or not column:
            raise MappingProfileError("Observable mapping column must be non-empty.")
        if not isinstance(field_path, str) or not field_path:
            raise MappingProfileError("Observable mapping field_path must be non-empty.")
        observables.append(ObservableMapping(column, kind, field_path))
    return CsvMappingProfile(
        profile_id=profile_id,
        delimiter=delimiter,
        columns={str(key): str(item) for key, item in columns.items()},
        defaults={str(key): str(item) for key, item in defaults.items()},
        observables=tuple(observables),
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def _header_error(
    fieldnames: Sequence[str] | None,
    profile: CsvMappingProfile,
) -> str | None:
    if fieldnames is None:
        return "CSV source does not contain a header row."
    required = set(profile.columns.values()) | {mapping.column for mapping in profile.observables}
    missing = sorted(required - set(fieldnames))
    return f"CSV header is missing mapped column(s): {', '.join(missing)}." if missing else None


def _map_row(
    row: dict[str, str | None],
    line_number: int,
    source_name: str,
    profile: CsvMappingProfile,
) -> dict[str, Any]:
    observations = tuple(
        mapped
        for mapping in profile.observables
        if (mapped := observable(row.get(mapping.column), mapping.field_path, mapping.kind))
        is not None
    )
    identity = _column(row, profile, "event_id") or line_number
    category = _column(row, profile, "category")
    action = _column(row, profile, "action")
    return build_envelope(
        adapter_id="mapped-csv",
        adapter_version="1.0.0",
        source_id=f"mapped-csv:{profile.profile_id}:{source_name}",
        position_kind="line",
        position_value=line_number,
        event_id=f"mapped-csv-{identity}",
        timestamp=_column(row, profile, "timestamp"),
        category=str(category or profile.defaults.get("category", "event")),
        action=str(action or profile.defaults.get("action", "observed")),
        host=_column(row, profile, "host"),
        user=_column(row, profile, "user"),
        observables=observations,
    )


def _column(row: dict[str, str | None], profile: CsvMappingProfile, role: str) -> object:
    name = profile.columns.get(role)
    return row.get(name) if name is not None else None


def _take(reader: csv.DictReader[str], limit: int) -> list[dict[str, str | None]]:
    values: list[dict[str, str | None]] = []
    for row in reader:
        values.append(row)
        if len(values) >= limit:
            break
    return values


def _profile_format(profile: CsvMappingProfile) -> str:
    return f"CSV with IOC mapping profile · {profile.profile_id} · mapping-sha256:{profile.sha256}"
