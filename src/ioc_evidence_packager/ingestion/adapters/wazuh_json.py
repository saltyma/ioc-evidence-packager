"""Selected Wazuh alerts JSONL adapter with attributed rule metadata."""

import re
from typing import Any

from ioc_evidence_packager.domain.observables import ObservableType
from ioc_evidence_packager.ingestion.adapters.common import (
    build_envelope,
    nested_value,
    observable,
)
from ioc_evidence_packager.ingestion.adapters.jsonl_base import JsonlRecordAdapter


class WazuhJsonAdapter(JsonlRecordAdapter):
    """Maps stable Wazuh alert fields without parsing free-form descriptions."""

    adapter_id = "wazuh-alert-jsonl"
    version = "1.0.0"
    format_name = "Wazuh alerts JSONL"

    def matches(self, record: dict[str, Any]) -> bool:
        return (
            isinstance(record.get("timestamp"), str)
            and isinstance(record.get("rule"), dict)
            and isinstance(record.get("agent"), dict)
        )

    def map_record(
        self,
        record: dict[str, Any],
        line_number: int,
        source_name: str,
    ) -> dict[str, Any]:
        groups = nested_value(record, "rule.groups")
        group_values = (
            [str(value).casefold() for value in groups] if isinstance(groups, list) else []
        )
        category = _category(group_values, record)
        observations: list[dict[str, str]] = []
        source_path = (
            "authentication.source_ip" if category == "authentication" else "network.source_ip"
        )
        candidates = (
            observable(
                nested_value(record, "data.srcip", "data.src_ip"),
                source_path,
                ObservableType.IPV4,
            ),
            observable(
                nested_value(record, "data.dstip", "data.dest_ip", "data.dst_ip"),
                "network.destination_ip",
                ObservableType.IPV4,
            ),
            observable(
                nested_value(record, "data.query", "data.dns.question"),
                "dns.question",
                ObservableType.DOMAIN,
            ),
            observable(
                _sha256_value(nested_value(record, "data.sha256", "data.file.sha256")),
                "file.sha256",
                ObservableType.SHA256,
            ),
        )
        observations.extend(value for value in candidates if value is not None)
        rule_id = nested_value(record, "rule.id") or "unknown"
        description = str(nested_value(record, "rule.description") or "rule-fired")
        return build_envelope(
            adapter_id=self.adapter_id,
            adapter_version=self.version,
            source_id=f"wazuh:{source_name}",
            position_kind="line",
            position_value=line_number,
            event_id=f"wazuh-{rule_id}-{line_number}",
            timestamp=record.get("timestamp"),
            category=category,
            action=_slug(description),
            host=nested_value(record, "agent.name"),
            user=nested_value(record, "data.srcuser", "data.user", "data.dstuser"),
            observables=tuple(observations),
        )


def _category(groups: list[str], record: dict[str, Any]) -> str:
    if any("authentication" in group or "login" in group for group in groups):
        return "authentication"
    if nested_value(record, "data.query", "data.dns.question") is not None:
        return "dns"
    if any("syscheck" in group or "file" in group for group in groups):
        return "file"
    return "network"


def _sha256_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    match = re.search(r"(?i)(?:sha256=)?([0-9a-f]{64})", value)
    return match.group(1) if match else value


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:80] or "rule-fired"
