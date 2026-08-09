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

Then add the five practical-adapter fixtures:

- `07-suricata-eve.jsonl` — selected Suricata DNS/alert fields;
- `08-wazuh-alerts.jsonl` — selected Wazuh authentication/network alert fields;
- `09-hayabusa-results.jsonl` — selected Hayabusa DNS/file fields;
- `10-generic-array.json` — a bounded flat JSON array;
- `11-mapped-proxy.csv` — CSV authorized by the adjacent `11-mapped-proxy.csv.ioc-map.json` mapping profile.

Do not select the `.ioc-map.json` sidecar separately. The CSV adapter discovers it next to the CSV and validates its schema and mapped headers.

The two diagnostic fixtures can be selected alongside the supported files:

- `05-partial-with-warning.jsonl` contains one valid event followed by intentionally malformed JSON. It should show **Warning** while retaining the valid sampled event.
- `06-unsupported-siem-export.csv` is a realistic safe CSV export with no mapping sidecar. It stays **Unsupported** because the application refuses to guess column meaning from header names alone.

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
| `06-unsupported-siem-export.csv` | Unsupported | 0 | none without an explicit mapping profile |
| `07-suricata-eve.jsonl` | Ready | 2 | domain, IPv4, UTC timestamp |
| `08-wazuh-alerts.jsonl` | Ready | 2 | IPv4, UTC timestamp |
| `09-hayabusa-results.jsonl` | Ready | 2 | domain, SHA-256, UTC timestamp |
| `10-generic-array.json` | Ready | 2 | domain, IPv4, UTC timestamp |
| `11-mapped-proxy.csv` | Ready | 2 | domain, IPv4, UTC timestamp |

## Expected import

| Selection | Durable evidence | Rejections | Notes |
|---|---:|---:|---|
| Four clean JSONL files | 12 | 0 | Complete successful run |
| Four clean files plus `05-partial-with-warning.jsonl` | 13 | 1 | The valid line is accepted; malformed line 2 is an `invalid_json` rejection |
| `06-unsupported-siem-export.csv` | 0 | 0 | It has no mapping sidecar and is not eligible for import |
| Five Phase 5 practical-adapter files | 10 | 0 | Two records from each adapter enter the same durable ledger |
| All eleven evidence files | 23 | 1 | Six adapter families are supported; the unmapped CSV stays visible but ineligible |

Importing the same previewed sources again does not duplicate durable evidence. If a file is changed after preview, the importer creates a `source_hash_mismatch` rejection and accepts no records from that source.

## Expected IPv4 analysis and coverage

With the lead `203.0.113.42` and all eleven evidence files selected:

- eight direct sightings are created: four canonical sightings plus Suricata DNS, Wazuh network, generic JSON network, and mapped CSV network sightings;
- the `198.51.100.25` address and similarly named domain remain context, never matches;
- DNS is `MATCH_FOUND`;
- network is `PARTIAL_COVERAGE` because one compatible source contains a rejected line;
- authentication is `SEARCHED_NO_MATCH`, which is neutral rather than a claim of safety;
- the unmapped CSV receives a `FORMAT_UNSUPPORTED` diagnostic cell.

Dashboard summarizes the results, Evidence exposes every rule and source position, Timeline orders all 23 accepted events, Sources compares every adapter and limitation, and Exports can build either a Full Internal or Redacted Shareable capsule. A checked redacted example is available in [`samples/expected/demo-capsule-redacted`](../../expected/demo-capsule-redacted).

## Scenario truth and expected evidence

The synthetic story is deliberately small but connected:

1. User `analyst-demo` signs in to `FIN-WS-014` at `09:11:31Z`.
2. The workstation queries `cdn-update.example.test`, which resolves to `203.0.113.42`.
3. `powershell.exe`, launched by `outlook.exe`, references the same domain.
4. A file named `invoice-review.exe` is written with the placeholder SHA-256 `aaaa…aaaa` and then executed.
5. The workstation connects twice to `203.0.113.42:443` using the same domain as TLS SNI.
6. `cdn-updates.example.test`, `198.51.100.25`, `invoice-reviewer.exe`, and the `bbbb…bbbb` hash are benign lookalikes. Exact matching must not confuse them with the lead values.
7. Authentication data provides host/user context but does not prove that the suspicious observable caused the login.
8. The Phase 5 formats deliberately restate a subset of the same synthetic observations through different tool/export schemas. They prove normalization and provenance interoperability, not independent corroboration from real systems.

These are planted facts for deterministic development—not a claim that any address, domain, hash, user, or process is malicious.
