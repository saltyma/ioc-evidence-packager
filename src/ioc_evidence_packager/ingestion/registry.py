"""Ordered built-in adapter registry."""

from pathlib import Path

from ioc_evidence_packager.ingestion.adapters import CanonicalJsonlAdapter
from ioc_evidence_packager.ingestion.base import EvidenceAdapter, ProbeResult


class AdapterRegistry:
    """Runs bounded probes and returns the first recognized format."""

    def __init__(self, adapters: tuple[EvidenceAdapter, ...] | None = None) -> None:
        self._adapters = adapters or (CanonicalJsonlAdapter(),)

    def detect(self, path: Path) -> tuple[EvidenceAdapter, ProbeResult] | None:
        for adapter in self._adapters:
            result = adapter.probe(path)
            if result.recognized:
                return adapter, result
        return None
