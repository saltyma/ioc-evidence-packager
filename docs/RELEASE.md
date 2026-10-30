# Release and completion contract

The portfolio release is the local investigation workflow described in README. The broader conception documents contain extension proposals; they are not a list of features shipped by this version.

| Audit finding | Delivered behavior | Evidence |
|---|---|---|
| IPv6 missing | Canonical values, exact recipe, IP adapter fields, graph/TI support | Observable and workflow regressions |
| Case lifecycle | Rename, archive, restore | Database regression |
| Time range | Inclusive timestamp bounds with required offsets | Validation and persistence tests |
| Review | Bookmark, note, export inclusion stored independently | Persistence/redaction tests |
| Export selection | Omitted records and associated citations removed; searched coverage disclosed | Capsule verifier regression |
| Export promises | Eight-artifact directory plus optional separate PDF/ZIP | Projection integrity tests |
| No CI | Windows/Linux Python 3.11/3.12 matrix | Quality workflow |
| No Windows build | Wheel, source distribution, frozen-app smoke test, per-user installer | Distribution workflow |
| No license | MIT | LICENSE |

## Windows distribution

Run the **Windows distribution** workflow manually or push a version tag. It runs tests and the demo, builds a wheel and frozen app, smoke-tests the executable, compiles an Inno Setup installer, and uploads artifacts.

Local developer build:

```powershell
python -m pip install -e ".[dev,build]"
python -m build
python tools/build_windows.py
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging/windows.iss
```

The per-user installer retains a stable AppId for upgrades and excludes case stores. Uninstall does not delete application-data cases. Back up case databases before upgrading important investigations. Runner smoke tests validate that environment; operational upgrades on real analyst machines need separate validation.

## Explicit future extensions

STIX/MISP/TheHive/OpenCTI/Timesketch handoffs, URL leads, Public Suffix List grouping, local ATT&CK data, Zeek/Plaso/Velociraptor/ECS/Parquet/OCSF adapters, detached signatures, collaboration, code signing, and production support are future extensions. They are not advertised as shipped capabilities.

## Release checks

Run lint, formatting, types, tests, demo verification, and a full-demo desktop smoke launch. Confirm only synthetic demo material is tracked. Keep games, generated books, case stores, environments, and credentials ignored. Inspect checks for the published commit before describing its distribution as validated.

Qt for Python is pinned to 6.11.1, the validated desktop build. A 6.12 runner failed during native interpreter cleanup after passing the Python tests. Do not widen this dependency without repeating the full matrix and frozen-app checks.
