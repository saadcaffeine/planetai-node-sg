"""packs/surface-heat, offline: the projection, the COG reader, the cloud mask, the cell against the ring, and the
day with no new clear scene. No network, no database.

The fixtures are two real 64x64 crops (ST_B10 and QA_PIXEL, 1.92 km a side) around this suite's test point in
Kuta Selatan, read from Planetary Computer on 15 Oct 2026: LC08 27 Sep 2026, clear over the cell, and LC09 28 Sep
2026, cloud over the cell. Landsat Collection 2 is USGS public domain; each file says so and names its scene.

h3 is imported without a guard, like numpy in test_earth: the pack's whole claim is which pixels belong to the
node's cell, and a suite that prints "skipped" without h3 would let that ship unchecked. CI installs
app/requirements.txt, which has it.
Run: PYTHONPATH=/tmp/stub:app python3 tests/test_surface_heat.py
"""
import importlib.util
import json
import math
import os
import struct
import sys
import tempfile
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

import h3

LAT, LON = -8.8271, 115.15709                    # the earth suite's test point; not the house
os.environ.setdefault("NODE_LAT", str(LAT))
os.environ.setdefault("NODE_LON", str(LON))

spec = importlib.util.spec_from_file_location("surfaceheat", "packs/surface-heat/adapter.py")
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
DATA = Path("tests/data/surface-heat")
CLEAR = json.loads((DATA / "LC08_L2SP_117066_20260927_02_T1.json").read_text())
CLOUDY = json.loads((DATA / "LC09_L2SP_116066_20260928_02_T1.json").read_text())
fwd = A.projection(CLEAR["epsg"])

# ---------------------------------------------------------------- the projection
# Two corners of the 27 Sep scene as USGS's own MTL file pairs them (CORNER_*_PRODUCT). The latitudes are given to
# five decimals, about a metre, so two metres is the tolerance and not a fudge.
for la, lo, x, y in ((-7.62695, 113.30973, 92700.0, -844800.0), (-9.73094, 115.36005, 320100.0, -1076100.0)):
    ex, ey = A.utm(la, lo, 50, False)
    assert abs(ex - x) < 2 and abs(ey - y) < 2, f"UTM 50 at {la},{lo}: {ex:.1f},{ey:.1f} against USGS {x},{y}"
assert CLEAR["epsg"] == 32650, "Landsat files Bali under 50 NORTH, negative northings"
assert A.utm(LAT, LON, 50, True)[1] - A.utm(LAT, LON, 50, False)[1] == 10000000.0
try:
    A.projection(4326)
    raise AssertionError("a CRS the reader does not know must be refused, not guessed")
except ValueError:
    pass
# the linear inverse is good to well under a metre at the ring's far edge, at the equator and at 41° N
for la, lo, ep in ((LAT, LON, 32650), (41.3874, 2.1686, 32631)):
    f = A.projection(ep)
    inv = A.local_inverse(f, la, lo)
    x0, y0 = f(la, lo)
    for dx, dy in ((3600, 0), (0, -3600), (-2500, 2500)):
        x, y = f(*inv(x0 + dx, y0 + dy))
        assert math.hypot(x - x0 - dx, y - y0 - dy) < 1.0, f"inverse off by {math.hypot(x - x0 - dx, y - y0 - dy):.2f} m"
# MODIS's sinusoidal grid: the test point falls in tile h29v09, as the STAC search said
sx, sy = A.sinusoidal(LAT, LON)
assert int(sx // 1111950.5197 + 18) == 29 and int(-sy // 1111950.5197 + 9) == 9
print("projection: UTM within 2 m of USGS's corners, the inverse within a metre, MODIS in h29v09")

# ---------------------------------------------------------------- the COG reader, on a TIFF made here


def tiff(values, w, h, tile, x0, y0, px, epsg, predictor=1):
    """A little-endian tiled uint16 GeoTIFF, deflate, the shape Planetary Computer serves."""
    across, down = -(-w // tile), -(-h // tile)
    blobs = []
    for tr in range(down):
        for tc in range(across):
            t = [0] * (tile * tile)
            for r in range(tile):
                for c in range(tile):
                    R, C = tr * tile + r, tc * tile + c
                    if R < h and C < w:
                        t[r * tile + c] = values[R * w + C]
            blobs.append(zlib.compress(struct.pack(f"<{tile * tile}H", *t)))
    geokeys = [1, 1, 0, 2, 1025, 0, 1, 1, 3072, 0, 1, epsg]
    entries = [(256, 3, [w]), (257, 3, [h]), (258, 3, [16]), (259, 3, [8]), (262, 3, [1]), (277, 3, [1]),
               (317, 3, [predictor]), (322, 3, [tile]), (323, 3, [tile]), (324, 4, None), (325, 4, [len(b) for b in blobs]),
               (33550, 12, [px, px, 0.0]), (33922, 12, [0.0, 0.0, 0.0, x0, y0, 0.0]), (34735, 3, geokeys)]
    fmt = {3: "H", 4: "I", 12: "d"}
    ifd_at = 8
    extra_at = ifd_at + 2 + 12 * len(entries) + 4
    extras, slots = b"", {}
    for tag, typ, vals in entries:
        n = len(blobs) if tag == 324 else len(vals)
        if struct.calcsize(fmt[typ]) * n > 4:
            slots[tag] = extra_at + len(extras)
            extras += b"\0" * (struct.calcsize(fmt[typ]) * n)
    data_at = extra_at + len(extras)
    offsets, at = [], data_at
    for b in blobs:
        offsets.append(at); at += len(b)
    ifd, ex = struct.pack("<H", len(entries)), bytearray(extras)
    for tag, typ, vals in entries:
        vals = offsets if tag == 324 else vals
        packed = struct.pack("<" + fmt[typ] * len(vals), *vals)
        if tag in slots:
            ex[slots[tag] - extra_at: slots[tag] - extra_at + len(packed)] = packed
            ifd += struct.pack("<HHII", tag, typ, len(vals), slots[tag])
        else:
            ifd += struct.pack("<HHI", tag, typ, len(vals)) + packed.ljust(4, b"\0")
    return b"II*\x00" + struct.pack("<I", ifd_at) + ifd + b"\0\0\0\0" + bytes(ex) + b"".join(blobs)


class Files:
    """get(url, start, end) over in-memory files, counting the requests."""
    def __init__(self, files):
        self.files, self.calls = files, []

    def __call__(self, url, start, end):
        self.calls.append((url, start, end))
        return self.files[url][start:end + 1]


vals = [(r * 37 + c * 11) % 65536 for r in range(10) for c in range(13)]
f = Files({"t": tiff(vals, 13, 10, 4, 1000.0, 2000.0, 30.0, 32650)})
cog = A.Cog(f, "t")
assert (cog.w, cog.h, cog.tw, cog.epsg, cog.x0, cog.y0, cog.sx) == (13, 10, 4, 32650, 1000.0, 2000.0, 30.0)
got = cog.read(3, 2, 9, 11)
assert got == [vals[r * 13 + c] for r in range(3, 9) for c in range(2, 11)], "a window across tile edges"
assert len(f.calls) == 1 + 3 * 3, "the header, then exactly the nine tiles the window touches"
assert cog.read(-5, -5, 2, 2) == [vals[r * 13 + c] for r in range(2) for c in range(2)], "clipped to the image"
assert cog.pixel(1000.0 + 30 * 4 + 1, 2000.0 - 30 * 7 - 1) == (7, 4)
try:
    A.Cog(Files({"p": tiff(vals, 13, 10, 4, 0.0, 0.0, 30.0, 32650, predictor=2)}), "p")
    raise AssertionError("a predictor this reader does not undo must be refused, not misread")
except ValueError as e:
    assert "predictor=2" in str(e)
print("COG reader: one range request per tile touched, windows across tile edges, odd layouts refused")

# ---------------------------------------------------------------- the conversion and the mask
# Scale and offset come from the STAC item's raster:bands, and these fixtures carry what it published on 15 Oct.
assert (CLEAR["scale"], CLEAR["offset"]) == (0.00341802, 149.0)
assert abs(A.kelvin_to_c(43000, 0.00341802, 149.0) - (43000 * 0.00341802 + 149.0 - 273.15)) < 1e-9
assert abs(A.kelvin_to_c(43000, 0.00341802, 149.0) - 22.82486) < 1e-4
try:
    A._band({"id": "x", "assets": {"lwir11": {"href": "h", "raster:bands": [{"offset": 149}]}}}, "lwir11")
    raise AssertionError("an item with no published scale must be refused")
except ValueError:
    pass
# Landsat C2 QA_PIXEL values as they occur: 21824 clear land, 21952 clear water, 22280 high-confidence cloud,
# 23888 cloud shadow, 54596 high cirrus, 1 fill.
assert A.clear(21824, 40000)
assert not A.clear(21952, 40000), "water is left out of both sides"
assert not A.clear(22280, 40000) and not A.clear(23888, 40000) and not A.clear(54596, 40000) and not A.clear(1, 40000)
assert not A.clear(21824, 0), "ST_B10 0 is no data even where QA says clear"
print("conversion: scale and offset as published; the mask keeps clear land and nothing else")

# ---------------------------------------------------------------- the cell against the ring, on a real scene
st, qa = CLEAR["st"], CLEAR["qa"]
res = A.surface(st, qa, LAT, LON, fwd, CLEAR["scale"], CLEAR["offset"], 900, inner_m=500)
assert res["lst"] is not None and res["cell_clear"] == 1.0, res
assert 20 < res["lst"] < 60 and 20 < res["lst_ring"] < 60, "a Bali morning's ground, in °C, not kelvin"
assert abs(res["lst_delta"] - (res["lst"] - res["lst_ring"])) < 1e-9
assert res["lst_pctile"] is None and res["ring_cells"] < 5, "too few ring cells in a 0.9 km ring to rank against"
# The cell's mean, recomputed independently: the cell's own boundary from h3, projected, and a point-in-polygon
# test per pixel, instead of the adapter's per-pixel inverse projection.
house = h3.latlng_to_cell(LAT, LON, 8)
poly = [fwd(la, lo) for la, lo in h3.cell_to_boundary(house)]


def inside(x, y):
    n, j, yes = len(poly), len(poly) - 1, False
    for i in range(n):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            yes = not yes
        j = i
    return yes


temps = [A.kelvin_to_c(dn, CLEAR["scale"], CLEAR["offset"])
         for k, (dn, q) in enumerate(zip(st["values"], qa["values"]))
         if A.clear(q, dn) and inside(st["x0"] + (k % 64 + 0.5) * 30, st["y0"] - (k // 64 + 0.5) * 30)]
assert len(temps) > 700, f"a res-8 cell is about 820 pixels of 30 m; found {len(temps)}"
assert abs(sum(temps) / len(temps) - res["lst"]) < 0.05, (sum(temps) / len(temps), res["lst"])
# heat the cell by 500 DN (1.709 K) and the difference moves by exactly that, the ring not at all
hot = dict(st, values=[dn + 500 if dn and inside(st["x0"] + (k % 64 + 0.5) * 30, st["y0"] - (k // 64 + 0.5) * 30)
                       else dn for k, dn in enumerate(st["values"])])
res2 = A.surface(hot, qa, LAT, LON, fwd, CLEAR["scale"], CLEAR["offset"], 900, inner_m=500)
assert abs(res2["lst_ring"] - res["lst_ring"]) < 1e-9
assert abs(res2["lst_delta"] - res["lst_delta"] - 500 * 0.00341802) < 0.02, res2["lst_delta"] - res["lst_delta"]
print(f"real scene, 27 Sep: cell {res['lst']:.1f} °C, ring {res['lst_ring']:.1f} °C; the mean matches an independent "
      f"polygon test over {len(temps)} pixels")

# the next day, cloud over the cell: no number, and the reason
res = A.surface(CLOUDY["st"], CLOUDY["qa"], LAT, LON, fwd, CLOUDY["scale"], CLOUDY["offset"], 900, inner_m=500)
assert res["lst"] is None and "cell" in res["why"] and res["cell_clear"] < 0.5, res
print(f"real scene, 28 Sep: {res['why']}, so no reading")

# ---------------------------------------------------------------- the percentile, on a field made to answer it
# A flat 40 °C field on the Bali grid with the node's cell 3 °C hotter: it ranks above every ring cell. Then the
# same cell 3 °C cooler: below every one.
W = 190
grid = {"w": W, "h": W, "x0": fwd(LAT, LON)[0] - W * 15, "y0": fwd(LAT, LON)[1] + W * 15, "sx": 30.0, "sy": 30.0}
flat = round((40 + 273.15 - 149.0) / 0.00341802)
inv = A.local_inverse(fwd, LAT, LON)
in_house = [h3.latlng_to_cell(*inv(grid["x0"] + (k % W + 0.5) * 30, grid["y0"] - (k // W + 0.5) * 30), 8) == house
            for k in range(W * W)]
qa_clear = dict(grid, values=[21824] * (W * W))
for bump, want in ((878, 100), (-878, 0)):
    field = dict(grid, values=[flat + bump if h else flat for h in in_house])
    r = A.surface(field, qa_clear, LAT, LON, fwd, 0.00341802, 149.0, 2400)
    assert r["ring_cells"] >= 5 and r["lst_pctile"] == want, (bump, r)
    assert abs(r["lst_delta"] - bump * 0.00341802) < 0.01
# the sea is left out: turn every pixel west of the node into clear water and the ring is still flat land at 40 °C
sea = dict(grid, values=[21952 if k % W < W // 2 else 21824 for k in range(W * W)])
r = A.surface(dict(grid, values=[flat] * (W * W)), sea, LAT, LON, fwd, 0.00341802, 149.0, 2400)
assert r["lst"] is not None and abs(r["lst_ring"] - 40) < 0.01 and abs(r["lst_delta"]) < 0.01, r
print("percentile: 100 for the hottest cell, 0 for the coolest; water is on neither side")

# ---------------------------------------------------------------- MODIS overpass times
assert A.overpass("2026-10-08T00:00:00Z", 1.5, LON) == datetime(2026, 10, 8, 17, 49, 22, 298400, tzinfo=timezone.utc)
assert A.overpass("2026-10-09T00:00:00Z", 22.5, LON).strftime("%d %H:%M") == "09 14:49"
assert A.overpass("2026-10-09T00:00:00Z", 22.5, -70.6693).strftime("%d %H:%M") == "09 03:12", "west of Greenwich"
print("MODIS: local solar overpass folded into the file's UTC day")

# ---------------------------------------------------------------- the day's check, end to end on fake hosts
# The two fixture crops served as COGs; a STAC search that returns both scenes, cloudy one newest.


def href(sid, band):
    return f"https://landsateuwest.blob.core.windows.net/landsat-c2/{sid}_{band}.TIF"


files = {}
items = []
for fx in (CLOUDY, CLEAR):
    for band, key in (("ST_B10", "st"), ("QA_PIXEL", "qa")):
        files[href(fx["scene"], band)] = tiff(fx[key]["values"], 64, 64, 32, fx[key]["x0"], fx[key]["y0"], 30.0, 32650)
    items.append({"id": fx["scene"], "properties": {"datetime": fx["datetime"], "platform": "landsat-8"},
                  "assets": {"lwir11": {"href": href(fx["scene"], "ST_B10"),
                                        "raster:bands": [{"scale": fx["scale"], "offset": fx["offset"]}]},
                             "qa_pixel": {"href": href(fx["scene"], "QA_PIXEL")}}})


class Resp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class Hc:
    def __init__(self, features):
        self.features, self.posts = features, 0

    def post(self, url, json=None):
        assert url == A.STAC and json["collections"] == ["landsat-c2-l2"]
        self.posts += 1
        return Resp({"features": self.features})


A.INNER_M = 500                                   # the crops are 1.92 km a side: a 0.5-0.9 km ring fits in them
state, get = {}, Files(files)
sensors, readings = A.landsat(Hc(items), state, LAT, LON, 900, 0.5, get=get)
assert [s["sensor_id"] for s in sensors] == ["surface-cell"] and sensors[0]["kind"] == "model" and not sensors[0]["local"]
assert sensors[0]["meta"]["scene"] == CLEAR["scene"], "the cloudy newer scene was skipped, the clear one used"
assert {r[2] for r in readings} == {"lst", "lst_ring", "lst_delta"}, "no percentile from two ring cells"
assert all(r[0] == datetime(2026, 9, 27, 2, 29, 58, 673123, tzinfo=timezone.utc) for r in readings), "stamped at the pass"
assert set(state["landsat_seen"]) == {CLEAR["scene"], CLOUDY["scene"]} and state["landsat_newest"] == CLEAR["datetime"]
# the next day, the same two scenes: no new one, nothing read, nothing written
get.calls.clear()
assert A.landsat(Hc(items), state, LAT, LON, 900, 0.5, get=get) == ([], []) and not get.calls
# a scene older than the one stored is not a new scene either, even unseen
old = dict(items[1], id="LC08_OLDER", properties={"datetime": "2026-09-01T02:29:00Z"})
assert A.landsat(Hc([old]), state, LAT, LON, 900, 0.5, get=get) == ([], []) and not get.calls
# only the cloudy one is new: it is read once, remembered, and gives nothing
state2 = {}
assert A.landsat(Hc(items[:1]), state2, LAT, LON, 900, 0.5, get=Files(files)) == ([], [])
assert state2["landsat_seen"] == [CLOUDY["scene"]] and "landsat_newest" not in state2
A.INNER_M = 1000
print("the day's check: cloudy newest passed over, clear one stored at its pass, the same scene never read twice")

# once a day, and the day survives a restart: a recent check on disk means no request at all
with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    A._save({"checked": time.time() - 3600})

    class Never:
        def __getattr__(self, name):
            raise AssertionError(f"fetch made a request ({name}) within a day of the last check")
    assert A.fetch(Never()) == ([], [])
    # both products failing raises, so status.errors says so, and the next try is in an hour, not a day
    A._save({})

    class Down:
        def post(self, *a, **k):
            raise ConnectionError("planetarycomputer.microsoft.com unreachable")
    try:
        A.fetch(Down())
        raise AssertionError("both products failing must raise")
    except RuntimeError as e:
        assert "landsat" in str(e) and "modis" in str(e)
    wait = A.DAY - (time.time() - A._load()["checked"])
    assert 3500 < wait < 3700, wait
    os.environ.pop("PACK_OUT")
print("once a day: remembered on disk; an outage retries in an hour")

print("all surface-heat pack tests pass")
sys.exit(0)
