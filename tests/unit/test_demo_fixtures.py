"""The bundled demo remains safe, coherent, and previewable."""

import ipaddress
import json
from pathlib import Path

from ioc_evidence_packager.domain.sources import PreviewStatus
from ioc_evidence_packager.ingestion.inspection import SourceInspectionService

DEMO_DIRECTORY = Path(__file__).parents[2] / "samples" / "input" / "demo-investigation"
CLEAN_FILES = (
    "01-dns-events.jsonl",
    "02-endpoint-events.jsonl",
    "03-network-events.jsonl",
    "04-authentication-events.jsonl",
)
EXPECTED_RECORDS = (3, 4, 3, 2)
SAFE_IPV4_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)


def test_clean_demo_files_are_canonical_and_preview_ready() -> None:
    service = SourceInspectionService()

    for name, expected_records in zip(CLEAN_FILES, EXPECTED_RECORDS, strict=True):
        path = DEMO_DIRECTORY / name
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        preview = service.inspect(path)

        assert preview.status is PreviewStatus.READY
        assert preview.sample_records == expected_records
        assert len(records) == expected_records
        assert [record["source"]["position"]["value"] for record in records] == list(
            range(1, expected_records + 1)
        )
        assert all(record["schema"] == "canonical-event/1.0.0" for record in records)
        assert all(record["observables"] for record in records)


def test_demo_ipv4_observables_use_only_private_or_documentation_ranges() -> None:
    for name in CLEAN_FILES + ("05-partial-with-warning.jsonl",):
        for line in (DEMO_DIRECTORY / name).read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for observable in record["observables"]:
                if observable["kind"] != "ipv4":
                    continue
                address = ipaddress.ip_address(observable["canonical"])
                assert any(address in network for network in SAFE_IPV4_NETWORKS)


def test_diagnostic_files_demonstrate_warning_and_unsupported_states() -> None:
    service = SourceInspectionService()

    partial = service.inspect(DEMO_DIRECTORY / "05-partial-with-warning.jsonl")
    unsupported = service.inspect(DEMO_DIRECTORY / "06-unsupported-siem-export.csv")

    assert partial.status is PreviewStatus.WARNING
    assert partial.sample_records == 1
    assert partial.warnings == ("Line 2 is not valid UTF-8 JSON.",)
    assert unsupported.status is PreviewStatus.UNSUPPORTED
    assert unsupported.sha256 is not None
