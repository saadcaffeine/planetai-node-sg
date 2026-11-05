"""The terrain pack's arithmetic and its contract, offline: no bucket, no rasterio, no database.

numpy is imported without a guard, as in test_earth: the pack's only claim is arithmetic, and a run that prints
"skipped" would let a broken fill ship.
Run: PYTHONPATH=/tmp/stub:app python3 tests/test_terrain.py
"""
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

import numpy as np

os.environ.setdefault("NODE_LAT", "-8.8271")
os.environ.setdefault("NODE_LON", "115.15709")
os.environ.setdefault("NODE_NAME", "test-node")
os.environ["PACK_OUT"] = tempfile.mkdtemp()
os.environ.pop("TERRAIN_RADIUS_M", None)

spec = importlib.util.spec_from_file_location("terrainpack", "packs/terrain/adapter.py")
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


# ---------------------------------------------------------------- tiles
check(A.tile_name(-8.8271, 115.15709, 10) == "Copernicus_DSM_COG_10_S09_00_E115_00_DEM", "node #1's tile name")
check(A.tile_name(41.68, 44.03, 30) == "Copernicus_DSM_COG_30_N41_00_E044_00_DEM", "a 90 m tile name")
check(A.tile_name(51.5, -0.1, 10) == "Copernicus_DSM_COG_10_N51_00_W001_00_DEM", "west of Greenwich floors to W001")
check(len(A.tiles_for(-8.8271, 115.15709, 5000, 10)) == 1, "node #1's square is one tile")
check(len(A.tiles_for(0.01, 0.01, 5000, 10)) == 4, "a square on a tile corner touches four")

# ---------------------------------------------------------------- fill
# A bowl: rim at 10, floor at 4, one cell lower at 2. Every inner cell fills to the rim (plus EPS steps).
z = np.full((7, 7), 10.0)
z[1:6, 1:6] = 4.0
z[3, 3] = 2.0
sea = np.zeros(z.shape, dtype=bool)
f = A.fill(z, sea)
check(abs((f - z)[3, 3] - 8.0) < 0.01, f"the pit fills to the rim: {(f - z)[3, 3]:.3f} m, not 8")
check(np.all(f >= z), "a fill never lowers the ground")
k, drop = A.steepest(f, 30.0, 30.0)
check(A.stuck(f, sea, drop) == 0, "after the fill every inner land cell has a lower neighbour")
# and without the fill the pit is stuck: the check can fail
_, d0 = A.steepest(z, 30.0, 30.0)
check(A.stuck(z, sea, d0) > 0, "stuck() finds the unfilled pit")

# ---------------------------------------------------------------- accumulation
# A plane falling to the south edge: every cell drains straight down its column, so the cell above the
# bottom row carries the column above it. The top row is the window's edge, an outlet, and sends its water out.
H, W = 6, 5
plane = np.repeat(np.arange(H, 0, -1, dtype=float)[:, None] * 10, W, axis=1)
sea = np.zeros(plane.shape, dtype=bool)
fp = A.fill(plane, sea)
k, _ = A.steepest(fp, 30.0, 30.0)
acc = A.accumulate(fp, sea, k)
check(acc[H - 2, 2] == H - 2, f"a column of {H - 2} inner cells reaches the row above the edge, got {acc[H - 2, 2]}")
check(acc[0, 2] == 1, "the top cell drains only itself")
# The sea takes water and sends none on.
sea2 = np.zeros(plane.shape, dtype=bool)
sea2[H - 1, :] = True
acc2 = A.accumulate(A.fill(plane, sea2), sea2, A.steepest(A.fill(plane, sea2), 30.0, 30.0)[0])
check(acc2[H - 2, 2] == H - 2, "land above the sea accumulates the same")

# ---------------------------------------------------------------- compute at a point
p = A.compute(z, np.zeros(z.shape, dtype=bool), 30.0, 30.0, (3, 3))
check(abs(p["hollow_m"] - 8.0) < 0.01, "compute reports the pit's depth")
check(p["upslope_m2"] >= 900.0, "the point drains at least its own pixel")
check(p["upslope_near_m2"] >= p["upslope_m2"], "the largest flow near is at least the point's own")
check(p["stuck"] == 0, "compute's own stuck count is zero")
# The "within 60 m" figure is a circle. At 90 m a pixel no neighbour is within 60 m, so a huge flow next door
# must not count; at 30 m the cell beside it (30 m) does and the diagonal two out (85 m) does not.
flat = np.zeros((9, 9)) + 5.0
acc_big = np.ones((9, 9)); acc_big[4, 5] = 999; acc_big[6, 6] = 777
A_fill, A_steep, A_acc = A.fill, A.steepest, A.accumulate
A.accumulate = lambda f, sea, k: acc_big
p90 = A.compute(flat, np.zeros((9, 9), dtype=bool), 90.0, 90.0, (4.5, 4.5))
p30 = A.compute(flat, np.zeros((9, 9), dtype=bool), 30.0, 30.0, (4.5, 4.5))
A.accumulate = A_acc
check(p90["upslope_near_m2"] == 1 * 8100.0, f"at 90 m only the point itself is within 60 m, got {p90['upslope_near_m2']}")
check(p30["upslope_near_m2"] == 999 * 900.0, f"at 30 m the neighbour counts, got {p30['upslope_near_m2']}")
# Measured from the point, not its pixel: pixel (4, 6)'s centre is 45 m from the east corner of pixel (4, 4) and
# 76 m from its west corner. The pixel the point falls in is the same both times.
acc_far = np.ones((9, 9)); acc_far[4, 6] = 999
A.accumulate = lambda f, sea, k: acc_far
far = A.compute(flat, np.zeros((9, 9), dtype=bool), 30.0, 30.0, (4.99, 4.99))
near = A.compute(flat, np.zeros((9, 9), dtype=bool), 30.0, 30.0, (4.0, 4.0))
A.accumulate = A_acc
check(far["upslope_near_m2"] == 999 * 900.0, "an off-centre point near the neighbour reaches it")
check(near["upslope_near_m2"] < 999 * 900.0, "the same pixel, its other corner, does not")
try:
    A.compute(z, np.ones(z.shape, dtype=bool), 30.0, 30.0, (3, 3))
    fails.append("a point on the sea should refuse")
except RuntimeError:
    pass

# ---------------------------------------------------------------- one rain source, never two
now = datetime(2026, 10, 23, tzinfo=timezone.utc)
check(A.pick([("forecast-om", 12.0, 24, now), ("forecast-bmkg", 30.0, 8, now)])["source"] == "forecast-bmkg",
      "BMKG first when both have rain rows")
check(A.pick([("forecast-om", 12.0, 24, now), ("forecast-bmkg", 30.0, 8, now)])["mm"] == 30.0, "and its sum alone")
check(A.pick([("forecast-om", 12.0, 24, now)])["source"] == "forecast-om", "Open-Meteo when it is the only one")
check(A.pick([]) is None, "no rows, no rain")

# ---------------------------------------------------------------- the contract
check(A.fetch(None) == ([], []), "nothing kept: no sensor, no readings")
lat, lon, radius = A.aoi()
kept = {"lat": lat, "lon": lon, "radius_m": radius, "computed_at": "2026-10-23T08:00:00+00:00",
        "dem": {"kind": "glo30", "tiles": ["x"], "missing": [], "why": "public 30 m tile"},
        "release": A.RELEASE, "attribution": A.ATTRIBUTION, "publish": True,
        "point": {"upslope_m2": 10400.0, "upslope_near_m2": 125000.0, "hollow_m": 0.32,
                  "pixel_m": [30.6, 30.9], "near_m": 60}}
A.cache().mkdir(parents=True, exist_ok=True)
A.result_file().write_text(json.dumps(kept))
A.rain = lambda: {"source": "forecast-bmkg", "mm": 40.0, "steps": 8, "until": now}
sensors, readings = A.fetch(None)
vals = {m: v for _, _, m, v in readings}
check(vals.get("water_24h_m3") == 416, f"40 mm on 1.04 ha is 416 m³, got {vals.get('water_24h_m3')}")
check(vals.get("terrain_upslope_ha") == 1.04 and vals.get("terrain_hollow_m") == 0.32, "the terrain rows")
check(sensors and sensors[0]["kind"] == "model" and not sensors[0]["local"], "a model row, never local")
check("Copernicus" in sensors[0]["meta"]["attribution"] and "liability" in sensors[0]["meta"]["attribution"],
      "the derived-data notice and the liability sentence travel with the row")
check(sensors[0]["meta"]["rain"]["source"] == "forecast-bmkg", "the rain's source is named")
A.rain = lambda: None
_, readings = A.fetch(None)
check({m for _, _, m, _ in readings} == {"terrain_upslope_ha", "terrain_upslope_near_ha", "terrain_hollow_m"},
      "no forecast: terrain rows only, no water figure")
A.result_file().write_text(json.dumps(kept | {"dem": {"kind": "file", "path": "/x.tif", "tiles": [], "missing": []}}))
check(A.result() == {}, "a file's result is not this node's when TERRAIN_DEM_PATH is unset")
os.environ["TERRAIN_DEM_PATH"] = "/y.tif"
check(A.result() == {}, "nor when TERRAIN_DEM_PATH names another file")
os.environ["TERRAIN_DEM_PATH"] = "/x.tif"
os.environ.pop("TERRAIN_DEM_LICENCE", None)
check(A.fetch(None) == ([], []), "an operator's DEM with no licence is never shown")
os.environ["TERRAIN_DEM_LICENCE"] = "CC BY 4.0, our own drone survey"
sensors, _ = A.fetch(None)
check(sensors and sensors[0]["meta"]["attribution"] == "CC BY 4.0, our own drone survey",
      "with a licence typed in it is shown, under that licence, read at the poll and not at the fetch")
os.environ.pop("TERRAIN_DEM_LICENCE")
check(A.fetch(None) == ([], []), "clearing the licence stops the rows at the next poll")
A.result_file().write_text(json.dumps(kept))
check(A.result() == {}, "a Copernicus result is not this node's once TERRAIN_DEM_PATH names a file")
os.environ.pop("TERRAIN_DEM_PATH")
A.result_file().write_text(json.dumps(kept | {"lat": lat + 0.01}))
check(A.result() == {}, "a result kept around another point does not describe this one")

if fails:
    print("\n".join(f"  ✗ {f}" for f in fails))
    sys.exit(1)
print("  ✓ terrain: tiles, fill, accumulation, one rain source, the contract")
