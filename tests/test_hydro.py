"""The hydro pack's geometry and its contract, offline: no download, no pyshp, no database.

Run: PYTHONPATH=/tmp/stub:app python3 tests/test_hydro.py
"""
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone

os.environ.setdefault("NODE_LAT", "-8.8271")
os.environ.setdefault("NODE_LON", "115.15709")
os.environ.setdefault("NODE_NAME", "test-node")
os.environ["PACK_OUT"] = tempfile.mkdtemp()
os.environ.pop("HYDRO_RADIUS_KM", None)

spec = importlib.util.spec_from_file_location("hydropack", "packs/hydro/adapter.py")
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


# ---------------------------------------------------------------- regions
check(set(A.candidates(-8.83, 115.16)) == {"as", "au"}, f"node #1 is in the Asia and Australasia boxes: {A.candidates(-8.83, 115.16)}")
check(A.candidates(41.42, 2.10) == ["eu"], "Barcelona is in Europe's box only")
check(A.candidates(-60.5, 30.0) == [], "the Southern Ocean is in no box")
check(A.PFAF_REGION[5] == "au" and A.PFAF_REGION[2] == "eu", "Pfafstetter's first digit names the region")

# ---------------------------------------------------------------- point in polygon
sq = [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]
hole = [(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)]
check(A.inside(2, 2, [sq]), "a point inside a square")
check(not A.inside(5, 2, [sq]), "a point outside it")
check(not A.inside(2, 2, [sq, hole]), "a point in the hole is outside the shape")
check(A.inside(0.5, 2, [sq, hole]), "a point between the hole and the edge is inside")

# ---------------------------------------------------------------- distance to a river
# A river running north-south 0.01 degrees east of the point, at the equator: 0.01 x 111320 m.
d = A.to_line(0.0, 0.0, [(0.01, -0.05), (0.01, 0.05)])
check(abs(d - 1113.2) < 1, f"the perpendicular foot of a segment, not its ends: {d:.1f} m")
d = A.to_line(0.0, 0.0, [(0.01, 0.02), (0.01, 0.05)])
check(abs(d - A.metres(0, 0, 0.02, 0.01)) < 1, f"past a segment's end the end is nearest: {d:.1f} m")
d = A.to_line(60.0, 0.0, [(0.02, 59.9), (0.02, 60.1)])
check(abs(d - 0.02 * 111320 * 0.5) < 2, f"a degree of longitude at 60 N is half: {d:.1f} m")

# ---------------------------------------------------------------- the square and the rounding
w, s, e, n = A.square(-8.8271, 115.15709, 25)
check(abs((n - s) * 111320 - 50000) < 1, "the square is 50 km tall")
check(e - w > n - s, "and wider in degrees than tall, away from the equator")
check(A.rnd([(1.000001, 2.0), (1.000002, 2.0), (1.5, 2.25)]) == [[1.0, 2.0], [1.5, 2.25]], "five decimals, repeats dropped")

# ---------------------------------------------------------------- the contract
check(A.fetch(None) == ([], []), "nothing kept: no sensor, no rows")
river = {"hyriv_id": 1, "dist_m": 4980, "dis_av_cms": 0.125, "ord_stra": 1, "upland_skm": 6.2, "dist_dn_km": 0.0,
         "endorheic": 0}
big = {"hyriv_id": 2, "dist_m": 23180, "dis_av_cms": 10.592, "ord_stra": 3, "upland_skm": 304.0, "dist_dn_km": 5.2,
       "endorheic": 0}
t = datetime(2026, 11, 8, 6, 0, tzinfo=timezone.utc)
kept = {"lat": -8.8271, "lon": 115.15709, "radius_km": 25, "region": "au", "fetched_at": t.isoformat(),
        "nearest": river, "largest": big,
        "basin": {"level12": {"hybas_id": 5120011560, "pfaf_id": 512000000000, "sub_area": 319.0, "up_area": 319.0},
                  "level4": {"hybas_id": 5040000000, "pfaf_id": 5150, "sub_area": 140535.0, "up_area": 140535.0}},
        "rivers": {"type": "FeatureCollection", "features": [{}, {}]}, "basins": {"type": "FeatureCollection", "features": [{}]}}
A.cache().mkdir(parents=True, exist_ok=True)
A.result_file().write_text(json.dumps(kept))
sensors, rows = A.fetch(None)
got = {m: v for _, _, m, v in rows}
check(len(sensors) == 1 and sensors[0]["kind"] == "model" and sensors[0]["sensor_id"] == "hydro-point", "one model sensor")
check(got == {"river_m": 4980, "river_flow_m3s": 0.125, "river_order": 1, "river_upland_km2": 6, "river_to_sea_km": 0,
              "river_largest_m3s": 10.592, "basin_up_km2": 319}, f"the rows: {got}")
check(all(ts == t for ts, *_ in rows), "every row carries the fetch's own time, so a poll re-sends and the database keeps one")
check(sensors[0]["meta"]["basin4"]["pfaf_id"] == 5150, "the level-4 basin, the bioregion index.fab.city draws, travels in meta")
check("reaches the sea there" in A.sentence(river), A.sentence(river))
check("5 km from the sea" in A.sentence(big), A.sentence(big))
check("where it ends inland" in A.sentence({**big, "endorheic": 1}), "an endorheic river does not reach the sea")

# metrics in pack.yaml are the rows fetch() sends, no more, no fewer
import re
m = re.search(r"^metrics:\s*\[(.*?)\]", open("packs/hydro/pack.yaml").read(), re.M)
check(set(x.strip() for x in m.group(1).split(",")) == set(got), "pack.yaml metrics match the rows")

# moved: a result kept around another point is not this node's
os.environ["NODE_LAT"] = "-8.80"
check(A.result() == {} and A.fetch(None) == ([], []), "a node that moved 3 km shows nothing until it fetches again")
os.environ["NODE_LAT"] = "-8.8271"
os.environ["HYDRO_RADIUS_KM"] = "10"
check(A.result() == {}, "a different square is not the kept one")
os.environ.pop("HYDRO_RADIUS_KM")
check(A.result() != {}, "and back, it is")

if fails:
    print("\n".join(f"  ✗ {f}" for f in fails))
    raise SystemExit(1)
print("  ✓ hydro: regions, point in polygon, distance to a river, the contract, a moved node")
