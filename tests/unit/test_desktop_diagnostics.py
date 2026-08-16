"""Tests for local desktop crash diagnostics."""

from pathlib import Path

from ioc_evidence_packager.presentation.desktop.diagnostics import (
    close_crash_diagnostics,
    install_crash_diagnostics,
)


def test_crash_diagnostics_create_and_release_a_local_log(tmp_path: Path) -> None:
    log_path = install_crash_diagnostics(tmp_path)
    try:
        assert log_path == tmp_path / "logs" / "crash.log"
        assert "Desktop session started" in log_path.read_text(encoding="utf-8")
    finally:
        close_crash_diagnostics()
    renamed = log_path.with_name("closed-crash.log")
    log_path.replace(renamed)
    assert renamed.is_file()
