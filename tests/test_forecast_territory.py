"""The node's territory at its scale: which points the forecast asks for, and what fetch stores for them.

Run: PYTHONPATH=app python3 tests/test_forecast_territory.py
home is the node alone; community is its res-7 cell and the ring round it (7); city is res 6, two rings (19); region
is res 5, two rings (19). The node's own point comes first, at the node's lat/lon, not the cell's centre.
"""
import datetime as dt
import os
import sys
import tempfile

import h3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packs", "forecast"))
import adapter as A  # noqa: E402
import territory as T  # noqa: E402

LAT, LON = -8.8271, 115.15709

# ---- the pure part
home = T.points("home", LAT, LON, "forecast-om")
assert home == [{"sid": "forecast-om", "cell": h3.latlng_to_cell(LAT, LON, 7), "lat": LAT, "lon": LON}], home
for scale, res, n in (("community", 7, 7), ("city", 6, 19), ("region", 5, 19)):
    pts = T.points(scale, LAT, LON, "forecast-om")
    own = h3.latlng_to_cell(LAT, LON, res)
    assert len(pts) == n, (scale, len(pts))
    assert pts[0] == {"sid": "forecast-om", "cell": own, "lat": LAT, "lon": LON}, "the node's own point is first, at its lat/lon"
    assert {p["cell"] for p in pts} == set(h3.grid_disk(own, 1 if scale == "community" else 2))
    assert [p["sid"] for p in pts[1:]] == [f"forecast-om-{p['cell']}" for p in pts[1:]]
    assert [p["cell"] for p in pts[1:]] == sorted(p["cell"] for p in pts[1:]), "the rest are sorted, so the order is stable"
    for p in pts[1:]:
        assert (p["lat"], p["lon"]) == h3.cell_to_latlng(p["cell"]), "the others are cell centres"
    assert len({p["sid"] for p in pts}) == n and len({p["cell"] for p in pts}) == n, "unique"
assert T.points("galaxy", LAT, LON, "forecast-om") == T.points("community", LAT, LON, "forecast-om"), "unknown is community"
assert T.points("community", LAT, LON, "forecast-cams")[1]["sid"] == f"forecast-cams-{T.points('community', LAT, LON, 'x')[1]['cell']}"

# ---- fetch: one call per source, 7 locations, 7 sensors each; marine stays one point
def payload(keys, lat, lon, hours=100):
    t0 = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=2)
    h = {"time": [(t0 + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]}
    h.update({k: [float(i) for i in range(hours)] for k in keys})
    return {"latitude": lat, "longitude": lon, "hourly": h}


class R:
    def __init__(s, j): s.j = j
    def raise_for_status(s): pass
    def json(s): return s.j


class HC:
    def __init__(s): s.asked = []
    def get(s, url, params=None, headers=None, timeout=None):
        s.asked.append((url, params))
        keys = {A.OPEN_METEO: A.OM_HOURLY.split(","), A.CAMS: list(A.CAMS_MAP), A.MARINE: list(A.MARINE_MAP)}[url]
        la = [float(x) for x in params["latitude"].split(",")]
        lo = [float(x) for x in params["longitude"].split(",")]
        out = [payload(keys, a - (0.03 if url == A.MARINE else 0), b) for a, b in zip(la, lo)]
        return R(out if len(out) > 1 else out[0])


def run(keep=False, **env):
    if not keep:
        os.environ["PACK_OUT"] = tempfile.mkdtemp()
    os.environ.update(FORECAST_BMKG="0", FORECAST_OPENMETEO="1", NODE_LAT=str(LAT), NODE_LON=str(LON))
    os.environ.pop("NODE_SCALE", None); os.environ.update(env)
    A._pack_on = lambda pid: pid == "coast"
    A.write_wind_field = lambda *a: None
    hc = HC()
    sens, rd = A.fetch(hc)
    return hc, sens, rd


def n_of(sens, base):
    return [s for s in sens if s["sensor_id"].startswith(base)]


hc, sens, rd = run()                                         # NODE_SCALE unset is community, as in app/index.py
by = {u: p for u, p in hc.asked}
assert [u for u, _ in hc.asked].count(A.OPEN_METEO) == 1 and [u for u, _ in hc.asked].count(A.CAMS) == 1, hc.asked
assert by[A.OPEN_METEO]["latitude"].count(",") == 6 and by[A.CAMS]["latitude"].count(",") == 6, "7 locations in one call"
assert by[A.MARINE]["latitude"].count(",") == 0, "the sea is one point"
for base in ("forecast-om", "forecast-cams"):
    ss = n_of(sens, base)
    assert len(ss) == 7 and all(s["meta"]["cell"] for s in ss) and len({s["meta"]["cell"] for s in ss}) == 7, base
    assert ss[0]["sensor_id"] == base and ss[0]["meta"]["cell"] == h3.latlng_to_cell(LAT, LON, 7)
assert len(n_of(sens, "forecast-marine")) == 1 and n_of(sens, "forecast-marine")[0]["meta"]["cell"] == h3.latlng_to_cell(LAT, LON, 7)
assert {s for _t, s, *_ in rd} >= {s["sensor_id"] for s in sens if s["sensor_id"] != "forecast-gap"}, "every sensor has rows"

hc, sens, _ = run(NODE_SCALE="home")
assert len(n_of(sens, "forecast-om")) == 1 and len(n_of(sens, "forecast-cams")) == 1
hc, sens, _ = run(NODE_SCALE="city")
assert len(n_of(sens, "forecast-om")) == 19 and len(n_of(sens, "forecast-cams")) == 19 and len(n_of(sens, "forecast-marine")) == 1
hc, sens, _ = run(NODE_SCALE="Home")
assert len(n_of(sens, "forecast-om")) == 1, "NODE_SCALE is read case-insensitively (app/index.py capitalizes it)"
hc, sens, _ = run(NODE_SCALE=" CITY ")
assert len(n_of(sens, "forecast-om")) == 19, "and trimmed"

# ---- the gap is BMKG against the node's OWN Open-Meteo point, never a neighbouring cell's
# own = 30, every neighbour = 20, BMKG = 30: the right gap is 0, fresh and read back from the rows file.
class Hot(HC):
    def get(s, url, params=None, headers=None, timeout=None):
        r = HC.get(s, url, params, headers, timeout)
        if url == A.OPEN_METEO:
            for i, d in enumerate(r.j):
                v = 30.0 if i == 0 else 20.0
                d["hourly"]["temperature_2m"] = [v] * len(d["hourly"]["time"])
                d["hourly"]["wind_speed_10m"] = [v] * len(d["hourly"]["time"])
        return r


T0 = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=5)
A.bmkg = lambda hc, adm4, la, lo: ([{"sensor_id": "forecast-bmkg"}],
                                   [(T0 + dt.timedelta(hours=i), "forecast-bmkg", m, 30.0) for i in range(3)
                                    for m in ("fc_temp", "fc_wind_speed")])


def gaps(rd):
    g = [(m, v) for _t, s, m, v in rd if s == "forecast-gap"]
    assert {m for m, _ in g} == {"fc_temp_gap", "fc_wind_speed_gap"}, g
    return {v for _m, v in g}


os.environ["PACK_OUT"] = tempfile.mkdtemp()
os.environ.update(FORECAST_BMKG="1", FORECAST_BMKG_ADM4="51.03.05.2002", FORECAST_OPENMETEO="1")
os.environ.pop("NODE_SCALE", None)
A._pack_on = lambda pid: False
sens, rd = A.fetch(Hot())
assert len(n_of(sens, "forecast-om")) == 7
assert gaps(rd) == {0.0}, f"fresh: the gap is against the node's own point: {gaps(rd)}"
saved = {sid for _t, sid, *_ in A._load_rows("om")}
assert saved == {"forecast-om"}, f"the rows file keeps the own point only: {saved}"
os.utime(A._stamp_file("bmkg"), (0, 0))                  # only BMKG is due now, so the gap reads om from the file
sens, rd = A.fetch(Hot())
assert [s["sensor_id"] for s in sens if s["sensor_id"] != "forecast-gap"] == ["forecast-bmkg"], sens
assert gaps(rd) == {0.0}, f"from the rows file: {gaps(rd)}"
print("test_forecast_territory: ok")
sys.exit(0)
