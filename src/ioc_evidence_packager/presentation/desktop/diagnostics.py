"""Local crash diagnostics for the desktop process."""

from __future__ import annotations

import atexit
import faulthandler
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import TextIO

_CRASH_STREAM: TextIO | None = None
_PREVIOUS_EXCEPTHOOK = sys.excepthook


def install_crash_diagnostics(application_data_directory: Path) -> Path:
    """Capture native fault stacks and uncaught Python errors in a bounded local log."""

    global _CRASH_STREAM, _PREVIOUS_EXCEPTHOOK
    log_directory = application_data_directory / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "crash.log"
    if _CRASH_STREAM is not None:
        return Path(_CRASH_STREAM.name)

    if log_path.is_file() and log_path.stat().st_size > 2_000_000:
        previous_path = log_directory / "crash.previous.log"
        previous_path.unlink(missing_ok=True)
        log_path.replace(previous_path)

    stream = log_path.open("a", encoding="utf-8", buffering=1)
    _CRASH_STREAM = stream
    _PREVIOUS_EXCEPTHOOK = sys.excepthook
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    stream.write(f"\n[{timestamp}] Desktop session started\n")
    faulthandler.enable(file=stream, all_threads=True)

    def report_uncaught_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        exception_traceback: TracebackType | None,
    ) -> None:
        active_stream = _CRASH_STREAM
        if active_stream is not None and not active_stream.closed:
            failure_time = datetime.now(UTC).isoformat(timespec="seconds")
            active_stream.write(f"[{failure_time}] Uncaught Python exception\n")
            traceback.print_exception(
                exception_type,
                exception,
                exception_traceback,
                file=active_stream,
            )
            active_stream.flush()
        _PREVIOUS_EXCEPTHOOK(exception_type, exception, exception_traceback)

    sys.excepthook = report_uncaught_exception
    return log_path


def close_crash_diagnostics() -> None:
    """Restore process hooks and close the retained fault-handler stream."""

    global _CRASH_STREAM
    if _CRASH_STREAM is None:
        return
    if faulthandler.is_enabled():
        faulthandler.disable()
    sys.excepthook = _PREVIOUS_EXCEPTHOOK
    _CRASH_STREAM.close()
    _CRASH_STREAM = None


atexit.register(close_crash_diagnostics)
