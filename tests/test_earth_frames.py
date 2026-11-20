"""The two satellite records are two records, and the route finds the frames a real node has.

node #1 is why this exists. `planetai run earth-engine timelapse` wrote
`out/bayu-2-2016-sentinel-3km.png` when the node was called bayu-2; NODE_NAME is bayu-ungasan now,
and a route that builds the filename from NODE finds nothing at all. The km in the name moves with
the pack's settings too. The year is the only part of that filename this node can be sure of.

Run: PYTHONPATH=app python3 tests/test_earth_frames.py   (needs the app's own deps, like import-check)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "app"))

tmp = tempfile.mkdtemp()
os.environ.update(PACK_OUT=tmp, DATABASE_URL="postgresql://x:x@127.0.0.1:1/x", NODE_NAME="bayu-ungasan",
                  NODE_CITY="bali", NODE_LAT="-8.8", NODE_LON="115.1", PACKS_DIR=str(ROOT / "packs"))
import importlib.util  # noqa: E402
import time  # noqa: E402
import settings  # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"PACKS_ENABLED": ""}}   # every pack on, no database
from fastapi import HTTPException  # noqa: E402


def _load(pack):  # the routes moved into their packs on 23 Oct 2026: packs/earth/routes.py, packs/earth-engine/routes.py
    spec = importlib.util.spec_from_file_location(f"t_{pack}_routes", ROOT / "packs" / pack / "routes.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


ER, EER = _load("earth"), _load("earth-engine")

fails = []
out = Path(tmp)
# exactly what node #1 has in out/, old node name and all
for n in ("bayu-2-2016-sentinel-3km.png", "bayu-2-2019-sentinel-3km.png",
          "bayu-2-2022-sentinel-3km.png", "bayu-2-2025-sentinel-3km.png",
          "bayu-2-2012-landsat-2km.png", "bayu-2-2025-landsat-2km.png",
          "bayu-2-timelapse-sentinel.html",          # not a frame
          "change_2024_2025.png", "notes-sentinel-x.png"):
    (out / n).write_bytes(b"\x89PNG")

got = EER.frames("sentinel")
if sorted(got) != [2016, 2019, 2022, 2025]:
    fails.append(f"sentinel frames found {sorted(got)}, expected [2016, 2019, 2022, 2025]")
if sorted(EER.frames("landsat")) != [2012, 2025]:
    fails.append(f"landsat frames found {sorted(EER.frames('landsat'))}, expected [2012, 2025]")
if any("timelapse" in p.name or p.name.startswith("change_") for p in got.values()):
    fails.append("the glob picked up something that is not a frame")

# the whole point: the filename carries the node's OLD name and must still be found
if not all("bayu-2-" in p.name for p in got.values()):
    fails.append("this test no longer exercises the renamed-node case")
if ER.pack.node() != "bayu-ungasan":
    fails.append("NODE is not the new name, so the case above is not being tested")

# The two records stay apart in /earth's body: `frames` is this node's own AlphaEarth layer,
# `imagery` is somebody else's photographs. A page that merged them would be calling a model output
# a photograph.
body = ER.earth()
if "imagery" not in body or sorted(body["imagery"]["sentinel"]) != [2016, 2019, 2022, 2025]:
    fails.append(f"/earth must publish which imagery years exist: {body.get('imagery')}")
if body["imagery"]["sentinel"] == body.get("frames"):
    fails.append("the two satellite records must not be the same list")
if not any("Copernicus" in c for c in body["imagery"]["credit"]):
    fails.append("the imagery must carry its credit line")

# the route refuses what it does not have, and says what it does
try:
    EER.earth_frame_png(year=1999, source="sentinel")
    fails.append("a year with no frame must 404")
except HTTPException as e:
    if "2016" not in str(e.detail):
        fails.append(f"the 404 must name the years this node has: {e.detail}")
try:
    EER.earth_frame_png(year=2016, source="sentinel")
except Exception as e:  # noqa: BLE001
    fails.append(f"2016 exists and must be served: {type(e).__name__}")

# with nothing rendered at all, the 404 says which command makes them
for f in out.glob("*sentinel*"):
    f.unlink()
try:
    EER.earth_frame_png(year=2016, source="sentinel")
    fails.append("with no frames at all, the route must 404")
except HTTPException as e:
    if "earth-engine timelapse" not in str(e.detail):
        fails.append(f"the empty 404 must name the command: {e.detail}")

# ---------------------------------------------------------------- and the AlphaEarth cache, same rename
# out/earth/<node>/ was keyed on NODE_NAME too, which cost node #1 a 930 MB re-download of its own square and
# left 555 MB nothing reads. The embeddings describe a place: a directory whose meta.json was written around
# this point, at this radius, is this node's square whatever it is called. the route reads the pack's own cache()
# since 23 Oct 2026, so the rule has one copy and it is checked here through the route's module.
earth = out / "earth"
(earth / "bayu-2").mkdir(parents=True)
(earth / "bayu-2" / "meta.json").write_text(json.dumps({"lat": -8.8, "lon": 115.1, "radius_m": 5000}))
if ER.pack.cache() != earth / "bayu-2":
    fails.append(f"/earth must read the square the node fetched under its old name, got {ER.pack.cache()}")
(earth / "bayu-2" / "change_2024_2025.json").write_text(json.dumps(
    {"year_a": 2024, "year_b": 2025, "mean": 0.041, "png": "change_2024_2025.png"}))
if [c["year_b"] for c in ER.pack.changes()] != [2025]:
    fails.append("the comparisons under the old name must reach /earth")

(earth / "bayu-ungasan").mkdir()
(earth / "bayu-ungasan" / "meta.json").write_text(json.dumps({"lat": -8.8, "lon": 115.1, "radius_m": 5000}))
if ER.pack.cache() != earth / "bayu-ungasan":
    fails.append("with both on disk — node #1 today — the node's own name must win, so nothing switches under it")

# a square read around somewhere else is never adopted, whatever it is called
for d in (earth / "bayu-2", earth / "bayu-ungasan"):
    for f in d.glob("*"):
        f.unlink()
    d.rmdir()
(earth / "santiago").mkdir()
(earth / "santiago" / "meta.json").write_text(json.dumps({"lat": -33.431, "lon": -70.6045, "radius_m": 5000}))
if ER.pack.cache() != earth / "bayu-ungasan":
    fails.append(f"another city's square must never answer for this node: {ER.pack.cache()}")

# /earth/wall.png: the image of the pair /wall picks (the newest year-over-year, else the newest), 204 without it
mine = earth / "bayu-ungasan"; mine.mkdir()
if ER.earth_wall_png().status_code != 204:
    fails.append("with no comparison, /earth/wall.png must be 204")
# a crop names the cell it was cut round, and only one cut round the house's cell now is served
HERE = ER.pack.wall_cell()
for a, b in ((2023, 2024), (2024, 2025), (2023, 2025)):
    (mine / f"change_{a}_{b}.json").write_text(json.dumps({"year_a": a, "year_b": b,
                                                           "wall": {"bounds": {}, "ha": 1.0, "cell": HERE}}))
(mine / "change_2023_2024_wall.png").write_bytes(b"\x89PNG old")
if ER.earth_wall_png().status_code != 204:
    fails.append("the newest year-over-year pair has no Wall image: 204, never an older pair's")
(mine / "change_2024_2025_wall.png").write_bytes(b"\x89PNG new")
r = ER.earth_wall_png()
if str(getattr(r, "path", None)) != str(mine / "change_2024_2025_wall.png") or r.media_type != "image/png":
    fails.append(f"/earth/wall.png must serve change_2024_2025_wall.png, got {getattr(r, 'path', r)}")
if (getattr(r, "headers", None) or {}).get("cache-control") != "no-cache":
    fails.append("/earth/wall.png must say no-cache: a screen asks again before it reuses last year's image")
# the PNG on disk is not enough: no crop, a crop with no cell (computed before crops named it), another cell
for wall_ in (None, {"bounds": {}, "ha": 1.0}, {"bounds": {}, "ha": 1.0, "cell": "8895a4c847fffff"}):
    (mine / "change_2024_2025.json").write_text(json.dumps({"year_a": 2024, "year_b": 2025, "wall": wall_}))
    for args in ({}, {"pair": "2024_2025"}):
        r = ER.earth_wall_png(**args)
        if r.status_code != 204 or r.headers.get("cache-control") != "no-cache":
            fails.append(f"/earth/wall.png with wall={wall_} {args}: 204 with no-cache, got {r.status_code}")
(mine / "change_2024_2025.json").write_text(json.dumps({"year_a": 2024, "year_b": 2025,
                                                       "wall": {"bounds": {}, "ha": 1.0, "cell": HERE}}))
# ?pair= is the pair /wall placed: that pair's image, or 204, never the latest in its corners
r = ER.earth_wall_png(pair="2023_2024")
if str(getattr(r, "path", None)) != str(mine / "change_2023_2024_wall.png"):
    fails.append(f"?pair=2023_2024 must serve that pair's image, never the latest, got {getattr(r, 'path', r)}")
for want in ("2023_2025", "2019_2020"):          # computed with no Wall image; never computed
    r = ER.earth_wall_png(pair=want)
    if r.status_code != 204 or r.headers.get("cache-control") != "no-cache":
        fails.append(f"?pair={want} has no Wall image: 204 with no-cache, got {r.status_code} {dict(r.headers)}")

# ---------------------------------------------------------------- nothing finer than the cell, to a stranger
# /earth handed a tokenless reader the node's point to five decimals (node #1's LAN, 18 Nov 2026), and the square
# itself placed the house as well: centred on it, ringed at it, and where a tile edge clips it, its size and every
# number over it say how far the house stands from that edge. Two houses in one res-8 cell, one of them clipped, read
# from one synthetic tile: a stranger must be handed the same answer for both, byte for byte, and the household its own.
import shutil  # noqa: E402
import types  # noqa: E402
import h3  # noqa: E402
import numpy as np  # noqa: E402

A = ER.pack
for d in list(earth.glob("*")):
    for f in d.glob("*"):
        f.unlink()
    d.rmdir()
TILE = np.random.default_rng(3).integers(-127, 128, size=(64, 400, 400), dtype=np.int8)
TILE2 = np.random.default_rng(4).integers(-127, 128, size=(64, 400, 400), dtype=np.int8)
CLAT, CLON = h3.cell_to_latlng(h3.latlng_to_cell(-8.8271, 115.15709, 8))
CR, CC, R = 200, 160, 1500                       # the cell's centre in the tile, and a 3 km square: 300 px a side


def house(k, j):
    """A house k pixels north and j east of the cell's centre, its square cut from the tile as fetch.py cuts it."""
    lat = CLAT + k * 10 / 111320.0
    lon = CLON + j * 10 / (111320.0 * np.cos(np.radians(lat)))
    assert h3.latlng_to_cell(lat, lon, 8) == h3.latlng_to_cell(CLAT, CLON, 8), "both houses must share the cell"
    os.environ.update(NODE_LAT=f"{lat:.7f}", NODE_LON=f"{lon:.7f}")
    lat, lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
    nr, nc = CR - k, CC + j
    r0, c0, r1, c1 = max(0, nr - R // 10), max(0, nc - R // 10), min(400, nr + R // 10), min(400, nc + R // 10)
    d = earth / "bayu-ungasan"
    shutil.rmtree(d, ignore_errors=True)                 # the public cuts too: each house cuts its own
    d.mkdir(parents=True)
    bounds = {"west": 500000 + c0 * 10, "east": 500000 + c1 * 10, "north": 9030000 - r0 * 10, "south": 9030000 - r1 * 10}
    win = {"bounds": bounds, "px": [c1 - c0, r1 - r0], "node_rc": [nr - r0, nc - c0], "clipped": (r0, c0) == (0, 0)}
    for y, t in ((2024, TILE), (2025, TILE2)):
        np.save(d / f"{y}.npy", t[:, r0:r1, c0:c1])
    view = {"mean": [0.0] * 64, "axis": [1.0] + [0.0] * 63, "breaks": list(np.linspace(-1, 1, 256))}
    (d / "meta.json").write_text(json.dumps({"lat": lat, "lon": lon, "radius_m": R, "view": view,
                                             "windows": {"2024": win, "2025": win}}))
    A.write_png(d / "year_2025.png", A.render_year(2025, view, tuple(win["node_rc"])))
    dist, masked = A.cosine_distance(np.load(d / "2024.npy"), np.load(d / "2025.npy"))
    ix = A.ramp_indices(dist, masked)
    A.draw_marks(ix, tuple(win["node_rc"]))
    A.write_png(d / "change_2024_2025.png", ix)
    (d / "change_2024_2025.json").write_text(json.dumps({
        "node": "bayu-ungasan", "year_a": 2024, "year_b": 2025, **A.change_stats(dist, masked, 0.15),
        "metres_per_pixel": 10, "bounds": bounds, "lat": lat, "lon": lon, "radius_m": R, "clipped": win["clipped"],
        "node_rc": win["node_rc"], "png": "change_2024_2025.png"}))
    return lat, lon


def reader(token=""):
    """A request from elsewhere on the LAN, as the route's own arguments."""
    return {"request": types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="192.168.68.50")),
            "authorization": token}


def png_ix(b):
    """Our own PNGs, back to palette indices: one IDAT, filter none on every row."""
    w, h = int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    i = b.index(b"IDAT")
    raw = zlib.decompress(b[i + 4:i + 4 + int.from_bytes(b[i - 4:i], "big")])
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w + 1)[:, 1:]


import zlib  # noqa: E402
os.environ["ACT_TOKEN"] = "act-tok"
seen = []
for k, j in ((25, 20), (-12, -30)):              # the second one's square is clipped by the tile's west edge
    lat, lon = house(k, j)
    body = ER.earth(public=True)
    flat = json.dumps(body)
    nums = [float(x) for x in __import__("re").findall(r"-?\d+\.\d+", flat)]
    if any(abs(x - lat) < 0.01 and x != body["lat"] for x in nums) or any(abs(x - lon) < 0.01 and x != body["lon"] for x in nums):
        fails.append(f"a stranger's /earth carries a degree finer than the cell's centre: {flat[:300]}")
    if body.get("position") != "cell" or "node_rc" in flat or '"lat": %s' % lat in flat:
        fails.append(f"a stranger's /earth must give the cell, never the point or the node's pixel: {body.get('position')}")
    ch = body["changes"][0]
    yr = ER.earth_year_png(**reader(), year=2025)
    cp = ER.earth_change_png(**reader(), pair="2024_2025")
    if any((png_ix(x.body) == A.NODE_IX).any() for x in (yr, cp)):
        fails.append("a picture served to a stranger still rings the node's point")
    kept = sorted(f.name for f in A.public_dir().glob("*"))
    if kept != ["change_2024_2025.json", "change_2024_2025.png", "year_2025.png"] or ER.earth_year_png(**reader(), year=2025).body != yr.body:
        fails.append(f"the cuts are kept on disk for the next reader, under the cell: {kept}")
    seen.append((json.dumps({k_: ch[k_] for k_ in ch if k_ != "computed_at"}, sort_keys=True), body["lat"], body["lon"],
                 yr.body, cp.body))
    # the household, and this machine, keep the square as it was read
    mine = ER.earth(public=False)
    if (mine["lat"], mine["lon"]) != (lat, lon) or mine["changes"][0].get("node_rc") is None:
        fails.append("the household's own /earth must keep the exact point and the node's pixel")
    full = ER.earth_year_png(**reader("Bearer act-tok"), year=2025)
    if not isinstance(full, ER.FileResponse):
        fails.append("the household's token must get the frame as drawn, ring and all")
if seen[0] != seen[1]:
    diff = [n for n, (x, y) in enumerate(zip(*seen)) if x != y]
    fails.append(f"two houses in one cell were told apart by a stranger's /earth (fields {diff}: numbers, lat, lon, "
                 f"frame, change map)")
ch = json.loads(seen[0][0])
if ch["px"] != [100, 100] or ch["radius_m"] != R - A.PUBLIC_MARGIN_M:
    fails.append(f"the public square is the cached one less PUBLIC_MARGIN_M a side: {ch['px']}, {ch['radius_m']}")
os.environ.update(NODE_LAT="-8.8", NODE_LON="115.1")

print("\n".join(f"  x {f}" for f in fails) or
      "  earth frames: the glob finds a renamed node's frames and its cache, keeps the two records "
      "apart, both 404s say what to do, and a stranger gets the cell, never the house")
sys.exit(1 if fails else 0)
