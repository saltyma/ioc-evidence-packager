# Roadmap

The roadmap is GUI-first and vertical. Every phase ends in a demonstrable analyst outcome while the evidence core stays headless and testable. Dates remain absent until the first two slices establish real velocity.

## Phase 0 - Product conception (current)

- Define the product vision, users, workflow, positioning, and guardrails.
- Specify GUI information architecture and interaction rules.
- Define facts, sightings, correlations, intelligence assertions, and assessments.
- Specify Evidence Coverage Matrix states and Case Capsule contract.
- Select PySide6, headless services, SQLite, and canonical JSONL for the first slice.
- Document adapter, enrichment, privacy, and handoff contracts.

**Exit:** implementation can begin without deciding what the product is during coding.

## Phase 1 - Desktop shell and durable cases

- Add PySide6 application entry point and native main window.
- Implement Home, recent cases, case shell, navigation, and visible Offline policy.
- Add SQLite migrations, repositories, transactional case creation/opening, and recovery state.
- Establish command/query ports and the job coordinator interface.
- Add domain tests, migration tests, and an offscreen Qt smoke test.

**Exit demo:** create a case, close the application, reopen it, and recover the same accurate state.

## Phase 2 - Guided evidence import

- Implement IPv4, domain, and SHA-256 value objects.
- Publish canonical JSONL schema and build the golden synthetic incident.
- Implement wizard lead, source, mapping, privacy, and review steps.
- Hash and preview sources, adapter capabilities, timestamps, fields, and warnings.
- Stream imports in background batches with progress, cancellation, retry, and structured rejections.

**Exit demo:** preview exactly how evidence will be interpreted, import it without freezing the UI, cancel safely, and trace accepted/rejected counts.

## Phase 3 - Evidence and coverage core

- Implement versioned IOC search recipes and structured direct-match explanations.
- Build the Evidence ledger, filters, raw/provenance drawer, bookmarks, and annotations.
- Implement the six Evidence Coverage Matrix states and calculation reasons.
- Add Dashboard summaries and a basic deterministic Timeline.
- Test planted matches, lookalikes, duplicates, missing sources, partial intervals, and invalid timestamps.

**Exit demo:** find all planted sightings, explain every inclusion, and show why missing or partial telemetry limits the conclusion.

## Phase 4 - Portable Case Capsule

- Build the shared immutable report model.
- Render self-contained HTML, evidence JSONL, coverage JSON, inventory JSON, and final manifest.
- Add safe destination validation, artifact hashes, verification, and export history.
- Add a checked-in example capsule and screenshots from synthetic data.
- Establish semantic determinism and security fixtures.

**Exit demo:** another analyst can open and verify the exported investigation without installing the application or accessing original consoles.

## Phase 5 - Practical adapters

- Add generic JSON arrays and CSV mapping profiles.
- Add selected Wazuh JSON, Hayabusa JSONL, and Suricata `eve.json` adapters.
- Add source capability coverage, schema-drift diagnostics, and time-zone fixtures.
- Measure performance and introduce improved batching/indexes; evaluate DuckDB only from evidence.

**Exit:** at least four meaningfully different safe sources produce one coherent, source-linked timeline and coverage matrix.

## Phase 6 - Relationships and next actions

- Add typed entity relationships and one-hop bounded graph/table views.
- Add observable pivots that preserve their origin.
- Implement deterministic next-action rules with evidence and coverage citations.
- Add analyst assessment and recommendation lifecycle.
- Extend the golden case with multi-host process/network pivots.

**Exit demo:** the application connects a file execution to process and network activity, then proposes a useful, justified next step without taking autonomous action.

## Phase 7 - Privacy-controlled intelligence

- Implement the policy gate, disclosure preview, credential references, cache, and provider assertion model.
- Integrate Public Suffix List and locally cached MITRE ATT&CK data.
- Add a small reliable provider set, starting with CIRCL hashlookup and selected abuse.ch services; evaluate RDAP and GreyNoise next.
- Display conflicting assertions without a universal score.
- Record provider, query, time, cache, raw-response hash, limits, and errors.

**Exit:** offline cases remain fully functional; connected cases show exactly what left the workstation and keep provider claims separate from local facts.

## Phase 8 - Packaging quality and handoffs

- Add redaction profiles and cross-artifact preview.
- Add timeline CSV, graph JSON, optional PDF, and ZIP capsule.
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
