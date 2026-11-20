"""The node's own copy of the AlphaEarth Satellite Embedding layers for its square of the planet, and the
year-over-year arithmetic on top of them.

Google publishes the Satellite Embedding dataset as Cloud-Optimized GeoTIFFs in a public bucket: one file per
UTM zone per year, 8192x8192 pixels at 10 m, 64 signed-8-bit channels, 2017-2025. This pack range-reads the
window around the node, keeps it under out/earth/, and compares two years pixel by pixel. Nothing is sent
anywhere; the node holds its own square.

kind='model', scale='city'. A Google artifact, mirrored under CC BY 4.0. Never a `live` cell.

The de-quantisation is not a scale factor. Each raw value maps to the analysis value by
    (v / 127.5) ** 2 * sign(v)
and the 64-vector has Euclidean length 1 AFTER that mapping, not before. Cosine arithmetic on the raw
integers is wrong by a factor of about 321 and silently plausible. Measured on 20,000 pixels of the Bali
tile: de-quantised norms 1.000093 +/- 0.002, raw norms ~321.

This module holds the shared work; the four scripts beside it are the commands. It imports numpy and rasterio
lazily so that a node without them loads the pack, logs once and idles.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import math
import os
import re
import urllib.request
from pathlib import Path

log = logging.getLogger("planetai.pack.earth")

GCS = "https://storage.googleapis.com"
BUCKET = f"{GCS}/alphaearth_foundations"
ROOT = f"{BUCKET}/satellite_embedding/v1/annual"
INDEX = f"{ROOT}/aef_index.csv"
DATASET = "satellite_embedding/v1/annual (AlphaEarth Foundations)"
ATTRIBUTION = ("The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind. "
               "CC BY 4.0.")
YEARS = tuple(range(2017, 2026))            # what the bucket holds today; verify re-reads the listing
# The columns of aef_index.csv, in order. The file has a header row, but a range read starts mid-file, so the
# header travels here instead.
COLUMNS = ("WKT,crs,path,year,utm_zone,utm_west,utm_south,utm_east,utm_north,"
           "wgs84_west,wgs84_south,wgs84_east,wgs84_north")
_ZONE_IN_PATH = re.compile(r"/annual/(\d{4})/(\d+)([NS])/")
_state = {"warned": False}


# ---------------------------------------------------------------- where and what

def node() -> str:
    return os.getenv("NODE_NAME", "node")


def aoi() -> tuple[float, float, int]:
    """The node's point and the radius the pack describes around it. EARTH_RADIUS_M is a half-width: 5000 asks
    for a 10 km square."""
    return float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]), int(os.getenv("EARTH_RADIUS_M", "5000") or 5000)


# The cache is a square around one point, so changing NODE_LAT/NODE_LON or EARTH_RADIUS_M in .env makes every
# cached year describe somewhere else. The tolerance keeps a corrected decimal from costing a nine-year re-read:
# 1% of the radius, never under 25 m. (The place pack carries the same rule; packs do not import each other.)
MOVE_FRAC, MOVE_MIN_M = 0.01, 25.0


def metres(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Metres between two points, flat-earth approximation: exact enough well inside one degree."""
    dy = (lat_b - lat_a) * 111320.0
    dx = (lon_b - lon_a) * 111320.0 * math.cos(math.radians((lat_a + lat_b) / 2))
    return math.hypot(dx, dy)


def move_tolerance(radius_m: int) -> float:
    return max(radius_m * MOVE_FRAC, MOVE_MIN_M)


def drift(m: dict, lat: float, lon: float):
    """How far the node is from the point the cache was fetched around, or None when the cache records no point."""
    if m.get("lat") is None or m.get("lon") is None:
        return None
    return metres(float(m["lat"]), float(m["lon"]), lat, lon)


def describes(m: dict, lat: float, lon: float, radius_m: int) -> bool:
    """Whether a cache's meta.json says it holds *this* square: read around this point, within the move
    tolerance, at this radius. The same test `fetch` makes before it re-reads a square and `verify` makes
    before it trusts one. A meta.json from before v0.33.4 records no radius; that is not a resize."""
    d = drift(m, lat, lon)
    return d is not None and d <= move_tolerance(radius_m) and m.get("radius_m") in (None, radius_m)


def wanted_years() -> list[int]:
    """EARTH_YEARS blank means every year the dataset has."""
    raw = (os.getenv("EARTH_YEARS", "") or "").replace(" ", "")
    if not raw:
        return list(YEARS)
    return sorted({int(y) for y in raw.split(",") if y})


def cache() -> Path:
    """The directory holding this node's square.

    Named for the node because something had to name it, but the embeddings describe a *place*: the same
    10 km square is the same square whatever the operator calls the machine. So a directory whose meta.json
    says it holds this square answers for this node whatever its name, the node's own name preferred when
    more than one does. Node #1 was renamed `bayu-2` → `bayu-ungasan` and re-read 930 MB it already had on
    disk, then kept both copies. The tolerance is the one a move already uses, so a rename costs nothing and
    a real move still costs everything. Nothing is moved or deleted: the abandoned directory stays where it
    is, and `earth status` names it for a person to decide about.
    """
    root = Path(os.getenv("PACK_OUT", "/app/out")) / "earth"
    mine = root / node()
    if not root.is_dir() or not (os.getenv("NODE_LAT") and os.getenv("NODE_LON")):
        return mine
    lat, lon, radius = aoi()
    for p in sorted(root.glob("*/meta.json"), key=lambda q: (q.parent != mine, q.parent.name)):
        try:
            if describes(json.loads(p.read_text()), lat, lon, radius):
                return p.parent
        except (OSError, ValueError, TypeError):        # unreadable or not this pack's json; the next one may be
            continue
    return mine


def utm_zone(lat: float, lon: float) -> str:
    """The UTM zone the dataset files this point under. Zones are 6 degrees wide from -180."""
    z = min(60, max(1, int((lon + 180) // 6) + 1))
    return f"{z}{'N' if lat >= 0 else 'S'}"


# ---------------------------------------------------------------- the tile index

def _get(url: str, start: int | None = None, end: int | None = None, timeout: int = 120) -> bytes:
    headers = {} if start is None else {"Range": f"bytes={start}-{end}"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:                    # noqa: S310  (https, fixed host)
        return r.read()


def _size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:                         # noqa: S310
        return int(r.headers["Content-Length"])


def _zone_key(zone: str) -> tuple[int, int]:
    return (0 if zone.endswith("N") else 1, int(zone[:-1]))


def _zone_at(url: str, offset: int) -> tuple[int, int] | None:
    """The zone of whichever row straddles this byte offset. A row is about 3 kB (the WKT polygon is most of
    it), so 12 kB always contains at least one complete path."""
    chunk = _get(url, offset, offset + 12000).decode("utf-8", "replace")
    m = _ZONE_IN_PATH.search(chunk)
    return _zone_key(m.group(2) + m.group(3)) if m else None


def zone_block(zone: str, log_bytes: dict | None = None) -> str:
    """The rows of aef_index.csv for one UTM zone.

    The index is 798 MB and there is no GeoJSON form of it, so downloading it is not on. It is sorted by UTM
    zone (1N..60N, then 1S..60S) with the years interleaved inside each zone, so a binary search over byte
    offsets finds the zone's block and one range read fetches it. Measured for 50S: 26 probes, 189 kB, then a
    single 8.8 MB read. The bounds are deliberately loose; the caller filters by zone.
    """
    size = _size(INDEX)
    target = _zone_key(zone)
    lo, hi = 0, size
    probes = 0
    while hi - lo > 200000:
        mid = (lo + hi) // 2
        k = _zone_at(INDEX, mid); probes += 1
        if k is None or k < target:
            lo = mid
        else:
            hi = mid
    low = lo
    lo, hi = low, size
    while hi - lo > 200000:
        mid = (lo + hi) // 2
        k = _zone_at(INDEX, mid); probes += 1
        if k is None or k <= target:
            lo = mid
        else:
            hi = mid
    body = _get(INDEX, low, hi)
    if log_bytes is not None:
        log_bytes["index_bytes"] = probes * 12001 + len(body)
        log_bytes["index_probes"] = probes
    text = body.decode("utf-8", "replace")
    return text[text.index("\n") + 1: text.rindex("\n")]                       # drop the two partial rows


def resolve(lat: float, lon: float, log_bytes: dict | None = None) -> dict[str, dict]:
    """{year: row} for the tiles covering this point, one per year. The dataset's own words: it is not
    possible to tell from a file name what part of the world it covers."""
    import csv
    import io
    zone = utm_zone(lat, lon)
    rows = csv.DictReader(io.StringIO(COLUMNS + "\n" + zone_block(zone, log_bytes)))
    out = {}
    for r in rows:
        if r["utm_zone"] != zone:
            continue
        if not (float(r["wgs84_west"]) <= lon <= float(r["wgs84_east"])
                and float(r["wgs84_south"]) <= lat <= float(r["wgs84_north"])):
            continue
        r.pop("WKT", None)
        out[r["year"]] = r
    if not out:
        raise RuntimeError(f"no tile in the index covers {lat},{lon} (zone {zone})")
    return out


# ---------------------------------------------------------------- the arithmetic

def dequantize(raw):
    """Raw signed bytes to the analysis values the embedding norms are defined on. README of the bucket:
    divide by 127.5, square, multiply by the sign."""
    import numpy as np
    f = raw.astype(np.float32) / 127.5
    return (f * f) * np.sign(f)


def cosine_distance(a, b, rows: int = 100):
    """1 - cosine similarity, per pixel, between two (64, H, W) raw arrays.

    The vectors are already unit length once de-quantised, so the dot product is the cosine and no
    renormalisation is needed. Done in row bands because a de-quantised year is 256 MB of float32 and a node
    may have 2 GB of memory; a band of 100 rows is 26 MB. Returns (distance, masked) as (H, W) arrays;
    -128 in any channel means no data and the README says it is then in every channel.
    """
    import numpy as np
    h, w = a.shape[1], a.shape[2]
    dist = np.empty((h, w), dtype=np.float32)
    masked = np.empty((h, w), dtype=bool)
    for i in range(0, h, rows):
        x = dequantize(np.asarray(a[:, i:i + rows, :]))
        y = dequantize(np.asarray(b[:, i:i + rows, :]))
        dist[i:i + rows] = 1.0 - np.clip((x * y).sum(0), -1.0, 1.0)
        masked[i:i + rows] = (np.asarray(a[0, i:i + rows, :]) == -128) | (np.asarray(b[0, i:i + rows, :]) == -128)
    dist[masked] = np.nan
    return dist, masked

def require(*mods: str) -> None:
    """Stop with the command that fixes it, before doing any work.

    `planetai update` ships this pack's code but not its libraries: `app/requirements-packs.txt` is written by
    `planetai packs install`, and it is gitignored, so a node that updates into a release carrying a new code
    pack has the scripts and not the wheels. Without this, `fetch` downloaded 9 MB of tile index and then
    printed `ModuleNotFoundError: No module named 'rasterio'` once per year, nine times, naming no remedy.
    """
    missing = [m for m in mods if importlib.util.find_spec(m) is None]
    if missing:
        raise SystemExit(
            f"earth: the app image has no {', '.join(missing)}.\n"
            f"  This pack declares {'it' if len(missing) == 1 else 'them'} in packs/earth/pack.yaml, but "
            f"`planetai update` does not install a\n"
            f"  pack's libraries — that is what `planetai packs install` is for.\n"
            f"\n"
            f"      planetai packs install     # rebuilds the image, a few minutes\n"
            f"      planetai restart\n"
            f"\n"
            f"  Then run this again. `planetai run earth verify` checks the whole chain.")


# ---------------------------------------------------------------- reading a COG over HTTPS

# GDAL's defaults are wrong for this file in two ways that cost minutes. Its 16 kB range chunks turn one
# 230 kB internal block into fourteen requests, and its block cache is smaller than the 256 MB a 64-band
# read touches, so blocks are fetched, evicted and fetched again. Measured on the Bali tile: 9+ minutes
# for one AOI-year with the defaults and one ds.read(), 149 s with these and one band at a time.
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",     # no directory listing per open
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tiff",
    "CPL_VSIL_CURL_CHUNK_SIZE": "262144",            # about one internal block
    "CPL_VSIL_CURL_CACHE_SIZE": "268435456",
    "GDAL_CACHEMAX": "64",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "2",
}


def open_cog(url: str):
    """rasterio.open on the bucket's HTTPS URL, with the settings that make it finish. No credentials: the
    bucket answers anonymous range requests."""
    for k, v in GDAL_ENV.items():
        os.environ.setdefault(k, v)
    import rasterio
    return rasterio.open("/vsicurl/" + url.replace("gs://", GCS + "/"))


def window_px(row: int, col: int, radius_m: int, height: int, width: int):
    """The square of side 2*radius centred on one pixel, clipped to the raster. Pure arithmetic, no raster and
    no projection, so the offline tests can check it. Returns (r0, c0, r1, c1, clipped), end-exclusive."""
    half = radius_m // 10                                                       # the dataset is 10 m
    r0, c0, r1, c1 = row - half, col - half, row + half, col + half
    kr0, kc0, kr1, kc1 = max(0, r0), max(0, c0), min(height, r1), min(width, c1)
    if kr1 <= kr0 or kc1 <= kc0:
        raise RuntimeError("the node's square falls outside the tile the index gave")
    return kr0, kc0, kr1, kc1, (kr0, kc0, kr1, kc1) != (r0, c0, r1, c1)


def window_for(ds, lat: float, lon: float, radius_m: int):
    """The pixel window of the square of side 2*radius centred on the point, clipped to the tile. Returns
    (window, bounds, clipped, node_rc) where bounds is {north, south, east, west} in the tile's UTM metres and
    node_rc is the node's (row, col) inside the window, in the file's own row order."""
    from rasterio.warp import transform as warp_transform
    from rasterio.windows import Window
    xs, ys = warp_transform("EPSG:4326", ds.crs, [lon], [lat])
    row, col = ds.index(xs[0], ys[0])
    kr0, kc0, kr1, kc1, clipped = window_px(row, col, radius_m, ds.height, ds.width)
    w = Window(kc0, kr0, kc1 - kc0, kr1 - kr0)
    left, bottom, right, top = ds.window_bounds(w)
    bounds = {"west": min(left, right), "east": max(left, right),
              "south": min(bottom, top), "north": max(bottom, top)}
    return w, bounds, clipped, (row - kr0, col - kc0)


def read_window(ds, w):
    """One band at a time into one array. See GDAL_ENV for why not ds.read(window=w)."""
    import numpy as np
    out = np.empty((ds.count, int(w.height), int(w.width)), dtype="int8")
    for i in range(1, ds.count + 1):
        out[i - 1] = ds.read(i, window=w)
    return out


# ---------------------------------------------------------------- drawing, without a library

# The ramp's top. Fixed rather than per-image so two years of the same place, or two places, can be put side
# by side and mean the same thing. 0.30 is above the 99.9th percentile of every consecutive-year pair
# measured at node #1, so a normal year uses the lower half of the ramp and a cleared hillside saturates.
RAMP_CEILING = 0.30
NODATA_IX, NODE_IX, RULE_IX = 0, 253, 254


def _palette() -> bytes:
    """256 RGB entries: black for no data, a grey ramp for the distance, one orange for the node, white for
    the scale bar."""
    out = bytearray(b"\x00\x00\x00")                       # 0: no data
    for i in range(1, 253):                                  # 1..252: grey 30..255
        g = 30 + round((i - 1) * (255 - 30) / 251)
        out += bytes((g, g, g))
    out += b"\xe8\x64\x1e"                                  # 253: the node
    out += b"\xff\xff\xff"                                  # 254: the scale bar
    out += b"\x00\x00\x00"                                  # 255: unused
    return bytes(out)


def ramp_indices(dist, masked):
    """(H, W) float distances to (H, W) palette indices."""
    import numpy as np
    x = np.clip(np.nan_to_num(dist, nan=0.0) / RAMP_CEILING, 0.0, 1.0)
    ix = (1 + np.rint(x * 251)).astype(np.uint8)
    ix[masked] = NODATA_IX
    return ix


def write_png(path, ix, texts: dict | None = None, palette: bytes | None = None, trns: bytes | None = None) -> int:
    """png_bytes() written to `path`. Returns the file size."""
    out = png_bytes(ix, texts, palette, trns)
    path.write_bytes(out)
    return len(out)


def png_bytes(ix, texts: dict | None = None, palette: bytes | None = None, trns: bytes | None = None) -> bytes:
    """An indexed-colour PNG from a (H, W) uint8 array of palette indices. zlib and struct are enough; the
    node has no image library and this pack is not going to add one.

    The attribution travels inside the file as a tEXt chunk, so a PNG that leaves the node still carries it.
    `palette` replaces the grey ramp, and `trns` is the alpha of the first palette entries (b"\x00": entry 0
    is transparent).
    """
    import struct
    import zlib
    h, w = ix.shape
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = bytearray()
    for r in range(h):
        raw.append(0)                                        # filter: none
        raw += ix[r].tobytes()
    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0))
    out += chunk(b"PLTE", palette or _palette())
    if trns is not None:
        out += chunk(b"tRNS", trns)
    for k, v in (texts or {}).items():
        out += chunk(b"tEXt", k.encode("latin-1", "replace") + b"\x00" + v.encode("latin-1", "replace"))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    out += chunk(b"IEND", b"")
    return out


# ---------------------------------------------------------------- the image the Wall may show

# The Wall is a screen with no token, and may show nothing finer than the house's res-8 cell (app/wall.py). The
# square this pack reads is centred on the house's pixel, so its edges, its ring and its hectares all give the house
# away. The Wall's image is cut from it by the cell instead: the community's res-7 cells (the disk of one around the
# res-8 cell's parent) that lie wholly inside a square centred on the res-8 cell's centre, whose half-width is the
# radius less the farthest the house can be from that centre. That square is inside the one read wherever the house
# stands in its cell, and the pixels are the dataset's own 10 m grid, so the image, its bounds and its hectares are
# the same for every point in the cell. Changed pixels only, in one colour; everything else is transparent.
WALL_PALETTE = b"\x00\x00\x00\xff\xbe\x78"          # 0: transparent (with trns=b"\x00"), 1: changed, #FFBE78
SNAP_M = 10                                             # the square read is snapped to the house's pixel


def projection(epsg: int):
    """(lat, lon) to metres in a UTM EPSG code, by the surface-heat pack's Snyder series: no pyproj on a node.
    A pure function borrowed from a sibling pack, as app/wall.py does."""
    spec = importlib.util.spec_from_file_location(
        "planetai_pack_surface_heat_for_earth", Path(__file__).resolve().parent.parent / "surface-heat" / "adapter.py")
    sh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sh)  # type: ignore[union-attr]
    return sh.projection(epsg)


def allowed_raster(bounds: dict, crs: str, shape: tuple[int, int], home: str, radius_m: float, clipped: bool = False):
    """(H, W) bool over the square read (north up, `bounds` in `crs`): True on the pixels whose centres fall in the
    community's res-7 cells that lie wholly inside the safe square round `home`'s centre, and inside the raster.

    All False when a tile edge clipped the window: where the edge cuts the square depends on where in the cell the
    house is, so which cells survive (or whether any does) would say where. All False too when the window was not
    clipped and still does not hold the safe square: it was read around a point that is not in this cell (a move
    inside fetch's tolerance), and which edge cells survive would say the same."""
    import h3
    import numpy as np
    fwd = projection(int(str(crs).rsplit(":", 1)[-1]))
    c = h3.cell_to_latlng(home)
    circum = max(h3.great_circle_distance(c, v, unit="m") for v in h3.cell_to_boundary(home))
    cx, cy = fwd(*c)
    half = int(radius_m) // 10 * 10 - circum - SNAP_M     # the half-width window_px really reads
    h, w = shape
    pw, ph = (bounds["east"] - bounds["west"]) / w, (bounds["north"] - bounds["south"]) / h
    west, east = max(cx - half, bounds["west"]), min(cx + half, bounds["east"])
    south, north = max(cy - half, bounds["south"]), min(cy + half, bounds["north"])
    if clipped or (west, east, south, north) != (cx - half, cx + half, cy - half, cy + half):
        return np.zeros(shape, bool)
    X = (bounds["west"] + (np.arange(w) + 0.5) * pw)[None, :]
    Y = (bounds["north"] - (np.arange(h) + 0.5) * ph)[:, None]
    out = np.zeros(shape, bool)
    for cell in h3.grid_disk(h3.cell_to_parent(home, 7), 1):
        ring = [fwd(*v) for v in h3.cell_to_boundary(cell)]
        if not all(west <= x <= east and south <= y <= north for x, y in ring):
            continue
        inside = np.zeros(shape, bool)                  # even-odd rule on the pixel centres
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if y1 == y2:
                continue
            inside ^= ((y1 > Y) != (y2 > Y)) & (X < x1 + (Y - y1) * (x2 - x1) / (y2 - y1))
        out |= inside
    return out


def wall_mask(dist, masked, threshold: float, allowed):
    """(H, W) uint8: 1 where the land changed (over `threshold`, not masked) inside `allowed`, else 0."""
    return ((dist > threshold) & ~masked & allowed).astype("uint8")


def wall_image(dist, masked, bounds: dict, crs: str, home: str, radius_m: float, threshold: float,
               clipped: bool = False):
    """The Wall's image and its crop: (ix, {"bounds", "ha"}), the image cut to the allowed cells' box, bounds in
    `crs`, ha the changed pixels inside the cells. None when no community cell fits the square, when a tile edge
    clipped the read, or when an unclipped window does not hold it (allowed_raster)."""
    import numpy as np
    allowed = allowed_raster(bounds, crs, dist.shape, home, radius_m, clipped)
    if not allowed.any():
        return None
    rows, cols = np.flatnonzero(allowed.any(1)), np.flatnonzero(allowed.any(0))
    r0, r1, c0, c1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
    h, w = dist.shape
    pw, ph = (bounds["east"] - bounds["west"]) / w, (bounds["north"] - bounds["south"]) / h
    ix = np.ascontiguousarray(wall_mask(dist, masked, threshold, allowed)[r0:r1, c0:c1])
    box = {"west": bounds["west"] + c0 * pw, "east": bounds["west"] + c1 * pw,
           "north": bounds["north"] - r0 * ph, "south": bounds["north"] - r1 * ph}
    return ix, {"bounds": box, "ha": round(int(ix.sum()) * pw * ph / 10000.0, 1)}


# A 3x5 digit, so a frame that leaves the node still says which year it is. Ten glyphs is cheaper than a
# font file and the pack has no image library to load one with.
DIGITS = {"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111",
          "4": "101101111001001", "5": "111100111001111", "6": "111100111101111", "7": "111001001001001",
          "8": "111101111101111", "9": "111101111001111"}


def draw_year(ix, year: int, scale: int = 4) -> None:
    """Burn the year into the bottom right, in place. Small, plain, and out of the way."""
    h, w = ix.shape
    gw = (3 * scale + scale) * len(str(year))
    x0, y0 = w - gw - 14, h - 5 * scale - 14
    if x0 < 0 or y0 < 0:
        return
    for i, ch in enumerate(str(year)):
        g = DIGITS.get(ch)
        if not g:
            continue
        for r in range(5):
            for c in range(3):
                if g[r * 3 + c] == "1":
                    y, x = y0 + r * scale, x0 + i * 4 * scale + c * scale
                    ix[y:y + scale, x:x + scale] = RULE_IX


def draw_marks(ix, node_rc: tuple[int, int] | None = None) -> None:
    """A 1 km scale bar bottom left, and optionally a ring where the node is. In place."""
    h, w = ix.shape
    bar = 100                                                # 100 px at 10 m is one kilometre
    y, x0 = h - 14, 14
    if w > x0 + bar + 4 and h > 20:
        ix[y:y + 3, x0:x0 + bar] = RULE_IX
        ix[y - 4:y + 7, x0] = RULE_IX
        ix[y - 4:y + 7, x0 + bar - 1] = RULE_IX
    if node_rc:
        r, c = node_rc
        for dr in range(-6, 7):
            for dc in range(-6, 7):
                d = (dr * dr + dc * dc) ** 0.5
                if 4.0 <= d <= 6.0 and 0 <= r + dr < h and 0 <= c + dc < w:
                    ix[r + dr, c + dc] = NODE_IX


# ---------------------------------------------------------------- one picture of the place, per year

# The frames are a rendering of the embedding, not a photograph: this pack never downloads imagery. The first
# component of a PCA over the 64 dimensions carries about three fifths of them and, at least in Bali, looks
# like a panchromatic satellite image — dark water, bright land, roads and plots legible.
#
# The projection is fitted once, over every year cached at the time, and then kept in meta.json. That matters
# for a record that grows: refitting when 2026 arrives would silently change every earlier frame, and a
# sequence whose colours move is not a sequence. A new year is projected through the existing basis.
VIEW_SAMPLE = 40000


def fit_view(years: list[int]) -> dict:
    """The shared projection: one direction through the 64 dimensions, and the 256 breakpoints that map it to
    grey. Fitted on a sample pooled from every year given, so no single year sets the exposure."""
    import numpy as np
    rng = np.random.default_rng(0)
    cols = []
    for y in years:
        v = dequantize(np.asarray(np.load(year_file(y), mmap_mode="r")).reshape(64, -1))
        cols.append(v[:, rng.choice(v.shape[1], min(VIEW_SAMPLE, v.shape[1]), replace=False)])
    x = np.concatenate(cols, axis=1)
    mu = x.mean(1, keepdims=True)
    u, _, _ = np.linalg.svd(x - mu, full_matrices=False)
    w = u[:, 0]
    proj = (w[None, :] @ (x - mu))[0]
    if float(((proj - proj.mean()) ** 3).mean()) > 0:      # a fixed sign, so two runs agree
        w, proj = -w, -proj
    return {"mean": [float(v) for v in mu[:, 0]], "axis": [float(v) for v in w],
            "breaks": [float(v) for v in np.percentile(proj, np.linspace(0, 100, 256))],
            "fitted_on": sorted(years)}


def render_year(year: int, view: dict, node_rc=None, window=None):
    """One year as palette indices: grey where there is data, the ramp shared with every other frame. `window`,
    (r0, c0, r1, c1), draws only that part of the square."""
    import numpy as np
    raw = np.load(year_file(year), mmap_mode="r")
    if window:
        raw = raw[:, window[0]:window[2], window[1]:window[3]]
    raw = np.asarray(raw)
    masked = raw[0] == -128
    v = dequantize(raw.reshape(64, -1))
    mu = np.array(view["mean"], dtype=np.float32)[:, None]
    w = np.array(view["axis"], dtype=np.float32)
    g = np.searchsorted(np.array(view["breaks"]), (w[None, :] @ (v - mu))[0])
    ix = (1 + np.clip(g, 0, 251)).astype(np.uint8).reshape(raw.shape[1], raw.shape[2])
    ix[masked] = NODATA_IX
    draw_marks(ix, node_rc)
    draw_year(ix, year)
    return ix


def year_png(year: int):
    return cache() / f"year_{year}.png"


# ---------------------------------------------------------------- the cache on disk

def year_file(year: int) -> Path:
    return cache() / f"{year}.npy"


def cached_years() -> list[int]:
    return sorted(int(p.stem) for p in cache().glob("*.npy") if p.stem.isdigit())


def meta() -> dict:
    p = cache() / "meta.json"
    return json.loads(p.read_text()) if p.is_file() else {}


def write_meta(d: dict) -> None:
    cache().mkdir(parents=True, exist_ok=True)
    (cache() / "meta.json").write_text(json.dumps(d, indent=1, sort_keys=True))


def change_file(a: int, b: int, suffix: str) -> Path:
    return cache() / f"change_{a}_{b}.{suffix}"


def changes() -> list[dict]:
    """Every computed comparison, newest pair last."""
    out = []
    for p in sorted(cache().glob("change_*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except Exception as e:                                                  # noqa: BLE001
            log.warning("earth: %s is not readable json (%s)", p.name, e)
    return sorted(out, key=lambda c: (c.get("year_b", 0), c.get("year_a", 0)))


def change_stats(dist, masked, threshold: float) -> dict | None:
    """The numbers a comparison publishes, over whatever square `dist` covers. None when every pixel is masked."""
    import numpy as np
    good = dist[~masked]
    if not good.size:
        return None
    over = float((good > threshold).mean())
    return {"mean": round(float(good.mean()), 5), "median": round(float(np.median(good)), 5),
            "p95": round(float(np.percentile(good, 95)), 5), "max": round(float(good.max()), 5),
            "threshold": threshold, "share_over_threshold": round(over, 5),
            "hectares_over_threshold": round(over * good.size * 100.0 / 10000.0, 1),      # a pixel is 10 m x 10 m
            "pixels": int(good.size), "pixels_masked": int(masked.sum()),
            "px": [int(dist.shape[1]), int(dist.shape[0])]}


# ---------------------------------------------------------------- the square a stranger sees
# The cached square is centred on the node's own point. Its centre, the ring drawn there, its size where a tile edge
# clips it and every number computed over it each place the house to 10 m, and AlphaEarth is public, so whoever holds
# the numbers can search the cell for the one square they fit. R25 (app/main.py::_published_position) lets nothing
# finer than the node's res-8 cell leave for a reader the node does not know. That reader gets the public square:
# centred on the cell's centre, PUBLIC_MARGIN_M in from each side of the cached one, no ring, with its own bounds and
# its own numbers. Two houses in one cell are handed the same square, byte for byte (tests/test_earth_frames.py).
PUBLIC_MARGIN_M = 1000      # a res-8 cell's centre is at most ~530 m from a point inside it, plus the move tolerance


def public_window(rc, shape, lat: float, lon: float, radius_m: int):
    """(r0, c0, r1, c1), end-exclusive, of the public square inside a north-up window of `shape` (rows, cols) whose
    node pixel is `rc`, read around (lat, lon). None when the cached square is too small to cut one from.

    The offset to the cell's centre is in flat-earth metres, so it ignores the UTM grid's convergence: a few metres
    inside the margin, under one pixel at node #1. A tile edge clips the public square where it clipped the cached
    one, and that edge is the tile's, not the house's."""
    import h3
    clat, clon = h3.cell_to_latlng(h3.latlng_to_cell(float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]), 8))
    dr = round((lat - clat) * 111320.0 / 10)                                    # north-up: rows run south
    dc = round((clon - lon) * 111320.0 * math.cos(math.radians(lat)) / 10)
    half = (radius_m - PUBLIC_MARGIN_M) // 10
    if half <= 0 or max(abs(dr), abs(dc)) * 10 > PUBLIC_MARGIN_M:
        return None
    r, c = int(rc[0]) + dr, int(rc[1]) + dc
    return max(0, r - half), max(0, c - half), min(shape[0], r + half), min(shape[1], c + half)


def window_bounds(bounds: dict, w) -> dict:
    """The UTM bounds of window `w` inside a north-up square whose bounds are `bounds`, at 10 m."""
    return {"west": bounds["west"] + w[1] * 10, "east": bounds["west"] + w[3] * 10,
            "north": bounds["north"] - w[0] * 10, "south": bounds["north"] - w[2] * 10}


def public_dir() -> Path:
    """Where the public cuts are kept: one directory per res-8 cell, so a node that moves cell cuts again."""
    import h3
    return cache() / "public" / h3.latlng_to_cell(float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]), 8)


def _kept(src: Path, *outs: Path) -> bool:
    """Whether every cut in `outs` is at least as new as the file it was cut from."""
    try:
        return all(o.stat().st_mtime_ns >= src.stat().st_mtime_ns for o in outs)
    except OSError:
        return False


def _keep(path: Path, data: bytes) -> None:
    """Write a cut whole or not at all. An out/ that cannot be written still answers; it cuts again next time."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError:
        pass


def public_change(c: dict):
    """(numbers, png bytes) of one comparison over the public square, or None when it cannot be cut. Kept on disk
    beside the comparison until `earth change` rewrites it: a cut takes about 6 s on node #1."""
    src = change_file(c.get("year_a"), c.get("year_b"), "json")
    d = public_dir()
    j, p = d / src.name, d / f"{src.stem}.png"
    if _kept(src, p, j):
        return json.loads(j.read_text()), p.read_bytes()
    try:
        cut = _cut_change(json.loads(src.read_text()))
    except OSError:
        return None
    if cut:
        _keep(p, cut[1])
        _keep(j, json.dumps(cut[0]).encode())
    return cut


def _cut_change(c: dict):
    import numpy as np
    try:
        w = public_window(c["node_rc"], (c["px"][1], c["px"][0]), float(c["lat"]), float(c["lon"]), int(c["radius_m"]))
        a, b, threshold = int(c["year_a"]), int(c["year_b"]), float(c["threshold"])
    except (KeyError, IndexError, TypeError, ValueError):                       # a comparison from before node_rc
        return None
    if not w:
        return None
    X, Y = (np.load(year_file(y), mmap_mode="r")[:, w[0]:w[2], w[1]:w[3]] for y in (a, b))
    dist, masked = cosine_distance(X, Y)
    numbers = change_stats(dist, masked, threshold)
    if not numbers:
        return None
    keep = ("node", "year_a", "year_b", "metres_per_pixel", "crs", "tiles", "dataset", "attribution", "computed_at", "png")
    out = {**{k: c[k] for k in keep if k in c}, **numbers, "radius_m": int(c["radius_m"]) - PUBLIC_MARGIN_M,
           "bounds": window_bounds(c["bounds"], w) if c.get("bounds") else None, "position": "cell"}
    ix = ramp_indices(dist, masked)
    draw_marks(ix)
    return out, png_bytes(ix, {
        "Title": f"Land change {a}-{b}, {node()}, around its res-8 cell",
        "Description": f"1 - cosine similarity of annual AlphaEarth embeddings, {a} to {b}. North up, 10 m per "
                       f"pixel, centred on the node's res-8 cell, grey ramp 0 to {RAMP_CEILING}. Black is no data.",
        "Copyright": ATTRIBUTION})


def public_year(year: int) -> bytes | None:
    """One year's frame over the public square, or None. Kept on disk until `earth frames` redraws the full frame,
    which it does whenever the shared view changes: a cut takes about 15 s on node #1."""
    src = year_png(year)
    out = public_dir() / src.name
    if _kept(src, out):
        return out.read_bytes()
    if not src.is_file():
        return None
    m = meta()
    win = (m.get("windows") or {}).get(str(year)) or {}
    try:
        w = public_window(win["node_rc"], (win["px"][1], win["px"][0]), float(m["lat"]), float(m["lon"]),
                          int(m["radius_m"]))
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    if not (w and m.get("view")):
        return None
    cut = png_bytes(render_year(year, m["view"], None, w), {
        "Title": f"{year}, {node()}, around its res-8 cell",
        "Description": f"AlphaEarth embedding for {year}, first principal component as grey. North up, 10 m per "
                       f"pixel, centred on the node's res-8 cell. Not a photograph.",
        "Copyright": ATTRIBUTION})
    _keep(out, cut)
    return cut


def warm() -> None:
    """Cut every comparison and frame not cut yet, so a screen without the token is not the one that waits."""
    try:
        for c in changes():
            public_change(c)
        for y in cached_years():
            public_year(y)
    except Exception as e:                                                      # noqa: BLE001
        log.warning("earth: could not cut the public square (%s: %s)", type(e).__name__, str(e)[:120])


def wall_cell() -> str | None:
    """The res-8 cell the Wall's crop is cut round: NODE_LAT/NODE_LON's, None before the node has a place."""
    if not (os.getenv("NODE_LAT") and os.getenv("NODE_LON")):
        return None
    import h3
    lat, lon, _ = aoi()
    return h3.latlng_to_cell(lat, lon, 8)


def latest_pair() -> tuple[int, int] | None:
    """The two most recent consecutive cached years. A gap is not a year-over-year comparison."""
    ys = cached_years()
    pairs = [(a, b) for a, b in zip(ys, ys[1:]) if b - a == 1]
    return pairs[-1] if pairs else None


# ---------------------------------------------------------------- the node's contract

def fetch(hc):                                                                  # noqa: ARG001  (no HTTP here; the cache is local)
    """Contract: (sensors, readings). Reads what `planetai run earth change` already computed. Nothing is
    downloaded on a poll: this pack fetches on command, not on a schedule, because one year is 103 MB."""
    cs = changes()
    if not cs:
        if not _state["warned"]:
            log.info("earth: nothing cached yet — planetai run earth fetch, then planetai run earth change")
            _state["warned"] = True
        return [], []
    # The public square's cuts, in the background: 6 s a comparison and 15 s a frame on node #1, once each.
    if not (_state.get("warm") and _state["warm"].is_alive()):
        import threading
        _state["warm"] = threading.Thread(target=warm, name="earth-public-cut", daemon=True)
        _state["warm"].start()
    from datetime import datetime, timezone
    lat, lon, radius = aoi()
    ys = cached_years()
    values: dict[str, float] = {"years_cached": float(len(ys))}
    yoy = [c for c in cs if c["year_b"] - c["year_a"] == 1]
    if yoy:
        values["land_change_yoy"] = yoy[-1]["mean"]
    since = [c for c in cs if c["year_a"] == 2017]
    if since:
        values["land_change_since_2017"] = since[-1]["mean"]
    latest = (yoy or cs)[-1]
    ts = datetime(latest["year_b"], 7, 1, tzinfo=timezone.utc)                  # mid-year stamp for an annual quantity
    sensor = {"sensor_id": "earth-point", "source": "earth",
              "name": f"Land within {radius // 1000} km (AlphaEarth, {latest['year_a']}→{latest['year_b']})",
              "lat": lat, "lon": lon, "indoor": False, "local": False,
              "kind": "model", "scale": "city", "cadence": "P1Y",
              "meta": {"dataset": DATASET, "radius_m": radius, "years": ys,
                       "tiles": latest.get("tiles", []), "attribution": ATTRIBUTION}}
    readings = [(ts, "earth-point", m, v) for m, v in values.items()]
    log.info("earth: %d metrics from %d cached years", len(readings), len(ys))
    return [sensor], readings
