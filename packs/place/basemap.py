"""Keep a detailed map of this place on the node's own disk.   planetai run place basemap [--only vector|drone] [--dry-run]

Two parts, both fetched once and then served by the node itself at GET /ground/*, so a map that draws them asks
nobody anything:

  vector   OpenStreetMap as vector tiles, cut out of Protomaps' daily planet build (ODbL): land, water, land use,
           roads with their names, buildings, places, points of interest. Zoom 0-15 around the node in three rings
           (wide for context, close for detail); a map overzooms vector tiles crisply to street level. Plus the
           label fonts (Noto Sans, OFL) for the Latin ranges, so names draw with no font server.
  drone    OpenAerialMap mosaics (CC BY 4.0, flown by named providers) that cross the node's close ring, at up to
           GROUND_DRONE_MAXZ. Centimetre imagery where somebody flew, nothing where nobody did.

The 10 m satellite base is the earth-engine pack's: planetai run earth-engine basemap.

WHAT IT REVEALS, ONCE. Range requests to build.protomaps.com name the tiles of the squares fetched, so that host
learns roughly where this node is: a square GROUND_RADIUS_KM*2 across. OpenAerialMap's API and tile server learn
the drone ring the same way. After the fetch nothing is sent: every tile is read from out/ground/.

Standard library only (urllib, gzip, sqlite3), so it runs on any node. Writes out/ground/{vector,drone}.mbtiles,
out/ground/glyphs/ and out/ground/meta.json, each replaced whole only when its fetch finishes.
"""
import concurrent.futures as cf
import gzip
import json
import math
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

LAT, LON = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
OUT = Path(os.getenv("PACK_OUT", "out")) / "ground"
R_KM = float(os.getenv("GROUND_RADIUS_KM", "12"))
DRONE_KM = float(os.getenv("GROUND_DRONE_RADIUS_KM", "4"))
DRONE_MAXZ = int(os.getenv("GROUND_DRONE_MAXZ", "18"))
UA = {"User-Agent": "planetai-node (+https://planetai.fab.city)"}
# Three rings: the wide one for the island and its neighbours, the middle for the district, the close one for streets.
VECTOR_RINGS = [(range(0, 9), 300.0), (range(9, 12), 60.0), (range(12, 16), R_KM)]
FONTS = ["Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic"]
GLYPH_RANGES = ["0-255", "256-511", "7680-7935", "8192-8447"]
GLYPHS_URL = "https://protomaps.github.io/basemaps-assets/fonts/{font}/{range}.pbf"


def get(url, headers=None, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------- tiles in a square round the node
def tiles_around(lat, lon, km, z):
    """Every (x, y) tile at zoom z that touches the square of half-width `km` round (lat, lon). Web Mercator."""
    dlat, dlon = km / 110.574, km / (111.320 * math.cos(math.radians(lat)))
    n = 2 ** z

    def xy(la, lo):
        r = math.radians(max(-85.05, min(85.05, la)))
        return (int((lo + 180) / 360 * n), int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n))
    x0, y0 = xy(lat + dlat, lon - dlon)
    x1, y1 = xy(lat - dlat, lon + dlon)
    return [(x % n, y) for x in range(x0, x1 + 1) for y in range(max(0, y0), min(n - 1, y1) + 1)]


# ---------------------------------------------------------------- PMTiles v3, read over HTTP range requests
def zxy_to_id(z, x, y):
    """The PMTiles tile id: tiles of every lower zoom, then the Hilbert index of (x, y). pmtiles' own algorithm."""
    acc = ((1 << (2 * z)) - 1) // 3
    s, d = (1 << z) >> 1, 0
    while s > 0:
        rx, ry = int(x & s > 0), int(y & s > 0)
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        s >>= 1
    return acc + d


def _varint(b, i):
    v = shift = 0
    while True:
        c = b[i]; i += 1
        v |= (c & 0x7F) << shift
        if c < 0x80:
            return v, i
        shift += 7


def parse_dir(raw):
    n, i = _varint(raw, 0)
    ids, runs, lens, offs = [], [], [], []
    last = 0
    for _ in range(n):
        d, i = _varint(raw, i); last += d; ids.append(last)
    for _ in range(n):
        v, i = _varint(raw, i); runs.append(v)
    for _ in range(n):
        v, i = _varint(raw, i); lens.append(v)
    for k in range(n):
        v, i = _varint(raw, i)
        offs.append(offs[k - 1] + lens[k - 1] if v == 0 and k > 0 else v - 1)
    return list(zip(ids, offs, lens, runs))


class PMTiles:
    def __init__(self, url):
        self.url, self.dirs = url, {}
        h = self.range(0, 127)
        if h[:7] != b"PMTiles" or h[7] != 3:
            raise RuntimeError(f"{url} is not a PMTiles v3 archive")
        u = lambda o: int.from_bytes(h[o:o + 8], "little")  # noqa: E731
        self.root = (u(8), u(16))
        self.leaf0, self.data0 = u(40), u(56)
        self.icomp, self.tcomp = h[97], h[98]
        self.maxz = h[101]

    def range(self, off, n):
        return get(self.url, {"Range": f"bytes={off}-{off + n - 1}"})

    def directory(self, off, n):
        if (off, n) not in self.dirs:
            raw = self.range(off, n)
            self.dirs[(off, n)] = parse_dir(gzip.decompress(raw) if self.icomp == 2 else raw)
        return self.dirs[(off, n)]

    def locate(self, tid):
        """(absolute offset, length) of tile `tid`, or None when the planet has no tile there (open sea, often)."""
        off, n = self.root
        for _ in range(4):                                   # the spec allows at most three levels of leaves
            ents = self.directory(off, n)
            lo, hi = 0, len(ents) - 1
            hit = None
            while lo <= hi:
                mid = (lo + hi) // 2
                if ents[mid][0] <= tid:
                    hit, lo = ents[mid], mid + 1
                else:
                    hi = mid - 1
            if hit is None:
                return None
            eid, eoff, elen, run = hit
            if run == 0:
                off, n = self.leaf0 + eoff, elen
                continue
            return (self.data0 + eoff, elen) if tid < eid + run else None
        return None


def fetch_spans(pm, want):
    """Read many tiles in few requests: sort by offset, merge spans less than 256 KB apart, cap each at 8 MB."""
    spans = sorted((loc[0], loc[1], key) for key, loc in want.items())
    groups, cur = [], []
    for s in spans:
        if cur and (s[0] - (cur[-1][0] + cur[-1][1]) > 256_000 or s[0] + s[1] - cur[0][0] > 8_000_000):
            groups.append(cur); cur = []
        cur.append(s)
    if cur:
        groups.append(cur)
    out = {}

    def one(g):
        start = g[0][0]
        blob = pm.range(start, g[-1][0] + g[-1][1] - start)
        return {key: blob[o - start:o - start + n] for o, n, key in g}
    with cf.ThreadPoolExecutor(6) as ex:
        for part in ex.map(one, groups):
            out.update(part)
    return out, len(groups)


# ---------------------------------------------------------------- MBTiles, the one format every map reads
def mbtiles(path, meta):
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE metadata (name TEXT, value TEXT);"
                     "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
                     "CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row);")
    db.executemany("INSERT INTO metadata VALUES (?, ?)", [(k, str(v)) for k, v in meta.items()])
    return db


def put(db, z, x, y, data):
    db.execute("INSERT OR IGNORE INTO tiles VALUES (?, ?, ?, ?)", (z, x, (1 << z) - 1 - y, data))   # MBTiles rows are TMS


def write_meta(key, value):
    p = OUT / "meta.json"
    m = json.loads(p.read_text()) if p.exists() else {}
    m[key] = value
    p.write_text(json.dumps(m, indent=1))


# ---------------------------------------------------------------- the parts
def vector(dry):
    builds = json.loads(get("https://build-metadata.protomaps.dev/builds.json"))
    build = builds[-1]
    url = f"https://build.protomaps.com/{build['key']}"
    pm = PMTiles(url)
    want_xyz = [(z, x, y) for zs, km in VECTOR_RINGS for z in zs if z <= pm.maxz for x, y in tiles_around(LAT, LON, km, z)]
    print(f"vector: Protomaps build {build['key']} (basemap v{build.get('version')}), {len(want_xyz)} tiles in three rings, "
          f"the closest {R_KM * 2:.0f} km across at zoom 12-15.", flush=True)
    t0 = time.time()
    locs = {}
    for z, x, y in want_xyz:
        loc = pm.locate(zxy_to_id(z, x, y))
        if loc:
            locs[(z, x, y)] = loc
    est = sum(n for _, n in locs.values())
    print(f"vector: {len(locs)} tiles hold data ({len(want_xyz) - len(locs)} are open sea), {est / 1e6:.1f} MB to read. "
          f"Directories read in {time.time() - t0:.0f}s.", flush=True)
    if dry:
        return
    tiles, reqs = fetch_spans(pm, locs)
    tmp = OUT / "vector.mbtiles.part"
    db = mbtiles(tmp, {"name": "vector", "format": "pbf", "minzoom": 0, "maxzoom": max(z for z, _, _ in locs),
                       "attribution": "© OpenStreetMap contributors (ODbL), Protomaps basemap", "build": build["key"]})
    for (z, x, y), data in tiles.items():
        put(db, z, x, y, data)                              # kept gzipped, as Protomaps ships them; served as such
    db.commit(); db.close()
    tmp.replace(OUT / "vector.mbtiles")
    for font in FONTS:
        d = OUT / "glyphs" / font
        d.mkdir(parents=True, exist_ok=True)
        for rg in GLYPH_RANGES:
            (d / f"{rg}.pbf").write_bytes(get(GLYPHS_URL.format(font=font.replace(" ", "%20"), range=rg)))
    size = (OUT / "vector.mbtiles").stat().st_size
    write_meta("vector", {"source": "Protomaps basemap, daily OpenStreetMap build", "build": build["key"],
                          "schema": build.get("version"), "licence": "ODbL 1.0", "attribution": "© OpenStreetMap contributors",
                          "tiles": len(tiles), "bytes": size, "requests": reqs + 2, "rings_km": [km for _, km in VECTOR_RINGS],
                          "maxzoom": max(z for z, _, _ in locs), "fonts": FONTS, "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(f"vector: {len(tiles)} tiles, {size / 1e6:.1f} MB, in {reqs} range requests and {time.time() - t0:.0f}s. "
          f"Fonts: {len(FONTS)} faces. Served at /ground/vector and /ground/glyphs.", flush=True)


def drone(dry):
    dlat, dlon = DRONE_KM / 110.574, DRONE_KM / (111.320 * math.cos(math.radians(LAT)))
    box = (LON - dlon, LAT - dlat, LON + dlon, LAT + dlat)
    found = json.loads(get("https://api.openaerialmap.org/meta?limit=50&bbox=" + ",".join(f"{v:.5f}" for v in box)))
    mosaics = [r for r in found.get("results", []) if (r.get("properties") or {}).get("tms")
               and str((r.get("properties") or {}).get("license", "")).upper().startswith("CC-BY")]
    mosaics.sort(key=lambda r: r.get("acquisition_end", ""), reverse=True)   # newest wins where two overlap
    print(f"drone: {len(mosaics)} open mosaic(s) cross the {DRONE_KM * 2:.0f} km ring.", flush=True)
    if not mosaics:
        write_meta("drone", {"source": "OpenAerialMap", "mosaics": [], "tiles": 0,
                             "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        return
    jobs = {}
    for r in mosaics:
        w, s, e, n = r["bbox"]
        cw, cs, ce, cn = max(w, box[0]), max(s, box[1]), min(e, box[2]), min(n, box[3])
        if cw >= ce or cs >= cn:
            continue
        clat, clon = (cs + cn) / 2, (cw + ce) / 2
        half = max((cn - cs) * 110.574, (ce - cw) * 111.320 * math.cos(math.radians(clat))) / 2
        for z in range(14, DRONE_MAXZ + 1):
            for x, y in tiles_around(clat, clon, half, z):
                jobs.setdefault((z, x, y), r)
    print(f"drone: {len(jobs)} tiles at zoom 14-{DRONE_MAXZ}.", flush=True)
    if dry:
        return
    t0 = time.time()

    def one(item):
        (z, x, y), r = item
        try:
            return (z, x, y), get(r["properties"]["tms"].replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y)), timeout=30)
        except Exception:  # noqa: BLE001 — outside a mosaic's footprint the server answers 404; that tile stays empty
            return (z, x, y), None
    tmp = OUT / "drone.mbtiles.part"
    db = mbtiles(tmp, {"name": "drone", "format": "png", "minzoom": 14, "maxzoom": DRONE_MAXZ,
                       "attribution": "; ".join(f"{r.get('provider')}, {r.get('title')} (OpenAerialMap, CC BY 4.0)" for r in mosaics)})
    kept = 0
    with cf.ThreadPoolExecutor(8) as ex:
        for (z, x, y), data in ex.map(one, jobs.items()):
            if data and len(data) > 200:
                put(db, z, x, y, data); kept += 1
    db.commit(); db.close()
    tmp.replace(OUT / "drone.mbtiles")
    size = (OUT / "drone.mbtiles").stat().st_size
    write_meta("drone", {"source": "OpenAerialMap", "licence": "CC BY 4.0", "tiles": kept, "bytes": size, "maxzoom": DRONE_MAXZ,
                         "mosaics": [{"title": r.get("title"), "provider": r.get("provider"), "gsd_m": r.get("gsd"),
                                      "date": (r.get("acquisition_end") or "")[:10], "bbox": r.get("bbox")} for r in mosaics],
                         "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(f"drone: {kept} tiles, {size / 1e6:.1f} MB, in {time.time() - t0:.0f}s. Served at /ground/drone.", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    dry = "--dry-run" in args
    only = args[args.index("--only") + 1] if "--only" in args else None
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"place basemap: this tells build.protomaps.com{'' if only == 'vector' else ' and OpenAerialMap'} which "
          f"{R_KM * 2:.0f} km square this node is in, once. After it, the map is read from {OUT} and sends nothing.", flush=True)
    if only in (None, "vector"):
        vector(dry)
    if only in (None, "drone"):
        drone(dry)
