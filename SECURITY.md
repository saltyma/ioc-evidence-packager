# Security and Responsible Evidence Handling

## Current maturity

The repository is a scaffold and must not yet be used as a forensic production tool. There is no stable release, security support window, or validated evidence-processing implementation.

## Reporting a vulnerability

Do not publish sensitive exploit details, real evidence, credentials, or personal data in a public issue. Use GitHub's private vulnerability reporting feature when enabled for this repository. If it is unavailable, contact the repository owner through a private channel before disclosure.

## Data-handling rules

- Use synthetic or explicitly approved, sanitized logs during development.
- Never commit production telemetry, access tokens, customer names, internal hostnames, or active malware.
- Work on copies of exported evidence; never modify originals.
- Store outputs only in approved locations and review them before sharing.
- Remember that HTML/PDF/JSON reports may reproduce sensitive source fields.
- A SHA-256 manifest detects changes but does not establish acquisition history or legal admissibility.

## Planned defensive controls

- No network access in the core packaging path.
- Input size/depth limits and streaming ingestion.
- Parameterized SQLite queries.
- Jinja2 auto-escaping and safe URL/path handling.
- Output-directory confinement and overwrite protection.
- Separation of raw evidence, normalized values, correlations, and analyst conclusions.
- Explicit counts for skipped files and rejected records.
- Security tests using malicious HTML, traversal strings, malformed Unicode/JSON, and oversized fields.

## External enrichment

Any future enrichment must be opt-in. The UI/CLI must clearly identify the provider and data leaving the workstation, avoid sending entire events, protect API keys, obey provider terms, and record the request time/provider in the manifest.

## Supported versions

No versions are currently supported. This section will be updated when the first release is published.
