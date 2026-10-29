# IOC Evidence Packager

[![Quality](https://github.com/saltyma/ioc-evidence-packager/actions/workflows/quality.yml/badge.svg)](https://github.com/saltyma/ioc-evidence-packager/actions/workflows/quality.yml)

Investigate a suspicious IP address, domain, or file fingerprint using exported security logs, then hand the findings to another analyst with their sources intact.

**Version 0.8.1. Python 3.11+. MIT license.** The desktop works offline and stores cases locally in SQLite.

An **IOC** (indicator of compromise) is a clue worth searching. You supply that clue and files from tools such as a firewall, endpoint monitor, DNS server, Wazuh, Suricata, or Hayabusa. The app shows where the exact value occurred, nearby activity, data that could not be searched, and records supporting each finding.

A **Case Capsule** is a portable handoff directory: a readable report, structured evidence files, and a manifest listing file hashes. Another analyst can verify that the exported files have not changed.

## Start here

```powershell
git clone https://github.com/saltyma/ioc-evidence-packager.git
cd ioc-evidence-packager
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m ioc_evidence_packager
```

On Linux, activate with `source .venv/bin/activate`. Windows is the primary desktop target. Linux is included in automated checks; desktop usability on each distribution still needs validation.

The [complete demo guide](docs/DEMO_GUIDE.md) gives exact inputs, clicks, expected results, and troubleshooting. Use documentation IP `203.0.113.42` and evidence files **01 through 11** from [the synthetic pack](samples/input/demo-investigation/README.md). Keep the `.ioc-map.json` sidecar beside its CSV; import file 12 later from Intelligence.

```powershell
python tools/verify_demo.py
python -m ioc_evidence_packager --smoke-test --smoke-demo
```

Expected demo: 23 evidence records, one intentional rejected line, eight IP sightings, 47 relationship nodes, 113 cited edges, and four recommendations. Retrying import preserves those totals. The two intelligence claims deliberately conflict and are expired after August 13, 2026.

## Investigation workflow

1. **Create a case.** Enter an IPv4, IPv6, domain, or SHA-256 lead. Optional start/end timestamps need an offset, such as `2026-08-06T09:00:00Z`.
2. **Preview sources.** Inspect detected format, SHA-256, mappings, time information, and warnings. Folder selection adds immediate JSON/JSONL/CSV children; review the selection for unrelated files.
3. **Import.** A background job rechecks source bytes and stores accepted evidence separately from rejected records. Cancellation and safe retry are supported.
4. **Review evidence.** Filter the ledger and click a row for provenance. The review button bookmarks, annotates, or excludes a record from export without changing source facts.
5. **Follow activity.** Timeline orders records in UTC. Relationships provides a cited edge table and interactive graph with zoom, pan, movable nodes, and evidence pivots.
6. **Check limits.** Coverage distinguishes matches, searched-no-match, partial data, missing sources, failed sources, and unsupported formats. A no-match does not establish that a system is clean.
7. **Review claims and actions.** Intelligence keeps provider claims separate from evidence. Recommendations cite their rules; accept, complete, or dismiss them with a reason.
8. **Preview and export.** Review the Full Internal or Redacted Shareable projection, build the capsule, and verify it. Select its history row to create a PDF print view or ZIP copy.

Rename or archive cases from Cases; Restore archived recovers them. Settings works without a case for device preferences and with a case for timezone/privacy preferences.

## Implemented scope

| Area | Supported |
|---|---|
| Leads | Exact normalized IPv4, IPv6, domain, SHA-256 |
| Inputs | Canonical JSONL, selected Suricata/Wazuh/Hayabusa JSONL, bounded JSON arrays, explicitly mapped CSV |
| Views | Dashboard, Evidence, Timeline, Relationships, Coverage, Intelligence, Recommendations, Sources, Exports, Settings |
| Review | Persistent bookmarks, notes, export selection, case rename/archive/restore |
| Time | Inclusive optional bounds; undated/out-of-window records stay stored but leave the scoped view |
| Intelligence | Manual/local JSON, conflicts, freshness, optional policy-gated VirusTotal reports |
| Handoff | Eight verified artifacts plus manifest, full/redacted profiles, preview, PDF/ZIP sidecars |
| Storage | SQLite schema 7 with migrations |
| Build | Windows/Linux CI and Windows distribution workflow |

Domains match exact normalized names; registrable-domain ownership grouping is future work. Generic JSON arrays have a 16 MiB limit. Selected vendor schemas are supported, rather than every export a product can produce. Unmapped CSV remains unsupported.

## Case Capsule

```text
case-capsule/
  report.html              Readable findings and limitations
  evidence.jsonl           Evidence and source references
  timeline.csv             Spreadsheet-safe chronology
  coverage.json            Search states and reasons
  source-inventory.json    File hashes, adapters, diagnostics
  relationships.json       Cited nodes and edges
  recommendations.json     Actions, lifecycle, citations
  intelligence.json        Attributed claims
  manifest.json            Expected sizes and SHA-256 hashes
```

The manifest is checked before publication. Full Internal includes source paths, preserved records, and analyst notes. Redacted Shareable omits raw records, paths, identifying case metadata, and notes, and pseudonymizes hosts/users. Review the preview before sharing; redaction has defined limits.

Excluding a record removes it from exported evidence and associated citations. Coverage still describes the searched case; the report discloses subset selection. PDF and ZIP are separate files outside the verified directory, preserving its manifest.

Independent verification and projection:

```powershell
python -m ioc_evidence_packager.capsule_cli "C:\Cases\case-capsule"
python -m ioc_evidence_packager.capsule_cli "C:\Cases\case-capsule" --format pdf --output "C:\Cases\handoff.pdf"
python -m ioc_evidence_packager.capsule_cli "C:\Cases\case-capsule" --format zip --output "C:\Cases\handoff.zip"
```

## Privacy and boundaries

Offline is the default. VirusTotal requires case policy, device enablement, an environment-only key, and confirmation of the exact disclosed value. It requests existing reports without uploading source files.

This app analyzes supplied exports. It does not collect endpoint data, run malware, monitor continuously, perform containment, or declare a host malicious. Hash verification detects changed exported bytes; it cannot establish source truth, acquisition history, or legal admissibility.

## Development and release

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
python tools/verify_demo.py
```

See [release/build instructions](docs/RELEASE.md), [changes](CHANGELOG.md), [contributing](CONTRIBUTING.md), and [security](SECURITY.md). Production support and code signing are separate commitments.

## Documentation

- [Project primer](docs/PROJECT_PRIMER.md): plain-language introduction.
- [Demo guide](docs/DEMO_GUIDE.md): complete offline investigation.
- [Release contract](docs/RELEASE.md): implemented scope and future extensions.
- [Architecture](docs/ARCHITECTURE.md): services, storage, adapters, trust boundaries.
- [Capsule contract](docs/CASE_CAPSULE.md): verification and redaction.
- [Features](docs/FEATURES.md), [roadmap](docs/ROADMAP.md), [scope study](docs/SCOPE.md): design and history.
- [Glossary](docs/GLOSSARY.md) and [references](docs/REFERENCES.md).

The local training game and book remain excluded from the public repository. The earlier synthetic demo is included.

## License

[MIT](LICENSE), copyright 2026 saltyma. Dependencies retain their own licenses.
