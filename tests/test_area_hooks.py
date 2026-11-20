"""The `area(cells, bbox)` hook in hydro, eyes and forecast (spec 2026-11-10 §2, plan Task 7), offline.

Loaded the way the node loads them (app/packs.py::collect), with every HTTP client replaced by a fake that records
what was asked and with what timeout. No network, no database.

Run: PACKS_DIR=packs PYTHONPATH=app python3 tests/test_area_hooks.py
"""
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

import h3
import httpx

HOME = "8895a4c843fffff"                       # node #1's res-8 cell
LAT, LON = h3.cell_to_latlng(HOME)
os.environ.update(NODE_LAT=str(LAT), NODE_LON=str(LON), NODE_NAME="test-node", PACK_OUT=tempfile.mkdtemp(),
                  DATABASE_URL="postgresql://unused/never-connected")   # eyes/routes.py imports db, which reads it
os.environ.pop("HYDRO_RADIUS_KM", None)
os.environ.pop("NODE_VERSION", None)
os.environ["FORECAST_OPENMETEO"] = "0"

import area   # noqa: E402
import packs  # noqa: E402
import settings  # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


ROWS = {"PACKS_ALLOW_CODE": "1", "PACKS_ENABLED": "hydro,eyes,forecast", "SPECIES_MATCH": "off"}


def setting(**kw):
    """The settings table without a database: the cache, pinned."""
    ROWS.update(kw)
    settings._cache.update(at=time.time() + 1e9, rows=dict(ROWS))
    packs._HOOKS["at"] = 0.0          # which packs are on is read again


def area_of(cells):
    return packs.collect("area", cells, area.bbox(cells))


def by_pack(got):
    return {a["pack"]: a for a in got}


# ---------------------------------------------------------------- a fake httpx.Client
ASKED = []          # (url, params, timeout)
ANSWER = {}         # url -> json, or an exception to raise


class FakeClient:
    def __init__(self, timeout=None, **_):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass

    def get(self, url, params=None, **_):
        ASKED.append((url, params, self.timeout))
        a = ANSWER[url]
        if isinstance(a, Exception):
            raise a
        return httpx.Response(200, json=a, request=httpx.Request("GET", url))


httpx.Client = FakeClient
GBIF = "https://api.gbif.org/v1/occurrence/search"
OM = "https://api.open-meteo.com/v1/forecast"

SEVEN = sorted(h3.grid_disk(HOME, 1))
setting()

# ---------------------------------------------------------------- collect works as it is; a pack that is off answers nothing
check(area_of(SEVEN) == [], f"nothing kept, nothing switched on: no answer at all, {area_of(SEVEN)}")
check(ASKED == [], "and nothing asked of anybody")
names = {n for n, _ in packs._hook_modules()}
check({"hydro", "eyes", "forecast"} <= names, f"the three hooks load through packs.collect: {names}")
setting(PACKS_ENABLED="air-quality")
check(not {"hydro", "eyes", "forecast"} & {n for n, _ in packs._hook_modules()}, "a pack that is off is not loaded")
setting(PACKS_ENABLED="hydro,eyes,forecast", PACKS_ALLOW_CODE="0")
check(not {"hydro", "eyes", "forecast"} & {n for n, _ in packs._hook_modules()},
      "no switch and no PACKS_ALLOW_CODE: their code does not run, as with their adapters")
setting(PACKS_ALLOW_CODE="1")
H = dict(packs._hook_modules())

# ---------------------------------------------------------------- hydro: what it keeps, the features touching the box
A = H["hydro"].A
A.cache().mkdir(parents=True, exist_ok=True)
t = datetime(2026, 11, 8, 6, 0, tzinfo=timezone.utc)


def river(rid, lon0, lat0, lon1, lat1):
    return {"type": "Feature", "properties": {"hyriv_id": rid, "dis_av_cms": 0.5},
            "geometry": {"type": "LineString", "coordinates": [[lon0, lat0], [lon1, lat1]]}}


def basin(bid, w, s, e, n):
    return {"type": "Feature", "properties": {"hybas_id": bid},
            "geometry": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}}


kept = {"lat": LAT, "lon": LON, "radius_km": 25, "region": "au", "fetched_at": t.isoformat(),
        "nearest": None, "largest": None, "basin": {"level12": None, "level4": None},
        "rivers": {"type": "FeatureCollection", "features": [
            river(1, LON - 0.01, LAT - 0.01, LON + 0.01, LAT + 0.01),        # across the home cell
            river(2, LON + 0.15, LAT, LON + 0.16, LAT + 0.01)]},             # 17 km east
        "basins": {"type": "FeatureCollection", "features": [
            basin(11, LON - 0.05, LAT - 0.05, LON + 0.05, LAT + 0.05),       # holds the node
            basin(12, LON + 0.12, LAT + 0.12, LON + 0.2, LAT + 0.2)]}}       # far up the square
A.result_file().write_text(json.dumps(kept))
got = by_pack(area_of(SEVEN))
hy = got.get("hydro") or {}
check(sorted(f["properties"].get("hyriv_id") or f["properties"].get("hybas_id") for f in hy.get("rows", [])) == [1, 11],
      f"the river and the basin touching the seven, not the far ones: {hy.get('rows')}")
check({f["properties"]["layer"] for f in hy.get("rows", [])} == {"river", "basin"}, "each row says which layer it is")
check(hy.get("source") == A.RELEASE and hy.get("licence") == A.ATTRIBUTION, "source and licence as the pack carries them")
check(hy.get("as_of") == t.isoformat(), "as of the fetch, not of the question")
check("note" not in hy, "a selection inside the square needs no note")
check(kept["rivers"]["features"][0]["properties"] == {"hyriv_id": 1, "dis_av_cms": 0.5}, "the kept file is not changed")
check(ASKED == [], "hydro asks nobody")

far = sorted(h3.grid_disk(h3.latlng_to_cell(LAT + 0.5, LON, 8), 1))           # 55 km north, out of the square
check("hydro" not in by_pack(area_of(far)), "outside the square hydro keeps: no answer, never an empty one")
edge = sorted(h3.grid_disk(h3.latlng_to_cell(LAT + 25000 / 111320.0, LON, 8), 1))   # straddles the north edge
e = by_pack(area_of(edge)).get("hydro") or {}
check(e.get("rows") == [], f"on the edge, nothing kept touches it: {e.get('rows')}")
check("25 km" in (e.get("note") or ""), f"and it says the rest was never kept: {e.get('note')}")
A.result_file().unlink()
check("hydro" not in by_pack(area_of(SEVEN)), "nothing kept: no answer")

# ---------------------------------------------------------------- eyes: GBIF's open records, one call per selection
E = H["eyes"]
ANSWER[GBIF] = {"count": 40, "facets": [{"field": "SPECIES_KEY", "counts": [
    {"name": "2925303", "count": 7}, {"name": "2970418", "count": 31}]}]}
check("eyes" not in by_pack(area_of(SEVEN)) and ASKED == [], "SPECIES_MATCH off: GBIF is not asked, eyes answers nothing")
setting(SPECIES_MATCH="on")
ey = by_pack(area_of(SEVEN)).get("eyes") or {}
check(len(ASKED) == 1 and ASKED[0][0] == GBIF, f"one call for the seven: {[a[0] for a in ASKED]}")
url, params, timeout = ASKED[0]
q = list(params)
check(timeout is not None, "the client keeps a timeout")
check(("license", "CC0_1_0") in q and ("license", "CC_BY_4_0") in q and ("limit", "0") in q
      and ("facet", "speciesKey") in q, f"open licences only, counts only: {q}")
check(not any(k in ("lat", "lon", "decimalLatitude", "decimalLongitude") for k, _ in q), "no point is sent")
geo = [v for k, v in q if k == "geometry"]
check(len(geo) == 1 and geo[0].startswith("POLYGON(("), f"one geometry, the seven as one outline: {geo}")
pts = [tuple(map(float, xy.split())) for xy in geo[0][len("POLYGON(("):-2].split(",")]
check(len(pts) == 19 and pts[0] == pts[-1], f"a closed outline of 18 corners: {len(pts)}")
check(sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in zip(pts, pts[1:])) < 0, "counter-clockwise, as GBIF asks")
inside = {h3.latlng_to_cell(y, x, 8) for x, y in pts[:-1]}
check(inside <= set(h3.grid_disk(HOME, 2)), "the outline's corners stand on the seven's rim")
check(ey.get("rows") == [{"species_key": 2970418, "records": 31}, {"species_key": 2925303, "records": 7}],
      f"records per species, most first, keys only (GBIF's facet carries no name): {ey.get('rows')}")
check(ey.get("licence") == "CC0_1_0 or CC_BY_4_0" and "gbif" in (ey.get("source") or "").lower() and ey.get("as_of"),
      f"source, licence, as_of: {ey}")
area_of(SEVEN)
check(len(ASKED) == 1, "the same selection again within a day: from the cache")
ASKED.clear()
two = sorted([HOME, h3.latlng_to_cell(LAT + 0.1, LON, 8)])
area_of(two)
g2 = [v for k, v in ASKED[0][1] if k == "geometry"][0] if ASKED else ""
check(len(ASKED) == 1 and g2.startswith("MULTIPOLYGON((("), f"two cells apart: one call, a MULTIPOLYGON: {g2[:30]}")
ASKED.clear()
big = sorted(h3.grid_disk(h3.latlng_to_cell(LAT - 0.3, LON, 8), 12))           # 469 cells, compact
check(len(big) <= area.AREA_CAP and len(E._wkt(big)) <= E.WKT_MAX,
      f"a compact selection near the cap fits in one outline: {len(E._wkt(big))} characters")
eb = by_pack(area_of(big)).get("eyes") or {}
check(len(ASKED) == 1 and "rows" in eb, "and is sent, once")
ASKED.clear()
spread = sorted({h3.latlng_to_cell(LAT - 0.4 - 0.03 * i, LON + 0.03 * j, 8) for i in range(7) for j in range(7)})
check(len(E._wkt(spread)) > E.WKT_MAX, f"49 cells apart make 49 hexagons: {len(E._wkt(spread))} characters")
es = by_pack(area_of(spread)).get("eyes") or {}
check(ASKED == [] and "error" in es and "rows" not in es, f"an outline past WKT_MAX is refused with a sentence, never sent: {es}")
ANSWER[GBIF] = httpx.ConnectError("down")
ed = by_pack(area_of([h3.latlng_to_cell(LAT + 0.2, LON, 8)])).get("eyes") or {}
check("error" in ed and "rows" not in ed, f"GBIF down: an error, no rows: {ed}")
ANSWER[GBIF] = {"count": 0, "facets": [{"field": "SPECIES_KEY", "counts": [
    {"name": str(k), "count": 1} for k in range(E.FACET_LIMIT)]}]}
en = by_pack(area_of([h3.latlng_to_cell(LAT + 0.25, LON, 8)])).get("eyes") or {}
check(len(en.get("rows", [])) == E.FACET_LIMIT and en.get("note"), "GBIF's facet cut off: the answer says so")
setting(SPECIES_MATCH="off")
ASKED.clear()

# ---------------------------------------------------------------- forecast: Open-Meteo at the centroid, one call
F = H["forecast"]
t0 = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
hours = 100
hourly = {"time": [(t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]}
hourly.update({k: [float(i) for i in range(hours)] for k in F.A.OM_HOURLY.split(",")})
hourly["precipitation_probability"] = [None] * hours                         # a variable the model does not give here
ANSWER[OM] = {"latitude": LAT, "longitude": LON, "hourly": hourly}
check("forecast" not in by_pack(area_of(SEVEN)) and ASKED == [],
      "FORECAST_OPENMETEO=0: the operator has not said yes to Open-Meteo, nothing asked")
os.environ["FORECAST_OPENMETEO"] = "1"
fc = by_pack(area_of(SEVEN)).get("forecast") or {}
check(len(ASKED) == 1 and ASKED[0][0] == OM and ASKED[0][2] is not None, f"one call, with a timeout: {ASKED}")
p = ASKED[0][1] if ASKED else {}
clat, clon = sum(h3.cell_to_latlng(c)[0] for c in SEVEN) / 7, sum(h3.cell_to_latlng(c)[1] for c in SEVEN) / 7
check(abs(float(p.get("latitude", 0)) - clat) < 1e-3 and abs(float(p.get("longitude", 0)) - clon) < 1e-3
      and "," not in str(p.get("latitude")), f"one point, the selection's centroid: {p.get('latitude')}, {p.get('longitude')}")
now = datetime.now(timezone.utc)
ts = [datetime.fromisoformat(r["ts"]) for r in fc.get("rows", [])]
check(ts and min(ts) >= now - timedelta(hours=1, minutes=1) and max(ts) <= now + timedelta(hours=24),
      f"now and the next 24 h: {min(ts) if ts else None} to {max(ts) if ts else None}")
check({r["metric"] for r in fc.get("rows", [])} == set(F.A.OM_MAP.values()) - {"fc_rain_prob"},
      "the forecast's own metrics; a variable with no value is left out, never 0")
check(all(r["value"] is not None for r in fc.get("rows", [])), "no row without a value")
check(fc.get("licence") == "CC-BY 4.0, free tier non-commercial only" and "Open-Meteo" in (fc.get("source") or ""),
      f"the words the pack already carries: {fc.get('licence')}")
check(fc.get("as_of"), "as of when the node asked")
area_of(SEVEN)
check(len(ASKED) == 1, "the same selection within the hour: from the cache")
key = tuple(SEVEN)
F._cache[key] = (F._cache[key][0] - 3601, F._cache[key][1])
area_of(SEVEN)
check(len(ASKED) == 2, "an hour later: asked again")
ANSWER[OM] = httpx.HTTPStatusError("429", request=httpx.Request("GET", OM), response=httpx.Response(429))
fe = by_pack(area_of([h3.latlng_to_cell(LAT + 0.2, LON, 8)])).get("forecast") or {}
check("error" in fe and "rows" not in fe, f"Open-Meteo refuses: an error, no rows: {fe}")

# ---------------------------------------------------------------- the switches POST /area reads (Task 8)
# A pack whose own switch is off answers None, which reads like "nothing here". The route reads the same switch from
# AREA_SWITCH to say "off on this node" instead, so the hook and the route must read one declaration.
check(getattr(H["eyes"], "AREA_SWITCH", None) == ("SPECIES_MATCH", "on"), "eyes declares the switch its area hook reads")
check(getattr(H["forecast"], "AREA_SWITCH", None) == ("FORECAST_OPENMETEO", "1"), "forecast declares the switch its area hook reads")
check(not hasattr(H["hydro"], "AREA_SWITCH"), "hydro has no switch: it answers from the file it keeps")
os.environ["FORECAST_OPENMETEO"] = "0"
setting(SPECIES_MATCH="off", FORECAST_OPENMETEO="1")         # the settings table wins over the environment, as everywhere
ASKED.clear()
ANSWER[OM] = {"latitude": LAT, "longitude": LON, "hourly": hourly}
check("forecast" in by_pack(area_of([h3.latlng_to_cell(LAT + 0.3, LON, 8)])) and len(ASKED) == 1,
      "forecast's area hook reads its switch from Set up, as the route does, not only from .env")
ROWS.pop("FORECAST_OPENMETEO")
setting()
op = {o["pack"]: o for o in area.open_(SEVEN, area.bbox(SEVEN))}
check(op.get("eyes", {}).get("off") is True and "SPECIES_MATCH=on" in op["eyes"].get("why", ""), f"eyes off, said: {op.get('eyes')}")
check(op.get("forecast", {}).get("off") is True and "FORECAST_OPENMETEO=1" in op["forecast"].get("why", ""), f"forecast off: {op.get('forecast')}")
check("hydro" in op and op["hydro"].get("off") is not True, f"hydro is on: its answer or 'nothing here', never off: {op.get('hydro')}")

if fails:
    print("area hooks FAILED:\n  " + "\n  ".join(fails))
    sys.exit(1)
print("area hooks: collect works as it is; hydro clips what it keeps, eyes asks GBIF once per selection, forecast once "
      "per selection an hour, each off when its switch is, each client with a timeout")
sys.exit(0)
