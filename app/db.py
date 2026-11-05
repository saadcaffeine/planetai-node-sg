"""The node's database connections, from one pool.

A new connection cost 12.8 ms on node #1 and a reused one 0.26 ms (22 Oct 2026), and every request, rule, poll and
MQTT message opened its own: `/issues` five or more. The pool keeps them open and hands one to each `with db() as con`,
which gives it back at the end of the block.

Every connection carries the session settings the SQL relies on: `timezone` from NODE_TZ, because rules and cells
find local midnight and local hours with `current_setting('TimeZone')` and Postgres defaults to UTC, which put day
boundaries and "evening" eight hours out in Bali; and the node's coordinates as `planetai.lat` / `planetai.lon`, so
rules can rank references by distance. Nothing may change a connection's session for good: the rules' `SET LOCAL
ROLE` ends with its transaction (index.run_ro), and a pack script that needs its own settings opens its own
connection.

The pool opens on first use, never at import: importing the app starts nothing (main.start).
"""
from __future__ import annotations

import atexit
import os
import threading

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DB = os.environ["DATABASE_URL"]
NODE_TZ = os.getenv("NODE_TZ", "").strip() or "UTC"

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def _kwargs() -> dict:
    lat, lon = os.getenv("NODE_LAT", "0") or "0", os.getenv("NODE_LON", "0") or "0"
    return {"row_factory": dict_row, "autocommit": True,
            "options": f"-c timezone={NODE_TZ} -c planetai.lat={lat} -c planetai.lon={lon}"}


def _open() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            # ponytail: four kept open (psycopg's default); a busier moment connects directly (db()), so the pool
            # never grows past them. Raise min_size if a node's connects show up in its timings.
            _pool = ConnectionPool(DB, min_size=4, max_size=4, timeout=30, open=True, name="planetai", kwargs=_kwargs())
            atexit.register(close)    # any process that opened it, a test or a script, closes it before Python finishes
    return _pool


def db():
    """A connection for one `with` block: `with db() as con, con.cursor() as cur:`.

    With no idle connection in the pool, a direct one, exactly as before the pool. If the database is down that fails
    at once with the real reason, where the pool would make every request wait out its 30 s timeout: /health answers
    "unreachable" on that error and `planetai doctor` reads it. If the pool is only busy, the request gets its own
    connection rather than a wait. The pool is a saving, never a queue."""
    pool = _pool or _open()
    if not pool.get_stats().get("pool_available"):
        return psycopg.connect(DB, **_kwargs())
    return pool.connection()


def close() -> None:
    """When the app stops (main._lifespan), so its threads end with the process rather than after it."""
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def q(sql: str, *args) -> list[dict]:
    """Rows as dicts, a datetime as its ISO string: what every read route returns. Here rather than in main, so a
    pack's routes.py can read the database without importing main (packs.routers())."""
    from datetime import datetime   # noqa: PLC0415
    with db() as con, con.cursor() as cur:
        cur.execute(sql, args)
        return [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()} for r in cur.fetchall()]
