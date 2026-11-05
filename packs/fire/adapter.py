"""Active fires near the node, from NASA FIRMS: what satellites saw burning in the last 24 hours, how far away, in
which direction, and whether it lies where the wind is coming from.

Two rings round the node: local (FIRE_LOCAL_KM, 25) for burning a household can smell, regional (FIRE_REGION_KM,
150) for smoke that travels. Every number is about the last 24 hours and is somebody else's satellite, so the
sensor is kind='model' and never local, and nothing here can make an Index cell say `live`.

WHERE IT READS. Without a key, NASA's public regional text files (VIIRS 375 m, no key, CC0), one per satellite. With
FIRMS_MAP_KEY, the keyed /api/area/ for just the regional ring's box, which is kilobytes instead of megabytes.

POLITE POLLING. FIRMS's file server ignores If-Modified-Since and If-None-Match (tested 14 Oct 2026: 200 with the
file's own ETag). So the pack asks with HEAD first and downloads only when the ETag or Last-Modified changed, and
still sends both conditional headers on the GET in case the server learns them. Unchanged files mean no new rows.
At most every FIRE_POLL_HOURS (3). The first start takes the 7-day file once, so the node has a week behind it.

STATE ON DISK. app/packs.py imports this file afresh on every poll, so a module-level "last asked at" resets every
five minutes. What the pack remembers (when it last asked, each file's validators and the detections it kept) is
a small JSON file under PACK_OUT, the node's one writable path.

THE KEY rides in the URL path of the keyed API. No message this file raises or logs contains a URL.

Contract: fetch(hc) -> (sensors, readings), like everything in app/sources.py.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from pathlib import Path

log = logging.getLogger("planetai.fire")

BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire"
API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SENSOR, SOURCE = "firms-fires", "firms"
# satellite -> (folder, file prefix, API source). Names checked with a HEAD each on 14 Oct 2026.
SATELLITES = {"noaa-20": ("noaa-20-viirs-c2", "J1_VIIRS_C2", "VIIRS_NOAA20_NRT"),
              "noaa-21": ("noaa-21-viirs-c2", "J2_VIIRS_C2", "VIIRS_NOAA21_NRT"),
              "suomi-npp": ("suomi-npp-viirs-c2", "SUOMI_VIIRS_C2", "VIIRS_SNPP_NRT")}
# (south, north, west, east) of each regional file: the extent of that file's own detections on 14 Oct 2026, rounded
# inwards. FIRMS publishes no box for its regions, so this is an inner bound: a ring that is not wholly inside one of
# these reads Global (6.4 MB a day per satellite) rather than a region that might stop short of it. Bali at 150 km,
# Singapore at 500 km and Menorca at 500 km all fit; Bali at 500 km does not.
REGIONS = {"SouthEast_Asia": (-12.0, 31.0, 88.0, 160.0), "Europe": (34.0, 66.0, -9.0, 34.7)}
UPWIND_DEG = 45     # a fire is upwind when it lies within 45° either side of where the wind comes from
GRID = 0.004        # ~445 m: one burning place per cell per day, however many satellites and passes saw it


def km(lat1, lon1, lat2, lon2) -> float:
    p1, p2, dl = radians(lat1), radians(lat2), radians(lon2 - lon1)
    return 6371 * 2 * asin(sqrt(sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2))


def bearing(lat1, lon1, lat2, lon2) -> float:
    """Compass bearing from point 1 to point 2, 0-360, north = 0."""
    p1, p2, dl = radians(lat1), radians(lat2), radians(lon2 - lon1)
    return (degrees(atan2(sin(dl) * cos(p2), cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl))) + 360) % 360


def upwind(fire_deg: float, wind_from: float) -> bool:
    return abs((fire_deg - wind_from + 180) % 360 - 180) <= UPWIND_DEG


def box(lat: float, lon: float, r_km: float) -> tuple:
    dlat, dlon = r_km / 111.0, r_km / (111.0 * max(cos(radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def region(lat: float, lon: float, r_km: float) -> str:
    s, n, w, e = box(lat, lon, r_km)
    for name, (bs, bn, bw, be) in REGIONS.items():
        if bs <= s and n <= bn and bw <= w and e <= be:
            return name
    return "Global"


def parse(text: str, lat: float, lon: float, reach_km: float) -> list[list]:
    """[epoch, lat, lon, frp] for every detection within reach_km that is not low confidence. Columns are read by
    name: the public files and the API differ (no `instrument` in the public C2 file), and the confidence is
    `low/nominal/high` in one and `l/n/h` in the other, so only its first letter is read."""
    if "latitude" not in text[:400]:
        raise RuntimeError("FIRMS answered something that is not a fire table: " + text.strip()[:60].replace("\n", " "))
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            la, lo = float(row["latitude"]), float(row["longitude"])
            t = datetime.strptime(f"{row['acq_date']} {str(row['acq_time']).zfill(4)}", "%Y-%m-%d %H%M")
            frp = float(row.get("frp") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if str(row.get("confidence") or "").strip().lower().startswith("l"):
            continue
        if km(lat, lon, la, lo) <= reach_km:
            out.append([t.replace(tzinfo=timezone.utc).timestamp(), la, lo, frp])
    return out


def places(spots: list[list]) -> list[list]:
    """One row per ~445 m cell, the latest time and the strongest FRP. NOAA-20, NOAA-21 and Suomi NPP pass about 50
    minutes apart and see the same fire, so counting detections would count one field three times.
    ponytail: grid rounding, not clustering; a fire on a cell edge counts twice. Cluster if counts ever matter to one."""
    cells: dict = {}
    for t, la, lo, frp in spots:
        k = (round(la / GRID), round(lo / GRID))
        c = cells.get(k)
        cells[k] = [t, la, lo, frp] if c is None else [max(c[0], t), c[1], c[2], max(c[3], frp)]
    return list(cells.values())


def summarise(spots: list[list], at: datetime, lat: float, lon: float, local_km: float, region_km: float,
              wind_from: float | None) -> list[tuple]:
    """The readings for the 24 hours before `at`. No nearest fire is invented when there is none, and nothing is
    said about upwind without a wind to reckon it by."""
    end = at.timestamp()
    seen = []
    for t, la, lo, frp in places([s for s in spots if end - 86400 < s[0] <= end]):
        d = km(lat, lon, la, lo)
        if d <= region_km:
            seen.append((d, bearing(lat, lon, la, lo), frp))
    near = [s for s in seen if s[0] <= local_km]
    ts = at.replace(second=0, microsecond=0)
    out = [(ts, SENSOR, "fires_local_24h", float(len(near))), (ts, SENSOR, "fires_region_24h", float(len(seen))),
           (ts, SENSOR, "frp_local_mw", round(sum(s[2] for s in near), 1)),
           (ts, SENSOR, "frp_region_mw", round(sum(s[2] for s in seen), 1))]
    if seen:
        k, b, _ = min(seen)
        out += [(ts, SENSOR, "fires_nearest_km", round(k, 1)), (ts, SENSOR, "fires_nearest_bearing", round(b))]
    if wind_from is not None:
        up = [s for s in seen if upwind(s[1], wind_from)]
        out += [(ts, SENSOR, "fires_local_upwind", float(sum(1 for s in up if s[0] <= local_km))),
                (ts, SENSOR, "fires_region_upwind", float(len(up))),
                (ts, SENSOR, "fire_wind_from_deg", round(wind_from))]
        if up:
            k, b, _ = min(up)
            out += [(ts, SENSOR, "fires_upwind_km", round(k, 1)), (ts, SENSOR, "fires_upwind_bearing", round(b))]
    return out


# The wind this node already holds, best first: a measured local kit, then the core Open-Meteo point, then the
# forecast pack. Forecast rows are stored at their VALID time, hours ahead, so every row is bounded ts <= now().
# A peer's row never counts (kind is sensor or model only).
WIND_SQL = """SELECT r.value FROM readings r JOIN sensors s USING (sensor_id)
              WHERE r.metric IN ('wind_direction', 'fc_wind_direction') AND s.kind IN ('sensor', 'model')
                AND r.ts <= now() AND r.ts > now() - interval '3 hours'
              ORDER BY (s.kind = 'sensor' AND s.local) DESC, (r.metric = 'wind_direction') DESC, r.ts DESC
              LIMIT 1"""


def wind() -> float | None:
    try:
        import psycopg
        with psycopg.connect(os.environ["DATABASE_URL"]) as con, con.cursor() as cur:
            cur.execute(WIND_SQL)
            row = cur.fetchone()
        return float(row[0]) if row else None
    except Exception as e:  # noqa: BLE001 — no wind means no upwind numbers, never no fires
        log.info("fire: no wind to reckon upwind by (%s)", type(e).__name__)
        return None


def _state_file() -> Path:
    return Path(os.getenv("PACK_OUT", "/app/out")) / "fire" / "state.json"


def _load() -> dict:
    try:
        return json.loads(_state_file().read_text())
    except (OSError, ValueError):
        return {}


def _save(st: dict) -> None:
    f = _state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".part")
    tmp.write_text(json.dumps(st))
    tmp.replace(f)


def _read(hc, url: str, old: dict | None, keyed: bool):
    """(text, etag, modified), or None when the file has not changed since `old`. Raises without the URL."""
    try:
        if old and not keyed:
            h = hc.head(url, timeout=30)
            h.raise_for_status()
            if (h.headers.get("etag"), h.headers.get("last-modified")) == (old.get("etag"), old.get("modified")):
                return None
        cond = {k: v for k, v in (("If-None-Match", (old or {}).get("etag")),
                                  ("If-Modified-Since", (old or {}).get("modified"))) if v and not keyed}
        r = hc.get(url, headers=cond, timeout=120)
        if r.status_code == 304:
            return None
        r.raise_for_status()
        return r.text, r.headers.get("etag"), r.headers.get("last-modified")
    except Exception as e:  # noqa: BLE001
        code = getattr(getattr(e, "response", None), "status_code", None)
        raise RuntimeError(f"FIRMS did not answer ({type(e).__name__}" + (f", HTTP {code}" if code else "") + ")") from None


def fetch(hc):
    if os.getenv("FIRE_ENABLED", "0").strip() != "1":
        return [], []
    lat, lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
    local_km = float(os.getenv("FIRE_LOCAL_KM") or 25)
    region_km = max(float(os.getenv("FIRE_REGION_KM") or 150), local_km)
    now = datetime.now(timezone.utc)
    st = _load()
    if now.timestamp() - st.get("checked", 0) < float(os.getenv("FIRE_POLL_HOURS") or 3) * 3600:
        return [], []
    key = os.getenv("FIRMS_MAP_KEY", "").strip()
    sats = [s.strip() for s in (os.getenv("FIRE_SATELLITES") or "noaa-20,noaa-21").split(",") if s.strip() in SATELLITES]
    where = "area" if key else region(lat, lon, region_km)
    first = not st.get("files")
    files = {k: v for k, v in (st.get("files") or {}).items() if k in sats}
    changed, failed = False, []
    for sat in sats:
        folder, prefix, api_src = SATELLITES[sat]
        if key:
            s, n, w, e = box(lat, lon, region_km)
            url = f"{API}/{key}/{api_src}/{w:.3f},{s:.3f},{e:.3f},{n:.3f}/{5 if first else 2}"   # whole UTC days
        else:
            url = f"{BASE}/{folder}/csv/{prefix}_{where}_{'7d' if first else '24h'}.csv"
        old = files.get(sat)
        if old and (old.get("where"), old.get("reach")) != (where, region_km):
            old = None                     # a different file or ring: what was kept is not this one's
        try:
            got = _read(hc, url, old, bool(key))
            if got is None:
                continue
            text, etag, modified = got
            files[sat] = {"where": where, "reach": region_km, "etag": etag, "modified": modified,
                          "spots": parse(text, lat, lon, region_km)}
            changed = True
        except RuntimeError as e:          # one satellite down, or an error page, must not blank the others
            failed.append(f"{sat}: {e}")
            log.warning("fire: %s: %s", sat, e)
    st.update(checked=now.timestamp(), files=files)
    _save(st)                              # also after a failure: a server that is down is asked again in hours
    if failed and len(failed) == len(sats):
        raise RuntimeError(failed[0])
    if not changed:
        return [], []
    spots = [s for f in files.values() for s in f.get("spots", [])]
    readings = summarise(spots, now, lat, lon, local_km, region_km, wind())
    if first:                              # the week the 7-day file brought, a day at a time; no wind for the past
        for d in range(1, 7):
            readings += summarise(spots, now - timedelta(days=d), lat, lon, local_km, region_km, None)
    sensor = {"sensor_id": SENSOR, "source": SOURCE, "name": f"NASA FIRMS, VIIRS satellites: nearby is within {local_km:.0f} km, the region {region_km:.0f} km",
              "lat": None, "lon": None, "indoor": False, "local": False, "kind": "model", "scale": "bioregion",
              "cadence": "PT3H",
              "meta": {"attribution": "NASA FIRMS, VIIRS 375 m active fire detections (CC0)", "local_km": local_km,
                       "region_km": region_km, "file": where, "satellites": sats,
                       "modified": {k: v.get("modified") for k, v in files.items()}}}
    return [sensor], readings
