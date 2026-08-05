# Scope and v1 Product Contract

## Goal

Build a local CLI that searches exported logs for one validated IOC and produces a deterministic, source-linked evidence package that another analyst can review without access to the tool.

## Primary users

- Junior SOC analysts escalating a suspicious observable.
- Incident responders receiving an initial evidence handoff.
- Small teams without a dedicated forensic timeline or intelligence platform.
- DFIR students and instructors working with synthetic evidence.

## Supported IOC types for v1

| Type | v1 normalization |
|---|---|
| IPv4 | Parse and compare canonical address form |
| IPv6 | Parse and compare canonical compressed form |
| Domain | Trim trailing dot; lowercase; validate labels; retain original |
| SHA-256 | Validate 64 hexadecimal characters; lowercase |

URLs, MD5, SHA-1, CIDR ranges, email addresses, registry keys, and fuzzy hashes are candidates for later versions. MD5/SHA-1 may be useful as identifiers but must never be presented as strong integrity hashes.

## Inputs

The initial vertical slice supports a documented canonical JSONL schema. v1 expands to:

- generic JSONL and JSON arrays;
- generic CSV with an explicit field-mapping file;
- selected Wazuh JSON exports;
- selected Sysmon events that have already been exported to JSON/XML.

Native EVTX parsing, direct SIEM queries, live endpoint access, packet capture, disk images, and cloud API collection are out of v1.

Every input file must receive a source identifier, byte size, SHA-256 hash, detected/declared adapter, accepted-record count, rejected-record count, and error summary.

## Canonical event requirements

A normalized event contains:

- stable event ID derived from source identity and record position;
- source file and source record/line reference;
- source type and adapter version;
- original timestamp text and normalized UTC timestamp when possible;
- host, user, process, parent process, file path, hashes, IPs, domains, and URLs when present;
- raw record or lossless source reference;
- parser warnings and normalization notes.

Missing optional fields are allowed. Missing or invalid timestamps must be disclosed and must not be silently invented.

## Matching behavior

v1 must:

1. detect or accept the IOC type;
2. reject malformed values with a useful error;
3. compare canonical values only in fields declared compatible by the adapter;
4. record the original field path, original value, normalized value, and rule for every match;
5. deduplicate the same source event without collapsing distinct events;
6. distinguish a **direct match** from a **context event**;
7. make context-window behavior configurable and disabled by default until tested.

Substring scanning of arbitrary raw text is not considered equivalent to a structured match. If added as a fallback, it must be labeled separately because it can produce false positives.

## Required outputs

### `report.html`

Contains query summary, source coverage, limitations, timeline, entity summaries, match explanations, warnings, and generation metadata. All untrusted values are HTML-escaped.

### `evidence.json`

Contains normalized matched events and explicit links to source records. Its schema is versioned and suitable for deterministic comparison.

### `manifest.json`

Contains tool/schema versions, execution parameters, creation time, input inventory and hashes, output hashes, warning/error counts, and the matching-policy identifier.

### `source-inventory.json`

Describes which inputs were processed, skipped, or rejected and why. Optional PDF output may be added only after HTML output is correct and testable.

## Non-functional requirements

- Local/offline operation is the default.
- No telemetry or automatic upload.
- Deterministic evidence ordering and stable JSON serialization.
- Cross-platform behavior on Windows and Linux.
- Bounded memory usage through streaming or batched ingestion.
- SQLite queries use parameters, not string interpolation.
- Output paths cannot escape the selected output directory.
- Jinja2 auto-escaping remains enabled for HTML.
- Errors identify the source without printing sensitive raw records by default.
- Synthetic fixtures contain reserved example addresses/domains, never real victim data.

## v1 acceptance criteria

The release is credible when:

- IPv4, IPv6, domain, and SHA-256 validation have positive/negative tests.
- A synthetic multi-source case contains planted true matches, benign lookalikes, duplicates, malformed records, and mixed time zones.
- All planted direct matches are found and all lookalikes are excluded.
- Every reported event maps back to its source and record position.
- Rejected records are counted and explained.
- Re-running with equivalent inputs/settings produces equivalent `evidence.json` content.
- Generated HTML safely renders malicious-looking strings as text.
- Input/output hashes in the manifest verify successfully.
- An end-to-end test builds the expected package without network access.
- The README includes a screenshot or checked-in example report once implementation exists.

## Explicit non-goals

- Live acquisition or remote endpoint commands.
- Continuous ingestion, retention, alerting, or detection.
- Automated containment or remediation.
- Malware execution or sandboxing.
- A threat reputation verdict or autonomous analyst conclusion.
- Enterprise user management, multi-tenancy, or case collaboration.
- Full chain-of-custody/court-admissibility claims.
- Replacing MISP, OpenCTI, Timesketch, Velociraptor, or a SIEM.
- Sending indicators or evidence to external APIs by default.
- A graphical interface before the CLI vertical slice is stable.

## Later candidates

Native EVTX, pluggable adapters, optional VirusTotal/MISP/OpenCTI enrichment, PDF, ZIP bundles, redaction profiles, STIX/MISP exports, batch IOC input, case notes, signed manifests, and a desktop/web interface must be evaluated after v1 rather than silently added to its contract.

## Decision rule for new features

A proposed feature belongs in this repository only if it improves the path from an existing IOC plus exported evidence to a more reviewable and reproducible evidence package. If its main purpose is acquisition, detection, long-term intelligence management, or case collaboration, integration with a specialist tool is preferred.
