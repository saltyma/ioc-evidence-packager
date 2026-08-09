"""Selected Hayabusa JSONL adapter for Windows event triage output."""

import re
from typing import Any

from ioc_evidence_packager.domain.observables import ObservableType
from ioc_evidence_packager.ingestion.adapters.common import build_envelope, observable
from ioc_evidence_packager.ingestion.adapters.jsonl_base import JsonlRecordAdapter


class HayabusaJsonlAdapter(JsonlRecordAdapter):
    """Maps explicit Hayabusa JSON fields and avoids IOC extraction from free text."""

    adapter_id = "hayabusa-jsonl"
    version = "1.0.0"
    format_name = "Hayabusa JSONL"

    def matches(self, record: dict[str, Any]) -> bool:
        return (
            isinstance(record.get("Timestamp"), str)
            and isinstance(record.get("Computer"), str)
            and "EventID" in record
            and isinstance(record.get("RuleTitle"), str)
        )

    def map_record(
        self,
        record: dict[str, Any],
        line_number: int,
        source_name: str,
    ) -> dict[str, Any]:
        observations: list[dict[str, str]] = []
        candidates = (
            observable(record.get("SrcIP"), "network.source_ip", ObservableType.IPV4),
            observable(record.get("DstIP"), "network.destination_ip", ObservableType.IPV4),
            observable(record.get("QueryName"), "dns.question", ObservableType.DOMAIN),
            observable(
                _sha256_value(record.get("SHA256") or record.get("Hashes")),
                "file.sha256",
                ObservableType.SHA256,
            ),
        )
        observations.extend(value for value in candidates if value is not None)
        category = _category(record)
        identity = record.get("RecordID") or record.get("EventRecordID") or line_number
        return build_envelope(
            adapter_id=self.adapter_id,
            adapter_version=self.version,
            source_id=f"hayabusa:{source_name}",
            position_kind="line",
            position_value=line_number,
            event_id=f"hayabusa-{record['EventID']}-{identity}",
            timestamp=record.get("Timestamp"),
            category=category,
            action=_slug(str(record.get("RuleTitle"))),
            host=record.get("Computer"),
            user=record.get("User"),
            observables=tuple(observations),
        )


def _category(record: dict[str, Any]) -> str:
    if record.get("QueryName"):
        return "dns"
    if record.get("DstIP") or record.get("SrcIP"):
        return "network"
    if record.get("SHA256") or record.get("Hashes"):
        return "file"
    return "windows-event"


def _sha256_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    match = re.search(r"(?i)(?:sha256=)?([0-9a-f]{64})", value)
    return match.group(1) if match else value


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:80] or "observed"
