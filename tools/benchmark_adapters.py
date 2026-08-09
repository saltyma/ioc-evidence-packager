"""Measure bounded preview/import throughput on the safe Phase 5 fixtures."""

import argparse
import json
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from ioc_evidence_packager.domain.models import CaseId
from ioc_evidence_packager.ingestion.inspection import SourceInspectionService
from ioc_evidence_packager.ingestion.registry import AdapterRegistry

NAMES = (
    "07-suricata-eve.jsonl",
    "08-wazuh-alerts.jsonl",
    "09-hayabusa-results.jsonl",
    "10-generic-array.json",
    "11-mapped-proxy.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")

    root = Path(__file__).resolve().parents[1]
    demo = root / "samples" / "input" / "demo-investigation"
    registry = AdapterRegistry()
    inspection = SourceInspectionService(registry)
    paths = tuple(demo / name for name in NAMES)

    tracemalloc.start()
    preview_start = time.perf_counter()
    for _iteration in range(args.iterations):
        previews = tuple(inspection.inspect(path) for path in paths)
    preview_seconds = time.perf_counter() - preview_start

    imported_at = datetime.now(UTC)
    item_count = 0
    import_start = time.perf_counter()
    for _iteration in range(args.iterations):
        for preview in previews:
            adapter = registry.adapter_for(preview.adapter_id)
            if adapter is None:
                raise RuntimeError(f"Fixture was not recognized: {preview.display_name}")
            item_count += sum(
                1 for _item in adapter.iter_items(CaseId("case-benchmark"), preview, imported_at)
            )
    import_seconds = time.perf_counter() - import_start
    _current, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    result = {
        "iterations": args.iterations,
        "sources_per_iteration": len(paths),
        "preview_operations_per_second": round(args.iterations * len(paths) / preview_seconds, 1),
        "mapped_records_per_second": round(item_count / import_seconds, 1),
        "peak_traced_mib": round(peak_bytes / (1024 * 1024), 2),
    }
    if args.as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("Phase 5 safe-fixture microbenchmark (not a production scale claim)")
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
