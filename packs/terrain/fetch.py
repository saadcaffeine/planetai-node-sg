"""Read this node's square of elevation, fill it, route it, and keep the result.  planetai run terrain fetch

About half a megabyte over HTTPS and a second of arithmetic for a 10 km square at 30 m. Run it again only when
the node moves or TERRAIN_RADIUS_M changes: the surface does not change between releases.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A                                                              # noqa: E402

A.require("numpy", "rasterio")
lat, lon, radius = A.aoi()
cov = A.coverage()
if cov["kind"] == "none":
    raise SystemExit(f"terrain: {cov['why']}. planetai run terrain coverage says more.")
licence = os.getenv("TERRAIN_DEM_LICENCE") or ""
t0 = time.time()
z, sea, dx, dy, rc = A.read(cov)
t1 = time.time()
p = A.compute(z, sea, dx, dy, rc)
t2 = time.time()
if p["stuck"]:
    raise SystemExit(f"terrain: {p['stuck']} land cells have nowhere to drain after the fill. That is a bug in the "
                     f"fill, not in the data; nothing was written.")
out = {"lat": lat, "lon": lon, "radius_m": radius, "computed_at": datetime.now(timezone.utc).isoformat(),
       "dem": {k: cov[k] for k in ("kind", "tiles", "missing", "why")} | ({"path": cov["path"]} if "path" in cov else {}),
       "release": A.RELEASE if cov["kind"] != "file" else None,
       "attribution": A.ATTRIBUTION if cov["kind"] != "file" else licence,
       "publish": cov["kind"] != "file" or bool(licence), "point": p}
A.cache().mkdir(parents=True, exist_ok=True)
A.result_file().write_text(json.dumps(out, indent=1, sort_keys=True))

print(f"terrain · {cov['kind']} · {p['shape'][0]} x {p['shape'][1]} px of {p['pixel_m'][0]} x {p['pixel_m'][1]} m · "
      f"read {t1 - t0:.1f} s, computed {t2 - t1:.1f} s")
print(f"  square: land {p['z_min']:.1f} to {p['z_max']:.1f} m, {p['sea_frac'] * 100:.1f} % sea, "
      f"{p['filled_frac'] * 100:.1f} % of the land in hollows (deepest {p['max_fill_m']:.1f} m)")
print(f"  this point: {p['height_m']:.1f} m high, {p['upslope_m2'] / 1e4:.2f} ha drains through it, "
      f"hollow {p['hollow_m']:.2f} m; the largest flow within {p['near_m']} m drains {p['upslope_near_m2'] / 1e4:.1f} ha")
if not out["publish"]:
    print("\n  Computed and kept, and not shown: TERRAIN_DEM_LICENCE is blank, so nothing says this DEM may be published.")
print(f"\n  {out['attribution']}")
