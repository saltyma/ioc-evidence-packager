"""SQLite connection configuration and schema initialization."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ioc_evidence_packager.storage.sqlite.migrations import apply_migrations


class SQLiteDatabase:
    """Owns the filesystem location and consistent SQLite configuration."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            apply_migrations(connection)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            connection.close()
