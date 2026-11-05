"""The place drawn and measured: GET /place/geojson and the map workbench, GET /geo/grid, /geo/cell, /geo/measure,
/geo/planet and /geo/rings.

A module of its own since 24 Oct 2026, moved unchanged out of app/main.py (review item 15). Every ring and distance
the Place door draws is answered here from app/issues/geometry.py, so the page computes no H3 and no distance. On no
SHARE_LEVEL allowlist but /geo/cell at open, which drops its node-relative fields for a caller without a token.
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Header, HTTPException, Query, Request

import settings
from db import db
from issues import geometry as _geo

log = logging.getLogger("planetai")

router = APIRouter()


@router.get("/place/geojson")
def place_geojson(kinds: str = "building,poi,green,road,sat", tolerance: float = Query(0.00002, ge=0.000001, le=0.01)):
    """The geometry the place pack stored: OpenStreetMap buildings, uses, green, roads, and the satellite's buildings
    (`sat`), as one GeoJSON FeatureCollection for the dashboard's plan. Simplified so a kilometre is a few hundred KB.
    Empty until the place pack has run; never an error.

    **On no SHARE_LEVEL allowlist, at any level: this machine or a token, and nothing else.** It is the exact building
    footprints and roads within PLACE_RADIUS_M of the address — the doorway A12 is about, drawn — and unlike a
    rounded coordinate there is no version of it that is safe to hand to the network. The dashboard's plan card is
    therefore empty on an unauthenticated screen and says so.

    `tolerance` carries bounds (F11): at 0 the query skipped ST_SimplifyPreserveTopology entirely and returned the
    unsimplified kilometre against a docstring promising a few hundred KB. The dashboard never passes it (:960)."""
    want = {k.strip() for k in kinds.split(",") if k.strip()}
    feats: list = []
    diag: dict = {"tables": {}, "rows": {}}
    try:
        with db() as con, con.cursor() as cur:
            one = lambda: next(iter(cur.fetchone().values()))        # rows are dicts in this app; take the single column  # noqa: E731
            for t in ("place_features", "place_buildings_sat", "place_runs"):
                cur.execute(f"SELECT to_regclass('{t}') IS NOT NULL AS ok"); diag["tables"][t] = bool(one())
                if diag["tables"][t]:
                    cur.execute(f"SELECT count(*) AS n FROM {t}"); diag["rows"][t] = one()
            if diag["tables"]["place_features"] and want - {"sat"}:
                cur.execute("""SELECT kind, category, name, tags->>'building' AS btype, tags->>'highway' AS hw,
                                      ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, %s), 6) AS g
                               FROM place_features WHERE kind = ANY(%s)""", (tolerance, list(want - {"sat"})))
                for r in cur.fetchall():
                    feats.append({"type": "Feature", "properties": {"kind": r["kind"], "category": r["category"], "name": r["name"], "building": r["btype"], "highway": r["hw"]}, "geometry": json.loads(r["g"])})
            if diag["tables"]["place_buildings_sat"] and "sat" in want:
                # only the satellite footprints with no mapped building within 3 m: the gap, drawn
                cur.execute("""SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(s.geom, %s), 6) AS g, s.confidence FROM place_buildings_sat s
                               WHERE s.source='open_buildings_v3' AND NOT EXISTS (
                                 SELECT 1 FROM place_features f WHERE f.kind='building' AND ST_DWithin(f.geom, s.geom, 0.00003))""", (tolerance,))   # geometry: uses the GiST index
                for r in cur.fetchall():
                    feats.append({"type": "Feature", "properties": {"kind": "sat", "confidence": r["confidence"]}, "geometry": json.loads(r["g"])})
    except Exception as e:  # noqa: BLE001
        log.warning("place/geojson: %s", e)
        diag["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    if not feats:
        diag["hint"] = ("the place pack has not stored anything yet: enable it (PACKS_ALLOW_CODE=1, planetai packs install, planetai restart) and let it poll, or planetai run place refresh"
                        if not diag["rows"].get("place_features") else "features exist but none matched; see error")
    return {"type": "FeatureCollection", "features": feats, "diag": diag,
            "center": [float(os.getenv("NODE_LON", 0) or 0), float(os.getenv("NODE_LAT", 0) or 0)],
            "radius_m": int(settings.get("PLACE_RADIUS_M", "1000") or 1000)}


# ---------------------------------------------------------------- the map workbench
# The redesign's Place door pans, zooms, inspects and measures. Every ring it draws and every distance it prints is
# answered here (app/issues/geometry.py), so the page computes no H3 and no distance: tools/check_ui.py holds it to
# that. **On no SHARE_LEVEL allowlist, like /place/geojson**: the node's cell at a fine resolution, rings centred on
# it and "metres from the node" each give away the point /health rounds on purpose. This machine or a token. The one
# exception is /geo/cell at SHARE_LEVEL=open, which answers without a token minus its node-relative fields.


def _here() -> tuple[float, float]:
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    if not (lat or lon):
        raise HTTPException(409, "this node has no NODE_LAT and NODE_LON yet, so there is no place to draw")
    return lat, lon


def _floats(text: str, n: int | None, what: str) -> list[float]:
    try:
        out = [float(x) for x in text.split(",")]
    except ValueError:
        raise HTTPException(422, f"{what}: numbers separated by commas") from None
    if n is not None and len(out) != n:
        raise HTTPException(422, f"{what}: {n} numbers")
    return out


@router.get("/geo/grid")
def geo_grid(bbox: str, res: int = Query(..., ge=0, le=15)):
    """The cells covering `bbox` (west,south,east,north) at `res`, one ring wider, and the node's own cell at that
    resolution, as `cells_ll` rows ([id, lat, lng, …]). 422 rather than a truncated covering when the box is too big."""
    lat, lon = _here()
    try:
        return _geo.grid(*_floats(bbox, 4, "bbox"), res, lat, lon)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.get("/geo/cell")
def geo_cell(request: Request, id: str | None = None, lat: float | None = Query(None, ge=-90, le=90),
             lon: float | None = Query(None, ge=-180, le=180), res: int | None = Query(None, ge=0, le=15),
             children: int | None = Query(None, ge=1, le=15), polar: bool = False):
    """One cell's facts, named by `id` or by `lat`, `lon` and `res`: area, edge, parent, and how many cells from the
    node's own at the same resolution. `children=<res>` adds how many children it has there and, up to 400, their
    rings; `polar=true` adds every ring as distance and bearing from the node."""
    here = _here()
    if id is None:
        if lat is None or lon is None or res is None:
            raise HTTPException(422, "name a cell: id, or lat, lon and res")
        import h3
        id = h3.latlng_to_cell(lat, lon, res)
    try:
        out = _geo.cell(id, *here, children=children, as_polar=polar)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    if not getattr(request.state, "share_trusted", False):
        for k in ("is_node", "cells_from_node", "ring_polar", "children_polar"):
            out.pop(k, None)
    return out


@router.get("/geo/measure")
def geo_measure(path: str, from_node: bool = False, each: bool = False):
    """Metres along `path`, lon,lat pairs separated by `;`, great-circle, each leg and the total. `from_node=true`
    starts the path at the node, which is how the inspector says how far a station is. `each=true` adds, for every
    point after the first, its distance and bearing from the first, in one answer."""
    pts = [tuple(_floats(p, 2, "each point")) for p in path.split(";") if p.strip()]
    if from_node:
        lat, lon = _here()
        pts = [(lon, lat)] + pts
    if not 2 <= len(pts) <= 200 or any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in pts):
        raise HTTPException(422, "path: 2 to 200 lon,lat points in degrees")
    return {**_geo.measure(pts), **({"each": _geo.each(pts)} if each else {})}


@router.get("/geo/planet")
def geo_planet(res: int = Query(2, ge=0, le=2)):
    """Every H3 cell on the planet at resolution 0, 1 or 2, as cells_ll rows: the world grid a map of nodes is drawn
    on, so the page computes none of it."""
    _here()
    return {"res": res, "cells_ll": _geo.planet(res)}


@router.get("/geo/rings")
def geo_rings(km: str = "2,5,15"):
    """Circles round the node at each distance in `km`, as [lat, lng] rings. At most eight, none past 500 km."""
    kms = _floats(km, None, "km")
    if not 1 <= len(kms) <= 8 or any(not 0 < k <= 500 for k in kms):
        raise HTTPException(422, "km: one to eight distances, each above 0 and at most 500")
    return {"rings": _geo.rings(*_here(), kms)}
