"""Shared safe mapping helpers for built-in structured evidence adapters."""

from datetime import UTC, datetime
from typing import Any

from ioc_evidence_packager.domain.errors import ValidationError
from ioc_evidence_packager.domain.observables import ObservableType, parse_observable

CANONICAL_SCHEMA_ID = "canonical-event/1.0.0"
MAX_SAMPLE_RECORDS = 20
MAX_LINE_BYTES = 1_048_576


def build_envelope(
    *,
    adapter_id: str,
    adapter_version: str,
    source_id: str,
    position_kind: str,
    position_value: int | str,
    event_id: str,
    timestamp: object,
    category: str,
    action: str,
    host: object = None,
    user: object = None,
    observables: tuple[dict[str, str], ...] = (),
    warnings: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build the canonical mapping envelope consumed by the durable importer."""

    time_value, time_warnings = normalized_time(timestamp)
    envelope: dict[str, Any] = {
        "schema": CANONICAL_SCHEMA_ID,
        "event_id": event_id,
        "source": {
            "source_id": source_id,
            "position": {"kind": position_kind, "value": position_value},
        },
        "time": time_value,
        "event": {
            "category": category.strip() or "unknown",
            "action": action.strip() or "observed",
        },
        "observables": list(observables),
        "adapter": {"id": adapter_id, "version": adapter_version},
        "warnings": list(warnings + time_warnings),
    }
    if (host_name := _display_string(host)) is not None:
        envelope["host"] = {"name": host_name}
    if (user_name := _display_string(user)) is not None:
        envelope["user"] = {"name": user_name}
    return envelope


def normalized_time(value: object) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Preserve the source timestamp and normalize only timezone-aware values."""

    original = _display_string(value)
    if original is None:
        return (
            {"original": "Unavailable", "utc": None, "precision": None, "assumptions": []},
            ("Source record does not contain a mapped timestamp.",),
        )
    try:
        parsed = datetime.fromisoformat(original.replace("Z", "+00:00"))
    except ValueError:
        return (
            {"original": original, "utc": None, "precision": None, "assumptions": []},
            ("Mapped timestamp is not valid ISO-8601; event remains undated.",),
        )
    if parsed.tzinfo is None:
        return (
            {"original": original, "utc": None, "precision": None, "assumptions": []},
            ("Mapped timestamp has no timezone; event remains undated.",),
        )
    utc_value = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return (
        {"original": original, "utc": utc_value, "precision": "second", "assumptions": []},
        (),
    )


def observable(
    value: object,
    field_path: str,
    expected_kind: ObservableType | None = None,
) -> dict[str, str] | None:
    """Validate one explicitly mapped IOC value without mining free-form text."""

    original = _display_string(value)
    if original is None:
        return None
    try:
        parsed = parse_observable(original)
    except ValidationError:
        return None
    if expected_kind is not None and parsed.observable_type is not expected_kind:
        return None
    return {
        "kind": parsed.observable_type.value,
        "field_path": field_path,
        "original": parsed.original_value,
        "canonical": parsed.canonical_value,
    }


def preview_profile(
    envelopes: list[dict[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...], datetime | None, datetime | None]:
    """Derive searchable fields, capabilities, and time bounds from mapped samples."""

    fields = sorted(
        {
            field
            for envelope in envelopes
            for field in field_paths(envelope) | declared_observable_fields(envelope)
        }
    )
    capabilities = sorted(
        {capability for envelope in envelopes for capability in record_capabilities(envelope)}
    )
    timestamps = [
        timestamp for envelope in envelopes if (timestamp := utc_timestamp(envelope)) is not None
    ]
    return (
        tuple(fields),
        tuple(capabilities),
        min(timestamps) if timestamps else None,
        max(timestamps) if timestamps else None,
    )


def envelope_warnings(envelopes: list[dict[str, Any]]) -> tuple[str, ...]:
    """Collect unique safe mapping limitations declared by sample envelopes."""

    values: list[str] = []
    for envelope in envelopes:
        warnings = envelope.get("warnings")
        if not isinstance(warnings, list):
            continue
        for warning in warnings:
            if isinstance(warning, str) and warning not in values:
                values.append(warning)
    return tuple(values)


def field_paths(value: Any, prefix: str = "", depth: int = 0) -> set[str]:
    if depth > 4:
        return set()
    if isinstance(value, dict):
        paths: set[str] = set()
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths.update(field_paths(child, path, depth + 1))
        return paths
    if isinstance(value, list):
        paths = set()
        for child in value[:10]:
            paths.update(field_paths(child, f"{prefix}[]", depth + 1))
        return paths
    return set()


def record_capabilities(record: dict[str, Any]) -> set[str]:
    capabilities: set[str] = set()
    time_value = record.get("time")
    if isinstance(time_value, dict) and time_value.get("utc"):
        capabilities.add("timestamp.utc")
    observables = record.get("observables")
    if not isinstance(observables, list):
        return capabilities
    for item in observables:
        if isinstance(item, dict) and item.get("kind") in {"ipv4", "domain", "sha256"}:
            capabilities.add(f"observable.{item['kind']}")
    return capabilities


def declared_observable_fields(record: dict[str, Any]) -> set[str]:
    observables = record.get("observables")
    if not isinstance(observables, list):
        return set()
    return {
        field
        for item in observables
        if isinstance(item, dict)
        and isinstance((field := item.get("field_path")), str)
        and bool(field)
    }


def utc_timestamp(record: dict[str, Any]) -> datetime | None:
    time_value = record.get("time")
    if not isinstance(time_value, dict) or not isinstance(time_value.get("utc"), str):
        return None
    try:
        parsed = datetime.fromisoformat(time_value["utc"].replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def nested_value(record: dict[str, Any], *paths: str) -> object:
    """Return the first non-empty dot-path value from a structured record."""

    for path in paths:
        current: object = record
        for segment in path.split("."):
            if not isinstance(current, dict) or segment not in current:
                current = None
                break
            current = current[segment]
        if current not in (None, "", [], {}):
            return current
    return None


def _display_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None
