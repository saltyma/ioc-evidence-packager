# Roadmap

The roadmap protects a small, demonstrable core. Dates are intentionally absent until effort is estimated from the first implementation slice.

## Phase 0 - Foundation (current)

- Define problem, users, scope, architecture, risks, and evidence terminology.
- Scaffold Python package, tests, samples, and contribution/security guidance.
- Record official research sources and explicit non-goals.

**Exit:** a reviewer can understand what will be built, where it fits, and how success will be tested.

## Phase 1 - Thin vertical slice

- Validate IPv4, IPv6, domain, and SHA-256 values.
- Import the canonical synthetic JSONL schema.
- Persist sources/events in SQLite with provenance.
- Find structured direct matches.
- Render deterministic `evidence.json`, source inventory, manifest, and safe HTML.
- Add one end-to-end synthetic incident.

**Exit:** one command packages a known sample IOC and all planted direct matches pass tests.

## Phase 2 - Practical local ingestion

- Generic CSV mapping files and JSON arrays.
- Selected Wazuh JSON and exported Sysmon adapters.
- Streaming/batched ingestion and useful parser diagnostics.
- Duplicate handling and mixed-time-zone test fixtures.

**Exit:** at least three meaningfully different safe sources produce a unified timeline.

## Phase 3 - Explainable context

- Optional same-host/process/user time windows.
- Related entity summaries and first/last seen statistics.
- Clear labels for direct matches, context events, and any raw-text fallback.
- Analyst notes and limitations sections that remain separate from evidence facts.

**Exit:** every inclusion is explained and correlation does not silently become a verdict.

## Phase 4 - Packaging quality

- Optional offline-safe PDF rendering.
- Portable ZIP bundle and verification command.
- Redaction profiles for selected display fields while retaining controlled originals.
- Example report screenshots and a 1-3 minute demo.

**Exit:** another analyst can verify and review the bundle without installing the application.

## Phase 5 - Integrations (only after validation)

- Native EVTX feasibility prototype.
- Explicit optional enrichment providers.
- STIX/MISP/OpenCTI and Timesketch-friendly exports.
- Batch IOC/case workflow evaluation.
- Signed manifest and desktop/web UI evaluation.

**Exit:** integrations strengthen the packaging workflow without turning the project into a SIEM, SOAR, collector, or intelligence platform.

## Portfolio proof checklist

- Safe demo data and reproducible command.
- Before/after workflow measurement.
- Architecture and threat-boundary diagrams.
- Example HTML/PDF and screenshot.
- Tests for malicious input, malformed records, time zones, duplicates, and determinism.
- Known limitations and rejected-record disclosure.
- Short demo video and concise project story.
