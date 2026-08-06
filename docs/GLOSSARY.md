# Glossary

## Observable

A value that can be seen or measured in security data, such as an IP, domain, URL, or file hash.

## Indicator of compromise (IOC)

An observable associated by intelligence or an investigation with potentially malicious activity. It is a lead requiring context, not an automatic verdict.

## Lead observable

The value that starts an investigation. Additional observables may be discovered as explicit pivots and retain their origin.

## Observable normalization

Conversion to a comparable representation, such as lowercasing a hash or canonicalizing an IP, while preserving the original value.

## Search recipe

A versioned set of compatible fields, normalization, direct-match rules, pivots, expected telemetry, and coverage steps for one observable type.

## Observed event

A canonical fact derived from a supplied source record, including time, entities, observables, provenance, and warnings.

## Direct sighting

An observed event whose compatible structured field normalizes exactly to a case observable. The field path, rule, and original/canonical values are recorded.

## Pivot result

Evidence discovered by following a declared relationship from an existing observable or event, such as a domain resolving to an IP. Its origin and rule remain visible.

## Context event

An event that does not directly contain the queried observable but is included by an explicit bounded correlation rule, such as the same host/process within a time window.

## Raw-text fallback

A lower-assurance search over unstructured record text. It is not equivalent to a structured match and must be labeled separately.

## Sighting

The linkage between an observable and an observed event, including source field, match class, rule, and explanation.

## Correlation

Connecting facts/entities through a declared rule such as shared host, user, process, file, network relationship, or time proximity. Correlation does not prove causation.

## Intelligence assertion

An attributed claim made by an external or internal provider about an observable. It remains separate from local observations and may be stale or contradictory.

## Analyst assessment

A human conclusion with rationale, cited evidence, confidence vocabulary, author, and time. The application may help organize it but does not authoritatively create it.

## Recommendation

A deterministic, cited next-action proposal generated from evidence, relationships, and coverage gaps. It never performs collection, containment, or remediation automatically.

## Evidence Coverage Matrix

A view and data model showing whether each expected telemetry/recipe scope was matched, searched without a match, only partially covered, not provided, failed, or unsupported.

## `MATCH_FOUND`

A compatible search completed and produced at least one explained match for the coverage cell.

## `SEARCHED_NO_MATCH`

A compatible search completed over the declared scope without a match. This means "not observed in this searched evidence," not "safe."

## `PARTIAL_COVERAGE`

Only part of the requested hosts, interval, records, fields, or recipe capability was searched reliably.

## `SOURCE_NOT_PROVIDED`

No evidence source was supplied for an expected telemetry category/scope.

## `SOURCE_FAILED`

A relevant supplied source could not be processed reliably.

## `FORMAT_UNSUPPORTED`

A supplied source format or schema has no compatible adapter/capability.

## Evidence ledger

The filterable source-linked set of observed facts, sightings, context, provenance, review state, and annotations in a case.

## Case

The durable local workspace holding the lead, sources, runs, facts, coverage, intelligence, analyst work, and export history.

## Run

One versioned execution of import, search recipes, coverage evaluation, relationships, or recommendations under an immutable policy/configuration snapshot.

## Job

A background unit of work with queued/running/cancelling/cancelled/succeeded/partial/failed state, progress, warnings, and checkpoints.

## Case Capsule

A portable, versioned export containing human and machine artifacts, coverage, source inventory, limitations, and an integrity manifest.

## Export profile

A declared projection such as Full Internal, Redacted Shareable, Executive, Machine Handoff, or Platform Handoff.

## Manifest

A machine-readable record of tool/schema/policy versions, sources, artifacts, hashes, warnings, and limitations for a Case Capsule.

## Source inventory

A list of supplied/skipped/failed sources with sizes, SHA-256 digests, adapters, counts, time/entity bounds, and diagnostics.

## Provenance

Information showing where a fact originated: source digest, source record/line, adapter/version, original field/value, and processing rule.

## Integrity digest

A cryptographic digest used to detect changed bytes. SHA-256 supports integrity checking but does not prove who acquired or possessed evidence.

## Canonical event

The project's vendor-neutral representation of a source record. "Canonical" means consistent for the documented schema/version, not more authoritative than the source.

## Adapter

A versioned parser/mapper that converts one source format/schema into canonical events and declares capabilities, assumptions, and diagnostics.

## Adapter capability

A declared field/observable/recipe function an adapter can reliably support. Coverage calculations depend on capabilities rather than filenames alone.

## Privacy policy

The immutable per-run rules that permit or deny network connectors and data categories. Initial profiles are Offline, Local Intelligence, Safe Enrichment, Enterprise, and Custom.

## Disclosure plan

The pre-execution list of exact values/categories, destinations, and purposes for proposed network requests.

## Redaction policy

A versioned set of transformations applied to a derived export. It never changes the local source facts.

## Deterministic evidence content

Normalized content and ordering that remain equivalent when source bytes, mappings, recipes, policies, and relevant versions are equivalent. Export time/ID may still vary.

## STIX

Structured Threat Information Expression, an OASIS standard for representing cyber-threat intelligence. The project may export STIX-aligned objects without using STIX as its internal database schema.

## SIEM

Security information and event management: centralized ingestion, search, correlation, alerting, and retention of security telemetry.

## EDR

Endpoint detection and response: endpoint telemetry, detection, investigation, and response capabilities.

## SOC

Security operations center: people and processes that monitor, triage, investigate, and respond to security events.

## DFIR

Digital forensics and incident response: acquisition, examination, analysis, and communication of digital evidence during investigations.

## Chain of custody

Documentation and controls tracking evidence possession and handling. Provenance and hashes help but this application alone cannot establish a complete legal chain of custody.
