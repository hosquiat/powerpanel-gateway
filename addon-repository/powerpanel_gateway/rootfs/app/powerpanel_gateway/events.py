"""Rolling event log backed by SQLite.

Stores the most recent ``max_rows`` events (default 1000). All methods are
synchronous and guarded by a lock; the async service layer calls them via the
event loop's default executor so the loop is never blocked on disk I/O.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from .models import Event, EventType, UpsState

_LOGGER = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    state TEXT,
    battery_percent INTEGER,
    remaining_runtime_minutes INTEGER,
    detail TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
"""


class EventStore:
    """Thread-safe SQLite-backed event log with rolling retention."""

    def __init__(self, db_path: Path, max_rows: int = 1000) -> None:
        self._path = db_path
        self._max_rows = max_rows
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def add(
        self,
        event_type: EventType,
        *,
        message: str = "",
        state: UpsState | None = None,
        battery_percent: int | None = None,
        remaining_runtime_minutes: int | None = None,
        detail: dict[str, object] | None = None,
        timestamp: datetime | None = None,
    ) -> Event:
        ts = timestamp or datetime.now(UTC)
        detail = detail or {}
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO events
                    (type, timestamp, message, state, battery_percent,
                     remaining_runtime_minutes, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type.value,
                    ts.isoformat(),
                    message,
                    state.value if state else None,
                    battery_percent,
                    remaining_runtime_minutes,
                    json.dumps(detail),
                ),
            )
            self._conn.commit()
            self._prune_locked()
            event_id = cur.lastrowid
        _LOGGER.info("event %s: %s", event_type.value, message)
        return Event(
            id=event_id,
            type=event_type,
            timestamp=ts,
            message=message,
            state=state,
            battery_percent=battery_percent,
            remaining_runtime_minutes=remaining_runtime_minutes,
            detail=detail,
        )

    def _prune_locked(self) -> None:
        self._conn.execute(
            """
            DELETE FROM events
            WHERE id NOT IN (
                SELECT id FROM events ORDER BY id DESC LIMIT ?
            )
            """,
            (self._max_rows,),
        )
        self._conn.commit()

    def list(
        self,
        *,
        limit: int = 200,
        event_type: EventType | None = None,
        since: datetime | None = None,
    ) -> list[Event]:
        query = "SELECT * FROM events"
        clauses: list[str] = []
        params: list[object] = []
        if event_type is not None:
            clauses.append("type = ?")
            params.append(event_type.value)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since.isoformat())
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
        return int(row["c"])

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            type=EventType(row["type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            message=row["message"],
            state=UpsState(row["state"]) if row["state"] else None,
            battery_percent=row["battery_percent"],
            remaining_runtime_minutes=row["remaining_runtime_minutes"],
            detail=json.loads(row["detail"]) if row["detail"] else {},
        )
