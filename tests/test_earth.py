"""The earth pack's arithmetic, offline: no bucket, no rasterio, no database.

numpy is imported without a guard on purpose. This pack's only claim is arithmetic, so a run that quietly
prints "skipped" because numpy is missing is worse than a run that fails: it would let the pack ship with the
de-quantisation wrong. If this line fails, install numpy on the dev machine.
Run: PYTHONPATH=/tmp/stub:app python3 tests/test_earth.py
"""
import importlib.util
import json
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path

import numpy as np

os.environ.setdefault("NODE_LAT", "-8.8271")
os.environ.setdefault("NODE_LON", "115.15709")
os.environ.setdefault("NODE_NAME", "test-node")

spec = importlib.util.spec_from_file_location("earthpack", "packs/earth/adapter.py")
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)

# ---------------------------------------------------------------- de-quantisation and the norm
# The bucket's README: divide by 127.5, square, keep the sign. Not a linear scale factor.
assert A.dequantize(np.array([127], dtype=np.int8))[0] == np.float32((127 / 127.5) ** 2)
assert A.dequantize(np.array([-127], dtype=np.int8))[0] == np.float32(-((127 / 127.5) ** 2))
assert A.dequantize(np.array([0], dtype=np.int8))[0] == 0.0
# monotone in the raw value, which is what makes it a usable quantisation at all
raw = np.arange(-127, 128, dtype=np.int8)
assert np.all(np.diff(A.dequantize(raw)) > 0)
# and it stays inside the range the README promises
assert A.dequantize(raw).min() >= -1.0 and A.dequantize(raw).max() <= 1.0

# Round trip: quantise a unit vector the way the dataset does, de-quantise it, and the length comes back to 1
# within the tolerance verify.py enforces on real pixels.
rng = np.random.default_rng(7)
v = rng.normal(size=(64, 500)).astype(np.float32)
v /= np.linalg.norm(v, axis=0)
q = np.clip(np.rint(np.sign(v) * np.sqrt(np.abs(v)) * 127.5), -127, 127).astype(np.int8)
norms = np.linalg.norm(A.dequantize(q), axis=0)
worst = float(np.abs(norms - 1.0).max())
assert worst < 0.01, f"quantisation round trip drifts by {worst}, more than verify.py's 0.01 tolerance"

# ---------------------------------------------------------------- the distance
def stack(vec, h, w):
    return np.repeat(vec[:, None, None], h, 1).repeat(w, 2)

u = v[:, 0] / np.linalg.norm(v[:, 0])
qu = np.clip(np.rint(np.sign(u) * np.sqrt(np.abs(u)) * 127.5), -127, 127).astype(np.int8)
same = stack(qu, 4, 4)
d, masked = A.cosine_distance(same, same)
assert not masked.any()
assert np.allclose(d, 0.0, atol=2e-3), f"a year against itself must be 0, got {d.max()}"

# the opposite vector is distance 2; a right angle is 1
d_opp, _ = A.cosine_distance(same, stack(-qu, 4, 4))
assert abs(float(d_opp.max()) - 2.0) < 2e-3, d_opp.max()
e0 = np.zeros(64, dtype=np.int8); e0[0] = 127
e1 = np.zeros(64, dtype=np.int8); e1[1] = 127
d_perp, _ = A.cosine_distance(stack(e0, 3, 3), stack(e1, 3, 3))
assert abs(float(d_perp.max()) - 1.0) < 2e-3, d_perp.max()

# every distance stays inside [0, 2] even on adversarial input
rand_a = rng.integers(-127, 128, size=(64, 40, 40)).astype(np.int8)
rand_b = rng.integers(-127, 128, size=(64, 40, 40)).astype(np.int8)
d_rand, _ = A.cosine_distance(rand_a, rand_b)
assert float(np.nanmin(d_rand)) >= 0.0 and float(np.nanmax(d_rand)) <= 2.0

# no data is -128 in every channel, it is excluded, and it does not become a number
a = stack(qu, 5, 5).copy(); a[:, 2, 3] = -128
d_m, m_m = A.cosine_distance(a, stack(qu, 5, 5))
assert m_m[2, 3] and m_m.sum() == 1 and np.isnan(d_m[2, 3])

# the band size must not change the answer
d1, _ = A.cosine_distance(rand_a, rand_b, rows=7)
assert np.allclose(np.nan_to_num(d_rand), np.nan_to_num(d1), atol=1e-6)

# ---------------------------------------------------------------- the window, against a known tile
# Node #1: -8.8271, 115.15709 falls in 50S tile x...-0000000000-0000008192, whose pixel origin is
# 254240 E. The measured centre pixel is row 680, col 4306, and a 5000 m radius gave a window at
# col_off 3806, row_off 180, 1000 x 1000. That is the arithmetic below, with no raster and no projection.
r0, c0, r1, c1, clipped = A.window_px(680, 4306, 5000, 8192, 8192)
assert (r0, c0, r1 - r0, c1 - c0) == (180, 3806, 1000, 1000), (r0, c0, r1, c1)
assert not clipped
# and at an edge it clips rather than reading outside the tile
r0, c0, r1, c1, clipped = A.window_px(100, 4306, 5000, 8192, 8192)
assert (r0, r1 - r0) == (0, 600) and clipped
try:
    A.window_px(-900, 4306, 5000, 8192, 8192); raise AssertionError("a square wholly off the tile must raise")
except RuntimeError:
    pass

# ---------------------------------------------------------------- the zone the index is searched by
assert A.utm_zone(-8.8271, 115.15709) == "50S"          # Bali
assert A.utm_zone(41.3874, 2.1686) == "31N"             # Barcelona
assert A.utm_zone(-33.4310, -70.6045) == "19S"          # Santiago
assert A.utm_zone(42.3601, -71.0589) == "19N"           # Boston
assert A.utm_zone(0.0, -180.0) == "1N" and A.utm_zone(-1.0, 179.999) == "60S"
# the index is sorted 1N..60N then 1S..60S; the search depends on that order
assert A._zone_key("1N") < A._zone_key("60N") < A._zone_key("1S") < A._zone_key("50S")

# ---------------------------------------------------------------- the ramp and the PNG
dist = np.array([[0.0, A.RAMP_CEILING / 2, A.RAMP_CEILING, 1.0]], dtype=np.float32)
mask = np.array([[False, False, False, False]])
ix = A.ramp_indices(dist, mask)
assert ix[0, 0] == 1 and ix[0, 2] == 252 and ix[0, 3] == 252, ix     # the ceiling clamps, it does not wrap
assert 120 < int(ix[0, 1]) < 135
assert A.ramp_indices(dist, np.array([[True, False, False, False]]))[0, 0] == A.NODATA_IX

with tempfile.TemporaryDirectory() as tmp:
    png = Path(tmp) / "t.png"
    grid = np.zeros((40, 200), dtype=np.uint8)
    A.draw_marks(grid, (20, 100))
    assert (grid == A.NODE_IX).sum() > 0, "the node ring was not drawn"
    assert (grid == A.RULE_IX).sum() > 0, "the scale bar was not drawn"
    n = A.write_png(png, grid, {"Copyright": A.ATTRIBUTION})
    blob = png.read_bytes()
    assert n == len(blob) and blob[:8] == b"\x89PNG\r\n\x1a\n"
    # walk the chunks: the length, type and CRC of each must agree, and the header must say what we meant
    pos, seen, idat = 8, [], b""
    while pos < len(blob):
        ln = struct.unpack(">I", blob[pos:pos + 4])[0]
        kind = blob[pos + 4:pos + 8]
        data = blob[pos + 8:pos + 8 + ln]
        crc = struct.unpack(">I", blob[pos + 8 + ln:pos + 12 + ln])[0]
        assert crc == zlib.crc32(kind + data) & 0xFFFFFFFF, f"bad CRC on {kind}"
        seen.append(kind.decode())
        if kind == b"IDAT":
            idat += data
        pos += 12 + ln
    assert seen[0] == "IHDR" and seen[-1] == "IEND" and "PLTE" in seen and "tEXt" in seen
    w_, h_, depth, ctype = struct.unpack(">IIBB", blob[16:26])
    assert (w_, h_, depth, ctype) == (200, 40, 8, 3)
    assert A.ATTRIBUTION.encode() in blob, "the attribution must travel inside the PNG"
    # the pixels come back exactly, filter byte and all
    rows = zlib.decompress(idat)
    assert len(rows) == h_ * (w_ + 1)
    back = np.frombuffer(rows, dtype=np.uint8).reshape(h_, w_ + 1)
    assert (back[:, 0] == 0).all() and np.array_equal(back[:, 1:], grid)

# ---------------------------------------------------------------- the cache and the adapter
with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    assert A.cached_years() == [] and A.latest_pair() is None
    A.cache().mkdir(parents=True)
    for y in (2017, 2020, 2024, 2025):
        np.save(A.year_file(y), np.zeros((2, 2, 2), dtype=np.int8))
    assert A.cached_years() == [2017, 2020, 2024, 2025]
    assert A.latest_pair() == (2024, 2025), "only consecutive years are a year-over-year pair"
    # and when the newest years are not adjacent, the pair is the newest adjacent one, not the newest two
    for y in (2020, 2024, 2025):
        A.year_file(y).unlink()
    for y in (2018, 2023):
        np.save(A.year_file(y), np.zeros((2, 2, 2), dtype=np.int8))
    assert A.cached_years() == [2017, 2018, 2023]
    assert A.latest_pair() == (2017, 2018), "2018 and 2023 are five years apart, not a year-over-year pair"
    A.year_file(2023).unlink(); A.year_file(2018).unlink()
    for y in (2020, 2024, 2025):
        np.save(A.year_file(y), np.zeros((2, 2, 2), dtype=np.int8))
    # an idle pack says nothing rather than raising or inventing a reading
    assert A.fetch(None) == ([], [])
    for a_, b_, mean in ((2024, 2025, 0.041), (2017, 2025, 0.128)):
        A.change_file(a_, b_, "json").write_text(json.dumps(
            {"year_a": a_, "year_b": b_, "mean": mean, "threshold": 0.15, "share_over_threshold": 0.01,
             "hectares_over_threshold": 100.0, "png": f"change_{a_}_{b_}.png", "tiles": ["gs://x"]}))
    sensors, readings = A.fetch(None)
    got = {m: v for _, _, m, v in readings}
    assert sensors[0]["sensor_id"] == "earth-point" and sensors[0]["kind"] == "model"
    assert sensors[0]["scale"] == "city" and sensors[0]["cadence"] == "P1Y" and not sensors[0]["local"]
    assert A.ATTRIBUTION in sensors[0]["meta"]["attribution"]
    assert got["land_change_yoy"] == 0.041 and got["land_change_since_2017"] == 0.128
    assert got["years_cached"] == 4.0
    assert all(ts.year == 2025 for ts, _, _, _ in readings), "an annual reading is stamped in its own year"
    os.environ.pop("PACK_OUT")

# the cell the pack ships must be partial, and must read the metric the adapter writes
import yaml                                                                      # noqa: E402
cells = yaml.safe_load(open("packs/earth/cells.yml"))
assert len(cells) == 1 and cells[0]["cell"] == "Environmental|City"
assert cells[0]["state"] == "partial", "a model's output is never live"
assert "land_change_yoy" in cells[0]["sql"] and "earth-point" in cells[0]["sql"]
manifest = yaml.safe_load(open("packs/earth/pack.yaml"))
assert set(manifest["metrics"]) == {"land_change_yoy", "land_change_since_2017", "years_cached"}
assert manifest["pip"] == ["rasterio", "numpy"] and manifest["scales"] == ["city"]
assert A.ATTRIBUTION == manifest["attribution"]

# ---------------------------------------------------------------- a square that stopped describing this node
# The cached years are named by year alone. Before this, changing NODE_LAT/NODE_LON re-resolved the tiles but every
# cached year was skipped as "already cached", so the node went on comparing the previous square, and verify passed
# because it measured the window's size and never its position.
BALI = (-8.8271, 115.15709)
assert round(A.metres(*BALI, BALI[0] + 0.001, BALI[1])) == 111
assert A.move_tolerance(5000) == 50.0 and A.move_tolerance(1000) == 25.0, "1% of the radius, floor 25 m"
assert A.drift({}, *BALI) is None, "a cache with no point recorded cannot be placed"
assert A.drift({"lat": BALI[0], "lon": BALI[1]}, *BALI) == 0.0
assert round(A.drift({"lat": BALI[0], "lon": BALI[1]}, BALI[0] + 0.002, BALI[1])) == 223
assert A.drift({"lat": 41.4036, "lon": 2.2033}, *BALI) > 1e6

_fetch = open("packs/earth/fetch.py").read()
assert "stale_square = moved or resized" in _fetch, "a moved or resized square must be detected"
assert "force or stale_square or not A.year_file(y).exists()" in _fetch, \
    "a stale square must re-read the cached years, not skip them as already cached"
assert 'prev_radius = m.get("radius_m")' in _fetch, "the previous radius has to be read before meta is replaced"
_verify = open("packs/earth/verify.py").read()
assert "A.drift(m, lat, lon)" in _verify, "verify must place the cache, not only measure it"
assert "A.year_file(y).unlink()" in _fetch, "years the run will not re-read must not survive a moved square"
_change = open("packs/earth/change.py").read()
assert 'orphan = [y for y, w in ((a, wa), (b, wb)) if not w.get("bounds")]' in _change, \
    "change must refuse a year with no window for the current square"

assert 'A.cache().glob("change_*")' in _fetch, "a moved square must not leave its comparison for the card to serve"

print("earth move tests pass")

# ---------------------------------------------------------------- a renamed node, and the square it already has
# The cache directory was keyed on NODE_NAME. Node #1 was renamed bayu-2 → bayu-ungasan and re-read 930 MB of
# embeddings it already had on disk, then carried both copies (555 + 562 MB) with nothing reading the first. The
# embeddings describe a place, not a machine's name, so the name is not the key: a directory whose meta.json says
# it holds this square answers for this node whatever it is called.
def _meta(d: Path, lat, lon, radius=5000, **extra):
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps({"lat": lat, "lon": lon, "radius_m": radius, **extra}))
    return d

with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    was_name = os.environ["NODE_NAME"]
    os.environ["NODE_NAME"] = "bayu-ungasan"
    root = Path(tmp) / "earth"
    LAT, LON = -8.8271, 115.15709
    assert A.node() == "bayu-ungasan"

    # nothing on disk: the node's own name, exactly as before
    assert A.cache() == root / "bayu-ungasan"

    # the square is there under the name it was fetched with. It is this node's square, so it is this node's cache.
    old = _meta(root / "bayu-2", LAT, LON)
    np.save(old / "2025.npy", np.zeros((2, 2, 2), dtype=np.int8))
    assert A.cache() == old, f"a renamed node must find its own square, got {A.cache()}"
    assert A.cached_years() == [2025], "and read it: this is the 930 MB that would be downloaded again"
    assert A.meta()["lat"] == LAT

    # both directories exist — node #1 today. The one named for the node wins, so nothing switches under a live
    # node and the older copy is left where it is for a person to decide about.
    new = _meta(root / "bayu-ungasan", LAT, LON)
    assert A.cache() == new, "the node's own name wins when both describe the square"

    # a directory read around somewhere else is not this node's cache, however it is named
    import shutil
    shutil.rmtree(new)
    _meta(root / "santiago", -33.4310, -70.6045)
    assert A.cache() == old, "the nearer-named square must not be displaced by an unrelated one"
    shutil.rmtree(old)
    assert A.cache() == root / "bayu-ungasan", "a square read around another city is never adopted"

    # a corrected decimal (inside the move tolerance) keeps the cache; a real move does not
    drifted = _meta(root / "bayu-2", LAT + 0.0002, LON)          # 22 m, tolerance is 50 m at 5000
    assert 0 < A.drift(json.loads((drifted / "meta.json").read_text()), LAT, LON) < 50
    assert A.cache() == drifted, "a 22 m correction must not orphan nine years of embeddings"
    _meta(root / "bayu-2", LAT + 0.01, LON)                      # 1.1 km: a different square
    assert A.cache() == root / "bayu-ungasan", "a moved node must not silently adopt the previous square"

    # the radius is part of the square. A bigger one is a different picture of the same place.
    _meta(root / "bayu-2", LAT, LON, radius=8000)
    assert A.cache() == root / "bayu-ungasan", "a resized square is not this square"
    _meta(root / "bayu-2", LAT, LON)
    assert A.cache() == root / "bayu-2"
    # a meta.json from before the radius was recorded is still this square: it must not force a re-read
    (root / "bayu-2" / "meta.json").write_text(json.dumps({"lat": LAT, "lon": LON}))
    assert A.cache() == root / "bayu-2", "a pre-v0.33.4 meta.json records no radius; that is not a resize"
    # and neither unreadable json nor a directory without meta.json stops the scan
    (root / "half-written").mkdir(); (root / "half-written" / "meta.json").write_text("{not json")
    (root / "empty").mkdir()
    assert A.cache() == root / "bayu-2"

    os.environ.pop("PACK_OUT")
    os.environ["NODE_NAME"] = was_name
print("earth cache: a rename costs nothing, a move still costs everything")

# ---------------------------------------------------------------- change: its arguments, and --all
# `planetai run earth change --all` used to print an ordinary result for the latest pair: the flag was not a
# digit so it was dropped, and an empty argument list meant "the default". Run the real script and read what
# it does, rather than grepping it for the word --all.
import subprocess
with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, "PACK_OUT": tmp, "NODE_NAME": "t", "NODE_LAT": "-8.8271", "NODE_LON": "115.15709",
           "EARTH_RADIUS_M": "5000", "PYTHONPATH": os.getcwd()}
    cache = Path(tmp) / "earth" / "t"; cache.mkdir(parents=True)
    win = {"crs": "EPSG:32750", "bounds": {"west": 0.0, "east": 40.0, "south": 0.0, "north": 40.0},
           "px": [4, 4], "clipped": False, "north_up": True, "node_rc": [2, 2], "object": "gs://x.tiff"}
    rng2 = np.random.default_rng(3)
    for y in (2020, 2021, 2022):
        np.save(cache / f"{y}.npy", rng2.integers(-100, 100, size=(64, 4, 4)).astype(np.int8))
    (cache / "meta.json").write_text(json.dumps(
        {"lat": -8.8271, "lon": 115.15709, "radius_m": 5000, "windows": {str(y): win for y in (2020, 2021, 2022)}}))

    def run(*a):
        return subprocess.run([sys.executable, "packs/earth/change.py", *a], env=env, capture_output=True, text=True)

    for bad in (["--evrything"], ["217", "2022"], ["2021"], ["2020", "2021", "2022"]):
        r = run(*bad)
        assert r.returncode == 1, f"change {' '.join(bad)} must fail, got {r.returncode}: {r.stdout}"
        assert "usage:" in r.stdout, f"change {' '.join(bad)} must print the usage: {r.stdout}"
    assert not list(cache.glob("change_*")), "a rejected argument must not compute anything"

    r = run()                                        # the default is still the latest consecutive pair
    assert r.returncode == 0, r.stdout + r.stderr
    assert {p.name for p in cache.glob("change_*.json")} == {"change_2021_2022.json"}, r.stdout

    r = run("--all")                                 # every consecutive pair, plus the span
    assert r.returncode == 0, r.stdout + r.stderr
    assert {p.name for p in cache.glob("change_*.json")} == {
        "change_2020_2021.json", "change_2021_2022.json", "change_2020_2022.json"}, r.stdout
    assert "the span" in r.stdout and "already computed, skipping 2021→2022" in r.stdout, r.stdout

    before = (cache / "change_2020_2021.json").stat().st_mtime_ns
    assert "already computed" in run("--all").stdout                       # idempotent
    assert (cache / "change_2020_2021.json").stat().st_mtime_ns == before
    assert "already computed" not in run("--all", "--force").stdout        # and --force redoes it
    assert (cache / "change_2020_2021.json").stat().st_mtime_ns != before
print("change: unknown arguments refused, --all walks the history, --force redoes it")

# ---------------------------------------------------------------- the yearly frames
# The projection must be fitted once and reused: refitting when a year arrives would silently redraw every
# earlier frame, and a sequence whose greys move is not a sequence.
with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    A.cache().mkdir(parents=True)
    rng3 = np.random.default_rng(11)
    for y in (2023, 2024):
        np.save(A.year_file(y), rng3.integers(-100, 100, size=(64, 24, 24)).astype(np.int8))
    view = A.fit_view([2023, 2024])
    assert view["fitted_on"] == [2023, 2024] and len(view["axis"]) == 64 and len(view["breaks"]) == 256
    assert abs(float(np.linalg.norm(view["axis"])) - 1.0) < 1e-5, "the axis is a direction, so unit length"
    assert A.fit_view([2023, 2024])["axis"] == view["axis"], "the same years must give the same axis"
    # The sign of a principal axis is arbitrary; SVD picking one is not a guarantee. The pack fixes it so the
    # projection is left-skewed, which is what keeps water dark and land bright when the fit is redone over a
    # different set of years. Check the property, not that two identical calls agree.
    _v = A.dequantize(np.asarray(np.load(A.year_file(2024), mmap_mode="r")).reshape(64, -1))
    _p = (np.array(view["axis"])[None, :] @ (_v - np.array(view["mean"])[:, None]))[0]
    assert float(((_p - _p.mean()) ** 3).mean()) <= 0, "fit_view must fix the axis sign, not take SVD's"
    ix = A.render_year(2023, view, (12, 12))
    assert ix.shape == (24, 24) and ix.dtype == np.uint8
    assert ix.min() >= 0 and ix.max() <= 254
    # a year drawn through a view fitted without it still renders, and identically each time
    assert np.array_equal(A.render_year(2024, view), A.render_year(2024, view))
    # no-data survives as no-data rather than becoming a grey
    raw = np.load(A.year_file(2023)); raw[:, 3, 4] = -128; np.save(A.year_file(2023), raw)
    assert A.render_year(2023, view)[3, 4] == A.NODATA_IX
    # the year is burnt in, in the rule colour, bottom right
    big = np.zeros((200, 200), dtype=np.uint8)
    A.draw_year(big, 2017)
    assert (big == A.RULE_IX).sum() > 0 and (big[:100, :100] == A.RULE_IX).sum() == 0, "bottom right"
    assert A.year_png(2017).name == "year_2017.png"
    os.environ.pop("PACK_OUT")
print("earth frames: one shared projection, reused, and no-data stays no-data")

# ---------------------------------------------------------------- the image the Wall may show
# The Wall is tokenless and may show nothing finer than the house's res-8 cell. change_<A>_<B>.png is a square
# centred on the house's pixel with a ring on it, so the Wall gets its own image: changed pixels only, inside the
# community's res-7 cells that lie wholly in a square centred on the cell's centre, transparent everywhere else.
import h3                                                                         # noqa: E402

def _chunks(png: bytes) -> dict:
    out, i = {}, 8
    while i < len(png):
        n = struct.unpack(">I", png[i:i + 4])[0]
        out.setdefault(png[i + 4:i + 8], []).append(png[i + 8:i + 8 + n]); i += 12 + n
    return out

# the mask: only changed, unmasked pixels inside `allowed` are lit
dist10 = np.full((10, 10), 0.05); dist10[::2, :] = 0.4
masked10 = np.zeros((10, 10), bool); masked10[0, 0] = True
allowed10 = np.zeros((10, 10), bool); allowed10[:, :5] = True
m10 = A.wall_mask(dist10, masked10, 0.15, allowed10)
assert m10.dtype == np.uint8 and set(np.unique(m10)) == {0, 1}
assert m10[:, 5:].sum() == 0, "nothing outside the allowed cells"
assert m10[0, 0] == 0, "a masked pixel is not change"
assert m10.sum() == 5 * 5 - 1 and np.array_equal(m10[:, :5] == 1, (dist10[:, :5] > 0.15) & ~masked10[:, :5])

# the PNG: a two-entry palette, the first transparent, and nothing else in it
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "w.png"
    A.write_png(p, m10, {"Copyright": A.ATTRIBUTION}, palette=A.WALL_PALETTE, trns=b"\x00")
    ch = _chunks(p.read_bytes())
    assert ch[b"PLTE"] == [b"\x00\x00\x00\xff\xbe\x78"], "transparent, then #FFBE78"
    assert ch[b"tRNS"] == [b"\x00"], "palette entry 0 is fully transparent"
    raw = zlib.decompress(b"".join(ch[b"IDAT"]))
    assert np.array_equal(np.frombuffer(raw, np.uint8).reshape(10, 11)[:, 1:], m10)
    A.write_png(p, m10)                                       # the old call is unchanged: no tRNS, 256 colours
    assert b"tRNS" not in _chunks(p.read_bytes()) and len(_chunks(p.read_bytes())[b"PLTE"][0]) == 768

# The crop, from a synthetic tile: every ground pixel has its own distance, so two windows read around two
# different points inside the same res-8 cell hold the same values wherever they overlap, as two fetches would.
fwd = A.projection(32750)
LATH, LONH = -8.8271, 115.15709
home = h3.latlng_to_cell(LATH, LONH, 8)
cen = h3.cell_to_latlng(home)

def window(lat, lon, radius=5000):
    x, y = fwd(lat, lon)
    i, j, half = int(x // 10), int(y // 10), radius // 10
    b = {"west": 10.0 * (i - half), "east": 10.0 * (i + half), "north": 10.0 * (j + half), "south": 10.0 * (j - half)}
    I = (i - half + np.arange(2 * half))[None, :]
    J = (j + half - 1 - np.arange(2 * half))[:, None]
    d = ((I * 7919 + J * 104729) % 1000) / 1000 * 0.3
    return d, ((I * 31 + J * 17) % 50 == 0) & np.ones_like(d, bool), b

shots = []
houses = [cen, (LATH, LONH)] + [(cen[0] + 0.97 * (v[0] - cen[0]), cen[1] + 0.97 * (v[1] - cen[1]))
                               for v in h3.cell_to_boundary(home)[:3]]
with tempfile.TemporaryDirectory() as tmp:
    for k, (la, lo) in enumerate(houses):
        assert h3.latlng_to_cell(la, lo, 8) == home, "every test house is inside the same res-8 cell"
        d, msk, b = window(la, lo)
        ix, crop = A.wall_image(d, msk, b, "EPSG:32750", home, 5000, 0.15)
        p = Path(tmp) / f"w{k}.png"
        A.write_png(p, ix, {"Copyright": A.ATTRIBUTION}, palette=A.WALL_PALETTE, trns=b"\x00")
        shots.append((crop, p.read_bytes(), ix))
assert all(s[0] == shots[0][0] for s in shots), [s[0] for s in shots]
assert all(s[1] == shots[0][1] for s in shots), "the PNG must not move with the house inside its cell"
crop, _, ix = shots[0]
assert set(crop) == {"bounds", "ha"} and set(crop["bounds"]) == {"west", "east", "north", "south"}
assert ix.shape == (round((crop["bounds"]["north"] - crop["bounds"]["south"]) / 10),
                    round((crop["bounds"]["east"] - crop["bounds"]["west"]) / 10)), "bounds are the image's edges"
assert crop["ha"] == round(int(ix.sum()) * 100 / 10000, 1), "ha counts the lit pixels and nothing else"

# the crop holds the community's cells that fit the safe square, whole, and nothing else
cx, cy = fwd(*cen)
circ = max(h3.great_circle_distance(cen, v, unit="m") for v in h3.cell_to_boundary(home))
half = 5000 - circ
fit = [c for c in h3.grid_disk(h3.cell_to_parent(home, 7), 1)
       if all(abs(x - cx) <= half and abs(y - cy) <= half for x, y in (fwd(*v) for v in h3.cell_to_boundary(c)))]
assert len(fit) == 7, f"at node #1's point all seven community cells fit a 5 km square, got {len(fit)}"
b = crop["bounds"]
assert cx - half <= b["west"] and b["east"] <= cx + half and cy - half <= b["south"] and b["north"] <= cy + half, \
    "the crop stays inside the square centred on the cell's centre"
d, msk, bw = window(*cen)
allowed = A.allowed_raster(bw, "EPSG:32750", d.shape, home, 5000)
area = sum(h3.cell_area(c, unit="m^2") for c in fit) / 100
assert abs(int(allowed.sum()) - area) / area < 0.01, (int(allowed.sum()), area)
# a smaller square drops the cells that no longer fit wholly, rather than cutting them
d3, msk3, b3 = window(*cen, radius=3000)
a3 = A.allowed_raster(b3, "EPSG:32750", d3.shape, home, 3000)
fit3 = [c for c in fit if all(abs(x - cx) <= 3000 - circ and abs(y - cy) <= 3000 - circ
                              for x, y in (fwd(*v) for v in h3.cell_to_boundary(c)))]
assert len(fit3) == 1 and abs(int(a3.sum()) - h3.cell_area(fit3[0], unit="m^2") / 100) < 0.01 * a3.sum()
assert A.wall_image(*window(*cen, radius=2000), "EPSG:32750", home, 2000, 0.15) is None, "no whole cell, no image"
# fetch reads radius // 10 pixels each way, so a radius that is not a multiple of 10 is read as the one below it
for la, lo in houses:
    d9, _, b9 = window(la, lo, radius=5009)
    assert np.array_equal(A.allowed_raster(b9, "EPSG:32750", d9.shape, home, 5009),
                          A.allowed_raster(b9, "EPSG:32750", d9.shape, home, 5000)), "5009 m is read as 5000"
# a window that is not clipped and still does not hold the safe square was read around somewhere else: which edge
# cells survived would say where, so there is no image. A tile edge is the same: where it cuts the square read round
# the house depends on where in the cell the house is, so a clipped read publishes nothing, even one that still holds
# every cell.
dt, mt, bt = window(*cen)
dt, mt, bt = dt[:, :-80], mt[:, :-80], {**bt, "east": bt["east"] - 800}   # 800 m short: past the 528 m slack
assert A.wall_image(dt, mt, bt, "EPSG:32750", home, 5000, 0.15) is None, "the square passes an unclipped edge"
assert A.wall_image(dt, mt, bt, "EPSG:32750", home, 5000, 0.15, clipped=True) is None, "a tile edge publishes nothing"
assert not A.allowed_raster(bw, "EPSG:32750", d.shape, home, 5000, clipped=True).any(), "clipped, nothing allowed"

# change.py writes it, end to end, beside the pair's map, and records the crop under `wall`
with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, "PACK_OUT": tmp, "NODE_NAME": "t", "NODE_LAT": str(LATH), "NODE_LON": str(LONH),
           "EARTH_RADIUS_M": "3000", "PYTHONPATH": os.getcwd()}
    cache = Path(tmp) / "earth" / "t"; cache.mkdir(parents=True)
    d3, _, b3 = window(LATH, LONH, radius=3000)
    rng4 = np.random.default_rng(5)
    base = rng4.integers(-100, 100, size=(64, 1, 1)).astype(np.int8)
    np.save(cache / "2024.npy", np.repeat(np.repeat(base, 600, 1), 600, 2))
    later = np.repeat(np.repeat(base, 600, 1), 600, 2); later[:, 300:, :] = -later[:, 300:, :]
    np.save(cache / "2025.npy", later)
    xh, yh = fwd(LATH, LONH)
    win = {"crs": "EPSG:32750", "bounds": b3, "px": [600, 600], "clipped": False, "north_up": True,
           "node_rc": [int(b3["north"] - yh) // 10, int(xh - b3["west"]) // 10], "object": "gs://x.tiff"}
    (cache / "meta.json").write_text(json.dumps({"lat": LATH, "lon": LONH, "radius_m": 3000,
                                                 "windows": {"2024": win, "2025": win}}))
    r = subprocess.run([sys.executable, "packs/earth/change.py"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    st = json.loads((cache / "change_2024_2025.json").read_text())
    wp = cache / "change_2024_2025_wall.png"
    assert wp.is_file() and set(st["wall"]) == {"bounds", "ha", "cell"} and st["wall"]["cell"] == home, r.stdout
    assert not list(cache.glob("*.part")), "the image is written beside and moved over, never left half"
    ch = _chunks(wp.read_bytes())
    assert ch[b"PLTE"] == [b"\x00\x00\x00\xff\xbe\x78"] and ch[b"tRNS"] == [b"\x00"]
    assert 0 < st["wall"]["ha"] < st["hectares_over_threshold"], st["wall"]
    px = np.frombuffer(zlib.decompress(b"".join(ch[b"IDAT"])), np.uint8)
    assert set(np.unique(px)) <= {0, 1}, "filter bytes and two colours: no node mark, no scale bar"
    # a pair computed before the Wall's image existed has no `wall` key: a plain run (no --force) computes it again
    old = {k: v for k, v in st.items() if k != "wall"}
    (cache / "change_2024_2025.json").write_text(json.dumps(old)); wp.unlink()
    r = subprocess.run([sys.executable, "packs/earth/change.py"], env=env, capture_output=True, text=True)
    assert r.returncode == 0 and "already computed" not in r.stdout, r.stdout + r.stderr
    assert wp.is_file() and json.loads((cache / "change_2024_2025.json").read_text())["wall"] == st["wall"]
    r = subprocess.run([sys.executable, "packs/earth/change.py"], env=env, capture_output=True, text=True)
    assert "already computed" in r.stdout, "with `wall` written, the pair is done"
    # a crop whose image is gone (a disk that filled mid-write) is not done: a plain run draws it again
    wp.unlink()
    r = subprocess.run([sys.executable, "packs/earth/change.py"], env=env, capture_output=True, text=True)
    assert "already computed" not in r.stdout and wp.is_file(), r.stdout + r.stderr
    # the house moved into another res-8 cell inside fetch's tolerance: the crop was cut round the old cell, so a plain
    # run cuts it again round the new one
    v = h3.cell_to_boundary(home)[0]
    moved = (cen[0] + 1.1 * (v[0] - cen[0]), cen[1] + 1.1 * (v[1] - cen[1]))
    assert h3.latlng_to_cell(*moved, 8) != home
    r = subprocess.run([sys.executable, "packs/earth/change.py"], env={**env, "NODE_LAT": str(moved[0]),
                                                                      "NODE_LON": str(moved[1])},
                       capture_output=True, text=True)
    assert "already computed" not in r.stdout, r.stdout + r.stderr
    st3 = json.loads((cache / "change_2024_2025.json").read_text())
    assert (st3["wall"] or {}).get("cell", st3.get("wall_cell")) == h3.latlng_to_cell(*moved, 8), st3.get("wall")

# two years read over different ground, one pixel apart, the same size: refused with the re-fetch, never differenced
with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, "PACK_OUT": tmp, "NODE_NAME": "t", "NODE_LAT": str(LATH), "NODE_LON": str(LONH),
           "EARTH_RADIUS_M": "3000", "PYTHONPATH": os.getcwd()}
    cache = Path(tmp) / "earth" / "t"; cache.mkdir(parents=True)
    for y in (2024, 2025):
        np.save(cache / f"{y}.npy", np.repeat(np.repeat(base, 600, 1), 600, 2))
    w24 = {"crs": "EPSG:32750", "bounds": b3, "px": [600, 600], "clipped": False, "north_up": True,
           "node_rc": [300, 300], "object": "gs://x.tiff"}
    w25 = {**w24, "bounds": {**b3, "west": b3["west"] + 10, "east": b3["east"] + 10}}
    for w_b, why in ((w25, "bounds"), ({**w24, "crs": "EPSG:32751"}, "crs")):
        (cache / "meta.json").write_text(json.dumps({"lat": LATH, "lon": LONH, "radius_m": 3000,
                                                     "windows": {"2024": w24, "2025": w_b}}))
        r = subprocess.run([sys.executable, "packs/earth/change.py"], env=env, capture_output=True, text=True)
        assert "different ground" in r.stdout and "planetai run earth fetch 2024 2025 --force" in r.stdout, \
            (why, r.stdout + r.stderr)
        assert not list(cache.glob("change_*")), (why, "nothing compared")

# no community cell fits a 2 km square: `wall` is null, no image, and the next plain run does not try again
with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, "PACK_OUT": tmp, "NODE_NAME": "t", "NODE_LAT": str(LATH), "NODE_LON": str(LONH),
           "EARTH_RADIUS_M": "2000", "PYTHONPATH": os.getcwd()}
    cache = Path(tmp) / "earth" / "t"; cache.mkdir(parents=True)
    _, _, b2 = window(LATH, LONH, radius=2000)
    for y in (2024, 2025):
        np.save(cache / f"{y}.npy", np.repeat(np.repeat(base, 400, 1), 400, 2) * (1 if y == 2024 else -1))
    win = {"crs": "EPSG:32750", "bounds": b2, "px": [400, 400], "clipped": False, "north_up": True,
           "node_rc": [200, 200], "object": "gs://x.tiff"}
    (cache / "meta.json").write_text(json.dumps({"lat": LATH, "lon": LONH, "radius_m": 2000,
                                                 "windows": {"2024": win, "2025": win}}))
    (cache / "change_2024_2025_wall.png").write_bytes(b"\x89PNG stale")
    r = subprocess.run([sys.executable, "packs/earth/change.py"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    st2 = json.loads((cache / "change_2024_2025.json").read_text())
    assert "wall" in st2 and st2["wall"] is None and st2["wall_cell"] == home, st2.get("wall")
    assert not (cache / "change_2024_2025_wall.png").exists(), "a stale image must not answer for a null crop"
    r = subprocess.run([sys.executable, "packs/earth/change.py"], env=env, capture_output=True, text=True)
    assert "already computed" in r.stdout, "a null `wall` is an answer, not a pair to redo on every run"
print("earth wall: changed pixels in whole community cells only, the same image wherever the house is in its cell")

print("all earth pack tests pass")
sys.exit(0)
