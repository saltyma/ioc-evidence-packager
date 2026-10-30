"""Exercise real process shutdown, not just window construction inside pytest."""

import os
import subprocess
import sys
from pathlib import Path


def test_complete_demo_smoke_exits_cleanly(tmp_path: Path) -> None:
    screenshot = tmp_path / "desktop.png"
    result = subprocess.run(  # noqa: S603 - fixed local interpreter and module
        [
            sys.executable,
            "-X",
            "faulthandler",
            "-m",
            "ioc_evidence_packager",
            "--smoke-test",
            "--smoke-demo",
            "--screenshot",
            str(screenshot),
        ],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert screenshot.is_file()
    assert screenshot.stat().st_size > 1000
