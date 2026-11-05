"""The forecast pack, against BMKG's and Open-Meteo's real answers for node #1's point on 7 September 2026.

Run: PYTHONPATH=/tmp/stub:app python3 tests/test_forecast.py
The fixtures are the payloads as they came back, saved whole. What is checked is what fails silently: a village
code for the wrong village, a unit that changed under us, and a forecast with no issue time — which cannot be
told from a fresh one afterwards.
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packs", "forecast"))
import adapter as A  # noqa: E402

LAT, LON = -8.8271, 115.15709
ADM4 = "51.03.05.2002"


def fixture(n):
    with open(os.path.join(ROOT, "tests/data", n)) as f:
        return json.load(f)


class R:
    def __init__(s, j): s.j = j
    def raise_for_status(s): pass
    def json(s): return s.j


class HC:
    def __init__(s, j): s.j = j
    def get(s, url, params=None, headers=None, timeout=None): return R(s.j)


# ---- the point. A Permendagri code is six digits of opaque; the only check that means anything is where BMKG
# says it is. 51.03.05.2002 is Ungasan, Kuta Selatan, Badung — 0.19 km from node #1.
bm = fixture("bmkg_ungasan_2026-09-07.json")
loc = bm["lokasi"]
assert (loc["kotkab"], loc["kecamatan"], loc["desa"]) == ("Badung", "Kuta Selatan", "Ungasan"), loc
km = A._km(LAT, LON, loc["lat"], loc["lon"])
assert km < 0.5, f"the forecast point must be this node's, not another village: {km:.2f} km"

sensors, readings = A.bmkg(HC(bm), ADM4, LAT, LON)
assert len(sensors) == 1 and sensors[0]["sensor_id"] == "forecast-bmkg"
assert sensors[0]["kind"] == "model" and sensors[0]["local"] is False, "a forecast is never a measurement here"
assert sensors[0]["meta"]["km_from_node"] < 0.5
assert sensors[0]["scale"] == "community", "this pack describes an address, not a region"

# ---- the issue time, stored per value. A forecast that has stopped refreshing reads exactly like a current one.
issued = A._utc(bm["data"][0]["cuaca"][0][0]["analysis_date"])
assert issued is not None and sensors[0]["meta"]["issued"] == issued.isoformat()
lead = {v for _ts, _s, m, v in readings if m == "fc_lead_hours"}
assert lead and all(l >= 0 for l in lead), "every value says how far ahead of its own forecast it is"

# ---- units as BMKG documents them, carried through unchanged. ws is km/h, wd_deg is degrees the wind comes FROM.
step = bm["data"][0]["cuaca"][0][0]
got = {(ts, m): v for ts, _s, m, v in readings}
ts0 = A._utc(step["utc_datetime"])
for key, metric in (("t", "fc_temp"), ("hu", "fc_humidity"), ("ws", "fc_wind_speed"),
                    ("wd_deg", "fc_wind_direction"), ("tcc", "fc_cloud"), ("tp", "fc_rain")):
    if step.get(key) is not None and (ts0, metric) in got:
        assert got[(ts0, metric)] == float(step[key]), f"{metric} was changed on the way in"

# ---- Open-Meteo. Its wind is km/h by default, which is what makes the gap channel subtractable from BMKG's.
om = fixture("openmeteo_ungasan_2026-09-07.json")
assert om["hourly_units"]["wind_speed_10m"] == "km/h", \
    "BMKG publishes km/h; if Open-Meteo ever changes default units the gap channel silently compares apples to pears"
PT = {"sid": "forecast-om", "cell": None, "lat": LAT, "lon": LON}
osens, oread = A.openmeteo(HC(om), [PT])
assert osens[0]["sensor_id"] == "forecast-om" and osens[0]["kind"] == "model"
# Open-Meteo has no model run time. Recording a fetch time as an issue time would be inventing provenance.
assert osens[0]["meta"]["issued"] is None and osens[0]["meta"]["fetched"], \
    "no issue time is published, so none is claimed"

# ---- the gap channel, only where both sources speak for the same hour
sg, gr = A.gap(readings, oread)
if gr:
    assert sg[0]["sensor_id"] == "forecast-gap"
    assert {m for _ts, _s, m, _v in gr} <= {"fc_temp_gap", "fc_wind_speed_gap"}
    assert all(v >= 0 for _ts, _s, _m, v in gr), "a gap is a distance, never signed toward one source"
assert A.gap(readings, []) == ([], []), "one source alone has nothing to disagree with"

# ---- the horizon. The card and the report want a day; the sources offer three.
horizon = max(ts for ts, _s, _m, _v in readings) if readings else None
if horizon:
    assert horizon <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=A.HOURS + 3), \
        "the pack stores the next day, not everything BMKG will say"

# ---- this pack never speaks. Three wrong warnings reached node #1's Telegram on 7 September; a forecast pack
# that starts talking is the next batch.
import yaml  # noqa: E402
rules = yaml.safe_load(open(os.path.join(ROOT, "packs/forecast/rules.yml")))
assert rules and all(r.get("contributes") == "report" for r in rules), "no rule here may have a level"
assert all("message" not in r for r in rules), "no rule here may have a message"
assert not os.path.exists(os.path.join(ROOT, "packs/forecast/cells.yml")), \
    "a forecast is not measured here and is nobody's Index cell"

# ---- the wind field the map draws moving: 64 points in ONE request, answered in the order asked, south to north and
# west to east, so the page reads row j, column i without working out where a point is.
wg = fixture("openmeteo_wind_grid_ungasan_2026-10-07.json")
lats, lons = A.wind_grid(LAT, LON)
assert len(lats) == len(lons) == 8 and lats == sorted(lats) and lons == sorted(lons), "south to north, west to east"
assert abs(lats[-1] - lats[0] - 60 / 110.574) < 1e-3, "the square is 2 x FORECAST_WIND_KM tall"
assert len(wg) == 65 and all(abs(p["latitude"] - lats[k // 8]) < .06 and abs(p["longitude"] - lons[k % 8]) < .06 for k, p in enumerate(wg[:64])), \
    "Open-Meteo answers in the order asked, within one model cell (cell_selection=nearest, never a land cell 12 km off)"
assert wg[0]["hourly_units"]["wind_speed_10m"] == "km/h", "the field is km/h, as the point forecast stores it"
_real_now = A.datetime
class _At(dt.datetime):
    @classmethod
    def now(cls, tz=None): return dt.datetime(2026, 10, 7, 6, 50, tzinfo=dt.timezone.utc)
A.datetime = _At
wf = A.wind_field(HC(wg), LAT, LON)
A.datetime = _real_now
assert wf["n"] == 8 and len(wf["times"]) == len(wf["speed_kmh"]) == len(wf["from_deg"]) and 24 <= len(wf["times"]) <= 26, len(wf["times"])
assert len(wf["speed_kmh"][0]) == 8 and len(wf["speed_kmh"][0][0]) == 8, "time, then row (south to north), then column"
k = wg[3 * 8 + 5]["hourly"]["time"].index(wf["times"][0][:-1])
assert wf["speed_kmh"][0][3][5] == wg[3 * 8 + 5]["hourly"]["wind_speed_10m"][k], "row 3, column 5 is point 29"
assert len(wf["at_node"]["speed_kmh"]) == len(wf["times"]) and wf["at_node"]["speed_kmh"][0] == wg[64]["hourly"]["wind_speed_10m"][k], \
    "the readout is the node's own point, asked as the 65th, not a value picked off the grid"
try:
    A.wind_field(HC(wg[:10]), LAT, LON); raise AssertionError("a short answer must be refused")
except ValueError:
    pass

# ---- 72 hours, and the five variables a day needs. A synthetic answer built from now, so the cut is where we say it is.
def om_payload(extra=(), hours=100):
    """An Open-Meteo hourly answer: every OM_HOURLY key, value = the hour's index, starting two hours ago."""
    t0 = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=2)
    keys = A.OM_HOURLY.split(",") + list(extra)
    h = {"time": [(t0 + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]}
    h.update({k: [float(i) for i in range(hours)] for k in keys})
    return {"latitude": LAT, "longitude": LON, "hourly": h}


assert A.HOURS == 72
_, rows = A.openmeteo(HC(om_payload()), [PT])
now = dt.datetime.now(dt.timezone.utc)
assert rows and max(ts for ts, *_ in rows) <= now + dt.timedelta(hours=72), "nothing past 72 hours is kept"
assert max(ts for ts, *_ in rows) > now + dt.timedelta(hours=70), "and the 72 hours are kept, not 24"
assert min(ts for ts, *_ in rows) >= now - dt.timedelta(hours=1), "the past is not kept"
NEW5 = {"wind_gusts_10m": "fc_wind_gusts", "precipitation_probability": "fc_rain_prob", "shortwave_radiation": "fc_shortwave",
        "et0_fao_evapotranspiration": "fc_et0", "soil_moisture_0_to_1cm": "fc_soil_moisture"}
for k, m in NEW5.items():
    assert k in A.OM_HOURLY.split(",") and A.OM_MAP[k] == m, (k, m)
assert {m for _ts, _s, m, _v in rows} >= set(NEW5.values()) | {"fc_lead_hours"}
# a multi-point answer is a list, and every point gets its own sensor, its cell in its meta
pts = [PT, {"sid": "forecast-om-8a1", "cell": "8a1", "lat": LAT + .1, "lon": LON}]
ss, rr = A.openmeteo(HC([om_payload(), om_payload()]), pts)
assert [x["sensor_id"] for x in ss] == ["forecast-om", "forecast-om-8a1"] and ss[1]["meta"]["cell"] == "8a1"
assert {s for _ts, s, *_ in rr} == {"forecast-om", "forecast-om-8a1"}
# the sensor's place is where the model ANSWERED from, and the cell asked for is in meta: Days counts cells by the first
ans = [dict(om_payload(), latitude=-8.75, longitude=115.25), dict(om_payload(), latitude=-8.75, longitude=115.25)]
ss2, _ = A.openmeteo(HC(ans), pts)
assert {(x["lat"], x["lon"]) for x in ss2} == {(-8.75, 115.25)} and [x["meta"]["cell"] for x in ss2] == [None, "8a1"], ss2
cs2, _ = A.cams(HC(ans), pts)
assert {(x["lat"], x["lon"]) for x in cs2} == {(-8.75, 115.25)} and cs2[1]["meta"]["cell"] == "8a1"
try:
    A.openmeteo(HC([om_payload()]), pts); raise AssertionError("a short answer must be refused")
except ValueError:
    pass
import yaml  # noqa: E402,F811
ch = {(c["source"], c["metric"]): c for c in yaml.safe_load(open(os.path.join(ROOT, "packs/forecast/channels.yml")))}
pk = yaml.safe_load(open(os.path.join(ROOT, "packs/forecast/pack.yaml")))
for m, u in (("fc_wind_gusts", "km/h"), ("fc_rain_prob", "%"), ("fc_shortwave", "W/m²"), ("fc_et0", "mm"), ("fc_soil_moisture", "m³/m³")):
    c = ch[("forecast-om", m)]
    assert c["role"] == "derived" and c["comparable"] is False and c["unit"] == u, (m, c)
    assert m in pk["metrics"], f"{m} is declared in pack.yaml"

# ---- Task 3: CAMS air and marine. Names and units were read from the live APIs' own hourly_units.
def hourly_payload(keys, lat=LAT, lon=LON, hours=100):
    t0 = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=2)
    h = {"time": [(t0 + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]}
    h.update({k: [float(i) for i in range(hours)] for k in keys})
    return {"latitude": lat, "longitude": lon, "hourly": h}


assert A.CAMS == "https://air-quality-api.open-meteo.com/v1/air-quality"
assert A.MARINE == "https://marine-api.open-meteo.com/v1/marine"
asked = []
class Spy:
    def __init__(s, j): s.j = j
    def get(s, url, params=None, headers=None, timeout=None): asked.append((url, params)); return R(s.j)


# 72 hours ahead is asked for, not whatever is left of the UTC day: forecast_days=4 always reaches past now + 72 h, and
# the rows are trimmed at HOURS. The wind field keeps its own two days.
asked.clear()
_, rr = A.openmeteo(Spy(om_payload(hours=140)), [PT])
assert asked[0][1]["forecast_days"] * 24 >= 72 + 24, "from midnight UTC, four days always reaches 72 h ahead"
assert max(t for t, *_ in rr) <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=72), "an answer longer than 72 h is trimmed"
asked.clear(); A.wind_field(Spy(wg), LAT, LON)
assert asked[0][1]["forecast_days"] == 2, "the map's wind field keeps its own next day"
asked.clear()

cams_pts = [PT, {"sid": "forecast-om-8a1", "cell": "8a1", "lat": LAT + .1, "lon": LON}]
cs, cr = A.cams(Spy([hourly_payload(["pm2_5", "uv_index"]), hourly_payload(["pm2_5", "uv_index"])]), cams_pts)
assert len(asked) == 1, "one call for all points"
assert asked[0][1]["forecast_days"] * 24 >= 72 + 24
assert asked[0][0] == A.CAMS and asked[0][1]["hourly"] == "pm2_5,uv_index" and asked[0][1]["forecast_days"] == 4
assert asked[0][1]["latitude"].count(",") == 1, "multi-location: the points go in one request"
assert [x["sensor_id"] for x in cs] == ["forecast-cams", "forecast-cams-8a1"] and cs[1]["meta"]["cell"] == "8a1"
assert {m for _t, _s, m, _v in cr} == {"fc_pm25", "fc_uv", "fc_lead_hours"}
assert max(t for t, *_ in cr) <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=72)
# a single-point answer is a dict, a multi-point answer a list: both parse
cs1, cr1 = A.cams(Spy(hourly_payload(["pm2_5", "uv_index"])), [PT])
assert [x["sensor_id"] for x in cs1] == ["forecast-cams"] and cr1

ms_keys = ["wave_height", "swell_wave_height", "swell_wave_period", "swell_wave_direction"]
os.environ["COAST_MAX_KM"] = "30"
asked.clear()
ms, mr = A.marine(Spy(hourly_payload(ms_keys, LAT - .035, LON - .03)), [PT])
assert len(asked) == 1 and asked[0][0] == A.MARINE and asked[0][1]["hourly"] == ",".join(ms_keys) and asked[0][1]["forecast_days"] == 4
assert [x["sensor_id"] for x in ms] == ["forecast-marine"]
assert (ms[0]["lat"], ms[0]["lon"]) == (LAT - .035, LON - .03), "the sea cell the API snapped to is stored"
assert {m for _t, _s, m, _v in mr} == {"fc_wave_m", "fc_swell_m", "fc_swell_s", "fc_swell_dir", "fc_lead_hours"}
assert A.marine(Spy(hourly_payload(ms_keys, LAT + 1.0, LON)), [PT]) == ([], []), "a sea cell 110 km off is not this node's sea (COAST_MAX_KM)"
for src, mets in (("forecast-cams", ("fc_pm25", "fc_uv")), ("forecast-marine", ("fc_wave_m", "fc_swell_m", "fc_swell_s", "fc_swell_dir"))):
    for m in mets + ("fc_lead_hours",):
        c = ch[(src, m)]
        assert c["role"] == "derived" and c["comparable"] is False and c["unit"], (src, m, c)
assert (ch[("forecast-cams", "fc_pm25")]["unit"], ch[("forecast-marine", "fc_swell_dir")]["unit"]) == ("µg/m³", "°")

# ---- the cadence. The pack runs in the core 300 s loop; FORECAST_POLL_HOURS is how often it may ask, and a restart
# or a failed fetch must not ask again sooner. 13 Oct: asking every poll spent Open-Meteo's daily limit by 06:15 UTC.
# Each source has its own stamp, out/forecast.<source>.last, so one that is refused does not hold the others.
import tempfile  # noqa: E402
os.environ["NODE_SCALE"] = "home"   # one point a source, so these fixtures answer one payload; the territory is tests/test_forecast_territory.py
real_pack_on, coast = A._pack_on, [False]
A._pack_on = lambda pid: coast[0] and pid == "coast"     # never the host's own PACKS_DIR: coast is off unless a test turns it on
os.environ["PACK_OUT"] = tempfile.mkdtemp()
calls = []
class Count:
    def get(s, url, params=None, headers=None, timeout=None): calls.append(url); raise RuntimeError("429")
os.environ.update(FORECAST_OPENMETEO="1", FORECAST_BMKG="0", NODE_LAT=str(LAT), NODE_LON=str(LON), FORECAST_POLL_HOURS="6")
A.fetch(Count()); first = len(calls)
assert first == 3, f"the refused point, the wind field on its own stamp, and the air are each asked once: {calls}"
A.fetch(Count()); A.fetch(Count())
assert len(calls) == first, "a second poll inside the retry wait asks nothing, even after a failure"
A.fetch(Count(), force=True)
assert len(calls) == 2 * first, "`planetai run forecast fetch` asks now"
stamp = lambda src: os.path.join(os.environ["PACK_OUT"], f"forecast.{src}.last")  # noqa: E731
assert not os.path.exists(os.path.join(os.environ["PACK_OUT"], "forecast.last")), "one stamp a source, not one for the pack"
for src in ("om", "wind", "cams"):
    os.utime(stamp(src), (0, 0))
A.fetch(Count())
assert len(calls) == 3 * first, "once the hours have passed, it asks again"


def aged(src, minutes):
    """Move a stamp `minutes` further into the past and say whether the source is due."""
    m = os.stat(stamp(src)).st_mtime - minutes * 60
    os.utime(stamp(src), (m, m))
    return A._due(src)


# a failure makes the source due again in 30 minutes: not on the next 300 s poll, and not after six hours
assert A.RETRY_S == 1800
A._stamp("om", ok=False)
assert not A._due("om") and not aged("om", 25), "a refused source is not asked again on the next poll or two"
assert aged("om", 10), "...but it is asked again after half an hour"
# a success is the full wait
A._stamp("om")
assert not aged("om", 31) and not aged("om", 300) and aged("om", 60), "a source that answered waits FORECAST_POLL_HOURS"
assert A._due("om", force=True) and A._due("never-stamped"), "force asks, and a source never asked is due"
os.environ["FORECAST_POLL_HOURS"] = "0.1"            # a poll shorter than the retry: the retry never waits longer than the poll
A._stamp("om", ok=False)
assert aged("om", 7), "the retry wait is never longer than FORECAST_POLL_HOURS"
os.environ["FORECAST_POLL_HOURS"] = "6"


class Route:
    """A fake hc that answers by URL, records what it was asked, and fails the URLs in `down`."""
    def __init__(s, down=()): s.down, s.asked = set(down), []
    def get(s, url, params=None, headers=None, timeout=None):
        s.asked.append(url)
        if url in s.down:
            raise RuntimeError("429")
        return R({A.BMKG: bm, A.OPEN_METEO: om_payload(),
                   A.CAMS: hourly_payload(["pm2_5", "uv_index"]),
                   A.MARINE: hourly_payload(ms_keys, LAT - .035, LON - .03)}[url])


def fresh(**env):
    os.environ["PACK_OUT"] = tempfile.mkdtemp()
    os.environ.update({"FORECAST_BMKG": "0", "FORECAST_OPENMETEO": "1", "FORECAST_BMKG_ADM4": ADM4}); os.environ.update(env)
    coast[0] = False
    A.write_wind_field = lambda *a: {}                    # the field is its own source ("wind"); counted above. None would be a failure


# an unwritable out/ asks nothing: the stamp is written before the request, so the failure is before it, not after
# (stamped after, the source was due again in 300 s: ~20,700 location-calls a day on a community node, the cap of 13 Oct)
fresh(FORECAST_BMKG="1")
os.environ["PACK_OUT"] = os.path.join(tempfile.mkdtemp(), "out")
open(os.environ["PACK_OUT"], "w").write("a file where the folder should be")
hc = Route()
try:
    A.fetch(hc)
    raise AssertionError("an unwritable out/ must stop the fetch")
except OSError:
    pass
assert hc.asked == [], f"nothing may be asked when the stamp cannot be written: {hc.asked}"

# one source refused: the others still fetch and store, and only the refused one waits 30 minutes
fresh(FORECAST_BMKG="1")
hc = Route(down=[A.OPEN_METEO]); sens, rd = A.fetch(hc)
assert {s["sensor_id"] for s in sens} == {"forecast-bmkg", "forecast-cams"}, "BMKG and the air answered and are stored"
assert not A._due("bmkg") and not A._due("cams") and not A._due("om")
assert aged("om", 31) and not aged("bmkg", 31) and not aged("cams", 31), "the refused one retries in 30 minutes, the others in six hours"
# two due sources make exactly two calls, a source that is not due makes none
fresh(FORECAST_BMKG="1"); A._stamp("om")
hc = Route(); A.fetch(hc)
assert sorted(hc.asked) == sorted([A.BMKG, A.CAMS]), f"bmkg and cams are due, om is not: {hc.asked}"
hc = Route(); A.fetch(hc)
assert hc.asked == [], "nothing is due now"
os.utime(stamp("om"), (0, 0))
hc = Route(); A.fetch(hc)
assert hc.asked == [A.OPEN_METEO], f"only om is due again: {hc.asked}"
# the point answers and the field is refused: the points are stored on om's own clock, and only the field is asked again
# in 30 minutes, as a source of its own, so a field-only failure never re-asks the 7 + 7 points
fresh(FORECAST_BMKG="0")
def _no_field(*a): raise RuntimeError("429")
A.write_wind_field = _no_field
sens, rd = A.fetch(Route())
assert [s["sensor_id"] for s in sens] == ["forecast-om", "forecast-cams"] and rd, "the point forecast is kept"
assert not A._due("om") and not aged("om", 31) and aged("om", 340), "om keeps its full wait"
assert not A._due("wind") and aged("wind", 31), "and the field is asked again in half an hour, not six hours"
hc = Route(); wind_asked = []
A.write_wind_field = lambda *a: wind_asked.append(1) or {}
A._stamp("om")
os.utime(stamp("wind"), (0, 0))
sens, rd = A.fetch(hc)
assert hc.asked == [] and wind_asked == [1], f"only the field is due: om and cams are not asked again: {hc.asked}"
fresh(FORECAST_BMKG="0"); os.environ["FORECAST_OPENMETEO"] = "0"; wind_asked.clear()
A.write_wind_field = lambda *a: wind_asked.append(1) or {}
A.fetch(Route())
assert wind_asked == [] and not os.path.exists(stamp("wind")), "the field is behind the same FORECAST_OPENMETEO switch"
# ---- marine runs only while the coast pack is on, and only with Open-Meteo on
fresh(FORECAST_BMKG="0")
hc = Route(); A.fetch(hc)
assert A.MARINE not in hc.asked and A.CAMS in hc.asked, f"coast is off, so no sea: {hc.asked}"
fresh(FORECAST_BMKG="0"); coast[0] = True
hc = Route(); sens, rd = A.fetch(hc)
assert hc.asked.count(A.MARINE) == 1 and {s["sensor_id"] for s in sens} == {"forecast-om", "forecast-cams", "forecast-marine"}, hc.asked
for sid in ("forecast-om", "forecast-cams", "forecast-marine"):
    assert any(s == sid and m == "fc_lead_hours" for _t, s, m, _v in rd), f"{sid} stores how far ahead each value is"
assert not A._due("om") and not A._due("cams") and not A._due("marine"), "each of the three has stamped its own clock"
fresh(FORECAST_BMKG="0"); os.environ["FORECAST_OPENMETEO"] = "0"
hc = Route(); sens, rd = A.fetch(hc)
assert hc.asked == [] and not sens, f"Open-Meteo is off, and that switch gates the air and the sea too: {hc.asked}"
fresh(FORECAST_BMKG="0"); os.environ.pop("FORECAST_OPENMETEO")
hc = Route(); A.fetch(hc)
assert hc.asked == [], "FORECAST_OPENMETEO unset is off"
# a sea cell too far off: asked once, stamped as answered, and nothing stored
fresh(FORECAST_BMKG="0"); coast[0] = True
class FarSea(Route):
    def get(s, url, params=None, headers=None, timeout=None):
        return R(hourly_payload(ms_keys, LAT + 1.0, LON)) if url == A.MARINE else Route.get(s, url, params, headers, timeout)
sens, rd = A.fetch(FarSea())
assert "forecast-marine" not in {s["sensor_id"] for s in sens} and not A._due("marine") and not aged("marine", 31), \
    "a node that is not coastal is not asked again in half an hour"
A._pack_on = real_pack_on                              # the dedicated test below is the real loader

# ---- the gap survives the sources keeping different clocks. One source is fetched alone, the other's last rows are on
# disk (out/forecast.<source>.rows.json, future hours only), and the gap is computed against them.
def future(metric, sid, k0=1, n=6, f=lambda i: 20.0 + i):
    t0 = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    return [(t0 + dt.timedelta(hours=k0 + i), sid, metric, f(i)) for i in range(n)]


bmkg_calls = []
fake_bmkg = lambda hc, adm4, la, lo: (bmkg_calls.append(1) or [A._sensor("forecast-bmkg", "BMKG", la, lo, {})],  # noqa: E731
                                      future("fc_temp", "forecast-bmkg") + future("fc_wind_speed", "forecast-bmkg", f=lambda i: 10.0))
real_bmkg, A.bmkg = A.bmkg, fake_bmkg
fresh(FORECAST_BMKG="1"); A._stamp("om"); A._stamp("cams")
A._save_rows("om", future("fc_temp", "forecast-om", k0=-3, f=lambda i: 23.0 + i) + future("fc_wind_speed", "forecast-om", k0=-3, f=lambda i: 12.0)
             + future("fc_cloud", "forecast-om", k0=-3))
hc = Route(); sens, rd = A.fetch(hc)
assert hc.asked == [] and bmkg_calls == [1], "only bmkg is due"
gp = [(t, m, v) for t, s_, m, v in rd if s_ == "forecast-gap"]
assert {m for _t, m, _v in gp} == {"fc_temp_gap", "fc_wind_speed_gap"} and "forecast-gap" in {x["sensor_id"] for x in sens}, \
    "bmkg alone, om's last rows on disk: the gap is still made"
assert all(t > dt.datetime.now(dt.timezone.utc) for t, _m, _v in gp), "only future hours, the stored past is dropped"
assert {v for _t, m, v in gp if m == "fc_wind_speed_gap"} == {2.0} and {v for _t, m, v in gp if m == "fc_temp_gap"} == {7.0}, "the hours both cover: 1 and 2 ahead"
# the same the other way round: om fetched alone against bmkg's stored rows
fresh(FORECAST_BMKG="1"); A._stamp("bmkg"); A._stamp("cams")
A._save_rows("bmkg", future("fc_temp", "forecast-bmkg"))
sens, rd = A.fetch(Route())
assert any(m == "fc_temp_gap" for _t, _s, m, _v in rd), "om alone, bmkg's last rows on disk: the gap is still made"
# nothing stored for the other source: no gap and no error
fresh(FORECAST_BMKG="1"); A._stamp("om"); A._stamp("cams")
sens, rd = A.fetch(Route())
assert [x["sensor_id"] for x in sens] == ["forecast-bmkg"] and not any(m.endswith("_gap") for _t, _s, m, _v in rd)
open(A._rows_file("om"), "w").write("{not json")
os.utime(stamp("bmkg"), (0, 0))
sens, rd = A.fetch(Route())
assert [x["sensor_id"] for x in sens] == ["forecast-bmkg"], "a rows file that does not parse is no gap, not a failure"
A.bmkg = real_bmkg

# _pack_on asks the loader that decides it: PACKS_ENABLED, or every pack in PACKS_DIR when that is blank
import packs as P  # noqa: E402
_real_dir = P.PACKS_DIR
P.PACKS_DIR = __import__("pathlib").Path(tempfile.mkdtemp())
for pid in ("coast", "forecast"):
    (P.PACKS_DIR / pid).mkdir(); (P.PACKS_DIR / pid / "pack.yaml").write_text(f"id: {pid}\n")
os.environ["PACKS_ENABLED"] = "forecast"
assert A._pack_on("forecast") and not A._pack_on("coast")
os.environ["PACKS_ENABLED"] = "forecast,coast"
assert A._pack_on("coast")
P.PACKS_DIR = _real_dir; os.environ.pop("PACKS_ENABLED")

# Open-Meteo off (the default) asks it nothing, BMKG still answers
fresh(FORECAST_BMKG="1"); os.environ.pop("FORECAST_OPENMETEO")
hc = Route(); sens, rd = A.fetch(hc)
assert hc.asked == [A.BMKG] and [s["sensor_id"] for s in sens] == ["forecast-bmkg"], hc.asked

print(f"test_forecast: ok — {loc['desa']}, {km*1000:.0f} m from the node, issued {issued:%d %b %H:%M} UTC, "
      f"{len(readings)} readings, {len(gr)} gap values, and not one thing it can say out loud")
