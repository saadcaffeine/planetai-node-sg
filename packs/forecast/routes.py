"""GET /forecast: official and model weather for this point, as the forecast pack stores it.

A route of this pack since 23 Oct 2026; until then app/main.py, moved unchanged. The node mounts it from here
(app/packs.py::routers) and answers 404 while this pack is off. `forecast()` is also what the Wall reads
(app/ask.py::wall_reads), so it stays a plain function the route wraps.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, Query

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # the pack loader does not put the pack on the path
import days  # noqa: E402
import packs  # noqa: E402
import settings  # noqa: E402
from db import NODE_TZ, q  # noqa: E402

log = logging.getLogger("planetai.forecast")
router = APIRouter()


_said: set = set()


def _warn_once(msg: str, *args) -> None:
    text = msg % args
    if text not in _said:
        _said.add(text)
        log.warning(text)


def _issue_lines() -> dict:
    """The line, unit and decimals of the air and heat issues as the engine loads them. A pack that is off has no
    issue, so its row is left out of `days`."""
    from issues import load  # noqa: PLC0415 — the engine's own loader: one place knows what an issue's line is
    try:
        decl = load()
    except Exception as e:  # noqa: BLE001 — the Wall reads this too; wind, rain and the sea do not need an issue file
        _warn_once("forecast: the issues did not load (%s); Next days has no air or heat rows", e)
        return {}
    return {k: {"value": d["line"]["value"], "unit": d["line"].get("unit", d.get("unit")), "dp": d.get("dp", 0)}
            for k in ("air", "heat") if (d := decl.get(k)) and d.get("line")}


@router.get("/forecast")
def forecast(hours: int = Query(24, ge=1, le=72)):
    """Official and model weather for this point: where the wind comes from, when rain is expected, and when the
    forecast was issued, and what the next three days look like in the issues' own terms (`days`, and a pack's own
    `lines`). Context for reading this node's own air. The node fetches it; it does not predict."""
    now = datetime.now(timezone.utc)
    who = q("""SELECT sensor_id, name, lat, lon, meta FROM sensors WHERE sensor_id ~ '^forecast-' ORDER BY sensor_id""")
    rows = q("""SELECT sensor_id, ts, metric, value FROM readings
                WHERE sensor_id ~ '^forecast-' AND ts > now() - interval '3 hours' AND ts < now() + interval '74 hours'
                ORDER BY ts, sensor_id, metric""")
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    return days.answer(who=who, rows=rows, issue_lines=_issue_lines(), ahead=packs.ahead_lines(now, NODE_TZ), tz=NODE_TZ,
                       now=now, point={"lat": lat, "lon": lon}, hours=hours,
                       openmeteo=settings.get("FORECAST_OPENMETEO", "0") == "1",
                       coast="coast" in {d.name for d in packs._enabled()})
