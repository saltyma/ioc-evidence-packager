# Performance notes

Performance claims remain evidence-based and deliberately narrow. The application does not advertise an arbitrary record scale.

## Phase 5 reference measurement

Measured on 2026-08-09 in the Windows development environment with Python 3.12, 200 iterations, and the five checked two-record practical-adapter fixtures:

| Measurement | Result |
|---|---:|
| Source preview operations | 210.9 per second |
| Mapped source records | 1,301.7 per second |
| Peak Python memory traced by the microbenchmark | 1.27 MiB |

These figures are a regression reference, not a production-capacity promise. The fixtures are tiny and benefit from operating-system file caching. Reproduce the measurement with:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python tools/benchmark_adapters.py --iterations 200
```

## Current engineering decision

- Canonical, Suricata, Wazuh, and Hayabusa JSONL sources are read line by line with a 1 MiB per-record limit.
- Mapped CSV is read row by row and requires a mapping sidecar no larger than 64 KiB.
- Generic JSON arrays use the standard-library decoder and are therefore bounded to 16 MiB; large JSON should be exported as JSONL until a measured use case justifies a streaming-array parser.
- Evidence is committed in bounded application batches to SQLite.
- The current safe-fixture results do not justify adding DuckDB or another scan engine. Larger generated fixtures and peak-memory/cancellation measurements should precede that decision.

Future measurements should publish cold-start, case-open, large-fixture import throughput, peak memory, cancellation latency, filtering latency, and capsule-generation results separately for each adapter.
