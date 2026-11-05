"""How hot the ground in this node's cell got, against the land around it, from satellites. Checked once a day.

Two public-domain products, read anonymously from Microsoft Planetary Computer:
  · Landsat 8/9 Collection 2 Level-2 surface temperature (ST_B10, collection `landsat-c2-l2`). 30 m pixels,
    resampled by USGS from a 100 m thermal band; one look at about 10:30 local time every 8 days per path, two
    paths over Bali. Clouds take most of them. From the newest clear scene: the mean ground temperature of the
    node's own H3 res-8 cell (`lst`), the mean of the land 1 to SURFACE_HEAT_RING_KM km around the node
    (`lst_ring`), the difference (`lst_delta`: the surface heat island at the house), and where the cell ranks
    among the res-8 cells of that ring (`lst_pctile`).
  · MODIS MOD11A1/MYD11A1 v061 land surface temperature (collection `modis-11A1-061`). 1 km, day and night, Terra
    and Aqua. The node's own pixel: `lst_night`, the heat the ground gives back to a house after dark, and
    `lst_day`.

Microsoft is the host, not the publisher: the numbers are USGS's and NASA's, and both are public domain.

kind='model', scale='city', local=False. A satellite retrieval of the ground's skin, not the air anyone breathes,
and never a `live` cell. Every reading is stamped with the overpass, not the poll, so a scene seen three days late
says three days old.

No new library. The app image has no numpy or rasterio and this pack does not add them: a Cloud-Optimized GeoTIFF
is a TIFF header and a grid of deflate-compressed tiles, so `Cog` below reads the header with one range request,
then only the tiles the window touches, and decompresses them with zlib. A Landsat scene is 68 MB; a 3 km ring
touches four 256x256 tiles of it, about 200 kB per band. h3, already in the image for the hero's ground, names
the cells.

Polite: one STAC search per collection a day, a scene or a MODIS day read once and remembered in
out/surface-heat/state.json, at most LANDSAT_READS scenes and MODIS_READS days read per day.
"""
from __future__ import annotations

import json
import logging
import math
import os
import struct
import sys
import time
import zlib
from array import array
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("planetai.pack.surface-heat")

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
ATTRIBUTION = ("Landsat Collection 2 Level-2 surface temperature courtesy of the U.S. Geological Survey; MODIS "
               "MOD11A1/MYD11A1 v061 from NASA LP DAAC. Both public domain. Read through Microsoft Planetary Computer.")
DAY = 86400
LANDSAT_DAYS, LANDSAT_READS = 32, 3    # two 16-day cycles back; at most three scenes' windows read in one day
MODIS_DAYS, MODIS_READS = 8, 4         # MODIS lands on Planetary Computer about five days late
INNER_M = 1000                         # the ring starts a kilometre out, past the node's own cell and its edge
HEAD = 65536                           # one range read holds a Landsat COG's first header and its tile tables

# QA_PIXEL bits (Landsat Collection 2). `clear` is USGS's own "neither cloud nor dilated cloud"; shadow and cirrus
# are separate bits, and a shadowed roof reads cool for a reason that is not the roof. Water is left out of both
# sides of the comparison: a coastal ring would otherwise be half sea, and the house would look hot against it.
FILL, CIRRUS, SHADOW, CLEAR, WATER = 1, 1 << 2, 1 << 4, 1 << 6, 1 << 7

# MODIS overpasses in local solar time. ponytail: nominal, so a stamp can be an hour or so off where the swath is
# wide; reading the Day/Night_view_time layers would fix it at two more requests per day per platform.
OVERPASS = {"terra": {"lst_day": 10.5, "lst_night": 22.5}, "aqua": {"lst_day": 13.5, "lst_night": 1.5}}


# ---------------------------------------------------------------- projections, without pyproj

def utm(lat: float, lon: float, zone: int, south: bool) -> tuple[float, float]:
    """WGS84 to UTM metres, Snyder's series (USGS Professional Paper 1395, eq. 8-9 to 8-10). Good to a few
    millimetres inside a zone. Landsat files its southern scenes under the NORTH zone with negative northings, so
    `south` comes from the file's EPSG code (327xx), never from the sign of the latitude."""
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    phi, lam = math.radians(lat), math.radians(lon - (zone * 6 - 183))
    s, c = math.sin(phi), math.cos(phi)
    n = a / math.sqrt(1 - e2 * s * s)
    t, cc, aa = math.tan(phi) ** 2, ep2 * c * c, lam * c
    m = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
             - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
             + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
             - (35 * e2 ** 3 / 3072) * math.sin(6 * phi))
    x = k0 * n * (aa + (1 - t + cc) * aa ** 3 / 6 + (5 - 18 * t + t * t + 72 * cc - 58 * ep2) * aa ** 5 / 120) + 500000
    y = k0 * (m + n * math.tan(phi) * (aa * aa / 2 + (5 - t + 9 * cc + 4 * cc * cc) * aa ** 4 / 24
                                       + (61 - 58 * t + t * t + 600 * cc - 330 * ep2) * aa ** 6 / 720))
    return x, y + (10000000.0 if south else 0.0)


def sinusoidal(lat: float, lon: float) -> tuple[float, float]:
    """The MODIS land grid: a sphere of radius 6371007.181 m, central meridian 0."""
    r = 6371007.181
    return r * math.radians(lon) * math.cos(math.radians(lat)), r * math.radians(lat)


def projection(epsg: int):
    if 32601 <= epsg <= 32660 or 32701 <= epsg <= 32760:
        return lambda la, lo: utm(la, lo, epsg % 100, epsg > 32700)
    raise ValueError(f"EPSG:{epsg} is not a UTM zone; this reader knows only what Landsat is filed in")


def local_inverse(fwd, lat: float, lon: float):
    """Projected metres back to lat/lon near one point, by the forward projection's own Jacobian there. Inside a
    few kilometres it is off by well under a metre (tests/test_surface_heat.py measures it), and an H3 res-8 cell is
    hundreds of metres across, so a full inverse series would buy nothing."""
    d = 1e-4
    x0, y0 = fwd(lat, lon)
    xa, ya = fwd(lat + d, lon)
    xb, yb = fwd(lat, lon + d)
    a, b, c, e = (xa - x0) / d, (xb - x0) / d, (ya - y0) / d, (yb - y0) / d
    det = a * e - b * c
    return lambda x, y: (lat + (e * (x - x0) - b * (y - y0)) / det, lon + (a * (y - y0) - c * (x - x0)) / det)


# ---------------------------------------------------------------- a COG over HTTP ranges

TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 11: ("f", 4), 12: ("d", 8), 16: ("Q", 8)}


class Cog:
    """Just enough of a Cloud-Optimized GeoTIFF to read a window of its full-resolution image: a little-endian
    classic TIFF, one band, tiled, deflate or uncompressed, no predictor. That is what Planetary Computer serves
    for both collections (checked 15 Oct 2026); anything else is refused by name rather than misread."""

    def __init__(self, get, url: str):
        self.get, self.url = get, url
        self.head = get(url, 0, HEAD - 1)
        if self.head[:4] != b"II*\x00":
            raise ValueError(f"{url.rsplit('/', 1)[-1]}: not a little-endian classic TIFF")
        off = struct.unpack_from("<I", self.head, 4)[0]
        self.tags = {}
        for i in range(struct.unpack_from("<H", self.head, off)[0]):
            tag, typ, n, val = struct.unpack_from("<HHII", self.head, off + 2 + 12 * i)
            fmt, size = TYPES.get(typ, ("B", 1))
            spec = f"<{n}s" if typ == 2 else "<" + fmt * n
            raw = self.head[off + 10 + 12 * i: off + 14 + 12 * i] if size * n <= 4 else self._bytes(val, size * n)
            self.tags[tag] = struct.unpack_from(spec, raw)
        t = self.tags
        self.w, self.h = t[256][0], t[257][0]
        self.bits, comp, pred = t[258][0], t[259][0], t.get(317, (1,))[0]
        if 322 not in t or comp not in (1, 8, 32946) or pred != 1 or t.get(277, (1,))[0] != 1 or self.bits not in (8, 16):
            raise ValueError(f"{url.rsplit('/', 1)[-1]}: a layout this reader does not handle "
                             f"(tiled={322 in t}, compression={comp}, predictor={pred}, bits={self.bits})")
        self.deflate = comp != 1
        self.tw, self.th = t[322][0], t[323][0]
        self.offsets, self.counts = t[324], t[325]
        self.sx, self.sy = t[33550][0], t[33550][1]
        i, j, _, x, y, _ = t[33922][:6]
        self.x0, self.y0 = x - i * self.sx, y + j * self.sy
        keys = t.get(34735, ())
        geo = {keys[k]: keys[k + 3] for k in range(4, len(keys) - 3, 4)}
        if geo.get(1025) == 2:                     # PixelIsPoint: the tie point is a pixel's centre, not its corner
            self.x0, self.y0 = self.x0 - self.sx / 2, self.y0 + self.sy / 2
        self.epsg = geo.get(3072)

    def _bytes(self, start: int, n: int) -> bytes:
        if start + n <= len(self.head):
            return self.head[start:start + n]
        return self.get(self.url, start, start + n - 1)

    def pixel(self, x: float, y: float) -> tuple[int, int]:
        return int((self.y0 - y) // self.sy), int((x - self.x0) // self.sx)

    def read(self, r0: int, c0: int, r1: int, c1: int) -> list[int]:
        """The window rows r0..r1-1, columns c0..c1-1, clipped to the image, row by row. One range request per tile
        it touches; a tile with no bytes is all zeros, which both products use for no data."""
        r0, c0, r1, c1 = max(0, r0), max(0, c0), min(self.h, r1), min(self.w, c1)
        if r1 <= r0 or c1 <= c0:
            raise ValueError("the window falls outside the image")
        w = c1 - c0
        out = [0] * ((r1 - r0) * w)
        across = (self.w + self.tw - 1) // self.tw
        code = "H" if self.bits == 16 else "B"
        for tr in range(r0 // self.th, (r1 - 1) // self.th + 1):
            for tc in range(c0 // self.tw, (c1 - 1) // self.tw + 1):
                k = tr * across + tc
                if not self.counts[k]:
                    continue
                raw = self.get(self.url, self.offsets[k], self.offsets[k] + self.counts[k] - 1)
                tile = array(code, zlib.decompress(raw) if self.deflate else raw)
                if code == "H" and sys.byteorder == "big":
                    tile.byteswap()
                for r in range(max(r0, tr * self.th), min(r1, (tr + 1) * self.th)):
                    a, b = max(c0, tc * self.tw), min(c1, (tc + 1) * self.tw)
                    s = (r - tr * self.th) * self.tw + (a - tc * self.tw)
                    out[(r - r0) * w + (a - c0):(r - r0) * w + (b - c0)] = tile[s:s + (b - a)]
        return out

    def window(self, x: float, y: float, radius_m: float) -> dict:
        """The square of half-side radius_m around a projected point, as the plain dict `surface` reads (and the
        test fixture stores)."""
        r0, c0 = self.pixel(x - radius_m, y + radius_m)
        r1, c1 = self.pixel(x + radius_m, y - radius_m)
        r0, c0, r1, c1 = max(0, r0), max(0, c0), min(self.h, r1 + 1), min(self.w, c1 + 1)
        return {"values": self.read(r0, c0, r1, c1), "w": c1 - c0, "h": r1 - r0,
                "x0": self.x0 + c0 * self.sx, "y0": self.y0 - r0 * self.sy, "sx": self.sx, "sy": self.sy}


# ---------------------------------------------------------------- the arithmetic

def kelvin_to_c(dn: int, scale: float, offset: float) -> float:
    """A stored integer to degrees Celsius, with the scale and offset the STAC item's raster:bands publish."""
    return dn * scale + offset - 273.15


def clear(qa: int, dn: int) -> bool:
    return bool(qa & CLEAR) and not qa & (SHADOW | CIRRUS | FILL | WATER) and dn > 0


def surface(st: dict, qa: dict, lat: float, lon: float, fwd, scale: float, offset: float, ring_m: float,
            inner_m: float = INNER_M, min_clear: float = 0.5) -> dict:
    """The node's res-8 cell against the ring around it, from two windows of one scene (ST_B10 and QA_PIXEL, same
    grid). Always returns a dict; `lst` is None with a `why` when clouds leave too little of either side.

    Both sides are a plain mean of clear land pixels, the same formula on each. A pixel counts towards a side's
    `clear` share unless it is fill or water: a cloud over the sea is counted as not clear, which can only make a
    coastal node wait for a better scene, never compare against the wrong thing.
    """
    import h3
    x_n, y_n = fwd(lat, lon)
    inv = local_inverse(fwd, lat, lon)
    house = h3.latlng_to_cell(lat, lon, 8)
    cells: dict[str, list] = {}                    # cell -> [sum °C, clear pixels, land pixels]
    ring = [0.0, 0, 0]
    reach = ring_m + 600                           # a ring cell's centre may sit at ring_m; its far corner beyond
    w, sx, sy = st["w"], st["sx"], st["sy"]
    for k, (dn, q) in enumerate(zip(st["values"], qa["values"])):
        if q & (FILL | WATER):
            continue
        r, c = divmod(k, w)
        x, y = st["x0"] + (c + 0.5) * sx, st["y0"] - (r + 0.5) * sy
        d = math.hypot(x - x_n, y - y_n)
        if d > reach:
            continue
        cell = h3.latlng_to_cell(*inv(x, y), 8)
        ok = clear(q, dn)
        t = kelvin_to_c(dn, scale, offset) if ok else 0.0
        acc = cells.setdefault(cell, [0.0, 0, 0])
        acc[0] += t; acc[1] += ok; acc[2] += 1
        if inner_m <= d <= ring_m and cell != house:
            ring[0] += t; ring[1] += ok; ring[2] += 1
    own = cells.get(house, [0.0, 0, 0])
    out = {"lst": None, "cell_clear": round(own[1] / own[2], 2) if own[2] else 0.0,
           "ring_clear": round(ring[1] / ring[2], 2) if ring[2] else 0.0}
    if not own[1] or own[1] < min_clear * own[2]:
        return {**out, "why": f"the cell is {out['cell_clear']:.0%} clear"}
    if not ring[1] or ring[1] < min_clear * ring[2]:
        return {**out, "why": f"the ring is {out['ring_clear']:.0%} clear"}
    lst, lst_ring = own[0] / own[1], ring[0] / ring[1]
    # The rank is among whole cells, not pixels: a mean against single pixels would put every cell near the
    # middle. A cell counts when its centre is in the ring and at least a quarter of its area is clear land.
    px = sx * sy
    means = []
    for cell, (s, n, land) in cells.items():
        if cell == house or not n or n < min_clear * land or n < 0.25 * h3.cell_area(cell, "m^2") / px:
            continue
        cx, cy = fwd(*h3.cell_to_latlng(cell))
        if inner_m <= math.hypot(cx - x_n, cy - y_n) <= ring_m:
            means.append(s / n)
    pct = round(100 * sum(m < lst for m in means) / len(means)) if len(means) >= 5 else None
    return {**out, "lst": lst, "lst_ring": lst_ring, "lst_delta": lst - lst_ring, "lst_pctile": pct,
            "ring_cells": len(means)}


def overpass(day: str, local_hours: float, lon: float) -> datetime:
    """A MODIS daily file's look as UTC. The file is a UTC day; the overpass is in local solar time, so convert and
    fold it back into that UTC day (Aqua's 01:30 over Bali is 17:50 UTC the same UTC day)."""
    d0 = datetime.fromisoformat(day[:10]).replace(tzinfo=timezone.utc)
    h = (local_hours - lon / 15) % 24
    return d0 + timedelta(hours=h)


# ---------------------------------------------------------------- Planetary Computer

def _search(hc, collection: str, lat: float, lon: float, days: int, query: dict | None = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    body = {"collections": [collection], "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "datetime": f"{(now - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')}/{now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "sortby": [{"field": "datetime", "direction": "desc"}], "limit": 50}
    if query:
        body["query"] = query
    r = hc.post(STAC, json=body)
    r.raise_for_status()
    return r.json().get("features") or []


def _reader(hc):
    """get(url, start, end) with a SAS token per storage container. The token is asked for by account and
    container, not by collection: for MODIS the collection's token was refused by its own container (15 Oct 2026)."""
    tokens: dict[str, str] = {}

    def get(url: str, start: int, end: int) -> bytes:
        account, container = url.split("//", 1)[1].split(".", 1)[0], url.split("/")[3]
        key = f"{account}/{container}"
        if key not in tokens:
            t = hc.get(f"{SAS}/{key}")
            t.raise_for_status()
            tokens[key] = t.json()["token"]
        r = hc.get(f"{url}?{tokens[key]}", headers={"Range": f"bytes={start}-{end}"})
        r.raise_for_status()
        if r.status_code != 206 and len(r.content) > end - start + 1:
            raise RuntimeError("the host ignored the range request; refusing to read whole files")
        return r.content[: end - start + 1]
    return get


def _band(item: dict, asset: str) -> tuple[str, float, float]:
    """An asset's href with the scale and offset its STAC item publishes. No default: a missing scale is a
    product this pack was not written for, and a guessed one is a number about nothing."""
    a = item["assets"][asset]
    b = (a.get("raster:bands") or [{}])[0]
    if "scale" not in b:
        raise ValueError(f"{item['id']} {asset}: the item publishes no scale")
    return a["href"], float(b["scale"]), float(b.get("offset", 0.0))


def landsat(hc, state: dict, lat: float, lon: float, ring_m: float, min_clear: float, get=None):
    """The newest clear Landsat scene this node has not read yet, or ([], []) when there is none today."""
    seen = set(state.get("landsat_seen") or [])
    newest = state.get("landsat_newest") or ""
    items = _search(hc, "landsat-c2-l2", lat, lon, LANDSAT_DAYS, {"platform": {"in": ["landsat-8", "landsat-9"]}})
    todo = [i for i in items if i["id"] not in seen and i["properties"]["datetime"] > newest
            and {"lwir11", "qa_pixel"} <= set(i.get("assets") or {})]
    if not todo:
        log.info("surface-heat: no new Landsat scene since %s", newest[:10] or "the pack started")
        return [], []
    get = get or _reader(hc)
    looked = []
    for item in todo[:LANDSAT_READS]:
        seen.add(item["id"])
        state["landsat_seen"] = sorted(seen)[-200:]
        href, scale, offset = _band(item, "lwir11")
        st_cog = Cog(get, href)
        fwd = projection(st_cog.epsg or int(item["properties"].get("proj:epsg") or 0))
        x, y = fwd(lat, lon)
        st = st_cog.window(x, y, ring_m + 600)
        qa = Cog(get, item["assets"]["qa_pixel"]["href"]).window(x, y, ring_m + 600)
        res = surface(st, qa, lat, lon, fwd, scale, offset, ring_m, inner_m=INNER_M, min_clear=min_clear)
        if res["lst"] is None:
            looked.append(f"{item['id']}: {res['why']}")
            continue
        ts = datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00"))
        state["landsat_newest"] = item["properties"]["datetime"]
        sensor = {"sensor_id": "surface-cell", "source": "landsat-lst", "name": "Ground in this cell (Landsat, 30 m)",
                  "lat": lat, "lon": lon, "indoor": False, "local": False, "kind": "model", "scale": "city",
                  "cadence": "P8D",
                  "meta": {"scene": item["id"], "collection": "landsat-c2-l2", "provenance": "satellite",
                           "platform": item["properties"].get("platform"),
                           "scene_cloud": item["properties"].get("eo:cloud_cover"),
                           "cell_clear": res["cell_clear"], "ring_clear": res["ring_clear"],
                           "ring_km": [INNER_M / 1000, ring_m / 1000], "ring_cells": res["ring_cells"],
                           "scale": scale, "offset": offset, "host": "Microsoft Planetary Computer",
                           "attribution": ATTRIBUTION}}
        readings = [(ts, "surface-cell", "lst", round(res["lst"], 2)),
                    (ts, "surface-cell", "lst_ring", round(res["lst_ring"], 2)),
                    (ts, "surface-cell", "lst_delta", round(res["lst_delta"], 2))]
        if res["lst_pctile"] is not None:
            readings.append((ts, "surface-cell", "lst_pctile", float(res["lst_pctile"])))
        log.info("surface-heat: %s, cell %.1f °C, ring %.1f °C", item["id"], res["lst"], res["lst_ring"])
        return [sensor], readings
    log.info("surface-heat: no new clear Landsat scene (%s)", "; ".join(looked))
    return [], []


def modis(hc, state: dict, lat: float, lon: float, get=None):
    """Night and day LST at the node's 1 km pixel, from every MODIS day not read yet (newest first, a few a day)."""
    seen = set(state.get("modis_seen") or [])
    items = [i for i in _search(hc, "modis-11A1-061", lat, lon, MODIS_DAYS) if i["id"] not in seen]
    if not items:
        return [], []
    get = get or _reader(hc)
    x, y = sinusoidal(lat, lon)
    readings, ids = [], []
    for item in items[:MODIS_READS]:
        seen.add(item["id"])
        state["modis_seen"] = sorted(seen)[-200:]
        hours = OVERPASS.get(str(item["properties"].get("platform", "")).lower())
        day = item["properties"].get("start_datetime") or item["properties"].get("datetime")
        if not hours or not day:
            continue
        for asset, metric in (("LST_Night_1km", "lst_night"), ("LST_Day_1km", "lst_day")):
            href, scale, offset = _band(item, asset)
            cog = Cog(get, href)
            r, c = cog.pixel(x, y)
            dn = cog.read(r, c, r + 1, c + 1)[0]
            if dn:                                   # 0 is "not produced": cloud, or a retrieval MODIS threw out
                readings.append((overpass(day, hours[metric], lon), "surface-modis", metric,
                                 round(kelvin_to_c(dn, scale, offset), 2)))
                ids.append(item["id"])
    if not readings:
        return [], []
    sensor = {"sensor_id": "surface-modis", "source": "modis-lst", "name": "Ground at this 1 km pixel (MODIS)",
              "lat": lat, "lon": lon, "indoor": False, "local": False, "kind": "model", "scale": "city",
              "cadence": "P1D", "meta": {"items": sorted(set(ids)), "collection": "modis-11A1-061",
                                         "provenance": "satellite", "host": "Microsoft Planetary Computer",
                                         "attribution": ATTRIBUTION}}
    return [sensor], readings


# ---------------------------------------------------------------- the day's check

def _state_file() -> Path:
    return Path(os.getenv("PACK_OUT", "/app/out")) / "surface-heat" / "state.json"


def _load() -> dict:
    try:
        return json.loads(_state_file().read_text())
    except (OSError, ValueError):
        return {}


def _save(state: dict) -> None:
    try:
        p = _state_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.with_suffix(".tmp").write_text(json.dumps(state, indent=1, sort_keys=True))
        p.with_suffix(".tmp").replace(p)
    except OSError as e:
        log.warning("surface-heat: cannot write %s (%s); tomorrow will search again", _state_file(), e)


def fetch(hc):
    """Contract: (sensors, readings). Once a day; the day is remembered on disk so a restart does not search again."""
    state = _load()
    if time.time() - float(state.get("checked") or 0) < DAY:
        return [], []
    lat, lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
    ring_m = float(os.getenv("SURFACE_HEAT_RING_KM") or 3) * 1000
    min_clear = float(os.getenv("SURFACE_HEAT_MIN_CLEAR") or 0.5)
    if ring_m <= INNER_M:
        raise RuntimeError(f"SURFACE_HEAT_RING_KM must be more than {INNER_M / 1000:g}: the ring starts there")
    sensors, readings, errors = [], [], []
    for name, part in (("landsat", lambda: landsat(hc, state, lat, lon, ring_m, min_clear)),
                       ("modis", lambda: modis(hc, state, lat, lon))):
        try:
            s, r = part()
            sensors += s; readings += r
        except Exception as e:  # noqa: BLE001 — one product failing must not cost the other its day
            errors.append(f"{name}: {type(e).__name__}: {str(e)[:160]}")
    # Both failed: Planetary Computer is probably down or unreachable. Try again in an hour, not tomorrow.
    state["checked"] = time.time() - (DAY - 3600 if len(errors) == 2 else 0)
    _save(state)
    if errors and not readings:
        raise RuntimeError("; ".join(errors))
    for e in errors:
        log.warning("surface-heat: %s", e)
    return sensors, readings
