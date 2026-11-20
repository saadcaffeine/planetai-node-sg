"""The area pull: ask the node about any set of cells or any drawn area (spec 2026-11-10, §2).

A selection is covered at res 8 and capped at AREA_CAP cells, refused before covering when the estimate is over, the
way geo.grid refuses past GRID_CAP. Three streams answer it; this file holds the two the node keeps itself:

- own: this node's custody sensors, read only inside the node's own cells. A selection elsewhere reads none of them.
- peers: kind='peer' sensors with a point in the selection. A peer with no point is counted, never guessed into a cell.

The third, open sources, is whatever each pack's `area(cells, bbox)` hook answers (open_). POST /area, at the end,
resolves a mark_id to its geometry, reads the rows and answers all three. h3 stays on the server: the page sends ids
or GeoJSON and draws what comes back.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import h3
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request

import cells as cells_mod

log = logging.getLogger("planetai")

AREA_CAP = 500                                  # res-8 cells one selection may cover, about 370 km²
RES = cells_mod.RES


def _poly_rings(geom) -> list[list[list]]:
    """Every polygon of a GeoJSON Polygon or MultiPolygon as a list of rings, each point checked as [lon, lat]."""
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("polygon must be a GeoJSON Polygon or MultiPolygon.")
    coords = geom.get("coordinates")
    polys = [coords] if geom["type"] == "Polygon" else coords
    if not isinstance(polys, list) or not polys:
        raise ValueError("The polygon has no coordinates.")
    for poly in polys:
        if not isinstance(poly, list) or not poly:
            raise ValueError("The polygon has no rings.")
        for ring in poly:
            if not isinstance(ring, list) or len(ring) < 3:
                raise ValueError("Each ring of the polygon needs at least three points.")
            for p in ring:
                if not (isinstance(p, list | tuple) and len(p) >= 2
                        and all(isinstance(v, int | float) and not isinstance(v, bool) for v in p[:2])
                        and -180 <= p[0] <= 180 and -90 <= p[1] <= 90):
                    raise ValueError("Each point of the polygon must be [longitude, latitude] in degrees.")
    return polys


def _area_m2(polys) -> float:
    """Shoelace on a local flat projection: outer ring minus holes. Good to a few percent at a city's size."""
    total = 0.0
    for poly in polys:
        for i, ring in enumerate(poly):
            k = math.cos(math.radians(sum(p[1] for p in ring) / len(ring))) * 111320
            xy = [(p[0] * k, p[1] * 110574) for p in ring]
            a = abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(xy, xy[1:] + xy[:1]))) / 2
            total += -a if i else a
    return total


def _over_cap() -> ValueError:
    return ValueError(f"That selection covers more than {AREA_CAP} cells at resolution {RES}. Choose a smaller area.")


def cover(sel: dict) -> list[str]:
    """The sorted res-8 cells a selection covers: {"cells": [...]} at res 5 to 10, or {"polygon": GeoJSON}.
    A mark_id is resolved to its polygon by the route before it gets here."""
    keys = [k for k in ("cells", "polygon", "mark_id") if k in (sel or {})]
    if len(keys) != 1:
        raise ValueError("A selection has exactly one of cells, polygon or mark_id.")
    if keys[0] == "mark_id":
        raise ValueError("A mark_id is read from the Place map first; send its polygon here.")
    if keys[0] == "cells":
        ids = sel["cells"]
        if not isinstance(ids, list) or not ids:
            raise ValueError("cells must be a list of H3 ids.")
        ids = set(ids)
        for c in ids:
            if not (isinstance(c, str) and h3.is_valid_cell(c) and 5 <= h3.get_resolution(c) <= 10):
                raise ValueError(f"{c!r} is not an H3 cell at resolution 5 to 10.")
        if sum(h3.cell_to_children_size(c, RES) if h3.get_resolution(c) < RES else 1 for c in ids) > AREA_CAP:
            raise _over_cap()
        out = set()
        for c in ids:
            r = h3.get_resolution(c)
            out |= set(h3.cell_to_children(c, RES)) if r < RES else {h3.cell_to_parent(c, RES)}
    else:
        polys = _poly_rings(sel["polygon"])
        if _area_m2(polys) / h3.average_hexagon_area(RES, unit="m^2") > AREA_CAP:
            raise _over_cap()
        try:
            out = set(h3.geo_to_cells(sel["polygon"], RES))
        except (ValueError, h3.H3BaseException) as e:
            raise ValueError("That polygon is not one H3 can cover.") from e
        if not out:   # an area smaller than a cell: the cells its corners stand in, never nothing
            out = {h3.latlng_to_cell(p[1], p[0], RES) for poly in polys for p in poly[0]}
    if len(out) > AREA_CAP:        # the estimate is a few percent off at the edge
        raise _over_cap()
    return sorted(out)


def bbox(cells: list[str]) -> tuple[float, float, float, float]:
    """west, south, east, north of the cells' boundaries."""
    # ponytail: no antimeridian handling; a selection across 180° gets a box round the world. Split it if one ever does.
    pts = [p for c in cells for p in h3.cell_to_boundary(c)]
    if not pts:
        raise ValueError("No cells, no box.")
    return min(p[1] for p in pts), min(p[0] for p in pts), max(p[1] for p in pts), max(p[0] for p in pts)


def _ts(v) -> datetime:
    t = datetime.fromisoformat(v) if isinstance(v, str) else v
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def summarise(rows: list[dict]) -> dict:
    """Per metric: the newest past reading (the mean of the sensors at that moment) and the mean over the last 24 h.
    A row timestamped in the future is a forecast, not a reading. No reading in 24 h: mean_24h is None, n is 0."""
    now = datetime.now(timezone.utc)
    by: dict[str, list[tuple[datetime, float]]] = {}
    for r in rows:
        if r.get("value") is None:
            continue
        t = _ts(r["ts"])
        if t <= now:
            by.setdefault(r["metric"], []).append((t, float(r["value"])))
    out = {}
    for m, xs in by.items():
        last = max(t for t, _ in xs)
        at = [v for t, v in xs if t == last]
        day = [v for t, v in xs if t > now - timedelta(hours=24)]
        out[m] = {"latest": sum(at) / len(at), "latest_at": last.isoformat(),
                  "mean_24h": sum(day) / len(day) if day else None, "n": len(day)}
    return out


def _placed(s: dict) -> str | None:
    return cells_mod.cell_of(s.get("lat"), s.get("lon"))


def _read(sensors: list[dict], readings: list[dict]) -> dict:
    ids = {s["sensor_id"] for s in sensors}
    return summarise([r for r in readings if r["sensor_id"] in ids])


def own(sensors, readings, selection: set[str], own_cells: set[str]) -> dict:
    """This node's custody sensors whose cell is in selection ∩ own_cells. One with no point is never guessed into a
    cell: it is counted in `unplaced` (a child, with no point on the aggregates wire, in children_unplaced), so the
    block never looks more complete than it is."""
    mine = set(selection) & set(own_cells)
    here = [s for s in sensors if s.get("custody") and s.get("kind") != "child" and _placed(s) in mine]
    nowhere = [s for s in sensors if s.get("custody") and _placed(s) is None]
    out = {"cells": sorted(mine), "sensors": len(here), "metrics": _read(here, readings),
           "unplaced": sum(1 for s in nowhere if s.get("kind") != "child"),
           "children_unplaced": sum(1 for s in nowhere if s.get("kind") == "child")}
    if not mine:
        out["why"] = "None of these cells is the node's own, so none of its readings are read here."
    elif not out["metrics"]:
        out["why"] = "No sensor of this node has a reading in these cells in the last 24 hours."
    return out


def peers(sensors, readings, selection: set[str]) -> dict:
    """kind='peer' sensors with a point in the selection. A peer with only a distance (radio) is counted as unplaced."""
    ps = [s for s in sensors if s.get("kind") == "peer"]
    here = [s for s in ps if _placed(s) in selection]
    out = {"sensors": len(here), "metrics": _read(here, readings), "unplaced": sum(1 for s in ps if _placed(s) is None)}
    if not out["metrics"]:
        out["why"] = "No neighbouring node has a reading in these cells in the last 24 hours."
    return out


# ---------------------------------------------------------------- open sources: the packs' `area` hook
def _area_packs() -> list[str]:
    """Every pack that ships an `area` hook, on this node or not: read as text, so nothing that is off gets imported."""
    import packs  # noqa: PLC0415
    return sorted(f.parent.name for f in packs.PACKS_DIR.glob("*/hooks.py") if "\ndef area(" in "\n" + f.read_text())


def open_(cells: list[str], box) -> list[dict]:
    """One entry per pack with an `area` hook: its answer, or why it gave none. "Off on this node" (PACKS_ENABLED, its
    code not allowed, its own AREA_SWITCH) is told apart from "nothing here", so an empty block never reads as an
    area that holds nothing. packs.collect drops a None and a failure alike, so the hooks are called here."""
    import packs  # noqa: PLC0415
    import settings  # noqa: PLC0415
    loaded, on = dict(packs._hook_modules()), {d.name for d in packs._enabled()}
    out = []
    for name in sorted(set(_area_packs()) | {n for n, m in loaded.items() if callable(getattr(m, "area", None))}):
        mod, sw, why = loaded.get(name), getattr(loaded.get(name), "AREA_SWITCH", None), None
        if name not in on:
            why = packs.REFUSED.get(name) or "PACKS_ENABLED leaves it out"
        elif mod is None and not packs._allow_code():
            why = "its code runs only with PACKS_ALLOW_CODE=1"
        elif sw and settings.get(sw[0], "") != sw[1]:
            why = f"set {sw[0]}={sw[1]} to ask it"
        if why:
            out.append({"pack": name, "off": True, "why": f"The {name} pack is off on this node: {why}."})
        elif mod is None:
            out.append({"pack": name, "error": f"The {name} pack's code did not load on this node; its log says why."})
        else:
            try:
                got = mod.area(cells, box)
            except Exception as e:  # noqa: BLE001 — a pack that fails costs its own block, never the pull
                log.warning("pack %s: area failed (%s)", name, type(e).__name__)
                got = {"pack": name, "error": f"The {name} pack failed on this area; the node's log says why."}
            out.append(got if got is not None else {"pack": name, "off": False, "why": f"The {name} pack has nothing for this area."})
    return out


# ---------------------------------------------------------------- POST /area
# The household's alone at every SHARE_LEVEL, as /place/cells: on no allowlist in app/auth.py, and the same gate.
router = APIRouter(dependencies=[Depends(cells_mod._household)])

_MARK = """SELECT ST_AsGeoJSON(k.geom)::json AS geometry FROM place_marks k JOIN place_maps p ON p.id = k.map_id
           WHERE k.id = %s AND k.kind = 'area' AND p.agent IS NULL AND p.from_node IS NULL"""
_SENSORS = "SELECT sensor_id, kind, custody, lat, lon FROM sensors WHERE custody OR kind = 'peer'"
_READINGS = """SELECT r.sensor_id, r.metric, r.ts, r.value FROM readings r
               WHERE r.sensor_id = ANY(%s) AND r.ts > now() - interval '24 hours' AND r.ts <= now()"""


@router.post("/area")
def pull(request: Request, sel: dict = Body(...), authorization: str = Header("")):
    """Body: {"cells": [...]} | {"polygon": GeoJSON} | {"mark_id": n}, a drawn area of the household's own maps.
    Answers own (home and held cells only), peers and open, one block per stream. 400 with the sentence on a bad
    selection, 404 on a mark that is not one of the household's drawn areas."""
    from auth import _shows_private  # noqa: PLC0415
    import packs  # noqa: PLC0415
    mark = set(sel) == {"mark_id"}           # with another key, cover() refuses it in its own words
    if mark and (not isinstance(sel["mark_id"], int) or isinstance(sel["mark_id"], bool)):
        raise HTTPException(400, "mark_id is the number of a drawing.")
    with cells_mod._db() as con, con.transaction(), con.cursor() as cur:
        if mark:
            cur.execute(_MARK, (sel["mark_id"],))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "No drawn area of this household has that number.")
            sel = {"polygon": row["geometry"]}
        try:
            got = cover(sel)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        selection = set(got)
        try:
            home = cells_mod._home()
            rows = cells_mod.states(home, cells_mod.load(cur, home), cells_mod._seen(cur))
            own_cells = {r["cell"] for r in rows if r["state"] in ("home", "held")}
        except HTTPException:
            own_cells = set()                 # a node with no place has no cells of its own; open sources still answer
        cur.execute(_SENSORS)
        sensors = cur.fetchall()
        ids = [s["sensor_id"] for s in sensors if _placed(s) in selection]
        q = _READINGS + ("" if _shows_private(request, authorization, raw=False) else " AND " + packs.public_sql("r"))
        cur.execute(q, (ids,))
        readings = cur.fetchall()
    return {"cells": len(got), "res": RES, "own": own(sensors, readings, selection, own_cells),
            "peers": peers(sensors, readings, selection), "open": open_(got, bbox(got))}
