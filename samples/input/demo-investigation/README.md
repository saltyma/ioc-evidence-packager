# Workstation download demo investigation

This directory is a safe, fully synthetic incident pack for exercising the **New Investigation** wizard. It contains no production telemetry, credentials, malware, or live infrastructure.

## Suggested case setup

| Field | Value |
|---|---|
| Case title | `Suspicious download on FIN-WS-014` |
| External reference | `DEMO-IR-2026-001` |
| Lead observable | `203.0.113.42` |
| Alternate domain lead | `cdn-update.example.test` |
| Alternate SHA-256 lead | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` |
| Display time zone | `UTC` |
| Summary | `Synthetic triage of a suspicious download and follow-on connection.` |

`203.0.113.42` is from an IANA documentation-only range. The domains use the reserved `.test` suffix, the workstation address is private, and the hashes are repeated placeholder characters.

## Files to select

Start by selecting the four clean files together:

1. `01-dns-events.jsonl`
2. `02-endpoint-events.jsonl`
3. `03-network-events.jsonl`
4. `04-authentication-events.jsonl`

The wizard hashes each complete file, inspects a bounded sample, and shows the detected fields, capabilities, UTC range, and warnings. After creating the investigation, open **Evidence** and choose **Import previewed sources**. Import runs in the background and can be cancelled safely between bounded batches.

Then try the two diagnostic fixtures separately or alongside the clean files:

- `05-partial-with-warning.jsonl` contains one valid event followed by intentionally malformed JSON. It should show **Warning** while retaining the valid sampled event.
- `06-unsupported-siem-export.csv` is a realistic safe CSV export. It should show **Unsupported** because a CSV mapping adapter has not been implemented yet.

At least one selected file must be recognized as Ready or Warning before the wizard can create the investigation.

![Expected source-preview screen](../../../docs/assets/source-preview-demo.png)

## Expected preview

| File | Expected state | Sampled records | Important capabilities |
|---|---:|---:|---|
| `01-dns-events.jsonl` | Ready | 3 | domain, IPv4, UTC timestamp |
| `02-endpoint-events.jsonl` | Ready | 4 | domain, SHA-256, UTC timestamp |
| `03-network-events.jsonl` | Ready | 3 | domain, IPv4, UTC timestamp |
| `04-authentication-events.jsonl` | Ready | 2 | IPv4, UTC timestamp |
| `05-partial-with-warning.jsonl` | Warning | 1 | IPv4, UTC timestamp |
| `06-unsupported-siem-export.csv` | Unsupported | 0 | none until a CSV adapter exists |

## Expected import

| Selection | Durable evidence | Rejections | Notes |
|---|---:|---:|---|
| Four clean JSONL files | 12 | 0 | Complete successful run |
| Four clean files plus `05-partial-with-warning.jsonl` | 13 | 1 | The valid line is accepted; malformed line 2 is an `invalid_json` rejection |
| `06-unsupported-siem-export.csv` | 0 | 0 | It is not eligible for the canonical JSONL importer |

Importing the same previewed sources again does not duplicate durable evidence. If a file is changed after preview, the importer creates a `source_hash_mismatch` rejection and accepts no records from that source.

## Expected IPv4 analysis and coverage

With the lead `203.0.113.42` and all six files selected:

- four direct sightings are created: DNS line 2, network lines 1 and 2, and partial-file line 1;
- the `198.51.100.25` address and similarly named domain remain context, never matches;
- DNS is `MATCH_FOUND`;
- network is `PARTIAL_COVERAGE` because one compatible source contains a rejected line;
- authentication is `SEARCHED_NO_MATCH`, which is neutral rather than a claim of safety;
- the CSV receives a `FORMAT_UNSUPPORTED` diagnostic cell.

Dashboard summarizes the results, Evidence exposes every rule and source line, Timeline orders all 13 accepted events, and Exports can build either a Full Internal or Redacted Shareable capsule. A checked redacted example is available in [`samples/expected/demo-capsule-redacted`](../../expected/demo-capsule-redacted).

## Scenario truth and expected evidence

The synthetic story is deliberately small but connected:

1. User `analyst-demo` signs in to `FIN-WS-014` at `09:11:31Z`.
2. The workstation queries `cdn-update.example.test`, which resolves to `203.0.113.42`.
3. `powershell.exe`, launched by `outlook.exe`, references the same domain.
4. A file named `invoice-review.exe` is written with the placeholder SHA-256 `aaaa…aaaa` and then executed.
5. The workstation connects twice to `203.0.113.42:443` using the same domain as TLS SNI.
6. `cdn-updates.example.test`, `198.51.100.25`, `invoice-reviewer.exe`, and the `bbbb…bbbb` hash are benign lookalikes. Exact matching must not confuse them with the lead values.
7. Authentication data provides host/user context but does not prove that the suspicious observable caused the login.

These are planted facts for deterministic development—not a claim that any address, domain, hash, user, or process is malicious.
