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

from fastapi import APIRouter, Query, Request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # the pack loader does not put the pack on the path
import days  # noqa: E402
import packs  # noqa: E402
import settings  # noqa: E402
import wall  # noqa: E402
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


def _for_a_stranger(body: dict) -> dict:
    """The answer for a reader without a token (R25): /forecast is on the open list, and the house's point beside a
    source's km from it, with that source's public point, gave the house away (BMKG's village and the sea's grid point
    are two circles that cross at it). So the point is the res-8 cell's centre, and each distance is whole km from that
    centre, judged unrounded, as /energy and the Wall measure. Before the node has a place there is no point at all."""
    c = wall.cell_centre()
    body["point"] = {"lat": c[1], "lon": c[0]} if c else None
    far = []
    for s in body.get("sources") or []:
        if s.get("km_from_node") is None:
            continue
        if c is None or s.get("lat") is None or s.get("lon") is None:
            s["km_from_node"] = None
            continue
        s["km_from_node"] = wall.km_from(c, s["lon"], s["lat"])
        if wall.dist_km(c, s["lon"], s["lat"]) > 10 and s["sensor_id"] != days.MARINE:
            far.append({"sensor_id": s["sensor_id"], "km": s["km_from_node"]})
    body["far_from_node"] = far or None
    return body


def forecast(hours: int = 24, trusted: bool = False) -> dict:
    """Official and model weather for this point: where the wind comes from, when rain is expected, and when the
    forecast was issued, and what the next three days look like in the issues' own terms (`days`, and a pack's own
    `lines`). Context for reading this node's own air. The node fetches it; it does not predict. Only a `trusted`
    reader gets the house's own point and distances from it."""
    now = datetime.now(timezone.utc)
    who = q("""SELECT sensor_id, name, lat, lon, meta FROM sensors WHERE sensor_id ~ '^forecast-' ORDER BY sensor_id""")
    rows = q("""SELECT sensor_id, ts, metric, value FROM readings
                WHERE sensor_id ~ '^forecast-' AND ts > now() - interval '3 hours' AND ts < now() + interval '74 hours'
                ORDER BY ts, sensor_id, metric""")
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    body = days.answer(who=who, rows=rows, issue_lines=_issue_lines(), ahead=packs.ahead_lines(now, NODE_TZ), tz=NODE_TZ,
                       now=now, point={"lat": lat, "lon": lon}, hours=hours,
                       openmeteo=settings.get("FORECAST_OPENMETEO", "0") == "1",
                       coast="coast" in {d.name for d in packs._enabled()})
    return body if trusted else _for_a_stranger(body)


@router.get("/forecast")
def forecast_route(request: Request, hours: int = Query(24, ge=1, le=72)):
    return forecast(hours, trusted=bool(getattr(request.state, "share_trusted", False)))
