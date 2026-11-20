"""GET /wall: the one route the Wall's map reads, without a token, at SHARE_LEVEL=open (app/wall.py).

The builders alone first (the three scales, whole km from the cell's centre, 24 hourly values, UTM corners back to
lon/lat), then the route with every query stubbed and every pack's file written to a temporary PACK_OUT. What is
held to is R25: nothing in the body places the house more finely than its res-8 cell.

    PACKS_DIR=packs PYTHONPATH=app python3 tests/test_wall.py
"""
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h3

HOME = "8895a4c843fffff"                      # node #1's res-8 cell (tests/test_cells.py)
LAT, LON = -8.8170, 115.1650                  # a point inside it, not its centre
OUT = Path(tempfile.mkdtemp())
os.environ.update(PACKS_DIR="packs", ADMIN_TOKEN="admin-tok", NODE_LAT=str(LAT), NODE_LON=str(LON), NODE_NAME="n1",
                  PACK_OUT=str(OUT), DATABASE_URL="postgresql://unused/never-connected")

import wall  # noqa: E402

# ---------------------------------------------------------------- scales
sc = wall.scales(HOME)
assert [s["k"] for s in sc] == ["base", "community", "city"] and [s["res"] for s in sc] == [8, 7, 6], sc
for s, km2 in zip(sc, (4.5, 31.4, 219.4)):
    assert len(s["cells"]) == 7, (s["k"], len(s["cells"]))
    assert abs(s["km2"] - km2) <= 0.1, (s["k"], s["km2"])
    assert sum(c["own"] for c in s["cells"]) == 1, s["k"]
    for c in s["cells"]:
        assert h3.get_resolution(c["id"]) == s["res"]
        assert len(c["ring"]) >= 7 and c["ring"][0] == c["ring"][-1], "every ring is closed"
        assert all(len(p) == 2 and -180 <= p[0] <= 180 and -90 <= p[1] <= 90 for p in c["ring"]), "[lon, lat]"
assert next(c for c in sc[0]["cells"] if c["own"])["id"] == HOME
assert next(c for c in sc[1]["cells"] if c["own"])["id"] == h3.cell_to_parent(HOME, 7)
print("  scales: seven cells at res 8, 7 and 6, closed rings, one own, 4.5 / 31.4 / 219.4 km2")

# ---------------------------------------------------------------- km_from
clat, clon = h3.cell_to_latlng(HOME)
k = wall.km_from((clon, clat), clon + 0.1, clat)
assert isinstance(k, int) and k == 11, k
assert isinstance(wall.km_from((clon, clat), clon, clat), int)
print("  km_from: whole km, an int")

# ---------------------------------------------------------------- hourly
now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
B = [now - timedelta(hours=h) for h in range(23, -1, -1)]
rows = [{"bucket": B[0], "sensor_id": "s1", "metric": "pm25", "mean": 12.345},
        {"bucket": B[5], "sensor_id": "s1", "metric": "pm25", "mean": 30.0},
        {"bucket": B[5], "sensor_id": "s2", "metric": "pm25", "mean": 99.0},
        {"bucket": B[6], "sensor_id": "s1", "metric": "pm10", "mean": 50.0}]
v = wall.hourly(rows, B, "s1", "pm25")
assert len(v) == 24 and v[0] == 12.35 and v[5] == 30.0 and v[6] is None and v.count(None) == 22, v
assert wall.hourly([], B, "s1", "pm25") == [None] * 24
print("  hourly: 24 values, None where a bucket has no row")

# ---------------------------------------------------------------- the clock is /issues' clock
from issues import engine  # noqa: E402
future = now + timedelta(hours=1)
assert engine.day_buckets(B + [future, B[3]], now) == B, "the last 24 hours that happened, once each"
print("  buckets: engine.day_buckets, the one /issues draws")

# ---------------------------------------------------------------- UTM 50S back to lon/lat
import packs  # noqa: E402
SH = packs.module("surface-heat", on_only=False)
fwd = SH.projection(32750)
x, y = fwd(-8.8, 117.0)
assert abs(x - 500000) < 1e-6, "the central meridian is x = 500 000"
for la, lo in ((-8.816, 115.163), (-8.86, 115.11), (-8.77, 115.21)):       # the cell's centre, and corners ~7 km off
    lon_, lat_ = wall.lonlat(*fwd(la, lo), 32750, (clat, clon))
    err = h3.great_circle_distance((la, lo), (lat_, lon_), unit="m")
    assert err < 0.05, (la, lo, lat_, lon_, err)
print("  lonlat: UTM 50S back to lon/lat, under 5 cm at 7 km")

# ---------------------------------------------------------------- grid: the 30 km cut and the substation's cell
C = (clon, clat)
E = lambda km: clon + km / (111.32 * 0.98818)  # noqa: E731 — a point `km` east of the centre
g = wall.grid({"cell": HOME, "sources": [{"kind": "plant", "name": "far", "mw": 5, "lat": clat, "lon": E(30.4)},
                                         {"kind": "plant", "name": "in", "mw": 5, "lat": clat, "lon": E(29.6)},
                                         {"kind": "substation", "lat": clat, "lon": E(2.2)}]}, C)
assert [(p["name"], p["km"]) for p in g["plants"]] == [("in", 30)], ("30.4 km is not within 30", g["plants"])
assert g["substation_km"] == 2
g = wall.grid({"cell": h3.cell_to_parent(HOME, 7), "sources": [{"kind": "substation", "lat": clat, "lon": E(2.2)}]}, C)
assert g["substation_km"] is None, "a result picked for another cell names no substation"
print("  grid: plants cut at 30 km before the km is made whole; no substation from another cell's result")

# ---------------------------------------------------------------- water: coverage from every point of the cell
HY = packs.module("hydro", on_only=False)
_city = [p for cc in wall.scales(HOME)[-1]["cells"] for p in cc["ring"]]
FRAME = (min(p[0] for p in _city), min(p[1] for p in _city), max(p[0] for p in _city), max(p[1] for p in _city))
reach = {"type": "Feature", "properties": {"dis_av_cms": 1.0},
         "geometry": {"type": "LineString", "coordinates": [[FRAME[0] - 0.01, clat], [FRAME[2] + 0.01, clat]]}}
fetches = [(clat + 0.95 * (v[0] - clat), clon + 0.95 * (v[1] - clon)) for v in h3.cell_to_boundary(HOME)]
assert all(h3.latlng_to_cell(la, lo, 8) == HOME for la, lo in fetches)
# 11.2 km holds the frame from some of these points and not from others: the pack's own square says which side
lit = [all(a <= b for a, b in zip(HY.square(la, lo, 11.2)[:2], FRAME[:2])) and
       all(a >= b for a, b in zip(HY.square(la, lo, 11.2)[2:], FRAME[2:])) for la, lo in fetches]
assert any(lit) and not all(lit), lit
for km, want in ((11.2, False), (12.0, True)):
    got = [wall.water({"lat": la, "lon": lo, "radius_km": km, "rivers": {"features": [reach]}}, FRAME, C, HY.inside,
                      HY.square)[0] is not None for la, lo in fetches]
    assert got == [want] * len(got), (km, got)
got = wall.water({"lat": clat - 0.02, "lon": clon, "radius_km": 30, "rivers": {"features": [reach]}}, FRAME, C,
                 HY.inside, HY.square)
assert got == (None, None, None), "a fetch from another cell: no water"
# a straight reach across the frame with both ends outside it is a reach in the frame
rv, _, rr = wall.water({"lat": clat, "lon": clon, "radius_km": 30, "rivers": {"features": [reach]}}, FRAME, C,
                       HY.inside, HY.square)
assert len(rv["features"]) == 1 and rr["nearest_km"] == 0, (rv, rr)
outside = {**reach, "geometry": {"type": "LineString", "coordinates": [[FRAME[0] - 0.02, clat], [FRAME[0] - 0.01, clat]]}}
assert wall.water({"lat": clat, "lon": clon, "radius_km": 30, "rivers": {"features": [outside]}}, FRAME, C, HY.inside,
                  HY.square)[0]["features"] == []
# no river at all and only rivers past the frame answer alike: which one a fetch got says how far its square reached
none = wall.water({"lat": clat, "lon": clon, "radius_km": 30, "rivers": {"features": []}}, FRAME, C, HY.inside,
                  HY.square)
past = wall.water({"lat": clat, "lon": clon, "radius_km": 30, "rivers": {"features": [outside]}}, FRAME, C, HY.inside,
                  HY.square)
assert none == past and none[0] == {"type": "FeatureCollection", "features": []} and none[2] is None, (none, past)
print("  water: the same block from every fetch centre in the cell; a reach crossing the frame is kept")

# ---------------------------------------------------------------- the route
try:
    from fastapi.testclient import TestClient
except ImportError:
    print("wall: route checks skipped (pip install -r app/requirements.txt)")
    raise SystemExit(0)

import settings  # noqa: E402
ROWS = {"PACKS_ENABLED": "", "SHARE_LEVEL": "open", "PLACE_RADIUS_M": "5000"}   # a Set up row the pack never fetched
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}

NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
BUCKETS = [NOW - timedelta(hours=h) for h in range(25, -1, -1)] + [NOW + timedelta(hours=3)]   # 26 past + 1 forecast
DAY = BUCKETS[2:-1]
HOURLY = ([{"bucket": DAY[i], "sensor_id": "bad-1", "metric": "pm25", "mean": 10.0 + i} for i in range(0, 24, 2)]
          + [{"bucket": b, "sensor_id": "om-point", "metric": "wind_speed", "mean": 14.26} for b in DAY]
          + [{"bucket": b, "sensor_id": "om-point", "metric": "wind_direction", "mean": 120.0} for b in DAY]
          + [{"bucket": DAY[-1], "sensor_id": "marine-point", "metric": "swell_height_m", "mean": 1.234}])
ANSWERS = {
    "DISTINCT bucket": [{"bucket": b} for b in BUCKETS],
    "kind = 'sensor' AND NOT local": [{"sensor_id": "bad-1", "source": "baliairdispatch", "lat": -8.81234567, "lon": 115.1234567},
                                      # 14.9 km south of the house: inside BAD's 15 km, beyond 15 km less the cell
                                      {"sensor_id": "bad-far", "source": "baliairdispatch", "lat": LAT - 14.9 / 111.32, "lon": LON},
                                      # 160 m north of the house: BAD keeps it, but inside the cell + 150 m of the centre
                                      {"sensor_id": "bad-near", "source": "baliairdispatch", "lat": LAT + 0.16 / 111.32, "lon": LON},
                                      # a Meshtastic radio, and the household's own kit away from home (stamp_local
                                      # sets it local=FALSE): not stations, though both pass NOT local AND NOT indoor
                                      {"sensor_id": "msh-64e0bfd1", "source": "meshtastic", "lat": -8.79, "lon": 115.15},
                                      {"sensor_id": "sc-19898", "source": "smartcitizen", "lat": -8.77, "lon": 115.19},
                                      {"sensor_id": "bad-2", "source": "baliairdispatch", "lat": -8.70001, "lon": 115.20001},
                                      {"sensor_id": "bad-3", "source": "baliairdispatch", "lat": None, "lon": None}],
    "readings_1h h": HOURLY,
    "kind = 'facility'": [{"name": "Fab Lab Bali", "lat": -8.6812345, "lon": 115.2312345},
                          {"name": "Far Lab", "lat": -6.2, "lon": 106.8}],
    "place_features": [{"n": 214}],
    "place_runs": [{"radius_m": 1000, "lat": LAT, "lon": LON}],
}
SEEN = []


class Cur:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, *a):
        SEEN.append((sql, a))
        self.rows = next((v for k, v in ANSWERS.items() if k in sql), [])
    def fetchall(self): return [dict(r) for r in self.rows]


class Con:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return Cur()


# ---- the packs' files
iso = lambda d: d.isoformat()  # noqa: E731
(OUT / "wall").mkdir(parents=True)
(OUT / "wall" / "island.json").write_text(json.dumps({"at": iso(NOW), "items": [
    {"lat": -8.5, "lon": 115.2, "pm25": 31.0, "at": iso(NOW - timedelta(minutes=40)), "network": "Government (KLHK)",
     "official": True, "place": "Kabupaten Badung Sempidi"},
    {"lat": round(LAT + 0.16 / 111.32, 3), "lon": round(LON, 3), "pm25": 9.0, "at": iso(NOW), "network": "PurpleAir",
     "official": False, "place": None},
    {"lat": -8.6, "lon": 115.3, "pm25": 8.0, "at": iso(NOW - timedelta(hours=5)), "network": "AirGradient",
     "official": False, "place": None}]}))
(OUT / "energy").mkdir()
(OUT / "energy" / "result.json").write_text(json.dumps({
    "cell": HOME, "share": {"low": 0.8412, "high": 0.9}, "today": {"sun_kwh_m2": 6.38, "roof_kwh": 9.57, "panel_kw": 2.0, "use_kwh": 14.2,
                                                     "measured": False}, "sources": [
        {"kind": "substation", "name": "GI Nusa Dua", "lat": -8.79, "lon": 115.2, "km": 4.123456},
        {"kind": "plant", "name": "PLTDG Pesanggaran", "fuel": "gas", "mw": 200, "lat": -8.7123456, "lon": 115.2123456, "km": 12.3456},
        {"kind": "plant", "name": "Tiny", "fuel": "solar", "mw": 0.5, "lat": -8.80, "lon": 115.17, "km": 1.0},
        {"kind": "plant", "name": "PLTD Genset", "fuel": "diesel", "mw": 1.2, "lat": -8.78, "lon": 115.19, "km": 4.2},
        {"kind": "plant", "name": "Celukan Bawang", "fuel": "coal", "mw": 380, "lat": -8.18, "lon": 114.83, "km": 79.0}]}))
hyd = OUT / "hydro" / "n1"
hyd.mkdir(parents=True)
inside_ring = [[115.10, -8.90], [115.25, -8.90], [115.25, -8.70], [115.10, -8.70], [115.10, -8.90]]
other_ring = [[115.30, -8.60], [115.40, -8.60], [115.40, -8.50], [115.30, -8.60]]
hyd_doc = {"lat": LAT, "lon": LON, "radius_km": 25,
           "nearest": {"dist_m": 3712, "dis_av_cms": 0.13}, "largest": {"dist_m": 9100, "dis_av_cms": 4.2},
           "basin": {"level12": {"hybas_id": 1}},
           "rivers": {"type": "FeatureCollection", "features": [
               {"type": "Feature", "properties": {"dist_m": 3712, "dis_av_cms": 0.13, "ord_stra": 1},
                "geometry": {"type": "LineString", "coordinates": [[clon + 0.04, clat], [clon + 0.05, clat + 0.01]]}},
               {"type": "Feature", "properties": {"dist_m": 9100, "dis_av_cms": 4.2, "ord_stra": 3},
                "geometry": {"type": "LineString", "coordinates": [[clon - 0.07, clat], [clon - 0.08, clat - 0.01]]}},
               {"type": "Feature", "properties": {"dist_m": 24000, "dis_av_cms": 40.0, "ord_stra": 5},
                "geometry": {"type": "LineString", "coordinates": [[clon + 0.22, clat + 0.22], [clon + 0.23, clat + 0.23]]}}]},
           "basins": {"type": "FeatureCollection", "features": [
               {"type": "Feature", "properties": {"here": True, "sub_area": 319.2, "up_area": 319.2, "hybas_id": 1},
                "geometry": {"type": "Polygon", "coordinates": [inside_ring]}},
               {"type": "Feature", "properties": {"sub_area": 50.0, "up_area": 50.0, "hybas_id": 2},
                "geometry": {"type": "Polygon", "coordinates": [other_ring]}}]}}
(hyd / "hydro.json").write_text(json.dumps(hyd_doc))
ea = OUT / "earth" / "n1"
ea.mkdir(parents=True)
# the square the earth pack read, centred on the point to 10 m: its corners would give the house away
sx, sy = fwd(LAT, LON)
square = {"west": sx - 5000, "east": sx + 5000, "south": sy - 5000, "north": sy + 5000}
wx, wy = fwd(clat, clon)
safe = {"west": wx - 3200, "east": wx + 3100, "south": wy - 2900, "north": wy + 3300}
stats = {"year_a": 2024, "year_b": 2025, "crs": "EPSG:32750", "bounds": square, "hectares_over_threshold": 129.4,
         "lat": LAT, "lon": LON, "png": "change_2024_2025.png", "node_rc": [500, 500]}
(ea / "change_2024_2025.json").write_text(json.dumps({**stats, "wall": {"bounds": safe, "ha": 61.2, "cell": HOME}}))
(ea / "change_2023_2024.json").write_text(json.dumps({**stats, "year_a": 2023, "year_b": 2024}))
(ea / "change_2024_2025_wall.png").write_bytes(b"\x89PNG\r\n\x1a\n")

import db  # noqa: E402
import main  # noqa: E402
assert db._pool is None, "importing main opened the database"
import wall as wall_mod  # noqa: E402
wall_mod.db = lambda: Con()
main.db = lambda: Con()
db.db = lambda: Con()
c = TestClient(main.app)

# ---- who may read it
ROWS["SHARE_LEVEL"] = "off"
r = c.get("/wall", headers={"host": "x"})
# the test client's peer is "testclient", not this machine, so no token is a stranger on the WiFi
assert r.status_code in (401, 403), (r.status_code, r.text)
ROWS["SHARE_LEVEL"] = "open"
r = c.get("/wall")
assert r.status_code == 200, r.text
W = r.json()
print("  /wall: 403 without a token at SHARE_LEVEL=off, 200 at open")

# ---- shape
assert set(W) == {"home", "centre", "scales", "hours", "stations", "island", "roofs", "lab", "rivers", "basin", "river",
                  "grid", "change"}, sorted(W)
assert W["home"] == HOME and W["centre"] == [round(clon, 5), round(clat, 5)], (W["home"], W["centre"])
assert W["scales"] == json.loads(json.dumps(wall.scales(HOME)))
H = W["hours"]
assert set(H) == {"buckets", "wind_kmh", "wind_from", "wave_from", "swell_m", "swell_s"}, sorted(H)
assert all(len(v) == 24 for v in H.values()), {k: len(v) for k, v in H.items()}
assert H["buckets"] == [iso(b) for b in DAY], "the last 24 hours that happened, never the forecast's"
assert H["wind_kmh"] == [14.26] * 24 and H["wind_from"] == [120.0] * 24
assert H["swell_m"] == [None] * 23 + [1.23] and H["wave_from"] == [None] * 24
assert [s["lat"] for s in W["stations"]] == [-8.812, -8.7] and W["stations"][0]["lon"] == 115.123, W["stations"]
assert h3.great_circle_distance((LAT, LON), (LAT - 14.9 / 111.32, LON), unit="km") < 15, "the far one is inside BAD's ring"
assert h3.great_circle_distance((LAT, LON), (LAT + 0.16 / 111.32, LON), unit="m") > 150, "and BAD keeps the near one"
ids = next(a[0][0] for q, a in reversed(SEEN) if "readings_1h h" in q)
assert "bad-far" not in ids and "bad-near" not in ids and "bad-1" in ids, "dropped before their hours are read"
assert "msh-64e0bfd1" not in ids and "sc-19898" not in ids, "only the station packs' sources are stations"
assert (-8.79, 115.15) not in [(s["lat"], s["lon"]) for s in W["stations"]] and len(W["stations"]) == 2
assert W["stations"][0]["pm25"][0] == 10.0 and W["stations"][0]["pm25"][1] is None and len(W["stations"][0]["pm25"]) == 24
assert W["stations"][1]["pm25"] == [None] * 24, "a station with no hour still stands; it is drawn grey"
assert not any("sensor_id" in s for s in W["stations"]), "a station's id is its network's, and says nothing on a wall"
assert W["island"]["at"] == iso(NOW) and len(W["island"]["items"]) == 1, "the stale one, and the one 160 m off"
assert W["island"]["items"][0]["place"] == "Kabupaten Badung Sempidi" and W["island"]["items"][0]["official"] is True
assert W["roofs"] == {"osm_in_cells": 214, "mapped_radius_m": int(1000 - wall.circum_m(HOME)) // 100 * 100}, W["roofs"]
assert W["roofs"]["mapped_radius_m"] == 400, "the run's 1000 m less the cell, never the 5000 m Set up row, whole 100 m"
roof_r = next(a[0][2] for q, a in reversed(SEEN) if "place_features" in q)
assert roof_r == 400, ("the roofs are counted over the radius the Wall says", roof_r)
assert W["lab"] == {"name": "Fab Lab Bali", "lat": -8.681, "lon": 115.231,
                    "km": wall.km_from((clon, clat), 115.2312345, -8.6812345)}, W["lab"]
assert W["grid"]["fossil_low_pct"] == 84, W["grid"]
assert W["grid"]["substation_km"] == wall.km_from((clon, clat), 115.2, -8.79), W["grid"]
assert [p["name"] for p in W["grid"]["plants"]] == ["PLTD Genset", "PLTDG Pesanggaran"], "1 MW and up, within 30 km of the cell"
assert [p["large"] for p in W["grid"]["plants"]] == [False, True], "the energy pack's own large cut, 100 MW"
assert W["grid"]["plants"][1]["km"] == wall.km_from((clon, clat), 115.2123456, -8.7123456) != 12
assert W["grid"]["sun"] == {"kwh_m2": 6.38, "roof_kwh": 9.57, "panel_kw": 2.0}, "sun today: three figures, never use_kwh"
assert [f["properties"]["m3s"] for f in W["rivers"]["features"]] == [0.13, 4.2], "only the reaches in the city frame"
assert W["basin"]["properties"] == {"sub_area": 319.2, "up_area": 319.2} and W["basin"]["geometry"]["type"] == "Polygon"
assert W["river"] == {"nearest_km": 4, "nearest_m3s": 0.13, "largest_km": 8, "largest_m3s": 4.2}, W["river"]
assert W["change"]["a"] == 2024 and W["change"]["b"] == 2025 and W["change"]["ha"] == 61.2, W["change"]
assert W["change"]["png"] == "/earth/wall.png?pair=2024_2025" and len(W["change"]["corners"]) == 4
tl = W["change"]["corners"][0]
assert abs(tl[0] - wall.lonlat(safe["west"], safe["north"], 32750, (clat, clon))[0]) < 1e-6, "placed by the wall's crop"
print("  /wall: every block, from the packs' own files and the hourly table")

# ---- R25: nothing finer than the res-8 cell
assert "lat" not in W and "lon" not in W
txt = r.text
for leak in ("dist_m", "here", "hybas_id", "node_rc", "radius_km", "bad-1", "3.712", "12.3456"):
    assert leak not in txt, leak
for k in ("west", "east", "south", "north"):
    assert str(round(square[k])) not in txt, "the earth square's own corners are centred on the house"


def walk(x, path=()):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from walk(v, path + (k,))
    elif isinstance(x, list):
        for v in x:
            yield from walk(v, path + ("[]",))
    else:
        yield path, x


for path, v in walk(W):
    key = path[-1] if path[-1] != "[]" else next((p for p in reversed(path) if p != "[]"), "")
    if key == "km" or key.endswith("_km"):
        assert v is None or type(v) is int, (path, v)
    if key in ("lat", "lon") and not {"ring", "corners", "geometry"} & set(path):
        assert v is None or round(v, 3) == v, (path, v)
        assert v not in (round(LAT, 3), round(LON, 3), round(LAT, 4), round(LON, 4)), ("the house's own point", path)
    if key == "name":
        assert path[:1] == ("lab",) or path[:2] == ("grid", "plants"), path
print("  R25: no top-level point, whole km, 3 dp at most, names only for the lab and the plants")

# ---- the earth square's own corners are never used
(ea / "change_2024_2025.json").write_text(json.dumps(stats))
assert c.get("/wall").json()["change"] is None, "no crop in the stats, no change: never the square centred on the house"
(ea / "change_2024_2025.json").write_text(json.dumps({**stats, "wall": {"bounds": safe, "ha": 61.2, "cell": "88"}}))
assert c.get("/wall").json()["change"] is None, "a crop cut round another cell waits for the next earth change"
(ea / "change_2024_2025.json").write_text(json.dumps({**stats, "wall": {"bounds": safe, "ha": 61.2, "cell": HOME}}))
(ea / "change_2024_2025_wall.png").unlink()
assert c.get("/wall").json()["change"] is None, "the Wall's image not drawn yet"
print("  change: null until the Wall's own image and crop exist")

# ---- the place pack's last run says what it fetched: no run, no roofs
ANSWERS["place_runs"] = []
assert c.get("/wall").json()["roofs"] is None, "no run row: nothing says how far the roofs reach"
ANSWERS["place_runs"] = [{"radius_m": 2000, "lat": LAT - 0.02, "lon": LON}]          # fetched 2 km south
assert c.get("/wall").json()["roofs"] is None, "a fetch from outside the house's cell: no bound the cell alone gives"
# the same run, the house anywhere in its cell, the run's own point included: the same radius and count. A radius less
# the metres the house moved since the fetch would move with each step. The water too: the hydro pack's 1 % tolerance
# round its fetch point (250 m at 25 km) is not what /wall goes by, or the rivers would say the house is within it.


def round_the_cell():
    out = []
    for la, lo in [(LAT, LON)] + [(clat + 0.95 * (v[0] - clat), clon + 0.95 * (v[1] - clon))
                                  for v in h3.cell_to_boundary(HOME)]:
        assert h3.latlng_to_cell(la, lo, 8) == HOME
        os.environ.update(NODE_LAT=str(la), NODE_LON=str(lo))
        w_ = c.get("/wall").json()
        out.append((w_["roofs"], next(a[0] for q, a in reversed(SEEN) if "place_features" in q), w_["river"]))
    os.environ.update(NODE_LAT=str(LAT), NODE_LON=str(LON))
    assert all(x == out[0] for x in out), out
    return out[0]


ANSWERS["place_runs"] = [{"radius_m": 1000, "lat": None, "lon": None}]       # an old run that recorded no centre
got = round_the_cell()
assert got[0] is None and got[2] == W["river"] is not None, ("a run with no centre may be from another cell", got)
ANSWERS["place_runs"] = [{"radius_m": 2000, "lat": LAT, "lon": LON}]         # centred on one point of the cell
assert round_the_cell()[0]["mapped_radius_m"] == 1400
ANSWERS["place_runs"] = [{"radius_m": 1000, "lat": LAT, "lon": LON}]
print("  roofs: the radius the place pack fetched less the cell; none without a run or from another cell; the roofs"
      " and the water the same wherever the house is in its cell")

# ---- a station pack whose settings do not read: its stations are withheld, never held to the defaults
_real = packs.module


class _Unread:
    @staticmethod
    def cfg():
        raise ValueError("could not convert string to float: 'four hundred'")


said = []
_h = logging.Handler()
_h.emit = lambda rec: said.append(rec.getMessage())
wall_mod.log.addHandler(_h)
packs.module = lambda p, *a, **k: _Unread if p == "bali-air-dispatch" else _real(p, *a, **k)
try:
    W = c.get("/wall").json()
    pub = main._public_rows([{"source": "baliairdispatch", "kind": "sensor", "lat": -8.70001, "lon": 115.20001}])
finally:
    packs.module = _real
    wall_mod.log.removeHandler(_h)
assert W["stations"] == [] and W["island"] is None, (W["stations"], W["island"])
assert pub == [], "/sensors and /issues withhold them too"
assert len([m for m in said if "bali-air-dispatch" in m]) == 1, ("said once a process, not on every read", said)
assert main._public_rows([{"source": "baliairdispatch", "kind": "sensor", "lat": -8.70001, "lon": 115.20001}]), \
    "with its settings read, the same station is shown"
assert len(c.get("/wall").json()["stations"]) == 2
print("  ring: a station pack whose settings do not read has no public stations, and the log says so")

# ---- the nearest lab by its unrounded distance: 4.4 km listed before 4.1 km, both whole 4
_labs = ANSWERS["kind = 'facility'"]
ANSWERS["kind = 'facility'"] = [{"name": "Lab 4.4", "lat": clat, "lon": clon + 4.4 / (111.32 * 0.98818)},
                                {"name": "Lab 4.1", "lat": clat, "lon": clon - 4.1 / (111.32 * 0.98818)}]
lab = c.get("/wall").json()["lab"]
ANSWERS["kind = 'facility'"] = _labs
assert lab["name"] == "Lab 4.1" and lab["km"] == 4, lab
print("  lab: the nearest by its unrounded km, only the km published is whole")

# ---- a malformed pack file costs its own block, never a 500
(ea / "change_2024_2025_wall.png").write_bytes(b"\x89PNG\r\n\x1a\n")
bad_stats = {k: v for k, v in stats.items() if k != "crs"}
(ea / "change_2024_2025.json").write_text(json.dumps({**bad_stats, "wall": {"bounds": safe, "ha": 61.2}}))
(OUT / "wall" / "island.json").write_text(json.dumps(["not", "a", "doc"]))
(OUT / "energy" / "result.json").write_text(json.dumps({"share": {"low": 0.5}, "sources": []}))
assert c.get("/wall").json()["grid"]["sun"] is None, "no `today` in the pack's result, no sun"
(OUT / "energy" / "result.json").write_text(json.dumps({"share": "nope", "sources": [{"kind": "plant", "lat": "x", "lon": 1}]}))
r = c.get("/wall")
assert r.status_code == 200, r.text
assert r.json()["change"] is None and r.json()["island"] is None and r.json()["grid"] is None, r.json()["grid"]
_real = packs.module
packs.module = lambda p, *a, **k: None if p == "surface-heat" else _real(p, *a, **k)
(ea / "change_2024_2025.json").write_text(json.dumps({**stats, "wall": {"bounds": safe, "ha": 61.2}}))
r = c.get("/wall")
packs.module = _real
assert r.status_code == 200 and r.json()["change"] is None, r.text
print("  a malformed file or a missing helper: that block is null, the route still answers")

# ---- a hydro square smaller than the city frame: its edge is round the house, so no water at all
os.environ["HYDRO_RADIUS_KM"] = "5"
(hyd / "hydro.json").write_text(json.dumps({**hyd_doc, "radius_km": 5}))
W = c.get("/wall").json()
assert W["rivers"] is None and W["basin"] is None and W["river"] is None, W["river"]
del os.environ["HYDRO_RADIUS_KM"]
print("  water: none when the pack's square is smaller than the city frame")

# ---- a stale island, every pack off, no rows: still 200, every block null
(OUT / "wall" / "island.json").write_text(json.dumps({"at": iso(NOW - timedelta(hours=4)), "items": [
    {"lat": -8.5, "lon": 115.2, "pm25": 31.0, "at": iso(NOW), "network": "x", "official": False, "place": None}]}))
assert c.get("/wall").json()["island"] is None, "written over 3 h ago"
ROWS["PACKS_ENABLED"] = "air-quality"
for k in list(ANSWERS):
    ANSWERS[k] = []
r = c.get("/wall")
assert r.status_code == 200, r.text
W = r.json()
assert all(W[k] is None for k in ("island", "roofs", "lab", "rivers", "basin", "river", "grid", "change")), W
assert W["stations"] == [] and W["hours"]["buckets"] == [] and len(W["scales"]) == 3
print("  every pack off and no rows: 200, the scales, and every block null")

# ---- the share list: /wall itself, and nothing under it
assert "/wall" in main._SHARE_OPEN[0] and not any("/wall/x".startswith(p) for p in main._SHARE_OPEN[1])
assert c.get("/wall/x").status_code in (401, 403), "no prefix opens what is added under /wall later"
print("wall: one tokenless route, nothing finer than the house's cell")
