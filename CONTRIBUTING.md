# Contributing

The project is in its design/scaffold stage. Contributions should protect the narrow product contract in [docs/SCOPE.md](docs/SCOPE.md).

## Development principles

- Preserve raw evidence and make transformations explicit.
- Make every match explainable and testable.
- Treat logs, paths, and report fields as untrusted.
- Prefer small adapters over vendor-specific conditions in core logic.
- Add synthetic fixtures for new parsing or matching behavior.
- Disclose rejected data instead of silently dropping it.
- Keep domain/application logic independent of Qt, SQL drivers, templates, and provider SDKs.
- Keep Offline mode complete and evidence content deterministic.
- Make coverage, network disclosure, and partial-success behavior explicit.

## Planned local setup

The first desktop slice is implemented. Create a local environment and run the quality gates with:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m mypy src
```

## Change workflow

1. Open an issue for a behavior change or new adapter.
2. Explain the user problem and how it fits the scope.
3. Add or update synthetic fixtures and tests.
4. Update relevant documentation and schemas.
5. Avoid real production logs, personal data, credentials, active malware, or harmful indicators.
6. Keep commits focused and describe evidence-handling implications in the pull request.

## Adapter checklist

- Declare format/vendor/schema assumptions and adapter version.
- Preserve source position and original values.
- Normalize only fields whose meaning is known.
- Bound record sizes/nesting and handle malformed encodings.
- Count accepted/rejected records and expose warnings.
- Test timestamps, missing fields, duplicates, malformed values, and malicious strings.

## GUI and background-job checklist

- Do not put matching, coverage, persistence, enrichment, or export rules in widgets.
- Keep imports and network calls outside the Qt event loop.
- Make cancellation cooperative and leave an accurate auditable job/run state.
- Use immutable view data and paginated/virtualized evidence lists.
- Escape evidence in all rich-text surfaces and avoid raw evidence in notifications.
- Add application-service tests plus a focused offscreen Qt smoke test.

## Connector checklist

- Declare capabilities, observable types, disclosure class, authentication, limits, cache TTL, and provider terms.
- Pass every request through the shared policy gate.
- Send the minimum allowed value and preserve provider attribution/time/raw-response hash.
- Test allow/deny, timeout, rate limit, schema drift, cache expiry, and secret leakage using fixtures.
- Keep live integration tests opt-in; normal CI must work offline.

## Documentation decisions

When implementation changes a frozen choice or normative state, update the relevant product document and explain the tradeoff in the pull request. Avoid letting code silently redefine the Case Capsule, coverage states, or facts-versus-assertions model.

## Commit and PR style

Use clear imperative commit subjects. Pull requests should include purpose, scope, tests, security/evidence impact, documentation impact, and screenshots only when output rendering changes.

## Licensing

No project license has been selected. Do not add third-party code, templates, images, or datasets until their licenses are compatible with the project's eventual license and properly attributed.
