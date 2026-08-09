"""Ordered built-in adapter registry."""

from pathlib import Path

from ioc_evidence_packager.ingestion.adapters.canonical_jsonl import CanonicalJsonlAdapter
from ioc_evidence_packager.ingestion.adapters.generic_json_array import GenericJsonArrayAdapter
from ioc_evidence_packager.ingestion.adapters.hayabusa_jsonl import HayabusaJsonlAdapter
from ioc_evidence_packager.ingestion.adapters.mapped_csv import MappedCsvAdapter
from ioc_evidence_packager.ingestion.adapters.suricata_eve import SuricataEveAdapter
from ioc_evidence_packager.ingestion.adapters.wazuh_json import WazuhJsonAdapter
from ioc_evidence_packager.ingestion.base import EvidenceAdapter, ProbeResult


class AdapterRegistry:
    """Runs bounded probes and returns the first recognized format."""

    def __init__(self, adapters: tuple[EvidenceAdapter, ...] | None = None) -> None:
        self._adapters = adapters or (
            CanonicalJsonlAdapter(),
            SuricataEveAdapter(),
            WazuhJsonAdapter(),
            HayabusaJsonlAdapter(),
            GenericJsonArrayAdapter(),
            MappedCsvAdapter(),
        )

    def detect(self, path: Path) -> tuple[EvidenceAdapter, ProbeResult] | None:
        for adapter in self._adapters:
            result = adapter.probe(path)
            if result.recognized:
                return adapter, result
        return None

    def adapter_for(self, adapter_id: str | None) -> EvidenceAdapter | None:
        """Return the installed adapter that produced a source preview."""

        if adapter_id is None:
            return None
        return next(
            (adapter for adapter in self._adapters if adapter.adapter_id == adapter_id),
            None,
        )
