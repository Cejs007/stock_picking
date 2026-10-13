import json
import sqlite3
import threading
import time
from collections.abc import Callable


class Cache:
    def __init__(
        self,
        db_path: str = ":memory:",
        ttl_hours: float = 24.0,
        _now: Callable[[], float] = time.time,
    ) -> None:
        self._ttl = ttl_hours * 3600
        self._now = _now
        # A single sqlite3 connection is shared across fetch_all's worker
        # threads. check_same_thread=False permits cross-thread use but does
        # NOT make concurrent use safe, so serialize every access with a lock.
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                ticker    TEXT NOT NULL,
                data_type TEXT NOT NULL,
                data      TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (ticker, data_type)
            )
            """
        )
        self._conn.commit()

    def get(self, ticker: str, data_type: str, ttl_hours: float | None = None) -> dict | None:
        ttl = ttl_hours * 3600 if ttl_hours is not None else self._ttl
        with self._lock:
            row = self._conn.execute(
                "SELECT data, cached_at FROM cache WHERE ticker = ? AND data_type = ?",
                (ticker, data_type),
            ).fetchone()
        if row is None:
            return None
        data, cached_at = row
        if self._now() - cached_at > ttl:
            return None
        return json.loads(data)

    def set(self, ticker: str, data_type: str, data: dict) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cache (ticker, data_type, data, cached_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker, data_type) DO UPDATE SET data = excluded.data, cached_at = excluded.cached_at
                """,
                (ticker, data_type, json.dumps(data), self._now()),
            )
            self._conn.commit()

    def invalidate(self, ticker: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache WHERE ticker = ?", (ticker,))
            self._conn.commit()
