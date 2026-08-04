"""
SQLite-backed idempotency store — integration-contract.md Section 5.3:
"Create a local SQLite DB or Redis cache key repository to track
processed sys_id values. If a duplicate sys_id webhook is received
within 5 minutes, reject it with 409 Conflict."

Swap for Redis if you're running more than one FastAPI worker process —
SQLite here assumes a single process (fine for a PDI/hackathon demo).
"""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

DB_PATH = Path(__file__).parent.parent / "idempotency.db"


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_webhooks (
                sys_id TEXT PRIMARY KEY,
                received_at REAL NOT NULL
            )
            """
        )


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def check_and_mark(sys_id: str) -> bool:
    """
    Returns True if this sys_id can proceed (not a recent duplicate).
    Returns False if it's a duplicate within the idempotency window —
    caller should respond 409 Conflict and no-op.
    """
    now = time.time()
    window_start = now - settings.idempotency_window_seconds

    with _connect() as conn:
        conn.execute("DELETE FROM processed_webhooks WHERE received_at < ?", (window_start,))
        row = conn.execute(
            "SELECT 1 FROM processed_webhooks WHERE sys_id = ?", (sys_id,)
        ).fetchone()
        if row:
            return False
        conn.execute(
            "INSERT INTO processed_webhooks (sys_id, received_at) VALUES (?, ?)",
            (sys_id, now),
        )
        return True
