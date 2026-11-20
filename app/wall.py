"""GET /wall: everything the Wall's map draws, in one read a screen with no token may make.

The Wall walks out from the house through three node sizes (the base node's seven res-8 cells, the community's seven
res-7, the city's seven res-6) and replays the last 24 hours on each. It runs on a kiosk with no token, so this route
is on the SHARE_LEVEL=open list (app/auth.py), and what it returns is held to R25 (_published_position in main.py):
nothing finer than the house's res-8 cell. So every distance is from that cell's centre, in whole km; every point is
a public thing's (a station, a lab, a power plant) at three decimals at most; and nothing is cut around the house's
own point. Where a pack kept something cut around the point, it is either re-cut around the cell's centre (the
rivers, the basin, the roofs) or left out until it is (the land-change image, whose square is centred on the
house to 10 m). docs/superpowers/specs/2026-11-18-wall-scales-map-design.md in planetai-design is the why.

Each block is null when its pack is off or has nothing yet; the route never fails on a missing pack.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h3
from fastapi import APIRouter, HTTPException

import packs
import settings
from db import db
from issues.engine import day_buckets

router = APIRouter()
log = logging.getLogger("planetai.wall")

SCALES = (("base", 8), ("community", 7), ("city", 6))
FRESH = timedelta(hours=3)          # the island's file, and each station in it
PLANT_KM = 30
HOURS = {"wind_kmh": ("om-point", "wind_speed"), "wind_from": ("om-point", "wind_direction"),
         "wave_from": ("marine-point", "wave_direction"), "swell_m": ("marine-point", "swell_height_m"),
         "swell_s": ("marine-point", "swell_period_s")}


# ---------------------------------------------------------------- pure builders

def _ring(cid: str) -> list:
    """A cell's boundary as [lon, lat] pairs, closed: h3 leaves the first vertex unrepeated."""
    pts = [[round(lng, 6), round(lat, 6)] for lat, lng in h3.cell_to_boundary(cid)]
    return pts + [pts[0]]


def scales(home: str) -> list[dict]:
    """The three node sizes: the seven-cell rule one resolution up each time (the cell holding the house and the six
    touching it), with the node's own cell at each size marked."""
    out = []
    for k, res in SCALES:
        own = h3.cell_to_parent(home, res)
        cells = [own] + sorted(set(h3.grid_disk(own, 1)) - {own})
        out.append({"k": k, "res": res, "km2": round(sum(h3.cell_area(c, unit="km^2") for c in cells), 1),
                    "cells": [{"id": c, "own": c == own, "ring": _ring(c)} for c in cells]})
    return out


def home_cell() -> str | None:
    """The res-8 cell /health names, None before the node has a place."""
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    return h3.latlng_to_cell(lat, lon, 8) if lat or lon else None


def cell_centre() -> tuple[float, float] | None:
    """(lon, lat) of the middle of the res-8 cell /health names, None before the node has a place: what a tokenless
    reader's every distance is measured from, here and in packs/energy's /energy."""
    home = home_cell()
    if home is None:
        return None
    clat, clon = h3.cell_to_latlng(home)
    return clon, clat


def dist_km(centre: tuple[float, float], lon: float, lat: float) -> float:
    """km from the cell's centre ((lon, lat)), unrounded: what to rank and cut by, never what to publish."""
    return h3.great_circle_distance((centre[1], centre[0]), (lat, lon), unit="km")


def km_from(centre: tuple[float, float], lon: float, lat: float) -> int:
    """Whole km from the cell's centre ((lon, lat)): a decimal of km beside a public point narrows the house."""
    return round(dist_km(centre, lon, lat))


def hourly(rows, buckets, sensor_id: str, metric: str) -> list[float | None]:
    """One value per bucket, None where the hour has no row."""
    got = {r["bucket"]: r["mean"] for r in rows if r["sensor_id"] == sensor_id and r["metric"] == metric}
    return [None if got.get(b) is None else round(float(got[b]), 2) for b in buckets]


def _utm(epsg: int, near: tuple[float, float]):
    """UTM metres of `epsg` back to [lon, lat], by surface-heat's own forward projection (Snyder) and its local
    inverse, with one Newton step from the first guess: under a centimetre 7 km from `near` (lat, lon). No pyproj on a
    node. The pack's module is loaded once here, not once per point."""
    sh = packs.module("surface-heat", on_only=False)
    fwd = sh.projection(epsg)
    first = sh.local_inverse(fwd, *near)

    def to(x: float, y: float) -> list[float]:
        lat, lon = sh.local_inverse(fwd, *first(x, y))(x, y)
        return [round(lon, 6), round(lat, 6)]
    return to


def lonlat(x: float, y: float, epsg: int, near: tuple[float, float]) -> list[float]:
    return _utm(epsg, near)(x, y)


def circum_m(home: str) -> float:
    """The farthest the house can be from its cell's centre: the farthest vertex."""
    c = h3.cell_to_latlng(home)
    return max(h3.great_circle_distance(c, v, unit="m") for v in h3.cell_to_boundary(home))


ROUNDED_M = 80      # how far a point at 3 dp can stand from where it is (55 m each way at the equator)


def kept(lat: float, lon: float, centre: tuple[float, float], far_m: float | None, near_m: float) -> bool:
    """Whether a station may be drawn, judged from the cell's centre only. A pack chose its stations round the house:
    within a radius, and never within a separation of it (packs/bali-air-dispatch). So a station that would be
    missing for being near the house or far from it is left out for everyone near the centre or far from it,
    `far_m` and `near_m` being those limits already widened by how far the house can be from the centre."""
    d = h3.great_circle_distance((centre[1], centre[0]), (lat, lon), unit="m")
    return d > near_m and (far_m is None or d <= far_m)


def _age(ts, now: datetime) -> timedelta | None:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return now - (t if t.tzinfo else t.replace(tzinfo=timezone.utc))


def island(doc: dict | None, now: datetime, ok=lambda lat, lon: True) -> dict | None:
    """packs/bali-air-dispatch's island-wide stations, null when the file is over 3 h old. Its `at` is when it was
    written, not when the stations read, so each item's own `at` is held to the same 3 h. `ok` is `kept`."""
    if not isinstance(doc, dict) or (_age(doc.get("at"), now) or FRESH * 2) > FRESH:
        return None
    keep = ("pm25", "at", "network", "official", "place")
    items = [{"lat": round(i["lat"], 3), "lon": round(i["lon"], 3), **{k: i.get(k) for k in keep}}
             for i in doc.get("items") or []
             if i.get("lat") is not None and i.get("lon") is not None and (_age(i.get("at"), now) or FRESH * 2) <= FRESH
             and ok(i["lat"], i["lon"])]
    return {"at": doc["at"], "items": items}


def _covers(square, home: str, km: float, frame: tuple) -> bool:
    """Whether the hydro square of `km` round any point of `home` holds the frame. The pack fetched round the house,
    so a square that holds it from one point of the cell and not from another would say which: judged at the
    corners of the cell's box, every point of the cell lies within them."""
    w, s, e, n = frame
    lats, lons = zip(*h3.cell_to_boundary(home))
    for la in (min(lats), max(lats)):
        for lo in (min(lons), max(lons)):
            sw, ss, se, sn = square(la, lo, km)
            if not (sw <= w and ss <= s and e <= se and n <= sn):
                return False
    return True


def _crosses(frame: tuple, a, b) -> bool:
    """Whether the segment a-b ([lon, lat] each) touches the frame (Liang-Barsky): a straight reach can cross it
    with both ends outside."""
    w, s, e, n = frame
    (x1, y1), (x2, y2) = a, b
    t0, t1 = 0.0, 1.0
    for p, q in ((x1 - x2, x1 - w), (x2 - x1, e - x1), (y1 - y2, y1 - s), (y2 - y1, n - y1)):
        if p == 0:
            if q < 0:
                return False
        elif p < 0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
    return t0 <= t1


def water(r: dict, frame: tuple, centre: tuple[float, float], inside, square=None) -> tuple:
    """(rivers, basin, river) from the hydro pack's result. The pack cut its square around the house and measured
    every reach from it (`dist_m`), so the reaches are re-chosen by the city frame, which lies inside that square
    and depends only on the cells, and measured again from the cell's centre. The basin is the one holding the
    centre, never the one holding the house: a basin edge through the cell would say which side the house is on."""
    if not r:
        return None, None, None
    home = h3.latlng_to_cell(centre[1], centre[0], 8)
    if square:          # a square smaller than the frame would show its own edge, and that edge is round the house
        if h3.latlng_to_cell(r["lat"], r["lon"], 8) != home or not _covers(square, home, r["radius_km"], frame):
            return None, None, None
    # A fetch that found no river at all and one whose rivers all lie outside the frame answer alike: which of the
    # two it is depends on how far the square reaches past the frame, so on where in the cell it was centred.
    reaches = [f for f in (r.get("rivers") or {}).get("features") or []
               if any(_crosses(frame, a, b) for c in [f["geometry"]["coordinates"]] for a, b in zip(c, c[1:] or c))]
    rivers = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"m3s": f["properties"].get("dis_av_cms"), "order": f["properties"].get("ord_stra")},
         "geometry": f["geometry"]} for f in reaches]}
    basin = next(({"type": "Feature", "geometry": f["geometry"],
                   "properties": {k: f["properties"].get(k) for k in ("sub_area", "up_area")}}
                  for f in (r.get("basins") or {}).get("features") or []
                  if inside(centre[0], centre[1], f["geometry"]["coordinates"])), None)
    river = None
    if reaches:
        from_c = [(min(h3.great_circle_distance((centre[1], centre[0]), (y, x), unit="km")
                       for x, y in _dense(f["geometry"]["coordinates"])), f["properties"].get("dis_av_cms") or 0)
                  for f in reaches]
        near, big = min(from_c), max(from_c, key=lambda t: t[1])
        river = {"nearest_km": round(near[0]), "nearest_m3s": near[1], "largest_km": round(big[0]), "largest_m3s": big[1]}
    return rivers, basin, river


def _dense(pts: list, step: float = 0.002) -> list:
    """A line's vertices with points every ~200 m between them, so the nearest point on a long straight reach is
    not missed. ponytail: point sampling, whole km is all it has to be right to."""
    out = [pts[0]]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        k = max(1, int(max(abs(x2 - x1), abs(y2 - y1)) / step))
        out += [(x1 + (x2 - x1) * i / k, y1 + (y2 - y1) * i / k) for i in range(1, k + 1)]
    return out


def grid(raw: dict, centre: tuple[float, float], large_mw: float = 100.0) -> dict | None:
    """The energy pack's raw result, measured again from the cell's centre: its `km` is from the house, to 10 m.
    `large` marks a plant of the pack's own large cut (adapter.LARGE_MW), the one the Wall draws its line to."""
    if not raw:
        return None
    src = [s for s in raw.get("sources") or [] if isinstance(s, dict) and s.get("lat") is not None and s.get("lon") is not None]
    # the house's nearest few, picked when the pack last polled: from a result for another cell, no substation at all
    same = raw.get("cell") == h3.latlng_to_cell(centre[1], centre[0], 8)
    subs = sorted(km_from(centre, s["lon"], s["lat"]) for s in src if s.get("kind") == "substation" and same)
    # ranked and cut by the unrounded km (30.4 km is not within 30), ties by name: only the km published is whole
    plants = [{"name": s.get("name"), "fuel": s.get("fuel"), "mw": s.get("mw"), "lat": round(s["lat"], 3),
               "lon": round(s["lon"], 3), "km": round(d), "large": (s.get("mw") or 0) >= large_mw}
              for d, s in sorted(((dist_km(centre, s["lon"], s["lat"]), s) for s in src
                                  if s.get("kind") == "plant" and (s.get("mw") or 0) >= 1),
                                 key=lambda t: (t[0], str(t[1].get("name") or ""), t[1]["lat"], t[1]["lon"]))
              if d <= PLANT_KM]
    low = (raw.get("share") or {}).get("low")
    today = raw.get("today")        # the cell's sun today and the panel size the house configured: no position in either
    sun = {"kwh_m2": today.get("sun_kwh_m2"), "roof_kwh": today.get("roof_kwh"), "panel_kw": today.get("panel_kw")} \
        if isinstance(today, dict) else None
    return {"fossil_low_pct": None if low is None else round(low * 100), "substation_km": subs[0] if subs else None,
            "plants": plants, "sun": sun}


def change(earth, near: tuple[float, float]) -> dict | None:
    """The newest land-change pair's Wall image (packs/earth writes change_<A>_<B>_wall.png), placed by the crop the
    earth pack records for it under `wall` in the pair's stats: {bounds (UTM, the stats' crs), ha}. Never by the
    stats' own `bounds`: that square is centred on the house's pixel, so its corners give the house to 10 m, and its
    hectares count the same square. Null until both the image and its crop exist."""
    cs = earth.changes() if earth else []
    if not cs:
        return None
    c = ([x for x in cs if x.get("year_b", 0) - x.get("year_a", 0) == 1] or cs)[-1]
    a, b, crop = c.get("year_a"), c.get("year_b"), c.get("wall") or {}
    bb = crop.get("bounds")
    # a crop cut round another cell (the house moved inside fetch's tolerance) waits for the next `earth change`
    if not bb or crop.get("cell") != h3.latlng_to_cell(near[0], near[1], 8) \
            or not earth.change_file(a, b, "png").with_name(f"change_{a}_{b}_wall.png").is_file():
        return None
    to = _utm(int(str(c["crs"]).rsplit(":", 1)[-1]), near)
    corners = [to(bb[x], bb[y]) for x, y in
               (("west", "north"), ("east", "north"), ("east", "south"), ("west", "south"))]
    # the pair in the URL: a screen that cached last year's image asks again when the pair changes
    return {"a": a, "b": b, "ha": crop.get("ha"), "corners": corners, "png": f"/earth/wall.png?pair={a}_{b}"}


def _inner_m(home: str, run: dict | None) -> int | None:
    """The radius round the cell's centre that the place pack's last fetch covers: its own `radius_m` (place_runs,
    what it really fetched, never the setting) less the farthest a point of the cell can be from its middle. A fetch
    circle round any point of the cell holds that circle, so the answer is the same wherever in the cell the fetch was
    centred and wherever the house is now. Nothing of the house's own point enters it: a radius less the distance the
    house moved since the fetch would say how far it moved. None with no run, when the fetch was centred in another
    cell, or when the run recorded no centre: an older run may have been fetched before a move, from another cell, and
    the place pack fetches again when it finds one (packs/place/adapter.py)."""
    if not run or not run.get("radius_m") or run.get("lat") is None or run.get("lon") is None:
        return None
    if h3.latlng_to_cell(run["lat"], run["lon"], 8) != home:
        return None
    return int(run["radius_m"] - circum_m(home))


_UNREAD_SAID: set = set()


def _ring_limits() -> tuple[float, float, set]:
    """(km, m, withheld): the tightest radius and the widest separation of the station packs that are on, 15 km and
    150 m (the ring's defaults) when none says, and the ids of the packs whose own settings cannot be read. A station
    left from a pack since switched off is held to the defaults. A pack whose settings do not read is withheld whole,
    never held to the defaults: its separation read as 150 m when it is 400 would publish the stations its own rule
    keeps off the list. Said once a process per pack, in the log, so the operator sees why the stations went and a
    kiosk polling /wall does not write it on every read."""
    lim, withheld = [], set()
    for p in packs.stations():
        if not p.get("radius"):
            continue
        try:
            lim.append((float(settings.get(p["radius"], "15") or 15),
                        float(packs.module(p["pack"], on_only=False).cfg().get("min_separation_m", 150))))
        except Exception as e:  # noqa: BLE001 — any failure withholds the pack, never widens the list
            withheld.add(p["pack"])
            if p["pack"] in _UNREAD_SAID:
                continue
            _UNREAD_SAID.add(p["pack"])
            log.warning("wall: %s's settings do not read (%s: %s), its stations are withheld", p["pack"],
                        type(e).__name__, e)
    return min(r for r, _ in lim or [(15.0, 0)]), max(m for _, m in lim or [(0, 150.0)]), withheld


def _safe(build, *args, empty=None):
    """A block built from a pack's file, or `empty` when the file is not what it should be: never a 500."""
    try:
        return build(*args)
    except Exception as e:  # noqa: BLE001 — one malformed file costs its own block
        log.warning("wall: %s: %s: %s", getattr(build, "__name__", "block"), type(e).__name__, e)
        return empty


# ---------------------------------------------------------------- the route

_BUCKETS = "SELECT DISTINCT bucket FROM readings_1h WHERE bucket > now() - interval '24 hours'"
# Only the station packs' own rows (pack.yaml `stations: source:`): `NOT local` alone also takes a Meshtastic radio and
# the household's own kit standing away from home, which stamp_local narrows to local=FALSE (app/sources.py).
_STATIONS = ("SELECT sensor_id, source, lat, lon FROM sensors WHERE kind = 'sensor' AND NOT local AND NOT indoor "
             "ORDER BY sensor_id")
_HOURLY = ("SELECT h.bucket, h.sensor_id, h.metric, h.mean FROM readings_1h h "
           "WHERE h.bucket > now() - interval '24 hours' AND h.sensor_id = ANY(%s) AND h.metric = ANY(%s)")
_LABS = "SELECT name, lat, lon FROM sensors WHERE kind = 'facility' AND lat IS NOT NULL AND lon IS NOT NULL"
_RUN = "SELECT radius_m, lat, lon FROM place_runs ORDER BY run_at DESC LIMIT 1"
_ROOFS = ("SELECT count(*) AS n FROM place_features WHERE kind = 'building' AND "
          "ST_DWithin(ST_Centroid(geom)::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)")


@router.get("/wall")
def wall():
    """What the Wall's map draws (docs/site/wall.md): the three sizes, the 24 hours /issues draws, the air stations
    around and across the island, the roofs, the lab, the water, the grid and the land that changed."""
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    if not (lat or lon):
        raise HTTPException(409, "this node has no NODE_LAT and NODE_LON yet, so there is no place to draw")
    home = h3.latlng_to_cell(lat, lon, 8)
    clat, clon = h3.cell_to_latlng(home)
    centre = (clon, clat)
    now = datetime.now(timezone.utc)
    sc = scales(home)
    city = [p for c in sc[-1]["cells"] for p in c["ring"]]
    frame = (min(p[0] for p in city), min(p[1] for p in city), max(p[0] for p in city), max(p[1] for p in city))
    on = {m["id"] for m in packs.manifests()}
    # The station packs chose their stations round the house: within the radius their pack.yaml names (`stations:
    # radius:`, read as /nearby reads it), and never within the separation their own cfg() reads. The Wall keeps only
    # what those rules keep wherever in the cell the house is. The make pack keeps labs within MAKE_RADIUS_KM.
    circ = circum_m(home)
    far_km, sep_m, withheld = _ring_limits()
    near_m = circ + sep_m + ROUNDED_M

    def ok(la, lo):
        return kept(la, lo, centre, far_km * 1000 - circ, near_m)

    roofs = lab = None
    with db() as con, con.cursor() as cur:
        cur.execute(_BUCKETS)
        buckets = day_buckets([r["bucket"] for r in cur.fetchall()], now)
        cur.execute(_STATIONS)
        srcs = {p["source"] for p in packs.stations() if p["pack"] not in withheld}
        found = [s for s in cur.fetchall() if s["source"] in srcs and s["lat"] is not None and s["lon"] is not None
                 and ok(s["lat"], s["lon"])]
        cur.execute(_HOURLY, ([s["sensor_id"] for s in found] + ["om-point", "marine-point"],
                              ["pm25"] + [m for _, m in HOURS.values()]))
        rows = cur.fetchall()
        if "make" in on:
            cur.execute(_LABS)
            far = float(os.getenv("MAKE_RADIUS_KM", "50")) * 1000 - circ
            labs = sorted((r for r in cur.fetchall() if kept(r["lat"], r["lon"], centre, far, 0)),
                          key=lambda r: (dist_km(centre, r["lon"], r["lat"]), str(r["name"] or "")))
            if labs:
                lab = {"name": labs[0]["name"], "lat": round(labs[0]["lat"], 3), "lon": round(labs[0]["lon"], 3),
                       "km": km_from(centre, labs[0]["lon"], labs[0]["lat"])}
        if "place" in on:
            try:            # the place pack may not have made its tables yet
                cur.execute(_RUN)
                r_m = _inner_m(home, next(iter(cur.fetchall()), None))
                r_m = r_m // 100 * 100 if r_m else None     # whole 100 m
                if r_m and r_m > 0:
                    cur.execute(_ROOFS, (clon, clat, r_m))
                    got = cur.fetchall()
                    roofs = {"osm_in_cells": int(got[0]["n"]), "mapped_radius_m": r_m} if got else None
            except Exception:  # noqa: BLE001
                roofs = None

    out_dir = Path(os.getenv("PACK_OUT", "/app/out"))
    try:
        isl = json.loads((out_dir / "wall" / "island.json").read_text()) \
            if "bali-air-dispatch" in on and "bali-air-dispatch" not in withheld else None
    except (OSError, ValueError):
        isl = None
    hydro, energy, earth = packs.module("hydro"), packs.module("energy"), packs.module("earth")
    rivers, basin, river = (_safe(lambda: water(hydro.result(near=False), frame, centre, hydro.inside, hydro.square),
                                  empty=(None, None, None)) if hydro else (None, None, None))
    return {
        "home": home, "centre": [round(clon, 5), round(clat, 5)], "scales": sc,
        "hours": {"buckets": [b.isoformat() if hasattr(b, "isoformat") else b for b in buckets],
                  **{k: hourly(rows, buckets, sid, m) for k, (sid, m) in HOURS.items()}},
        "stations": [{"lat": round(s["lat"], 3), "lon": round(s["lon"], 3), "pm25": hourly(rows, buckets, s["sensor_id"], "pm25")}
                     for s in found],
        # the island is island-wide: no far edge, only the near one
        "island": _safe(island, isl, now, lambda la, lo: kept(la, lo, centre, None, near_m)), "roofs": roofs, "lab": lab,
        "rivers": rivers, "basin": basin, "river": river,
        "grid": _safe(lambda: grid(energy.result(), centre, energy.LARGE_MW)) if energy else None,
        "change": _safe(change, earth, (clat, clon)),
    }
