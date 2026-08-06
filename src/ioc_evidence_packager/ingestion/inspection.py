"""Source hashing and bounded adapter detection service."""

import hashlib
from pathlib import Path
from uuid import uuid4

from ioc_evidence_packager.domain.sources import (
    PreviewStatus,
    SourcePreview,
    SourcePreviewId,
)
from ioc_evidence_packager.ingestion.registry import AdapterRegistry

HASH_CHUNK_SIZE = 1_048_576


class SourceInspectionService:
    """Builds a safe source preview without ingesting evidence records."""

    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self._registry = registry or AdapterRegistry()

    def inspect(self, path: Path) -> SourcePreview:
        resolved = path.expanduser().resolve(strict=False)
        preview_id = SourcePreviewId(f"preview-{uuid4()}")
        try:
            if not resolved.is_file():
                raise OSError("The selected path is not a readable file.")
            byte_size = resolved.stat().st_size
            digest = _sha256_file(resolved)
            detected = self._registry.detect(resolved)
        except (OSError, PermissionError) as error:
            return SourcePreview(
                preview_id=preview_id,
                path=resolved,
                display_name=resolved.name or str(resolved),
                byte_size=0,
                sha256=None,
                status=PreviewStatus.FAILED,
                adapter_id=None,
                adapter_version=None,
                format_name=None,
                sample_records=0,
                fields=(),
                capabilities=(),
                warnings=(str(error),),
            )

        if detected is None:
            return SourcePreview(
                preview_id=preview_id,
                path=resolved,
                display_name=resolved.name,
                byte_size=byte_size,
                sha256=digest,
                status=PreviewStatus.UNSUPPORTED,
                adapter_id=None,
                adapter_version=None,
                format_name=None,
                sample_records=0,
                fields=(),
                capabilities=(),
                warnings=("No installed adapter recognizes this source.",),
            )

        adapter, probe = detected
        status = PreviewStatus.WARNING if probe.warnings else PreviewStatus.READY
        return SourcePreview(
            preview_id=preview_id,
            path=resolved,
            display_name=resolved.name,
            byte_size=byte_size,
            sha256=digest,
            status=status,
            adapter_id=adapter.adapter_id,
            adapter_version=adapter.version,
            format_name=probe.format_name,
            sample_records=probe.sample_records,
            fields=probe.fields,
            capabilities=probe.capabilities,
            warnings=probe.warnings,
            earliest_time=probe.earliest_time,
            latest_time=probe.latest_time,
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()
