"""Frozen desktop entry point used by the Windows distribution workflow."""

import os
import traceback
from pathlib import Path

if __name__ == "__main__":
    try:
        from ioc_evidence_packager.presentation.desktop.app import main

        result = main()
    except Exception:
        if diagnostic := os.environ.get("IOC_PACKAGER_STARTUP_LOG"):
            Path(diagnostic).write_text(traceback.format_exc(), encoding="utf-8")
        raise
    raise SystemExit(result)
