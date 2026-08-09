# Case Capsule Contract

## Purpose

A Case Capsule is a portable projection of a local investigation. It lets another analyst review the evidence story, verify artifact integrity, understand coverage and limitations, and import machine-readable facts without needing the desktop application or original security consoles.

The capsule is an export, not the live case database and not a complete legal chain-of-custody record.

**Implementation status:** the v0.6.0 desktop ships the filesystem capsule with Full Internal and Redacted Shareable profiles, multi-adapter source inventory, background rendering, atomic publication, manifest verification, export history, and a checked synthetic example.

## Logical structure

```text
case-001/
|-- report.html
|-- report.pdf                      # Optional by profile
|-- evidence.jsonl
|-- timeline.csv
|-- graph.json
|-- coverage.json
|-- source-inventory.json
|-- assessments.json
|-- recommendations.json
|-- enrichment/
|   |-- normalized-assertions.json
|   `-- raw-response-index.json
|-- attachments/                    # Optional, allow-listed artifacts only
`-- manifest.json
```

The implemented v1 capsule requires `report.html`, `evidence.jsonl`, `timeline.csv`, `coverage.json`, `source-inventory.json`, and `manifest.json`. Other artifacts are introduced by roadmap phase and declared in the manifest.

## Artifact roles

| Artifact | Role |
|---|---|
| `report.html` | Self-contained human-readable findings, coverage, limitations, and evidence references |
| `report.pdf` | Optional fixed-layout shareable rendering; never the only evidence representation |
| `evidence.jsonl` | Versioned normalized facts, sightings, provenance, and review/export state |
| `timeline.csv` | Flat analyst-friendly event sequence with spreadsheet-safe escaping |
| `graph.json` | Typed nodes/edges with supporting evidence IDs |
| `coverage.json` | Normative coverage cells, states, reasons, and supporting source/job IDs |
| `source-inventory.json` | Supplied/skipped/failed sources, digests, adapter/format versions, mapped fields, capabilities, counts, warnings, and time bounds |

`source-inventory/1.1.0` adds the detected format, sampled-record count, mapped fields, and declared capabilities. For mapped CSV, the format identity includes the mapping-profile ID and complete SHA-256. Changing either the CSV bytes or its mapping profile after preview blocks import and requires a new preview.
| `assessments.json` | Human-authored assessments, confidence vocabulary, rationale, and citations |
| `recommendations.json` | Proposed/accepted/completed/dismissed next actions and their evidence links |
| `enrichment/*` | Provider assertions and an index of retained raw responses |
| `manifest.json` | Capsule identity, schema/tool versions, policies, artifact hashes, and warnings |

## Export profiles

### Full Internal

Includes all analyst-selected evidence, source references, notes, assessments, intelligence assertions, and limitations. Raw source files are not included by default because duplication affects sensitivity and size.

### Redacted Shareable

Applies a named, versioned redaction policy. Typical transformations include pseudonymizing host/user identifiers, removing internal paths or query parameters, excluding raw provider responses, and shortening notes.

The report and manifest disclose which policy and transformations were used. Redaction creates a derived export; it never changes the local case.

### Executive

Prioritizes analyst-approved findings, business/technical impact, affected-entity counts, material limitations, and recommended actions. It omits raw-record bodies and low-level diagnostics but retains evidence references that a permitted reviewer can request.

### Machine Handoff

Prioritizes JSONL, JSON, CSV, schema versions, and manifest. It may omit PDF and long narrative sections.

### Platform Handoff

Uses a destination-specific connector such as STIX, MISP, OpenCTI, TheHive, or Timesketch. It records a mapping/receipt but is not necessarily a filesystem capsule.

## Manifest minimum fields

```json
{
  "capsule_schema": "1.0.0",
  "capsule_id": "case-001-export-0001",
  "case_id": "case-001",
  "export_profile": "full-internal",
  "created_at": "2026-08-06T14:00:00Z",
  "tool": {
    "name": "ioc-evidence-packager",
    "version": "0.6.0"
  },
  "run_ids": ["run-0001"],
  "policy_versions": {
    "search_recipe": "ip/1.0.0",
    "privacy": "offline/1.0.0",
    "redaction": null
  },
  "sources": [],
  "artifacts": [],
  "warning_summary": {},
  "limitations": []
}
```

The example communicates shape, not a frozen serialization schema. Formal JSON Schemas will be versioned with the implementation.

Each artifact entry includes relative path, media type, byte size, SHA-256, schema/version when applicable, and logical role. Paths use a documented portable separator and cannot be absolute or traverse outside the capsule.

## Evidence JSONL principles

- One logical evidence record per line for streaming and partial inspection.
- Stable record type and schema version fields.
- Original values and normalized values remain distinguishable.
- Provenance identifies source digest and source position.
- Match, context, and relationship explanations use stable rule IDs.
- Unknown optional values are null/absent according to the schema; no invented defaults.
- Analyst annotations are separately attributed.
- Raw records are omitted, embedded, or referenced according to the export profile.

## Integrity and verification

Export sequence:

1. create an empty validated staging directory;
2. render every non-manifest artifact;
3. flush and close writers;
4. calculate byte size and SHA-256 for every artifact;
5. write `manifest.json` last;
6. re-read and verify all listed artifacts;
7. atomically publish or rename the completed directory/ZIP when supported;
8. record the successful export in the local case.

The verifier checks schema support, safe relative paths, missing/extra files, byte sizes, hashes, duplicate paths, and internally referenced evidence IDs. A future detached signature can authenticate a manifest, but signatures do not replace acquisition and custody procedures.

## Determinism

Equivalent source bytes, mappings, recipe/policy versions, and evidence selections should produce equivalent evidence content and ordering. Export identifiers and creation times are expected to vary and are excluded from golden semantic comparison.

Normalization rules, ordering keys, JSON encoding, floating-point avoidance, newline format, and CSV dialect must be documented and tested.

## Redaction model

A redaction rule identifies:

- target semantic field or JSON path;
- transformation such as omit, replace, stable pseudonym, truncate, or mask;
- scope such as report only, all machine artifacts, or attachments;
- rule version and reason.

Redaction is applied to a derived report projection before rendering. It cannot alter source digests, internal evidence identity, or historical exports. Cross-artifact pseudonyms must remain consistent within one capsule when the policy requires useful relationships.

The export preview shows a field-level summary and blocks a profile if a selected artifact cannot honor its redaction policy.

## Safe HTML and PDF

- HTML is self-contained and uses no remote scripts, fonts, images, or analytics.
- All evidence and analyst text is escaped; permitted markup is generated only by trusted templates.
- External links are visibly labeled and use allow-listed schemes.
- Content Security Policy is included where compatible with a portable file.
- PDF conversion runs with network access disabled and a restricted local-resource root.
- Large raw records are summarized with evidence IDs rather than forcing dangerous or unusable pages.

## Safe CSV

Timeline CSV uses a fixed dialect, UTF-8, explicit time format, and protection against spreadsheet formula execution. Values beginning with formula-control characters receive a documented display-safe transformation; machine-readable originals remain in JSONL when allowed.

## Attachments

Attachments are disabled by default. Allowed attachments must be explicitly selected, size-limited, hashed, named with application-generated safe identifiers, and listed in the manifest. Active malware, executable samples, archives with unknown contents, original source evidence, and credentials are never silently attached.

## Compatibility

- Capsule schemas follow semantic versions.
- Readers reject unsupported major versions and warn on newer minor fields.
- Renderers and importers do not infer undocumented legacy fields.
- Migrations transform a copied/imported representation, never the original capsule.

## Definition of done

A Case Capsule implementation is complete when a golden synthetic case can be exported twice, semantically compared, hash-verified, safely opened offline, redacted consistently across artifacts, and reviewed back to each included source position.
