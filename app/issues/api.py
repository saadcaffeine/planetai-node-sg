"""`GET /issues` and `GET /issues/fixtures/{name}`.

Two routes on one prefix, which is the point: `/issues` goes on the `SHARE_LEVEL=open` allowlist and
never on the `off` one, and that single entry covers both. A snapshot carries 15-minute means, alert
texts and sensor names — the household's own data — so a fixture must not be served from `/static/`,
which is readable at `off`.

`app/main.py` learns about this file in exactly two lines: `include_router` and the `/issues` prefix
in `_SHARE_OPEN`. Everything else about issues lives in this package.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Path as PathParam, Query

from . import load
from . import engine

log = logging.getLogger("planetai.issues")
router = APIRouter(prefix="/issues", tags=["issues"])

FIXTURES = Path(__file__).resolve().parent / "fixtures"
# A name, not a path. `{name:path}` would be one `..` away from reading the filesystem, and this port
# answers a household LAN — the same reasoning as COMPANIONS in app/main.py.
NAME = r"^[a-z0-9][a-z0-9._-]{0,63}$"


@router.get("")
@router.get("/")
def issues_now():
    """Every issue this node declares: state, stack, line, attribution, sentence, asks, series.

    The order is `NODE_ISSUES`; an issue the keeper has not declared still appears, marked
    `watched: false`, so a stranger can see what this node could report. `headline` is the issue
    with the highest state, ties going to the declared order.

    The node computes; the page draws. Nothing in the response needs arithmetic to render, and
    nothing in it came from a model.
    """
    import main                    # noqa: PLC0415 — main imports this module at the bottom of itself
    with main.db() as con, con.cursor() as cur:
        # `mesh_state` and `MQTT_HOST` are `app/main.py`'s own module-level names, already used by its
        # `/health` route — reading them here costs no query and no network call (Ruling P3: /issues
        # never makes a network call, so the Reticulum bridge's peer list is Task 4's problem, not this
        # one's). `place` is left to default to the node's own coordinates.
        # The facility rows the `make` pack stores. One query, on the cursor already open, and only
        # what the pack's own sentence needs — a place has no readings, so it is in neither `stats`
        # nor the five reads the engine makes.
        cur.execute("SELECT sensor_id, name, meta FROM sensors WHERE kind = 'facility'")
        facilities = [dict(r) for r in cur.fetchall()]
        # The alert events block. A node whose events cannot be read still draws every issue: the block then
        # carries the reason, which is a different fact from a node too old to have events (SPEC §5).
        import events_wire          # noqa: PLC0415 — events_wire imports events_pg, which imports this package
        now = datetime.now(timezone.utc)
        try:
            with con.transaction():
                events = events_wire.live(cur, load(), main.settings.get("ALERT_LOCALE", "en") or "en", now)
        except Exception as e:  # noqa: BLE001
            log.warning("issues: the events block did not read (%s: %s)", type(e).__name__, str(e)[:120])
            events = {"engine": events_wire.engine_of(main.settings.get("ALERT_ENGINE", "rules")),
                      "error": "this node could not read its alert events just now", "open": [], "recent": [],
                      "buttons": {}, "cleared_today": 0, "last_cleared": None}
        return engine.compute(cur, main.settings, load(), earth=_earth(),
                               mesh=main.mesh_state if main.MQTT_HOST else None,
                               facilities=facilities, now=now, events=events)


@router.get("/days")
def issues_days(days: int = Query(7, ge=1, le=engine.DAYS_MAX)):
    """Each issue's hourly series over the last `days` local days, the hero distance's hours over the line counted per
    day, and the alert events in the window (docs/SPEC_dashboard_figures.md §3.4). The same engine as `/issues`, so a
    day here is the 24 hours `/issues` draws. Under the `/issues` prefix, so it shares exactly as `/issues` does."""
    import main                    # noqa: PLC0415
    with main.db() as con, con.cursor() as cur:
        return engine.days(cur, main.settings, load(), days)


def _earth():
    """`/earth`'s body, or None. The earth pack's record has exactly one reader in this repo and it
    is `main.earth()`; land's region column asks it rather than opening the pack's files again."""
    import main                    # noqa: PLC0415
    try:
        return main.earth()
    except Exception as e:  # noqa: BLE001
        log.warning("issues: /earth did not answer (%s: %s) — land falls back", type(e).__name__, str(e)[:120])
        return None


@router.get("/fixtures")
def fixtures():
    """Which snapshots this node ships, so a design round does not have to guess a name."""
    return {"fixtures": sorted(p.stem for p in FIXTURES.glob("*.json"))}


@router.get("/fixtures/{name}")
def fixture(name: str = PathParam(pattern=NAME)):
    """One committed snapshot, with its issues computed at the hour it was captured.

    The dashboard reads this with `?fixture=<name>` and renders exactly what it renders from live
    data — same engine, same shape — which is the only way a page reviewed against a fixture tells
    you anything about the page.
    """
    import main                    # noqa: PLC0415
    f = FIXTURES / f"{name}.json"
    if not f.is_file():
        raise HTTPException(404, f"no such fixture; this node ships {fixtures()['fixtures']}")
    snap = json.loads(f.read_text())
    try:
        snap["issues"] = engine.replay(snap, main.settings, load())
    except LookupError as e:        # a snapshot missing a table the engine reads
        snap["issues"] = {"error": str(e)}
    return snap
