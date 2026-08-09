# Roadmap

The roadmap is GUI-first and vertical. Every phase ends in a demonstrable analyst outcome while the evidence core stays headless and testable. Dates remain absent until the first two slices establish real velocity.

## Phase 0 - Product conception (complete)

- Define the product vision, users, workflow, positioning, and guardrails.
- Specify GUI information architecture and interaction rules.
- Define facts, sightings, correlations, intelligence assertions, and assessments.
- Specify Evidence Coverage Matrix states and Case Capsule contract.
- Select PySide6, headless services, SQLite, and canonical JSONL for the first slice.
- Document adapter, enrichment, privacy, and handoff contracts.

**Exit:** implementation can begin without deciding what the product is during coding.

## Phase 1 - Desktop shell and durable cases (implemented)

- Add PySide6 application entry point and native main window.
- Implement Home, recent cases, case shell, navigation, and visible Offline policy.
- Add SQLite migrations, repositories, transactional case creation/opening, and recovery state.
- Establish command/query ports and the job coordinator interface.
- Add domain tests, migration tests, and an offscreen Qt smoke test.

**Exit demo:** create a case, close the application, reopen it, and recover the same accurate state.

## Phase 2 - Guided evidence import (core implemented)

- [x] Implement IPv4, domain, and SHA-256 value objects.
- [x] Publish canonical JSONL schema and build the first safe synthetic fixture.
- [x] Implement the lead, source-preview, and review steps of the wizard.
- [x] Hash and preview sources, adapter capabilities, timestamps, fields, and warnings.
- [ ] Add explicit mapping and connected-privacy steps when another adapter/provider needs them.
- [x] Stream imports in background batches with progress, cancellation, retry, and structured rejections.

**Exit demo:** preview exactly how evidence will be interpreted, import it without freezing the UI, cancel safely, and trace accepted/rejected counts.

## Phase 3 - Evidence and coverage core (core implemented)

- [x] Implement versioned IOC search recipes and structured direct-match explanations.
- [x] Build the source-linked Evidence ledger and raw/provenance detail view.
- [x] Add Evidence text/classification filters.
- [ ] Add bookmarks and analyst annotations as reviewed workflow refinements.
- [x] Implement the six Evidence Coverage Matrix states and calculation reasons.
- [x] Add coverage-aware Dashboard summaries.
- [x] Add a basic deterministic Timeline with an Undated lane.
- [x] Test planted matches, lookalikes, missing sources, partial processing, and failed sources.
- [ ] Expand mixed-time-zone and ambiguous-timestamp fixtures with practical adapters.
- [x] Test import duplicates, malformed records, changed source bytes, and cancellation boundaries.

**Exit demo:** find all planted sightings, explain every inclusion, and show why missing or partial telemetry limits the conclusion.

## Phase 4 - Portable Case Capsule (implemented)

- [x] Build the shared immutable report model.
- [x] Render self-contained HTML, evidence JSONL, timeline CSV, coverage JSON, inventory JSON, and final manifest.
- [x] Add safe destination validation, artifact hashes, verification, atomic publication, and export history.
- [x] Add Full Internal and Redacted Shareable profiles.
- [x] Add a checked-in example capsule and screenshots from synthetic data.
- [x] Establish semantic determinism, redaction, and tamper-detection fixtures.

**Exit demo:** another analyst can open and verify the exported investigation without installing the application or accessing original consoles.

## Phase 5 - Practical adapters (implemented in v0.6.0)

- [x] Add bounded generic JSON arrays and explicit versioned CSV mapping profiles.
- [x] Add selected Wazuh JSONL, Hayabusa JSONL, and Suricata `eve.json` adapters.
- [x] Add a filterable Sources workspace with digests, adapters, capabilities, counts, limitations, and diagnostics.
- [x] Add source-capability coverage, schema-drift diagnostics, and mixed-time-zone fixtures.
- [x] Measure [safe-fixture preview/import behavior](PERFORMANCE.md) and retain the streaming/SQLite design; current evidence does not justify DuckDB.

**Exit achieved:** six adapter families produce one coherent, source-linked Evidence ledger, Timeline, Coverage Matrix, Sources inventory, and Case Capsule.

## Phase 6 - Relationships and next actions (implemented in v0.7.0)

- [x] Add typed entity relationships and focused one-hop graph/table views.
- [x] Add observable pivots that preserve evidence origin.
- [x] Implement deterministic next-action rules with evidence, coverage, and relationship citations.
- [x] Add the persisted Proposed/Accepted/Completed/Dismissed recommendation lifecycle.
- [x] Extend the synthetic demo with multi-source host, DNS, network, file, and user pivots.

**Exit demo:** the application connects a file execution to process and network activity, then proposes a useful, justified next step without taking autonomous action.

## Phase 7 - Privacy-controlled intelligence (foundation implemented in v0.7.0)

- [x] Implement the policy gate, disclosure preview, environment-only credential reference, cache lifetime, and provider assertion model.
- [ ] Integrate Public Suffix List and locally cached MITRE ATT&CK data when relationship rules consume them.
- [x] Add manual entry, versioned local assertion import, and a VirusTotal v3 existing-object report connector; evaluate additional providers only against reliability and licensing requirements.
- [x] Display conflicting assertions without a universal score.
- [x] Record provider, query value, retrieval/data time, expiry/cache state, origin, source reference, and raw-response hash.

**Exit achieved for the v0.7 connector boundary:** offline cases remain fully functional; connected lookups show exactly what leaves the workstation and keep provider claims separate from local facts.

## Phase 8 - Packaging quality and handoffs

- Add redaction profiles and cross-artifact preview.
- [x] Add timeline CSV and relationship graph JSON to the verified capsule.
- Add optional PDF and ZIP capsule projections.
- Add verification utility and evaluate detached signatures.
- Add one reviewed platform handoff such as TheHive, MISP, OpenCTI, or Timesketch.
- Package a Windows installer; test upgrades, migrations, and clean-machine launch.

**Exit:** internal, redacted, executive, and machine handoffs are reliable, verifiable, and clearly scoped.

## Phase 9 - Broader ecosystem, only after validation

- Zeek, Plaso, Velociraptor result, ECS, Parquet, and OCSF adapters.
- Read-only Wazuh/OpenSearch or SIEM query connectors with query provenance.
- Small multi-observable cases and saved investigation templates.
- Optional local prose drafting with citations and analyst approval.
- Evaluate signed activity history, importable capsules, and collaboration handoff—not real-time multi-user editing by default.

**Exit:** each addition improves the evidence-to-handoff workflow without turning the application into a SIEM, SOAR, collector, or intelligence platform.

## Portfolio proof checklist

- Safe multi-source golden incident and deterministic outputs.
- Polished New Investigation wizard and evidence/coverage workflow.
- Before/after analyst task timing and review exercise.
- Screenshots of Dashboard, Evidence, Coverage, Timeline, and Export preview.
- Demonstration of one match, one benign lookalike, one missing source, one failed record, and one partial interval.
- Trace from dashboard statement to evidence ID to source digest/position.
- Offline network test and disclosure-plan demonstration.
- Security tests for hostile content, paths, formulas, malformed records, and secrets.
- Verified Full Internal and Redacted Shareable Case Capsules.
- Architecture, implementation tradeoffs, known limitations, and a short demo video.

## Prioritization rule

Do not begin a later phase because it looks impressive in isolation. Begin it when the preceding exit condition works in the desktop application, has synthetic test evidence, and remains understandable to a second analyst.
