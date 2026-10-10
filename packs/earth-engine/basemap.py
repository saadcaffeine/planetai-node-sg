"""This node's own satellite base: a cloud-free Sentinel-2 picture of its place, kept on its own disk.

    planetai run earth-engine basemap [--months 12] [--dry-run]

The median of every clear Sentinel-2 pass over the last --months (default twelve), in true colour, 10 m. Built in
this node's own Earth Engine project from Copernicus data (free, full and open) and fetched once as map tiles at
zoom 8-15, in two rings: GROUND_SAT_WIDE_KM round the node for context, GROUND_RADIUS_KM for detail. Written to
out/ground/imagery.mbtiles and served by the node at GET /ground/imagery, so a map that draws it asks nobody
anything. 10 m is Sentinel-2's own grain: past zoom 15 a map enlarges it, and only a drone mosaic is sharper
(planetai run place basemap --only drone).

WHAT IT REVEALS, ONCE: Earth Engine runs the composite for the two squares, so Google learns them, under this
node's own project. After the fetch nothing is sent.
"""
import argparse
import concurrent.futures as cf
import json
import math
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

LAT, LON = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
OUT = Path(os.getenv("PACK_OUT", "/app/out")) / "ground"
R_KM = float(os.getenv("GROUND_RADIUS_KM", "12"))
WIDE_KM = float(os.getenv("GROUND_SAT_WIDE_KM", "60"))
RINGS = [(range(8, 12), WIDE_KM), (range(12, 16), R_KM)]
S2 = "COPERNICUS/S2_SR_HARMONIZED"
# True colour, stretched for a tropical coast: reflectance 0 to 0.22, a little gamma to open the vegetation.
VIS = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 2200, "gamma": 1.25}


def tiles_around(lat, lon, km, z):
    """Every (x, y) tile at zoom z touching the square of half-width `km` round (lat, lon). Same as place/basemap.py."""
    dlat, dlon = km / 110.574, km / (111.320 * math.cos(math.radians(lat)))
    n = 2 ** z

    def xy(la, lo):
        r = math.radians(max(-85.05, min(85.05, la)))
        return (int((lo + 180) / 360 * n), int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n))
    x0, y0 = xy(lat + dlat, lon - dlon)
    x1, y1 = xy(lat - dlat, lon + dlon)
    return [(x % n, y) for x in range(x0, x1 + 1) for y in range(max(0, y0), min(n - 1, y1) + 1)]


def composite(ee, aoi, months):
    """Median of the clear pixels: shadow, medium and high cloud, cirrus and saturated pixels masked by the scene
    classification Sentinel-2 ships with every pass."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=int(months * 30.5))

    def clear(img):
        scl = img.select("SCL")
        ok = scl.neq(1).And(scl.neq(3)).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return img.select(["B4", "B3", "B2"]).updateMask(ok)
    col = ee.ImageCollection(S2).filterBounds(aoi).filterDate(str(start), str(end)).map(clear)
    return col.median(), col.size(), (str(start), str(end))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    jobs = sorted({(z, x, y) for zs, km in RINGS for z in zs for x, y in tiles_around(LAT, LON, km, z)})
    print(f"earth-engine basemap: {len(jobs)} tiles at zoom 8-15, {WIDE_KM * 2:.0f} km wide and {R_KM * 2:.0f} km close. "
          f"Earth Engine learns these two squares, once; after it the map is read from {OUT}.", flush=True)
    if a.dry_run:
        return
    try:
        import ee
    except ImportError:
        sys.exit("earth-engine: the app image has no earthengine-api.  planetai packs install, then planetai restart")
    from timelapse import _init
    proj = _init()
    dlat, dlon = WIDE_KM / 110.574, WIDE_KM / (111.320 * math.cos(math.radians(LAT)))
    aoi = ee.Geometry.Rectangle([LON - dlon, LAT - dlat, LON + dlon, LAT + dlat])
    img, n, (d0, d1) = composite(ee, aoi, a.months)
    passes = n.getInfo()
    if not passes:
        sys.exit(f"earth-engine: no Sentinel-2 pass over this place between {d0} and {d1}")
    fetcher = img.getMapId(VIS)["tile_fetcher"]
    print(f"earth-engine basemap: median of {passes} passes, {d0} to {d1}, in project {proj}.", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "imagery.mbtiles.part"
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript("CREATE TABLE metadata (name TEXT, value TEXT);"
                     "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
                     "CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row);")
    credit = f"Contains modified Copernicus Sentinel data {d0[:4]}-{d1[:4]}, composited by this node in Earth Engine"
    db.executemany("INSERT INTO metadata VALUES (?, ?)", [("name", "imagery"), ("format", "png"), ("minzoom", "8"),
                                                          ("maxzoom", "15"), ("attribution", credit)])
    t0 = time.time()

    def one(job):
        z, x, y = job
        for attempt in range(3):
            try:
                return job, fetcher.fetch_tile(x=x, y=y, z=z)
            except Exception:  # noqa: BLE001 — Earth Engine throttles bursts; wait and ask again
                time.sleep(2 * (attempt + 1))
        return job, None
    kept = 0
    with cf.ThreadPoolExecutor(4) as ex:
        for (z, x, y), data in ex.map(one, jobs):
            if data:
                db.execute("INSERT OR IGNORE INTO tiles VALUES (?, ?, ?, ?)", (z, x, (1 << z) - 1 - y, data)); kept += 1
    db.commit(); db.close()
    tmp.replace(OUT / "imagery.mbtiles")
    size = (OUT / "imagery.mbtiles").stat().st_size
    mp = OUT / "meta.json"
    m = json.loads(mp.read_text()) if mp.exists() else {}
    m["imagery"] = {"source": "Sentinel-2 L2A median composite (Copernicus), this node's Earth Engine", "collection": S2,
                    "passes": passes, "from": d0, "to": d1, "licence": "Copernicus open data", "attribution": credit,
                    "tiles": kept, "missing": len(jobs) - kept, "bytes": size, "maxzoom": 15, "metres_per_pixel": 10,
                    "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    mp.write_text(json.dumps(m, indent=1))
    print(f"earth-engine basemap: {kept} of {len(jobs)} tiles, {size / 1e6:.1f} MB, in {time.time() - t0:.0f}s. "
          f"Served at /ground/imagery.", flush=True)


if __name__ == "__main__":
    main()
