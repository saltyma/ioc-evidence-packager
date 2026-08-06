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

The wizard hashes each complete file, inspects a bounded sample, and shows the detected fields, capabilities, UTC range, and warnings. Slice 2 stores this preview metadata; it does not import the records yet.

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

## Scenario truth for future slices

The synthetic story is deliberately small but connected:

1. User `analyst-demo` signs in to `FIN-WS-014` at `09:11:31Z`.
2. The workstation queries `cdn-update.example.test`, which resolves to `203.0.113.42`.
3. `powershell.exe`, launched by `outlook.exe`, references the same domain.
4. A file named `invoice-review.exe` is written with the placeholder SHA-256 `aaaa…aaaa` and then executed.
5. The workstation connects twice to `203.0.113.42:443` using the same domain as TLS SNI.
6. `cdn-updates.example.test`, `198.51.100.25`, `invoice-reviewer.exe`, and the `bbbb…bbbb` hash are benign lookalikes. Exact matching must not confuse them with the lead values.
7. Authentication data provides host/user context but does not prove that the suspicious observable caused the login.

These are planted facts for deterministic development—not a claim that any address, domain, hash, user, or process is malicious.
