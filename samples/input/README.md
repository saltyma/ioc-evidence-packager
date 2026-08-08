# Synthetic input fixtures

Only safe, synthetic log exports belong here. Use IANA-reserved example ranges such as `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `2001:db8::/32`, and reserved `.test` domains.

Each fixture must document its schema/source, adapter capability, planted sightings and pivots, benign lookalikes, expected rejected records, time-zone assumptions, time/entity coverage, and the scenario it demonstrates. The golden incident should deliberately exercise all six coverage states rather than containing only successful inputs.

Never add production logs, personal data, credentials, active malware, real victim indicators, or provider responses whose terms prohibit redistribution.

## Current reference fixture

`canonical-demo.jsonl` implements the canonical event v1 envelope and contains three safe synthetic DNS, process, and network events. It exercises source hashing, adapter detection, ingestion, observable recipes, coverage, Timeline, and capsule export.

## Runnable demo investigation

`demo-investigation/` is the recommended hands-on pack. Its README provides exact case values, four coherent canonical JSONL exports, planted sightings and benign lookalikes, expected preview/import/match/coverage results, an intentionally malformed JSONL file, and an intentionally unsupported CSV export.
