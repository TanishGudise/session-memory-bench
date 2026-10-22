"""Applies billing/migrations/*.sql in name order, once each."""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).parent / "migrations"


def pending(conn: sqlite3.Connection) -> list[Path]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    return [p for p in sorted(MIGRATIONS.glob("*.sql")) if p.stem not in done]


def migrate(conn: sqlite3.Connection, until: str | None = None) -> list[str]:
    """Apply pending migrations (only those whose name sorts <= `until`, if given)."""
    applied = []
    for path in pending(conn):
        if until is not None and path.stem > until:
            break
        conn.executescript(path.read_text())
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (path.stem,))
        conn.commit()
        applied.append(path.stem)
    return applied
