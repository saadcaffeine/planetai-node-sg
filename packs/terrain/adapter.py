"""Where the rain goes around this node: its own square of elevation, filled and routed here, and the rain the
forecast puts on the ground that drains through it.

The elevation is Copernicus DEM GLO-30 (or GLO-90 where the 30 m tile is not public, or a GeoTIFF the operator
supplies), range-read once on command around the node and kept under out/terrain/. Two numbers come out of it for
the node's own pixel: how much ground drains through it, and how deep water would stand there before it runs on.
Every poll then sums the next 24 hours of `fc_rain` from ONE forecast source and multiplies.

kind='model', scale='city'. Region distance only: at 30 m a pixel is a street block, and the model is a SURFACE
model (roofs and canopy are in the heights). Never an Index cell, never an alert.

No wetness index and no percentile, on purpose. TWI is ln(a / tan b), and on a filled pixel tan b is clipped to
near zero, so the index is mostly the clip: at node #1 ln(1/0.001) was 6.9 of 12.74. A percentile ranks the square
against itself, so every square has a "wettest tenth". The two physical numbers TWI is made from need neither.

numpy and rasterio are imported lazily, so a node without them loads the pack, logs once and idles.
"""
from __future__ import annotations

import heapq
import importlib.util
import json
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("planetai.pack.terrain")

BUCKETS = {"glo30": ("https://copernicus-dem-30m.s3.amazonaws.com", 10),
           "glo90": ("https://copernicus-dem-90m.s3.amazonaws.com", 30)}
RELEASE = "2021 (the AWS copy; objects last modified 9 May 2022)"
# Art. 6b and 6c of the COP-DEM-GLO-30-F licence: the notice for derived data and the no-liability sentence, both
# required wherever a number derived from it is shown, and both binding on whoever we pass it to (Art. 6e).
ATTRIBUTION = ("produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH "
               "2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. "
               "The organisations in charge of the Copernicus programme by law or by delegation do not incur any "
               "liability for any use of the Copernicus WorldDEM-30.")
EPS = 1e-4            # metres a filled flat falls per cell, so that it still drains
NEAR_M = 60           # the "flow passing near" radius: about two GLO-30 pixels, past the error of a typed address
SOURCES = ("forecast-bmkg", "forecast-om")      # one only, in this order: the official forecast first (as app/ask.py)
_state = {"warned": False}


# ---------------------------------------------------------------- where

def node() -> str:
    return os.getenv("NODE_NAME", "node")


def aoi() -> tuple[float, float, int]:
    """The node's point, and the half-width of the square around it. 5000 is a 10 km square, earth's own."""
    return float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]), int(os.getenv("TERRAIN_RADIUS_M") or 5000)


def metres(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    dy = (lat_b - lat_a) * 111320.0
    dx = (lon_b - lon_a) * 111320.0 * math.cos(math.radians((lat_a + lat_b) / 2))
    return math.hypot(dx, dy)


def cache() -> Path:
    return Path(os.getenv("PACK_OUT", "/app/out")) / "terrain" / node()


def result_file() -> Path:
    return cache() / "terrain.json"


def result() -> dict:
    """What `planetai run terrain fetch` computed, or {} when it has not, or when it was computed around a point
    or a square this node no longer is (same tolerance as earth: 1 % of the radius, never under 25 m)."""
    try:
        r = json.loads(result_file().read_text())
    except (OSError, ValueError):
        return {}
    lat, lon, radius = aoi()
    if r.get("radius_m") != radius or metres(r["lat"], r["lon"], lat, lon) > max(radius * 0.01, 25.0):
        return {}
    # Nor a result from another DEM: a file computed before TERRAIN_DEM_PATH changed (or was cleared) must not be
    # shown under the licence typed for the current one, and Copernicus must not stand in for a file.
    path = os.getenv("TERRAIN_DEM_PATH") or ""
    dem = r.get("dem") or {}
    if (dem.get("kind") == "file") != bool(path) or (path and dem.get("path") != path):
        return {}
    return r


# ---------------------------------------------------------------- coverage

def tile_name(lat: float, lon: float, arcsec: int) -> str:
    """Copernicus_DSM_COG_<10|30>_<S09_00>_<E115_00>_DEM: the one-degree tile whose south-west corner is under
    the point."""
    la, lo = math.floor(lat), math.floor(lon)
    return (f"Copernicus_DSM_COG_{arcsec}_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_"
            f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM")


def tile_url(kind: str, name: str) -> str:
    return f"{BUCKETS[kind][0]}/{name}/{name}.tif"


def degrees(lat: float, radius_m: int) -> tuple[float, float]:
    return radius_m / 111320.0, radius_m / (111320.0 * math.cos(math.radians(lat)))


def tiles_for(lat: float, lon: float, radius_m: int, arcsec: int) -> list[str]:
    """Every tile the square touches. One at node #1; up to four at a corner."""
    dlat, dlon = degrees(lat, radius_m)
    return sorted({tile_name(a, b, arcsec) for a in (lat - dlat, lat + dlat) for b in (lon - dlon, lon + dlon)})


def coverage(hc=None) -> dict:
    """Which elevation this node would use, in the order the README gives, before anything is downloaded.

    {"kind": "file"|"glo30"|"glo90"|"none", "tiles": [...], "missing": [...], "why": "..."}. A tile missing from
    the 30 m bucket and present at 90 m is one of the 25 Caucasus tiles; missing from both is open sea or nothing
    published, and the two cannot be told apart from here.
    """
    path = os.getenv("TERRAIN_DEM_PATH") or ""
    if path:
        ok = Path(path).is_file()
        return {"kind": "file" if ok else "none", "path": path, "tiles": [], "missing": [] if ok else [path],
                "why": "the operator's own DEM" if ok else f"TERRAIN_DEM_PATH names {path}, which is not a file"}
    import httpx
    hc = hc or httpx.Client(timeout=30)
    lat, lon, radius = aoi()
    seen = {}
    for kind in ("glo30", "glo90"):
        names = tiles_for(lat, lon, radius, BUCKETS[kind][1])
        found = [n for n in names if hc.head(tile_url(kind, n)).status_code == 200]
        seen[kind] = (names, found)
        # The node's own tile must exist; a neighbour missing is sea (the pack reads it as 0, as the README says).
        if tile_name(lat, lon, BUCKETS[kind][1]) in found:
            return {"kind": kind, "tiles": found, "missing": sorted(set(names) - set(found)),
                    "why": "public 30 m tile" if kind == "glo30" else
                           "no public 30 m tile here (the Caucasus tiles are 90 m only on AWS)"}
    return {"kind": "none", "tiles": [], "missing": seen["glo30"][0],
            "why": "no tile in either bucket: open sea, or nothing published"}


# ---------------------------------------------------------------- reading

def require(*mods: str) -> None:
    missing = [m for m in mods if importlib.util.find_spec(m) is None]
    if missing:
        raise SystemExit(f"terrain: the app image has no {', '.join(missing)}. It is declared in "
                         f"packs/terrain/pack.yaml; `planetai update` does not install a pack's libraries.\n\n"
                         f"      planetai packs install\n      planetai restart\n\nThen run this again.")


def read(cov: dict):
    """(z, transform-free geometry) for the square: z in metres as float64, `sea` True where nothing drains in,
    pixel size in metres, and the node's (row, col). Tiles are mosaicked by rasterio.merge with the window as
    bounds, so a square across a tile edge is one array; a missing neighbour tile reads 0, the sea."""
    import numpy as np
    import rasterio
    from rasterio.merge import merge
    from rasterio.warp import transform, transform_bounds
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
    lat, lon, radius = aoi()
    dlat, dlon = degrees(lat, radius)
    srcs = ([cov["path"]] if cov["kind"] == "file" else
            ["/vsicurl/" + tile_url(cov["kind"], n) for n in cov["tiles"]])
    dss = [rasterio.open(s) for s in srcs]
    try:
        crs = dss[0].crs
        bounds = transform_bounds("EPSG:4326", crs, lon - dlon, lat - dlat, lon + dlon, lat + dlat)
        nodata = dss[0].nodata
        if cov["kind"] == "file":       # outside the file is missing, never ground at 0 m: float, NaN-filled
            arr, tr = merge(dss, bounds=bounds, nodata=nodata if nodata is not None else float("nan"), dtype="float64")
        else:                           # a missing Copernicus neighbour tile is the sea, which GLO writes as 0
            arr, tr = merge(dss, bounds=bounds, nodata=0)
    finally:
        for d in dss:
            d.close()
    z = arr[0].astype("float64")
    # GLO stores the sea as exactly 0 and has no nodata. An operator's file marks outside with its own nodata, NaN
    # included (NaN never equals NaN), and a 0 in it is ground at sea level. Land below sea level (a polder) is
    # negative and stays land either way.
    if cov["kind"] == "file":
        sea = np.isnan(z) | ((z == nodata) if nodata is not None and not math.isnan(nodata) else False)
        z[sea] = 0.0
    else:
        sea = z == 0
    if crs.is_geographic:
        dx = abs(tr.a) * 111320.0 * math.cos(math.radians(lat))
        dy = abs(tr.e) * 111320.0
    else:
        unit = crs.linear_units_factor[1]  # metres per CRS unit: 1 for UTM, 0.3048 for a state plane in feet
        dx, dy = abs(tr.a) * unit, abs(tr.e) * unit
    xs, ys = transform("EPSG:4326", crs, [lon], [lat])
    col, row = ~tr * (xs[0], ys[0])
    return z, np.asarray(sea), dx, dy, (row, col)      # fractional: the point inside its pixel, for the 60 m circle


# ---------------------------------------------------------------- the arithmetic, numpy and heapq only

N8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def fill(z, sea):
    """Priority-flood (Barnes, Lehman & Mulla 2014). The window's edge and the sea are outlets; every other cell
    is raised to at least the cell it is reached from plus EPS, so after this every land cell has a strictly
    lower neighbour. `filled - z` is how deep water would stand before it overflows.
    ponytail: a pure-Python heap, ~0.2 s for 10 km at 30 m; a 20 km square is about 2 s. numba if it ever matters."""
    import numpy as np
    H, W = z.shape
    f = z.copy()
    done = np.zeros(z.shape, dtype=bool)
    pq = []
    for r in range(H):
        for c in range(W):
            if sea[r, c] or r in (0, H - 1) or c in (0, W - 1):
                heapq.heappush(pq, (f[r, c], r, c))
                done[r, c] = True
    while pq:
        e, r, c = heapq.heappop(pq)
        for a, b in N8:
            rr, cc = r + a, c + b
            if 0 <= rr < H and 0 <= cc < W and not done[rr, cc]:
                done[rr, cc] = True
                if f[rr, cc] < e + EPS:
                    f[rr, cc] = e + EPS
                heapq.heappush(pq, (f[rr, cc], rr, cc))
    return f


def steepest(f, dx: float, dy: float):
    """(direction index into N8, drop per metre) for every cell, on the filled surface. Off the window's edge is
    a drop of 1e9: an edge cell always leaves."""
    import numpy as np
    H, W = f.shape
    pad = np.pad(f, 1, constant_values=-1e9)
    drops = np.stack([(f - pad[1 + a:1 + a + H, 1 + b:1 + b + W]) / math.hypot(a * dy, b * dx) for a, b in N8])
    return drops.argmax(0), drops.max(0)


def accumulate(f, sea, k):
    """D8 upslope count, including the cell itself: highest first, each cell hands its count downhill."""
    import numpy as np
    H, W = f.shape
    acc = np.ones(f.shape)
    acc[sea] = 0
    for i in np.argsort(-f, axis=None, kind="stable"):
        r, c = divmod(int(i), W)
        if sea[r, c]:
            continue
        a, b = N8[k[r, c]]
        rr, cc = r + a, c + b
        if 0 <= rr < H and 0 <= cc < W:
            acc[rr, cc] += acc[r, c]
    return acc


def stuck(f, sea, drop) -> int:
    """Land cells off the edge with no lower neighbour. Zero after a correct fill; verify and the test hold it."""
    inner = ~sea
    inner[0, :] = inner[-1, :] = inner[:, 0] = inner[:, -1] = False
    return int((inner & (drop <= 0)).sum())


def compute(z, sea, dx: float, dy: float, rc: tuple[float, float]) -> dict:
    """Everything the pack keeps: the node's pixel, the largest flow within NEAR_M, and the square's shape."""
    import numpy as np
    f = fill(z, sea)
    k, drop = steepest(f, dx, dy)
    acc = accumulate(f, sea, k)
    depth = f - z
    rf, cf = rc                                     # the point, in pixel units (row, col) from the window's corner
    r, c = int(rf), int(cf)                         # the pixel it falls in
    H, W = z.shape
    if not (0 <= r < H and 0 <= c < W) or sea[r, c]:
        raise RuntimeError("the node's point is outside the square or on the sea")
    n = math.ceil(NEAR_M / min(dx, dy)) + 1
    r0, c0 = max(0, r - n), max(0, c - n)
    rows, cols = np.ogrid[r0:min(H, r + n + 1), c0:min(W, c + n + 1)]
    # A circle from the point itself to each pixel's centre; the point's own pixel always counts.
    within = np.hypot((rows + 0.5 - rf) * dy, (cols + 0.5 - cf) * dx) <= NEAR_M
    within[r - r0, c - c0] = True
    near = acc[r0:r + n + 1, c0:c + n + 1][within]
    land = ~sea
    px = dx * dy
    return {
        "upslope_m2": float(acc[r, c] * px), "upslope_near_m2": float(near.max() * px),
        "hollow_m": float(depth[r, c]), "height_m": float(z[r, c]),
        "pixel_m": [round(dx, 1), round(dy, 1)], "shape": [H, W], "near_m": NEAR_M,
        "sea_frac": float(sea.mean()), "filled_frac": float((depth[land] > 0.05).mean()) if land.any() else 0.0,
        "max_fill_m": float(depth.max()), "z_min": float(z[land].min()), "z_max": float(z[land].max()),
        "stuck": stuck(f, sea, drop),
    }


# ---------------------------------------------------------------- the rain

RAIN_SQL = """SELECT sensor_id, sum(value), count(*), max(ts) FROM readings
              WHERE metric = 'fc_rain' AND sensor_id = ANY(%s)
                AND ts > now() AND ts <= now() + interval '24 hours'
              GROUP BY sensor_id"""


def pick(rows) -> dict | None:
    """One source's next 24 hours, never two added: BMKG and Open-Meteo step at 3 h and 1 h, and a sum over both
    would double the rain. `rows` is (sensor_id, mm, steps, last ts) per source."""
    by = {r[0]: r for r in rows if r[1] is not None}
    sid = next((s for s in SOURCES if s in by), None)
    if sid is None:
        return None
    _, mm, steps, last = by[sid]
    return {"source": sid, "mm": float(mm), "steps": int(steps), "until": last}


def rain() -> dict | None:
    try:
        import psycopg
        with psycopg.connect(os.environ["DATABASE_URL"]) as con, con.cursor() as cur:
            cur.execute(RAIN_SQL, (list(SOURCES),))
            return pick(cur.fetchall())
    except Exception as e:  # noqa: BLE001 — no forecast means no water figure, never no terrain
        log.info("terrain: no forecast rain to read (%s)", type(e).__name__)
        return None


# ---------------------------------------------------------------- the node's contract

def fetch(hc):                                                                  # noqa: ARG001  (the DEM is read on command)
    """Contract: (sensors, readings). Reads what `planetai run terrain fetch` computed, and joins the forecast.

    The terrain rows carry the computation's own timestamp, so a poll re-sends them and the database keeps one.
    The rain and the water are stamped on the hour: one row an hour, and a forecast that stops leaves an hour that
    stops moving, which the page shows as age."""
    r = result()
    if not r:
        if not _state["warned"]:
            log.info("terrain: nothing computed for this point yet: planetai run terrain fetch")
            _state["warned"] = True
        return [], []
    if r["dem"]["kind"] == "file" and not os.getenv("TERRAIN_DEM_LICENCE"):
        return [], []           # an operator's DEM with no licence typed in now: computed, never shown
    lat, lon, radius = aoi()
    t = datetime.fromisoformat(r["computed_at"])
    p = r["point"]
    readings = [(t, "terrain-point", "terrain_upslope_ha", round(p["upslope_m2"] / 1e4, 2)),
                (t, "terrain-point", "terrain_upslope_near_ha", round(p["upslope_near_m2"] / 1e4, 2)),
                (t, "terrain-point", "terrain_hollow_m", round(p["hollow_m"], 2))]
    fc = rain()
    meta = {"dem": r["dem"], "radius_m": radius, "pixel_m": p["pixel_m"], "near_m": p["near_m"],
            "release": r.get("release"),
            "attribution": os.getenv("TERRAIN_DEM_LICENCE") if r["dem"]["kind"] == "file" else ATTRIBUTION}
    if fc:
        hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        readings += [(hour, "terrain-point", "rain_24h_mm", round(fc["mm"], 1)),
                     # an upper bound: as if none of it soaks in, which the sentence says
                     (hour, "terrain-point", "water_24h_m3", round(fc["mm"] / 1000 * p["upslope_m2"]))]
        meta["rain"] = {"source": fc["source"], "steps": fc["steps"],
                        "until": fc["until"].isoformat() if hasattr(fc["until"], "isoformat") else fc["until"]}
    kind = {"glo30": "Copernicus DEM GLO-30", "glo90": "Copernicus DEM GLO-90"}.get(r["dem"]["kind"], "the operator's DEM")
    sensor = {"sensor_id": "terrain-point", "source": "terrain",
              "name": f"Ground within {radius // 1000} km ({kind}, {p['pixel_m'][0]:.0f} m)",
              "lat": lat, "lon": lon, "indoor": False, "local": False,
              "kind": "model", "scale": "city", "cadence": "PT1H", "meta": meta}
    return [sensor], readings
