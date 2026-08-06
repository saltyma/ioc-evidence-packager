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

- Complete Offline mode: no provider calls, DNS resolution, update checks, remote UI assets, or telemetry.
- A policy gate and disclosure preview before every optional network connector receives data.
- Input size/depth limits and streaming ingestion.
- Parameterized SQLite queries.
- Plain-text/escaped GUI evidence display, Jinja2 auto-escaping, and safe URL/path handling.
- Output-directory confinement and overwrite protection.
- Separation of raw evidence, normalized values, correlations, and analyst conclusions.
- Explicit counts for skipped files and rejected records.
- Transactional background jobs with accurate failed/cancelled/partial states.
- Operating-system credential storage or secret references; no keys in case databases or exports.
- Security tests using malicious HTML, CSV formulas, traversal strings, malformed Unicode/JSON, oversized fields, and secret-leak assertions.

## External enrichment

Any future enrichment must be opt-in. The GUI must show the provider, exact observable/category leaving the workstation, purpose, cache behavior, and authentication state before execution. Safe Enrichment sends observable values only; files, raw events, usernames, hostnames, paths, notes, and case titles remain denied by default. Provider assertions retain attribution and never replace local facts.

The CLI, when added, must apply the same policy service and require an explicit non-offline policy/configuration rather than bypassing GUI safeguards.

## Desktop and case storage

- Treat case databases, caches, logs, recovery files, and exports as sensitive evidence-derived material.
- Make source reference-versus-copy behavior explicit and warn when referenced bytes are no longer available.
- Never show raw evidence or credentials in notifications, crash dialogs, or ordinary logs.
- Verify database migrations and back up a case before an incompatible migration.
- Do not load remote images, fonts, HTML, or scripts in the GUI or exported reports.
- Installer, update, and code-signing security must be designed before distributing production builds.

## Supported versions

No versions are currently supported. This section will be updated when the first release is published.
