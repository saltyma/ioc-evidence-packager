# Complete Manual Demo Guide

This is the operator walkthrough for IOC Evidence Packager v0.7.0. It exercises the real application from case creation through a verified Case Capsule. It is deliberately separate from the future investigation-game/playbook.

The demo is entirely synthetic and works offline. Use the documentation-only IPv4 address `203.0.113.42`; do not substitute a personal, Kali, public, or production address.

## Verified outcome

The repository fixtures were re-run end to end against v0.7.0. A correct run produces:

| Checkpoint | Expected result |
|---|---:|
| Selected evidence sources | 11 |
| Preview states | 9 Ready, 1 Warning, 1 Unsupported |
| Durable evidence | 23 |
| Structured rejections | 1 intentional `invalid_json` rejection |
| Direct IPv4 sightings | 8 |
| Context evidence | 15 |
| Timeline | 23 dated rows, 0 undated |
| Timeline bounds | `2026-08-06 09:11:31Z` to `09:15:00Z` |
| Relationship graph | 47 nodes, 113 evidence-backed edges |
| Recommendations | 4: 2 Immediate, 2 Useful |
| Intelligence import | 2 assertions, both marked as conflicting |
| Capsule | 8 hashed artifacts plus `manifest.json`; verification passes |

IDs and export hashes are case/export-specific. Compare the counts, states, rules, and verifier result—not IDs from a different run.

## 1. Prepare the application

Requirements:

- Windows with PowerShell;
- Python 3.11 or newer;
- the repository at `D:\Porfolio\ioc-evidence-packager`.

Open PowerShell and run:

```powershell
cd D:\Porfolio\ioc-evidence-packager
python --version
python -m pip install -e ".[dev]"
```

If `python --version` is older than 3.11, use an installed 3.11+ interpreter instead.

Optional preflight:

```powershell
python tools\verify_demo.py
python -m pytest -q
python -m ioc_evidence_packager --smoke-test --smoke-demo --smoke-page Dashboard
```

`verify_demo.py` hashes all 13 fixtures and checks the complete offline pipeline against the expected counts above. The smoke command uses a temporary database, opens briefly, and exits automatically. Neither replaces the manual walkthrough.

## 2. Start with an isolated demo database

Using a separate database keeps the demonstration out of the normal case store and avoids deleting anything.

```powershell
$demoRoot = Join-Path $env:LOCALAPPDATA "IOC Evidence Packager\Demos"
New-Item -ItemType Directory -Path $demoRoot -Force | Out-Null
$demoDb = Join-Path $demoRoot ("manual-demo-{0}.sqlite3" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
python -m ioc_evidence_packager --database "$demoDb"
```

Keep this PowerShell window open. To reopen the same run later, launch the application again with the same path printed in `$demoDb`:

```powershell
$demoDb
python -m ioc_evidence_packager --database "$demoDb"
```

## 3. Create the investigation

On **Cases**, select **New investigation**.

### Step 1 — Lead

Enter exactly:

| Field | Value |
|---|---|
| Case title | `Suspicious download on FIN-WS-014` |
| External reference | `DEMO-IR-2026-001` |
| Lead observable | `203.0.113.42` |
| Display time zone | `UTC` |
| Summary | `Synthetic triage of a suspicious download and follow-on connection.` |

The lead validation card should identify an IPv4 value and show the same canonical value. Select **Next**.

### Step 2 — Evidence sources

Select **Add evidence files** and open:

```text
D:\Porfolio\ioc-evidence-packager\samples\input\demo-investigation
```

Select these eleven files:

```text
01-dns-events.jsonl
02-endpoint-events.jsonl
03-network-events.jsonl
04-authentication-events.jsonl
05-partial-with-warning.jsonl
06-unsupported-siem-export.csv
07-suricata-eve.jsonl
08-wazuh-alerts.jsonl
09-hayabusa-results.jsonl
10-generic-array.json
11-mapped-proxy.csv
```

Do not select:

- `11-mapped-proxy.csv.ioc-map.json` — the CSV adapter discovers this sidecar automatically;
- `12-intelligence-assertions.json` — this is provider context, not evidence;
- `README.md`.

Wait until every preview job finishes. Clicking a source row opens the non-modal details window with its full path, SHA-256, adapter, fields, capabilities, time bounds, and warnings.

Expected preview:

| Source | State | Samples | Adapter |
|---|---:|---:|---|
| `01-dns-events.jsonl` | Ready | 3 | `canonical-jsonl` |
| `02-endpoint-events.jsonl` | Ready | 4 | `canonical-jsonl` |
| `03-network-events.jsonl` | Ready | 3 | `canonical-jsonl` |
| `04-authentication-events.jsonl` | Ready | 2 | `canonical-jsonl` |
| `05-partial-with-warning.jsonl` | Warning | 1 | `canonical-jsonl` |
| `06-unsupported-siem-export.csv` | Unsupported | 0 | none |
| `07-suricata-eve.jsonl` | Ready | 2 | `suricata-eve-jsonl` |
| `08-wazuh-alerts.jsonl` | Ready | 2 | `wazuh-alert-jsonl` |
| `09-hayabusa-results.jsonl` | Ready | 2 | `hayabusa-jsonl` |
| `10-generic-array.json` | Ready | 2 | `generic-json-array` |
| `11-mapped-proxy.csv` | Ready | 2 | `mapped-csv` |

The Warning and Unsupported states are intentional:

- source 05 contains one valid line and one malformed line, demonstrating partial processing;
- source 06 has no mapping sidecar, demonstrating that the application refuses to guess CSV semantics.

### Step 3 — Review

Select **Next**. Confirm:

- the case and canonical lead are correct;
- 11 sources are listed;
- the policy is Offline;
- source bytes have not been imported yet.

Select **Create investigation**.

## 4. Import the evidence

The new case opens on Dashboard with zero evidence because preview and import are separate operations.

1. Open **Evidence**.
2. Select **Import previewed sources**.
3. Watch the Jobs indicator and progress text.
4. Wait for the job to finish.

Expected Evidence state:

- `Evidence · 23`;
- `Rejections · 1`;
- the rejection is source 05, line 2, code `invalid_json`;
- the unsupported source contributes no records and remains visible in Sources/Coverage.

Click a normal evidence row. The popup should show labeled, wrapping, color-coded values including the Evidence ID, classification, source path/hash, positions, observables, rule explanation, and preserved source record.

Open **Rejections**, then click its only row. The popup should show the stable code, safe message, line, and bounded excerpt. This rejected line is not evidence.

### Verify idempotent retry

Select **Import previewed sources** again and let it finish. The importer processes the same valid lines, but the durable totals must remain:

- 23 evidence records;
- 1 rejection.

## 5. Walk through every workspace

### Dashboard

Expected cards:

- Lead observables: `1`;
- Evidence records: `23` with one rejection;
- Direct sightings: `8` exact IPv4 matches;
- Coverage: one matched recipe step and two limitations.

The timeline summary should span `2026-08-06 09:11:31 UTC` through `09:15:00 UTC`.

### Evidence

Use the classification filter:

| Filter | Expected rows |
|---|---:|
| All evidence | 23 |
| Direct matches | 8 |
| Context | 15 |
| Undated | 0 |

Useful searches:

- `203.0.113.42` — the lead IPv4;
- `cdn-update.example.test` — the exact suspicious domain;
- `198.51.100.25` — a documentation-only context IP, not the lead;
- `cdn-updates.example.test` — a deliberately similar domain that must not match;
- `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` — the synthetic SHA-256.

Clear the search before moving on.

### Timeline

Expected:

- 23 rows;
- 8 Direct and 15 Context;
- no Undated rows;
- first event at `09:11:31 UTC` and last event at `09:15:00 UTC`.

Click a row to inspect its provenance and preserved source record. Use the text and classification filters to verify that Timeline and Evidence describe the same records.

### Relationships

Expected summary: 47 typed nodes and 113 evidence-backed edges.

1. In the focus selector, choose `IPV4 · 203.0.113.42`.
2. Observe the bounded one-hop graph rather than an unbounded hairball.
3. Change the relationship filter to `resolved to`.
4. Search for `cdn-update.example.test`.
5. Open **Evidence-backed edges** and click a row.

The detail popup must identify From/To types and values, relation, rule ID, explanation, and supporting evidence IDs.

Select **Pivot to Evidence**. The app should open Evidence with the related entity value already filtered.

### Coverage

Expected states:

| Recipe/diagnostic | Expected state | Meaning |
|---|---|---|
| DNS resolution | `MATCH_FOUND` | The lead occurs in compatible DNS evidence |
| Network endpoint | `PARTIAL_COVERAGE` | Valid records exist, but source 05 has a rejected line/warning |
| Authentication origin | `SEARCHED_NO_MATCH` | Compatible authentication evidence was searched without a lead match |
| Source 06 diagnostic | `FORMAT_UNSUPPORTED` | No adapter/mapping authorizes its fields |

Click every row to inspect the calculation, stable reason code, recovery action, supporting sources, and evidence IDs. **Re-run analysis** should reproduce the same states and 8 sightings.

`SEARCHED_NO_MATCH` is not “safe,” and `FORMAT_UNSUPPORTED` is not a negative search result.

### Intelligence

Keep the case Offline. No API key or network request is required.

1. Select **Import assertion file**.
2. Choose `samples\input\demo-investigation\12-intelligence-assertions.json`.
3. Confirm two rows appear.
4. Set the filter to **Conflicts only**.

Expected assertions for `203.0.113.42`:

- Synthetic TI Alpha: `Malicious`, Demo high confidence;
- Synthetic TI Beta: `Benign`, Demo medium confidence.

Both rows must display `CONFLICT`. Click each row to inspect provider/version, origin, native confidence, summary, retrieval/data/expiry times, source reference, and response/file digest.

The fixture expires on 2026-08-13. Before then it displays Fresh; afterward it correctly displays Expired. Expiry does not delete it or resolve the conflict.

These are synthetic provider assertions. They do not change the 8 direct sightings and do not prove compromise.

Optional checks:

- use **Add manual assertion** to add clearly labeled analyst/provider context;
- archive it and confirm it leaves the active table while remaining in SQLite audit history.

The VirusTotal connector is not required for this demo. Leave it disabled unless you intentionally configure an API key and Safe Enrichment policy.

### Recommendations

Expected four Proposed recommendations:

| Priority | Recommendation |
|---|---|
| Immediate | Complete partial telemetry for Network endpoint |
| Immediate | Preserve and review direct-match records |
| Useful | Map unsupported telemetry for `06-unsupported-siem-export.csv` |
| Useful | Pivot across DNS resolutions |

Click each row and verify its rationale, expected value, safety note, action, rule/version, and citations.

Exercise the lifecycle:

1. select **Preserve and review direct-match records**;
2. select **Accept**;
3. select the row again and choose **Mark completed**;
4. select the unsupported-source recommendation and choose **Dismiss with reason**;
5. enter `Known unsupported fixture retained to demonstrate diagnostics.`;
6. use the state filter to review Completed and Dismissed items.

For a recommendation with evidence citations, select **Open cited evidence**. Evidence should open with exactly the cited evidence ID filtered. Clear the filter afterward.

Analyst states and dismissal reasons persist and are included in a Full Internal capsule. Redacted Shareable omits analyst-note text.

### Sources

Expected per-source durable counts:

| Source group | Accepted | Rejected |
|---|---:|---:|
| Sources 01–04 | 12 | 0 |
| Source 05 | 1 | 1 |
| Source 06 | 0 | 0 |
| Sources 07–11 | 10 | 0 |

Click source 11 and confirm the `mapped-csv` adapter, mapped/searchable fields, capabilities, CSV SHA-256, and mapping-profile identity are visible. Click sources 05 and 06 to compare Warning and Unsupported diagnostics.

### Settings

For the baseline demo:

- Case privacy mode: Offline;
- Display timezone: UTC;
- VirusTotal connector: disabled.

To test presentation preferences safely:

1. open **Appearance**;
2. set the detail popup width to `700 px`;
3. optionally switch between Comfortable and Compact;
4. keep semantic colors enabled;
5. select **Save settings**;
6. reopen any table row and confirm the popup uses the new bounded width.

Open **Storage & versions** and confirm application v0.7.0 and SQLite schema 6.

## 6. Build and verify a Case Capsule

Open **Exports**.

1. Select **Redacted Shareable**.
2. Select **Browse parent…** and choose a writable parent directory.
3. The app creates a new non-existing capsule-directory name automatically.
4. Select **Build and verify capsule**.
5. Wait for the background job.

Expected success text: 8 artifacts verified and published. The directory contains nine files because `manifest.json` indexes the eight hashed artifacts:

```text
report.html
evidence.jsonl
timeline.csv
coverage.json
source-inventory.json
relationships.json
recommendations.json
intelligence.json
manifest.json
```

Redacted Shareable should omit source paths/raw JSON and replace host/user values and graph IDs with capsule-local pseudonyms.

Click the export-history row to inspect profile, destination, artifact count, and manifest SHA-256. Then select **Verify existing capsule…**, choose the new capsule directory, and confirm `VERIFIED · 8 artifact(s)`.

Open `report.html` in a browser and review Coverage, Evidence, Relationships, Recommendations, Intelligence, Sources, and Limitations. The report is self-contained and does not fetch remote assets.

Optional PowerShell integrity view:

```powershell
Get-Content "<capsule-path>\manifest.json"
Get-ChildItem "<capsule-path>" -File | Get-FileHash -Algorithm SHA256
```

Do not edit the capsule before verifying it. Any artifact change should produce a hash/size failure.

## 7. Confirm persistence

Close the app normally, then reopen the same database:

```powershell
python -m ioc_evidence_packager --database "$demoDb"
```

Open the recent case. Confirm:

- 23 evidence records and one rejection remain;
- analysis, coverage, graph, and recommendations rebuild consistently;
- recommendation lifecycle changes remain;
- both intelligence assertions remain;
- export history remains;
- case Settings remain.

## 8. Troubleshooting

### Import button is disabled

- Wait for every preview job to finish.
- Ensure at least one Ready/Warning evidence source is selected.
- Do not select only source 06, the mapping sidecar, intelligence file, or README.

### Source 06 is Unsupported

This is correct. It deliberately has no mapping profile.

### Source 11 is Unsupported

Keep `11-mapped-proxy.csv.ioc-map.json` beside the CSV. Do not rename, move, edit, or select the sidecar separately.

### Source 05 produces a rejection

This is correct. Its malformed second line creates one `invalid_json` rejection while its first line becomes evidence.

### Intelligence import fails

Import source 12 from Intelligence, not Evidence. The complete file SHA-256 is listed below; restore the repository copy if it differs.

### Capsule export says the destination exists

Exports never overwrite an existing directory. Use **Browse parent…** again or accept the next generated suffix.

### VirusTotal button is disabled

That is correct for the Offline demo. Remote lookup requires a Safe Enrichment/Enterprise case mode, the device provider toggle, an environment API key, and disclosure confirmation.

### IDs differ from the checked example capsule

Expected. Case, run, evidence, export, and capsule-local pseudonym IDs are generated per run. The verifier, counts, states, citations, and rules are the comparison points.

## Appendix A — Fixture checksums

Use this command to compare your local files:

```powershell
Get-ChildItem .\samples\input\demo-investigation -File |
    Get-FileHash -Algorithm SHA256 |
    Sort-Object Path
```

| File | SHA-256 |
|---|---|
| `01-dns-events.jsonl` | `e20a70beb42d5b009e2707aa728a12e61ecd7e6ef0c3ae0fb98f9d006f231661` |
| `02-endpoint-events.jsonl` | `af71027aa8e1af38a27242a2e968c83eefa3c7cd1314b7e040ead6078bc64c00` |
| `03-network-events.jsonl` | `82a0dfdbe4c5a18ae155c0aa3647fbc9d8fa518f51f155a631e60c219699fa44` |
| `04-authentication-events.jsonl` | `978ebc4d3a396c2018c21178917718ddcacaf8390c96dd8f1108c5ad67b3f74e` |
| `05-partial-with-warning.jsonl` | `8fce4bfbb3167ba323260c878825e63154506ac4e0e2243c5b90c2e11c270229` |
| `06-unsupported-siem-export.csv` | `ebd7c3fe81e5653e078082b29435fa27a3b37f08f9ead7fbbf94241a457144ce` |
| `07-suricata-eve.jsonl` | `b806f2db3a98d92725304025de4c296e91ee639f713f0440ce4af6a14aabbd5a` |
| `08-wazuh-alerts.jsonl` | `687a9b080f2c32e0751ec91a4656aef86a6ab417bf21348899216d0526026482` |
| `09-hayabusa-results.jsonl` | `a9d96d6703916cca37be202babeb35b30506357689313c39de297430f8e33089` |
| `10-generic-array.json` | `c1ce90cd8aeabfc3d57f819b755648dc06cf4c71a7a02c71ce5b585bae68bbb5` |
| `11-mapped-proxy.csv` | `74fef217e0bd3a47bcdf95eaa6ff8bdc0104005137eaf0368b9ff5cbfdf0c931` |
| `11-mapped-proxy.csv.ioc-map.json` | `7ce87df151b448606bb9bd93b1d35dc42aa249cbc77461f7e67134525fdcb977` |
| `12-intelligence-assertions.json` | `dc0f0c11ac253e6c7b19a15c64a77b79c9d5b4bdce36e1c0b5cf72fe3441f4b8` |

## Appendix B — Automated demonstration screenshots

To render a temporary automatic demo page without touching the normal database:

```powershell
python -m ioc_evidence_packager `
    --smoke-test `
    --smoke-demo `
    --smoke-page Recommendations `
    --screenshot "$env:TEMP\ioc-packager-recommendations.png"
```

Valid smoke pages are Dashboard, Evidence, Timeline, Relationships, Coverage, Intelligence, Recommendations, Sources, Exports, and Settings.
