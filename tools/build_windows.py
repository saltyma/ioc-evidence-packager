"""Build the Windows app without inheriting unrelated codec/system runtimes."""

import os
import shutil
import sys
from pathlib import Path


def sanitize_runtime(binary_root: Path, quarantine: Path) -> None:
    """Windows supplies API sets, UCRT and ICU; never ship unrelated PATH copies."""
    quarantine.mkdir(parents=True, exist_ok=True)
    for item in binary_root.iterdir():
        name = item.name.casefold()
        if item.is_file() and (
            name.startswith("api-ms-win-")
            or name == "ucrtbase.dll"
            or (name.startswith("icu") and name.endswith(".dll"))
        ):
            shutil.move(str(item), str(quarantine / item.name))


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Build the Windows distribution on Windows.")
    root = Path(__file__).resolve().parents[1]
    python_root = Path(sys.executable).parent
    windows = Path(os.environ["SystemRoot"])
    os.environ["PATH"] = os.pathsep.join(
        str(path) for path in (python_root, python_root / "Scripts", windows / "System32", windows)
    )
    os.chdir(root)
    import PyInstaller.__main__

    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            "--windowed",
            "--name",
            "IOCEvidencePackager",
            "--collect-all",
            "ioc_evidence_packager",
            "--icon",
            "src/ioc_evidence_packager/presentation/desktop/assets/app-icon.ico",
            "tools/desktop_entry.py",
        ]
    )
    sanitize_runtime(root / "dist/IOCEvidencePackager/_internal", root / "build/system-dlls")


if __name__ == "__main__":
    main()
