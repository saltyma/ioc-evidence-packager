"""Selected Suricata eve.json adapter with explicit IOC field mappings."""

from typing import Any

from ioc_evidence_packager.domain.observables import ObservableType
from ioc_evidence_packager.ingestion.adapters.common import (
    build_envelope,
    nested_value,
    observable,
)
from ioc_evidence_packager.ingestion.adapters.jsonl_base import JsonlRecordAdapter


class SuricataEveAdapter(JsonlRecordAdapter):
    """Maps common DNS, flow, alert, TLS, HTTP, and fileinfo eve records."""

    adapter_id = "suricata-eve-jsonl"
    version = "1.0.0"
    format_name = "Suricata eve.json JSONL"

    def matches(self, record: dict[str, Any]) -> bool:
        return isinstance(record.get("event_type"), str) and any(
            key in record for key in ("timestamp", "flow_id", "src_ip", "dest_ip")
        )

    def map_record(
        self,
        record: dict[str, Any],
        line_number: int,
        source_name: str,
    ) -> dict[str, Any]:
        event_type = str(record.get("event_type") or "event")
        observations: list[dict[str, str]] = []
        candidates = (
            observable(record.get("src_ip"), "network.source_ip", ObservableType.IPV4),
            observable(record.get("dest_ip"), "network.destination_ip", ObservableType.IPV4),
            observable(
                nested_value(record, "dns.rrname"),
                "dns.question",
                ObservableType.DOMAIN,
            ),
            observable(
                nested_value(record, "http.hostname"),
                "http.hostname",
                ObservableType.DOMAIN,
            ),
            observable(
                nested_value(record, "tls.sni"),
                "tls.sni",
                ObservableType.DOMAIN,
            ),
            observable(
                nested_value(record, "fileinfo.sha256"),
                "file.sha256",
                ObservableType.SHA256,
            ),
        )
        observations.extend(value for value in candidates if value is not None)
        dns_answers = nested_value(record, "dns.answers")
        if isinstance(dns_answers, list):
            for index, answer in enumerate(dns_answers):
                answer_value = answer.get("rdata") if isinstance(answer, dict) else answer
                mapped = observable(answer_value, f"dns.answers[{index}]")
                if mapped is not None:
                    observations.append(mapped)

        action = _suricata_action(event_type, record)
        identity = record.get("flow_id") or record.get("tx_id") or line_number
        return build_envelope(
            adapter_id=self.adapter_id,
            adapter_version=self.version,
            source_id=f"suricata:{source_name}",
            position_kind="line",
            position_value=line_number,
            event_id=f"suricata-{identity}-{line_number}",
            timestamp=record.get("timestamp"),
            category=event_type,
            action=action,
            observables=tuple(observations),
        )


def _suricata_action(event_type: str, record: dict[str, Any]) -> str:
    if event_type == "dns":
        return "dns-answer" if nested_value(record, "dns.answers") else "dns-query"
    if event_type == "alert":
        return "alert"
    if event_type == "flow":
        return str(nested_value(record, "flow.state") or "connection")
    return event_type
