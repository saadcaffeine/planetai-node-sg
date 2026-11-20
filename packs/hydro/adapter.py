"""Where the rivers are around this node, and which basins it drains into.

The node fetches its HydroSHEDS region once, on command: which region comes from the level-1 basins (a few MB each),
then the region's HydroRIVERS (50-110 MB) and its level-12 and level-4 HydroBASINS. It keeps what falls in its
square, plus its own basin at both levels, as one small json under out/hydro/, and deletes the downloads. Every
poll re-sends the figures for the nearest river: how far away it is, how much water it carries on average, its
order, the ground that drains into it, and how far it runs to the sea.

The geometry is HydroSHEDS v1 (Lehner & Grill 2013), shown under HydroATLAS v1.0's CC-BY 4.0 (Linke et al. 2019),
which publishes the same rivers and basins. HydroSHEDS' own download carries its v1 licence agreement, which forbids
distributing the data "as a stand-alone product"; the node fetches from there because HydroATLAS's figshare copy
(several GB) refuses scripted downloads, and it never passes the files on whole.

kind='model', scale='city'. Rivers are traced from a 15 arc-second (about 500 m) surface and drawn where at least
10 km2 drains or 0.1 m3/s flows, so a stream, a canal or a subak channel is not on this map; OpenStreetMap's are,
on the street map. Never an Index cell, never an alert. The level-4 basin is the bioregion index.fab.city draws.

pyshp is imported lazily, so a node without it loads the pack, logs once and idles.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import math
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger("planetai.pack.hydro")

BASINS = "https://data.hydrosheds.org/file/HydroBASINS/standard/hybas_{r}_lev{lev:02d}_v1c.zip"
RIVERS = "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_{r}_shp.zip"
RELEASE = "HydroSHEDS v1: HydroBASINS v1c, HydroRIVERS v1.0"
ATTRIBUTION = ("Rivers and basins: HydroSHEDS (Lehner & Grill 2013, Hydrological Processes 27: 2171-2186), as "
               "published in HydroATLAS v1.0 (Linke et al. 2019, Scientific Data 6: 283) under CC-BY 4.0. "
               "Data available at www.hydrosheds.org.")
# The regions HydroSHEDS cuts the world into, with a generous box each. The boxes overlap on purpose: the level-1
# basins decide, and a point in two boxes costs one more small download.
REGIONS = {"af": (-26, -36, 64, 38), "eu": (-32, 11, 75, 82), "si": (55, 44, 180, 82), "as": (55, -13, 155, 56),
           "au": (90, -56, 180, 24), "sa": (-93, -57, -32, 16), "na": (-170, 4, -50, 64), "ar": (-180, 50, -50, 84),
           "gr": (-75, 58, -10, 84)}
# Pfafstetter's first digit is the region (HydroBASINS TechDoc v1c, table 1)
PFAF_REGION = {1: "af", 2: "eu", 3: "si", 4: "as", 5: "au", 6: "sa", 7: "na", 8: "ar", 9: "gr"}
RIVER_KEEP = ("HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "LENGTH_KM", "DIST_DN_KM", "UPLAND_SKM", "DIS_AV_CMS", "ORD_STRA",
              "ORD_FLOW", "ENDORHEIC", "HYBAS_L12")
BASIN_KEEP = ("HYBAS_ID", "NEXT_DOWN", "MAIN_BAS", "DIST_SINK", "SUB_AREA", "UP_AREA", "PFAF_ID", "ENDO", "COAST")
_state = {"warned": False}


# ---------------------------------------------------------------- where

def node() -> str:
    return os.getenv("NODE_NAME", "node")


def aoi() -> tuple[float, float, int]:
    """The node's point and the half-width of its square, in km. 25 km is a river you would know by name."""
    return float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]), int(os.getenv("HYDRO_RADIUS_KM") or 25)


def cache() -> Path:
    return Path(os.getenv("PACK_OUT", "/app/out")) / "hydro" / node()


def result_file() -> Path:
    return cache() / "hydro.json"


def metres(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    dy = (lat_b - lat_a) * 111320.0
    dx = (lon_b - lon_a) * 111320.0 * math.cos(math.radians((lat_a + lat_b) / 2))
    return math.hypot(dx, dy)


def square(lat: float, lon: float, km: float) -> tuple[float, float, float, float]:
    """(west, south, east, north) of the square, in degrees."""
    dlat, dlon = km * 1000 / 111320.0, km * 1000 / (111320.0 * max(math.cos(math.radians(lat)), 0.01))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def result(near: bool = True) -> dict:
    """What `planetai run hydro fetch` kept, or {} when it has not run, or ran around a point or square this node no
    longer is (1 % of the radius, never under 25 m, as terrain). `near=False` skips the point's tolerance and keeps the
    square's size: app/wall.py judges the fetch by the house's res-8 cell instead, since whether the house is within
    that tolerance of the fetch point would say where in the cell it is."""
    try:
        r = json.loads(result_file().read_text())
    except (OSError, ValueError):
        return {}
    lat, lon, km = aoi()
    if r.get("radius_km") != km or (near and metres(r["lat"], r["lon"], lat, lon) > max(km * 10.0, 25.0)):
        return {}
    return r


# ---------------------------------------------------------------- geometry, plain Python

def candidates(lat: float, lon: float) -> list[str]:
    return [r for r, (w, s, e, n) in REGIONS.items() if w <= lon <= e and s <= lat <= n]


def inside(lon: float, lat: float, rings: list) -> bool:
    """Even-odd point in polygon over every ring of a shape (a shapefile's holes are rings too)."""
    hit = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                hit = not hit
    return hit


def rings_of(shape) -> list:
    """A pyshp shape's parts as lists of (lon, lat)."""
    parts = list(shape.parts) + [len(shape.points)]
    return [shape.points[a:b] for a, b in zip(parts, parts[1:])]


def to_segment(lat: float, lon: float, a, b) -> float:
    """Metres from the point to the segment a-b ((lon, lat) pairs), on a plane at the point's latitude."""
    k = 111320.0 * math.cos(math.radians(lat))
    ax, ay, bx, by = (a[0] - lon) * k, (a[1] - lat) * 111320.0, (b[0] - lon) * k, (b[1] - lat) * 111320.0
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)


def to_line(lat: float, lon: float, pts: list) -> float:
    return min(to_segment(lat, lon, a, b) for a, b in zip(pts, pts[1:])) if len(pts) > 1 else metres(lat, lon, pts[0][1], pts[0][0])


def touches(bbox, box) -> bool:
    return not (bbox[2] < box[0] or bbox[0] > box[2] or bbox[3] < box[1] or bbox[1] > box[3])


def rnd(pts, dp: int = 5) -> list:
    """Coordinates to five decimals (about a metre), repeats dropped."""
    out = []
    for x, y in pts:
        q = [round(x, dp), round(y, dp)]
        if not out or out[-1] != q:
            out.append(q)
    return out


def props(rec, keep: tuple) -> dict:
    d = rec.as_dict()
    return {k.lower(): (round(d[k], 3) if isinstance(d[k], float) else d[k]) for k in keep if k in d}


# ---------------------------------------------------------------- the node's contract

def require(*mods: str) -> None:
    missing = [m for m in mods if importlib.util.find_spec(m) is None]
    if missing:
        raise SystemExit(f"hydro: {', '.join(missing)} not installed. planetai packs install, then planetai restart")


def sentence(n: dict) -> str:
    """The nearest river in one line, as the page and the bot say it."""
    km, end = n["dist_m"] / 1000, ("the sea" if not n.get("endorheic") else "where it ends inland")
    return (f"{km:.1f} km to a river carrying {n['dis_av_cms']:g} m³/s on average (order {n['ord_stra']}, "
            f"{n['upland_skm']:,.0f} km² drains into it), "
            + (f"which reaches {end} there" if n["dist_dn_km"] < 1 else f"{n['dist_dn_km']:,.0f} km from {end}"))


def fetch(hc):                                                                  # noqa: ARG001  (read on command)
    """Contract: (sensors, readings). Re-sends what `planetai run hydro fetch` kept, stamped with the fetch's own
    time, so the database keeps one row per figure per fetch."""
    r = result()
    if not r or not r.get("nearest"):
        if not _state["warned"]:
            log.info("hydro: nothing kept for this point yet: planetai run hydro fetch")
            _state["warned"] = True
        return [], []
    lat, lon, km = aoi()
    t = datetime.fromisoformat(r["fetched_at"])
    n, b12, b4 = r["nearest"], r["basin"].get("level12") or {}, r["basin"].get("level4") or {}
    readings = [(t, "hydro-point", "river_m", round(n["dist_m"])),
                (t, "hydro-point", "river_flow_m3s", n["dis_av_cms"]),
                (t, "hydro-point", "river_order", n["ord_stra"]),
                (t, "hydro-point", "river_upland_km2", round(n["upland_skm"])),
                (t, "hydro-point", "river_to_sea_km", round(n["dist_dn_km"]))]
    if r.get("largest"):
        readings.append((t, "hydro-point", "river_largest_m3s", r["largest"]["dis_av_cms"]))
    if b12:
        readings.append((t, "hydro-point", "basin_up_km2", round(b12["up_area"])))
    meta = {"region": r["region"], "radius_km": km, "release": RELEASE, "attribution": ATTRIBUTION,
            "sentence": sentence(n), "largest": sentence(r["largest"]) if r.get("largest") else None, "basin12": {k: b12.get(k) for k in ("hybas_id", "pfaf_id", "sub_area", "up_area")},
            "basin4": {k: b4.get(k) for k in ("hybas_id", "pfaf_id", "sub_area", "up_area")},
            "rivers": len(r["rivers"]["features"]), "basins": len(r["basins"]["features"])}
    sensor = {"sensor_id": "hydro-point", "source": "hydro", "name": f"Rivers within {km} km (HydroRIVERS, about 500 m)",
              "lat": lat, "lon": lon, "indoor": False, "local": False,
              "kind": "model", "scale": "city", "cadence": "P1D", "meta": meta}
    return [sensor], readings
