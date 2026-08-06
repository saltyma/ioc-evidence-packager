# Core and Smart Features

This document defines what the product should do, why each capability matters, and the guardrails that keep "smart" behavior explainable.

## Feature tiers

| Tier | Meaning | Examples |
|---|---|---|
| Core | Required for the first credible desktop release | Cases, import, matching, evidence ledger, coverage, exports |
| Smart | High-value reasoning built from explicit rules | Search recipes, relationships, recommendations, gap analysis |
| Connected | Optional network or platform capabilities | Enrichment providers, SIEM search, case-system handoff |
| Later | Valuable only after the core is proven | Batch campaigns, signatures, collaboration, optional local prose AI |

## 1. Case workspace

**Tier:** Core

A case holds the lead, observables, time range, imported sources, runs, evidence, notes, assessments, enrichment results, and exports. Autosave is transactional. Re-running creates a new run record instead of silently replacing previous results.

Useful behavior:

- case templates for IP, domain, URL, and file-hash investigations;
- status such as Draft, Processing, Ready for Review, Reviewed, and Exported;
- labels, bookmarks, analyst notes, and an activity log;
- safe reopening after a crash;
- clone a case without duplicating external source files unless requested.

## 2. Guided import and source preview

**Tier:** Core

Before ingesting, the application previews each file's detected format, expected adapter, size, hash status, timestamp interpretation, recognized fields, sample values, and warnings.

The analyst can:

- accept the detected adapter or choose another;
- define CSV/JSON field mappings;
- set the source time zone when absent;
- limit an import by requested time range;
- reject a file before processing;
- see which IOC recipes the source can support.

Unsupported or malformed records are counted and explained; they are never quietly discarded.

## 3. IOC validation and search recipes

**Tier:** Core and Smart

A search recipe is a versioned, testable set of compatible fields, normalization rules, pivots, and coverage expectations for one observable type.

### IP recipe

- canonicalize IPv4/IPv6 values;
- search source/destination/network/address fields declared by adapters;
- distinguish direct endpoints from an IP embedded in a URL or command line;
- pivot to domains resolved to the IP, processes making connections, and affected hosts;
- optionally check RDAP, reputation, and known scanning/noise sources.

### Domain recipe

- lowercase and remove a trailing root dot while preserving the original;
- use the Public Suffix List to distinguish registrable domain and subdomain;
- search DNS query/answer, SNI, HTTP host, URL, email, and command-line fields where supported;
- pivot to resolved IPs, requesting hosts, processes, and URLs;
- never use naive suffix matching that makes `notexample.com` match `example.com`.

### URL recipe

- parse scheme, authority, port, path, query, and fragment without discarding the original;
- compare exact normalized URLs separately from domain/path pivots;
- redact credentials or sensitive query parameters in shareable views;
- pivot to domain, IP, downloading process, referrer, and resulting file hash.

### Hash recipe

- recognize SHA-256 first; later accept MD5/SHA-1 only as identifiers;
- search declared file, process-image, module, download, and antivirus hash fields;
- pivot to file path, signer, process execution, parent process, user, host, and network activity;
- never upload the file automatically; any future sample acquisition is a separate, explicit action outside the core.

Every match records the recipe version, rule ID, field path, original value, normalized value, and explanation.

## 4. Evidence ledger

**Tier:** Core

The Evidence view is a filterable ledger, not an opaque results list. Each evidence item includes:

- stable case-local evidence ID;
- normalized UTC time plus original timestamp and time-zone assumption;
- host, user, process, file, network, and observable fields when present;
- source ID, source SHA-256, adapter/version, and source record position;
- inclusion class: direct match, pivot result, context event, or analyst-added item;
- rule ID and plain-language inclusion explanation;
- parser warnings, annotations, review state, and raw-record access.

The analyst may annotate or exclude an item from a particular export, but cannot edit the preserved source fact. Corrections become annotations with author, time, and rationale.

## 5. Evidence Coverage Matrix

**Tier:** Core and defining feature

The matrix crosses the investigation's expected telemetry or recipe steps with supplied sources and time ranges.

| Status | Interpretation | UI treatment |
|---|---|---|
| `MATCH_FOUND` | Search completed and produced one or more matches | Positive finding with count and links |
| `SEARCHED_NO_MATCH` | Search completed over compatible data with no result | Neutral, never rendered as "clean" |
| `PARTIAL_COVERAGE` | Search covered only part of the expected records, fields, hosts, or interval | Warning with the precise gap |
| `SOURCE_NOT_PROVIDED` | No source was supplied for the category | Missing-source prompt |
| `SOURCE_FAILED` | A supplied source could not be processed reliably | Error with recovery action |
| `FORMAT_UNSUPPORTED` | No adapter can search the supplied schema | Unsupported notice and mapping option |

Coverage is calculated from evidence, adapter capabilities, requested time range, source inventory, parser results, and recipe requirements. It is not a subjective confidence score.

Examples of useful gap statements:

- "DNS was searched for WS-014 from 09:00 to 09:30 UTC; the requested case interval ends at 10:00 UTC."
- "Proxy records were supplied for WS-014 and WS-022; no proxy source was supplied for WS-031."
- "The file contains 4,102 records; 87 were rejected because their timestamps were invalid."

## 6. Timeline

**Tier:** Core

The timeline shows direct evidence and context with visually distinct categories. It supports zoom, entity filters, source filters, bookmarks, time-zone display, and a side-by-side raw record.

Ordering is deterministic: normalized time, then source ID, then source position. Records without a trustworthy normalized time appear in an "undated" lane rather than being assigned an invented time.

## 7. Relationship graph

**Tier:** Smart, after the evidence table

Nodes represent observables, events, hosts, users, processes, files, and provider assertions. Edges are typed and carry their rule and supporting evidence IDs.

Examples:

- event `observed-on` host;
- process `executed` file;
- process `connected-to` IP;
- domain `resolved-to` IP;
- assertion `describes` observable;
- assessment `supported-by` evidence.

Graph expansion is bounded to avoid a "hairball." The default graph contains the lead, direct sightings, and one-hop entities. Analysts deliberately request additional pivots.

## 8. Intelligence panel

**Tier:** Connected

Provider results remain separate from local evidence and from one another. The panel shows provider, retrieval time, query value, response age, terms/licensing note, raw-response hash, cache state, and a normalized summary.

The application does not average providers into a universal score. Contradictory results are displayed as contradictory assertions.

## 9. Explainable next-action engine

**Tier:** Smart

Recommendations are deterministic rules over evidence, relationships, source capabilities, and coverage gaps. Each recommendation contains:

- action title and category;
- priority such as Immediate, Useful, or Optional;
- rationale in plain language;
- supporting evidence IDs and/or coverage cells;
- preconditions and safety notes;
- suggested destination tool or query template;
- state: proposed, accepted, completed, dismissed, with analyst reason.

Example rules:

| Condition | Suggested action |
|---|---|
| Hash observed executing on a host and no process ancestry is available | Acquire or search process creation telemetry for that host and interval |
| Domain matched in DNS and a resolved IP has not been searched | Add the IP as a case observable and run the IP recipe |
| External connection exists but proxy coverage is missing | Request proxy/firewall telemetry for the host and interval |
| Threat intelligence says a hash is malware but no local execution is observed | Search execution and module-load telemetry; do not claim execution |
| Same file appears on multiple hosts | Compare first-seen time, user, path, and parent process across hosts |

Rules never execute containment, collection, or remote searches automatically.

## 10. Privacy firewall and enrichment policies

**Tier:** Core policy, Connected execution

The New Investigation wizard requires one policy:

| Policy | Network behavior |
|---|---|
| Offline | No network resolution, enrichment, updates, or remote assets |
| Local intelligence | Query only configured on-premise services |
| Safe enrichment | Query approved low-disclosure providers with observable values only |
| Enterprise | Use configured licensed providers and organization systems |
| Custom | Per-provider allow/deny rules with a disclosure preview |

Before execution, the UI shows a disclosure plan such as `203.0.113.42 -> GreyNoise Community`. Files, raw events, usernames, hostnames, and paths are denied by default. All requests and cache hits are recorded.

## 11. Export profiles and Case Capsule

**Tier:** Core

- **Full internal:** all selected evidence, raw references, intelligence, notes, and limitations.
- **Redacted shareable:** applies an explicit redaction profile and records what was transformed.
- **Executive PDF:** concise findings, impact, limitations, and analyst assessment; no raw-record dump.
- **Machine handoff:** JSONL/CSV/graph/coverage/manifest for another tool.
- **Platform handoff:** later STIX, MISP, OpenCTI, TheHive, or Timesketch connector.

Exports are projections from the same versioned case/report model, so screens and reports cannot disagree because of independent logic.

## 12. Run history and reproducibility

**Tier:** Core

Each import, analysis, enrichment, and export is a job with configuration, start/end time, status, versions, counts, warnings, and error details. A rerun points to the previous run and explains changed inputs or policies.

## 13. Optional local prose assistant

**Tier:** Later and non-authoritative

If added, a local or explicitly configured language model may draft a narrative from analyst-selected, redacted facts. The draft must retain citations to evidence IDs, remain visibly unapproved, and never add, remove, classify, or rank evidence. The first releases do not require AI.

## Explicitly rejected "smart" behavior

- one unexplained incident or maliciousness score;
- automatic reputation queries before the disclosure preview;
- autonomous evidence selection or suppression;
- automatic sample upload or malware download;
- automatic containment, blocking, or endpoint commands;
- relationships inferred only by a language model;
- claims of compromise from a single IOC hit;
- claims of safety from a no-match result without full coverage.

## Delivery rule

A smart feature is ready only when its rule, input facts, limitations, failure state, and expected output can be expressed as deterministic tests using synthetic data.
