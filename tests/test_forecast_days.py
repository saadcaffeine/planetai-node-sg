"""/forecast's `days` and `lines`, and the `ahead:` a pack declares (docs/SPEC_next_days.md §4).

Run: PACKS_DIR=packs PYTHONPATH=app python3 tests/test_forecast_days.py
     WRITE_FIXTURES=1 PACKS_DIR=packs PYTHONPATH=app python3 tests/test_forecast_days.py   (regenerates tests/data/forecast/)

days.build is pure: hours in, the three local days out, the issues' lines handed in. The four JSON files under
tests/data/forecast/ are whole /forecast answers that days.answer produced; the page's tests read them.
"""
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packs", "forecast"))
os.environ.setdefault("PACKS_DIR", "packs")
import days as D  # noqa: E402
import packs  # noqa: E402
from issues import engine  # noqa: E402

TZ = "Asia/Makassar"                       # UTC+8
Z = ZoneInfo(TZ)
UTC = timezone.utc
NOW = datetime(2026, 11, 3, 6, 20, tzinfo=UTC)          # 14:20 on 3 Nov in Bali
LINES = {"air": {"value": 15, "unit": "µg/m³", "dp": 0}, "heat": {"value": 35, "unit": "°C", "dp": 1}}
OM, CAMS, MAR, BMKG = "forecast-om", "forecast-cams", "forecast-marine", "forecast-bmkg"


def L(day, hour):
    """Local hour `hour` on `day` November 2026, as the ISO string the database hands back (UTC)."""
    return datetime(2026, 11, day, hour, tzinfo=Z).astimezone(UTC).isoformat()


def step(day, hour, source, **m):
    return {"ts": L(day, hour), "source": source, **m}


def build(steps, lines=LINES, own=None, now=NOW):
    return D.build(steps, lines, TZ, now, own or {})


# ---- the cuts: local days in Asia/Makassar, "rest" from the next whole hour to midnight
steps = [step(3, 13, CAMS, fc_pm25=10), step(3, 14, CAMS, fc_pm25=20), step(3, 15, CAMS, fc_pm25=30),
         step(3, 23, CAMS, fc_pm25=40), step(4, 0, CAMS, fc_pm25=50), step(4, 23, CAMS, fc_pm25=60),
         step(5, 0, CAMS, fc_pm25=70), step(6, 0, CAMS, fc_pm25=80)]
d = build(steps)
assert [(x["date"], x["part"]) for x in d] == [("2026-11-03", "rest"), ("2026-11-04", "day"), ("2026-11-05", "day")], d
a0, a1, a2 = (x["rows"]["air"] for x in d)
assert a0["value"] == 35 and a0["peak"] == 40 and a0["peak_at"] == "23:00" and a0["n"] == 2, \
    "23:00 local is 15:00 UTC and is still the 3rd; 13:00 and 14:00 are behind us; rest starts at 15:00"
assert a1["value"] == 55 and a1["n"] == 2, "00:00 local on the 4th is the 4th, not the 3rd"
assert a2["value"] == 70 and a2["n"] == 1, "00:00 on the 6th is a fourth day and is not drawn"
assert build(steps, now=datetime(2026, 11, 3, 15, 59, tzinfo=UTC))[0]["rows"] == {}, "23:59 local: nothing is left of the 3rd"

# ---- air: the mean, the peak, hours over; state words are the engine's own (near is a tenth below)
air = build([step(3, 15, CAMS, fc_pm25=13), step(3, 16, CAMS, fc_pm25=15)])[0]["rows"]["air"]
assert air == {"value": 14, "unit": "µg/m³", "metric": "fc_pm25", "of": "mean", "peak": 15, "peak_at": "16:00",
               "source": CAMS, "line": 15, "state": "near", "hours_over": 0, "n": 2}, air
air = build([step(3, 15, CAMS, fc_pm25=20), step(3, 16, CAMS, fc_pm25=30), step(3, 17, CAMS, fc_pm25=4)])[0]["rows"]["air"]
assert air["value"] == 18 and air["state"] == "over" and air["hours_over"] == 2 and air["peak"] == 30
air = build([step(3, 15, CAMS, fc_pm25=5), step(3, 16, CAMS, fc_pm25=7)])[0]["rows"]["air"]
assert air["state"] == "under" and air["hours_over"] == 0
for v in (3, 14, 16):
    got = build([step(3, 15, CAMS, fc_pm25=v)])[0]["rows"]["air"]["state"]
    assert got == engine._line_key({"kind": "sensed"}, v, {"value": 15}), "the engine's own comparison"

# the state is the engine's on the figure as measured, not as shown: only `value` is rounded
a = build([step(3, 15, CAMS, fc_pm25=15.3)])[0]["rows"]["air"]
assert a["value"] == 15 and a["state"] == "over" and a["hours_over"] == 1, "15.3 is over 15; shown as 15, rounding must not flip it"
a = build([step(3, 15, CAMS, fc_pm25=14.0)])[0]["rows"]["air"]
assert a["state"] == "near" and a["hours_over"] == 0 and a["value"] == 14
for v in (13.46, 13.5, 14.96, 15.0, 15.04, 15.4, 16.6):
    got = build([step(3, 15, CAMS, fc_pm25=v)])[0]["rows"]["air"]
    assert got["state"] == engine._line_key({"kind": "sensed"}, v, {"value": 15}) and got["hours_over"] == (v > 15), v
for t in range(26, 40):          # a heat figure a hair over the line, which one decimal rounds down onto it
    ap = engine.apparent(t, 70)
    if round(ap, 1) < ap and ap - round(ap, 1) < 0.05:
        break
hl = {"heat": {"value": round(ap, 1), "unit": "°C", "dp": 1}}
h = build([step(3, 15, OM, fc_temp=t, fc_humidity=70)], lines=hl)[0]["rows"]["heat"]
assert h["value"] == hl["heat"]["value"] and h["state"] == "over" and h["hours_over"] == 1, (ap, h)

# ---- heat: the max of `apparent` as the engine computes it, against the heat issue's line
hot = [step(3, 15, OM, fc_temp=33, fc_humidity=80), step(3, 16, OM, fc_temp=28, fc_humidity=60),
       step(3, 17, OM, fc_temp=34, fc_humidity=85)]
heat = build(hot)[0]["rows"]["heat"]
at = [engine.apparent(t, h) for t, h in ((33, 80), (28, 60), (34, 85))]
assert heat["value"] == round(max(at), 1) and heat["of"] == "max" and heat["metric"] == "apparent"
assert heat["line"] == 35 and heat["unit"] == "°C" and heat["source"] == OM and heat["state"] == "over"
assert heat["hours_over"] == sum(1 for x in at if x > 35) == 2 and "also" not in heat
cool = build([step(3, 15, OM, fc_temp=24, fc_humidity=60)])[0]["rows"]["heat"]
assert cool["state"] == "under" and cool["hours_over"] == 0
assert "heat" not in build([step(3, 15, OM, fc_temp=33)])[0]["rows"], "temperature alone is not apparent"

# ---- wind and rain: the highest gust, the day's rain, the wettest 3 hours
wr = build([step(3, h, OM, fc_wind_gusts=g, fc_rain=r) for h, g, r in
            ((15, 20, 0), (16, 25, 2), (17, 38, 3), (18, 30, 5), (19, 10, 1))])[0]["rows"]["wind_rain"]
assert wr == {"gust": 38, "rain_mm": 11.0, "rain_hours": "16:00–19:00", "source": OM, "n": 5}, wr
dry = build([step(3, 15, OM, fc_wind_gusts=12, fc_rain=0)])[0]["rows"]["wind_rain"]
assert dry["rain_mm"] == 0 and dry["rain_hours"] is None
late = build([step(3, 22, OM, fc_rain=1), step(3, 23, OM, fc_rain=4)])[0]["rows"]["wind_rain"]
assert late["rain_hours"] == "22:00–00:00", "a block never runs past the day it belongs to"

# ---- the sea
sea = build([step(3, 15, MAR, fc_wave_m=1.1), step(3, 16, MAR, fc_wave_m=1.43)])[0]["rows"]["sea"]
assert sea == {"value": 1.4, "unit": "m", "metric": "fc_wave_m", "of": "max", "source": MAR, "n": 2}, sea

# ---- a source with no rows leaves its row out; no sources at all is three empty days (Review Focus 1, 2)
assert [x["rows"] for x in build([])] == [{}, {}, {}] and len(build([])) == 3
only = build([step(3, 15, BMKG, fc_temp=30, fc_humidity=70, fc_rain=0.5),
              step(3, 18, BMKG, fc_temp=29, fc_humidity=75, fc_rain=2)])[0]["rows"]
assert set(only) == {"heat", "wind_rain"}, "BMKG alone: heat and wind and rain, no air, no sea"
assert only["heat"]["source"] == BMKG and only["wind_rain"]["source"] == BMKG and only["wind_rain"]["gust"] is None
assert only["wind_rain"]["rain_mm"] == 2.5
assert build(hot, lines={})[0]["rows"] == {} and "heat" not in build(hot, lines={"air": LINES["air"]})[0]["rows"], \
    "a row whose issue is off is left out"

# ---- two sources: Open-Meteo for the detail, BMKG named in `also`
both = build(hot + [step(3, 15, BMKG, fc_temp=30, fc_humidity=70, fc_rain=1, fc_wind_speed=9)] +
             [step(3, 15, OM, fc_wind_gusts=20, fc_rain=0)])[0]["rows"]
assert both["heat"]["source"] == OM and both["heat"]["also"] == [BMKG], both["heat"]
assert both["wind_rain"]["source"] == OM and both["wind_rain"]["also"] == [BMKG]

# ---- hours, not steps: BMKG is 3-hourly, so each of its values stands for 3 hours; Open-Meteo and CAMS are hourly
bm3 = build([step(3, 15, BMKG, fc_temp=33, fc_humidity=80), step(3, 18, BMKG, fc_temp=28, fc_humidity=60),
             step(3, 21, BMKG, fc_temp=34, fc_humidity=85)])[0]["rows"]["heat"]
assert bm3["hours_over"] == 6 and bm3["n"] == 9, ("two 3-hourly steps over the line are 6 hours over, of 9 hours", bm3)
bm_one = build([step(3, 15, BMKG, fc_temp=34, fc_humidity=85), step(3, 18, BMKG, fc_temp=34, fc_humidity=85),
                step(4, 15, BMKG, fc_temp=34, fc_humidity=85)])[1]["rows"]["heat"]
assert bm_one["hours_over"] == 3 and bm_one["n"] == 3, "a day with one value takes the cadence from the source's own series"
assert build([step(3, 15, BMKG, fc_temp=34, fc_humidity=85)])[0]["rows"]["heat"]["n"] == 1, "one value alone, nothing to measure a step by: 1 h"
bw = build([step(3, 15, BMKG, fc_rain=1), step(3, 18, BMKG, fc_rain=2)])[0]["rows"]["wind_rain"]
assert bw["n"] == 6, "wind and rain count hours too"
assert build([step(3, 15, MAR, fc_wave_m=1.0), step(3, 16, MAR, fc_wave_m=1.2)])[0]["rows"]["sea"]["n"] == 2

# ---- a community: the node's own cell is the value, the others say how many cells are over
C1, C2 = "forecast-cams-8a1", "forecast-cams-8a2"
cells = {CAMS: "own", C1: "n1", C2: "n2"}
com = build([step(3, 15, CAMS, fc_pm25=20), step(3, 15, C1, fc_pm25=10), step(3, 15, C2, fc_pm25=30)], own=cells)
assert com[0]["rows"]["air"]["value"] == 20 and com[0]["rows"]["air"]["cells"] == 3 \
    and com[0]["rows"]["air"]["cells_over"] == 2, com[0]["rows"]["air"]
assert build([step(3, 15, CAMS, fc_pm25=20), step(3, 15, C1, fc_pm25=15.3), step(3, 15, C2, fc_pm25=14.0)],
             own=cells)[0]["rows"]["air"]["cells_over"] == 2, "cells over are counted on the unrounded day value too"
solo = build([step(3, 15, CAMS, fc_pm25=20)], own={CAMS: "own"})[0]["rows"]["air"]
assert "cells" not in solo and "cells_over" not in solo, "one cell is no territory"
assert "air" not in build([step(3, 15, C1, fc_pm25=10), step(3, 15, C2, fc_pm25=30)], own=cells)[0]["rows"], \
    "the neighbours alone are not this node's air"
hc = build([step(3, 15, OM, fc_temp=36, fc_humidity=80), step(3, 15, "forecast-om-8a1", fc_temp=24, fc_humidity=50)],
           own={OM: "own", "forecast-om-8a1": "n1"})[0]["rows"]["heat"]
assert hc["cells"] == 2 and hc["cells_over"] == 1 and hc["state"] == "over"

# ---- cells are distinct model grid points, not sensors: res-7 neighbours sit 2.5 km apart and the models are 10-44 km
same = build([step(3, 15, OM, fc_temp=36, fc_humidity=80)] + [step(3, 15, f"forecast-om-n{i}", fc_temp=36, fc_humidity=80)
                                                          for i in range(6)], own={OM: "g0", **{f"forecast-om-n{i}": "g0" for i in range(6)}})
assert "cells" not in same[0]["rows"]["heat"] and "cells_over" not in same[0]["rows"]["heat"], "7 sensors, one grid point: no territory"
pts = {OM: "A", "forecast-om-n0": "A", "forecast-om-n1": "A", "forecast-om-n2": "B", "forecast-om-n3": "B",
       "forecast-om-n4": "B", "forecast-om-n5": "C"}
vals = {"A": (36, 80), "B": (24, 50), "C": (25, 50)}
three = build([step(3, 15, sid, fc_temp=vals[g][0], fc_humidity=vals[g][1]) for sid, g in pts.items()], own=pts)[0]["rows"]["heat"]
assert three["cells"] == 3 and three["cells_over"] == 1, ("3 grid points, one over, however many sensors sit on it", three)
air3 = build([step(3, 15, CAMS, fc_pm25=20)] + [step(3, 15, f"forecast-cams-n{i}", fc_pm25=v) for i, v in enumerate((20, 20, 5, 5, 5, 8))],
             own={CAMS: "A", "forecast-cams-n0": "A", "forecast-cams-n1": "A", "forecast-cams-n2": "B", "forecast-cams-n3": "B",
                  "forecast-cams-n4": "B", "forecast-cams-n5": "C"})[0]["rows"]["air"]
assert air3["cells"] == 3 and air3["cells_over"] == 1, air3

# ---- the whole answer, from rows as the database hands them back
POINT = {"lat": -8.8271, "lon": 115.15709}


def synth(sid, i0=0, n=72, **fns):
    """Readings of one sensor from 15:00 local on the 3rd, one a hour: {metric: f(i)}."""
    t0 = datetime(2026, 11, 3, 15, tzinfo=Z).astimezone(UTC)
    return [{"sensor_id": sid, "ts": (t0 + timedelta(hours=i)).isoformat(), "metric": m, "value": round(f(i), 2)}
            for i in range(i0, n) for m, f in fns.items()]


def hr(i):
    return (15 + i) % 24            # the local hour of step i


def sensor(sid, name, lat=None, lon=None, **meta):
    return {"sensor_id": sid, "name": name, "lat": lat, "lon": lon, "meta": meta}


def om_fns(k=0):
    return dict(fc_temp=lambda i: 26 + 7 * (1 if 10 <= hr(i) <= 16 else 0) + k, fc_humidity=lambda i: 75 - (10 if 10 <= hr(i) <= 16 else 0),
                fc_wind_gusts=lambda i: 18 + (i % 9) * 3, fc_rain=lambda i: 3.0 if hr(i) in (16, 17, 18) and i < 30 else 0.0)


def cams_fns(k=0):
    return dict(fc_pm25=lambda i: 6 + k + (24 if hr(i) in (19, 20, 21) else 0))


def marine_fns():
    return dict(fc_wave_m=lambda i: 0.9 + 0.5 * ((i % 24) / 24))


FETCHED = "2026-11-03T05:00:00+00:00"
OWN_META = dict(fetched=FETCHED, issued=None, km_from_node=0.0)
W_OM = sensor(OM, "Open-Meteo forecast", POINT["lat"], POINT["lon"], cell="own", **OWN_META)
W_CAMS = sensor(CAMS, "Open-Meteo CAMS air forecast", POINT["lat"], POINT["lon"], cell="own", **OWN_META)
W_MAR = sensor(MAR, "Open-Meteo Marine forecast, sea cell 3 km off", -8.86, 115.16, cell="sea", fetched=FETCHED,
               issued=None, distance_km=3.2)       # the marine adapter writes distance_km, not km_from_node
W_BMKG = sensor(BMKG, "BMKG forecast, Ungasan", -8.82, 115.16, cell="bmkg", issued="2026-11-03T00:00:00+00:00",
                fetched=FETCHED, km_from_node=1.2)
BM_FNS = dict(fc_temp=lambda i: 28 + (4 if 10 <= hr(i) <= 16 else 0), fc_humidity=lambda i: 78, fc_rain=lambda i: 0.0)


def bmkg_rows():
    return [r for r in synth(BMKG, 0, 72, **BM_FNS) if (r["ts"] > NOW.isoformat()) and int(r["ts"][11:13]) % 3 == 0]


def answer(who, rows, lines=LINES, ahead=(), hours=24, openmeteo=True, coast=True):
    return D.answer(who=who, rows=rows, issue_lines=lines, ahead=list(ahead), tz=TZ, now=NOW, point=POINT,
                    hours=hours, openmeteo=openmeteo, coast=coast)


def ahead_surf():
    mans = [{"id": "surf", "ahead": {"id": "surf", "title": {"en": "Surf", "es": "Olas", "id": "Ombak"}, "sensor": "surf",
                                       "days": ["ahead_d1", "ahead_d2"]}}]
    meta = {"fetched": FETCHED}
    for loc, t in (("en", "Uluwatu 16:00–18:00 · Impossibles 16:00–18:00"), ("es", "Uluwatu 16:00–18:00"),
                   ("id", "Uluwatu 16.00–18.00")):
        meta[f"ahead_{loc}_d1"], meta[f"ahead_{loc}_d2"] = t, "nothing looks good" if loc == "en" else "nada bueno"
    packs.manifests, packs._sensor_meta = (lambda: mans), (lambda sid: meta if sid == "surf" else None)
    return packs.ahead_lines(NOW, TZ)


marine_rows = synth(MAR, **marine_fns())
FULL_ROWS = (synth(OM, **om_fns()) + synth(CAMS, **cams_fns()) + synth(MAR, **marine_fns()) + bmkg_rows())
full = answer([W_BMKG, W_OM, W_CAMS, W_MAR], FULL_ROWS, ahead=ahead_surf(), hours=72)   # what Next days asks
NEIGH = [("forecast-om-8a1", 2), ("forecast-om-8a2", -3), ("forecast-cams-8a1", 4), ("forecast-cams-8a2", -3)]
com_rows = FULL_ROWS + [r for sid, k in NEIGH for r in synth(sid, **(om_fns(k) if "om" in sid else cams_fns(k * 3)))]
com_who = [W_BMKG, W_OM, W_CAMS, W_MAR] + [sensor(sid, f"Open-Meteo {sid}", cell=sid[-3:], fetched=FETCHED)
                                          for sid, _ in NEIGH]
community = answer(com_who, com_rows, ahead=ahead_surf(), hours=72)
FIXTURES = {
    "full": full,
    "om_off": answer([W_BMKG], bmkg_rows(), openmeteo=False, coast=False, hours=72),
    "none": answer([], [], openmeteo=False, coast=False, hours=72),
    "community": community,
}

# top level, and the nested names the page reads: this is the contract (tools/check_wire.py pins the top level)
assert list(full) == ["point", "sources", "hours", "attribution", "far_from_node", "days", "lines", "openmeteo", "schema"], list(full)
assert full["schema"] == "forecast-v0" and full["openmeteo"] is True
assert [x["part"] for x in full["days"]] == ["rest", "day", "day"]
assert all(set(x) == {"date", "part", "rows"} for x in full["days"])
ROW_KEYS = {"air": {"value", "unit", "metric", "of", "peak", "peak_at", "source", "line", "state", "hours_over", "n"},
            "heat": {"value", "unit", "metric", "of", "source", "line", "state", "hours_over", "n", "also"},
            "wind_rain": {"gust", "rain_mm", "rain_hours", "source", "n", "also"},
            "sea": {"value", "unit", "metric", "of", "source", "n"}}
for x in full["days"]:
    assert list(x["rows"]) == ["air", "heat", "wind_rain", "sea"], "the order of Now's rows, then wind and rain, then the sea"
    for k, row in x["rows"].items():
        assert set(row) == ROW_KEYS[k], (k, set(row) ^ ROW_KEYS[k])
        assert row["state"] in ("over", "near", "under") if "state" in row else True
assert full["days"][0]["rows"]["heat"]["also"] == [BMKG], "BMKG is named beside Open-Meteo"
assert all("cells" not in r for x in full["days"] for r in x["rows"].values()), "a home node has one cell"
assert full["lines"] == [{"pack": "surf", "id": "surf", "title": {"en": "Surf", "es": "Olas", "id": "Ombak"},
                          "days": {"2026-11-04": {"en": "Uluwatu 16:00–18:00 · Impossibles 16:00–18:00", "es": "Uluwatu 16:00–18:00",
                                                  "id": "Uluwatu 16.00–18.00"},
                                   "2026-11-05": {"en": "nothing looks good", "es": "nada bueno", "id": "nada bueno"}}}], full["lines"]
assert set(community["days"][0]["rows"]["air"]) == ROW_KEYS["air"] | {"cells", "cells_over"}
assert set(community["days"][1]["rows"]["heat"]) == ROW_KEYS["heat"] | {"cells", "cells_over"}
assert community["days"][0]["rows"]["air"]["cells"] == 3
assert community["days"][0]["rows"]["air"]["cells_over"] == 1, community["days"][0]["rows"]["air"]

# the same sensors on ONE answered grid point (lat, lon as Open-Meteo answered): no cells in the rows, one in `sources`
one_pt = [dict(w, lat=-8.8, lon=115.1) for w in com_who if w["sensor_id"] in (OM, CAMS) or "-8a" in w["sensor_id"]]
dup = answer([W_BMKG, W_MAR] + one_pt, com_rows, ahead=ahead_surf(), hours=72)
assert all("cells" not in r for x in dup["days"] for r in x["rows"].values()), "7 sensors on one model cell are one cell"
assert {s["sensor_id"]: s.get("cells") for s in dup["sources"]} == {BMKG: None, OM: 1, CAMS: 1, MAR: None}, dup["sources"]

# sources: one entry a source, the cells counted; hours: the node's own point, never a neighbour
assert [s["sensor_id"] for s in community["sources"]] == [BMKG, OM, CAMS, MAR]
assert {s["sensor_id"]: s.get("cells") for s in community["sources"]} == {BMKG: None, OM: 3, CAMS: 3, MAR: None}
assert set(community["sources"][1]) == {"sensor_id", "name", "lat", "lon", "issued", "fetched", "km_from_node", "cells"}
assert {h["source"] for h in community["hours"]} == {BMKG, OM, CAMS, MAR}, {h["source"] for h in community["hours"]}
# an hour with temperature and humidity carries the feels-like heat's line is on (Next days draws heat's 72 h with it)
h_om = next(h for h in full["hours"] if h["source"] == OM and "fc_temp" in h)
assert h_om["apparent"] == round(engine.apparent(h_om["fc_temp"], h_om["fc_humidity"]), 1), h_om
assert all("apparent" not in h for h in full["hours"] if "fc_temp" not in h), "no temperature, no feels-like"
assert community["far_from_node"] is None
assert [s["km_from_node"] for s in community["sources"]][3] == 3.2, "the sea's distance is read from the key the adapter writes"
far_sea = answer([dict(W_MAR, meta={**W_MAR["meta"], "distance_km": 22.0})], marine_rows)
assert far_sea["far_from_node"] is None, "the sea is never the weather point: the classic card reads far_from_node[0] as that"
assert next(x for x in far_sea["sources"] if x["sensor_id"] == MAR)["km_from_node"] == 22.0, "a sea cell far from the node is still said, through its source"
both_far = answer([dict(W_BMKG, meta={**W_BMKG["meta"], "km_from_node": 14.0}), dict(W_MAR, meta={**W_MAR["meta"], "distance_km": 22.0})],
                  bmkg_rows() + marine_rows)
assert both_far["far_from_node"] == [{"sensor_id": BMKG, "km": 14.0}], "only the weather point is far_from_node[0]"
w = answer([dict(W_BMKG, meta={**W_BMKG["meta"], "km_from_node": 14.0})], bmkg_rows())
assert w["far_from_node"] == [{"sensor_id": BMKG, "km": 14.0}]
assert max(h["ts"] for h in answer([W_OM], FULL_ROWS, hours=6)["hours"]) <= (NOW + timedelta(hours=6)).isoformat() \
    and len(answer([W_OM], FULL_ROWS, hours=72)["hours"]) > len(answer([W_OM], FULL_ROWS, hours=6)["hours"])

# a source whose switch is on and has no rows is named; Open-Meteo off says so (Review Focus 1)
gone = answer([W_BMKG, W_OM], synth(OM, **om_fns()) + bmkg_rows())
assert {"sensor_id": CAMS, "absent": True} in gone["sources"] and {"sensor_id": MAR, "absent": True} in gone["sources"]
assert {"sensor_id": MAR, "absent": True} not in answer([W_OM], synth(OM, **om_fns()), coast=False)["sources"], "no coast, no sea asked"
ALL_WHO = [W_BMKG, W_OM, W_CAMS, W_MAR, sensor("forecast-gap", "BMKG against Open-Meteo")]
stale = answer(ALL_WHO, FULL_ROWS + synth("forecast-gap", fc_temp_gap=lambda i: 1.0), openmeteo=False, coast=False, hours=72)
assert stale == FIXTURES["om_off"], "Open-Meteo switched off: the last fetch's om, cams, marine and gap rows are not drawn for 72 h"
nocoast = answer(ALL_WHO, FULL_ROWS)
assert nocoast["openmeteo"] is True
nocoast = answer(ALL_WHO, FULL_ROWS, coast=False)
assert all("sea" not in x["rows"] for x in nocoast["days"]) and all(x["rows"].get("air") for x in nocoast["days"][:2])
assert MAR not in {s["sensor_id"] for s in nocoast["sources"]} and MAR not in {h["source"] for h in nocoast["hours"]}, \
    "coast off drops the sea and keeps the rest of Open-Meteo"
off = FIXTURES["om_off"]
assert off["openmeteo"] is False and not any(s.get("absent") for s in off["sources"]), "off is not absent"
assert [s["sensor_id"] for s in off["sources"]] == [BMKG]
assert all(set(x["rows"]) == {"heat", "wind_rain"} for x in off["days"])
none = FIXTURES["none"]
assert none["sources"] == [] and none["hours"] == [] and len(none["days"]) == 3 and all(x["rows"] == {} for x in none["days"])
assert none["lines"] == [] and none["far_from_node"] is None

# the whole answers, as Task 6 reads them
FX = os.path.join(ROOT, "tests", "data", "forecast")
for name, doc in FIXTURES.items():
    path = os.path.join(FX, f"{name}.json")
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("WRITE_FIXTURES") == "1":
        os.makedirs(FX, exist_ok=True)
        open(path, "w").write(text)
    assert os.path.isfile(path), f"{path} is missing: WRITE_FIXTURES=1 regenerates it"
    assert json.load(open(path)) == json.loads(text), f"{name}.json is not what days.answer produces now"

# ---- `ahead:` a pack's line in Next days
MANS = {"id": "surf", "ahead": {"id": "surf", "title": {"en": "Surf", "es": "Olas", "id": "Ombak"}, "sensor": "surf",
                                  "days": ["ahead_d1", "ahead_d2"]}}
META = {"fetched": "2026-11-03T05:00:00+00:00", "ahead_en_d1": "a" * 200, "ahead_en_d2": "two", "ahead_es_d1": "uno",
        "ahead_es_d2": "dos", "ahead_id_d1": "satu", "ahead_id_d2": "dua"}


def lines_for(mans, meta, now=NOW):
    packs.manifests, packs._sensor_meta = (lambda: mans), (lambda sid: meta if sid == "surf" else None)
    return packs.ahead_lines(now, TZ)


got = lines_for([MANS], META)
assert len(got) == 1 and got[0]["pack"] == "surf" and got[0]["title"] == MANS["ahead"]["title"]
assert got[0]["days"]["2026-11-04"] == {"en": "a" * 160, "es": "uno", "id": "satu"}, "three locales, a key over 160 is cut"
assert got[0]["days"]["2026-11-05"] == {"en": "two", "es": "dos", "id": "dua"}
assert lines_for([], META) == [], "a pack that is off gives no line"
assert lines_for([MANS], dict(META, fetched="2026-11-02T05:00:00+00:00")) == [], "yesterday's fetch is not tomorrow's line"
assert lines_for([MANS], dict(META, fetched="2026-11-02T17:00:00+00:00")) != [], "17:00 UTC is 01:00 on the 3rd in Bali: today"
import time  # noqa: E402
os.environ["TZ"] = "America/Los_Angeles"; time.tzset()
try:
    assert lines_for([MANS], dict(META, fetched="2026-11-02T10:00:00")) == [], "a stamp with no zone is UTC, not the host's"
    assert lines_for([MANS], dict(META, fetched="2026-11-03T05:00:00")) != []
    # a date alone is the date the pack meant (surf writes the spot's local date): it is compared as a local date, never
    # read as UTC midnight, which west of UTC is yesterday evening and kept the line off all day
    LA = "America/Los_Angeles"
    la_now = datetime(2026, 11, 3, 20, 0, tzinfo=ZoneInfo(LA))      # 04:00 UTC on the 4th
    packs.manifests, packs._sensor_meta = (lambda: [MANS]), (lambda sid: dict(META, fetched="2026-11-03") if sid == "surf" else None)
    west = packs.ahead_lines(la_now, LA)
    assert west and list(west[0]["days"]) == ["2026-11-04", "2026-11-05"], ("a date-only fetched that is today west of UTC", west)
    packs._sensor_meta = lambda sid: dict(META, fetched="2026-11-02") if sid == "surf" else None
    assert packs.ahead_lines(la_now, LA) == [], "yesterday's date is not today"
    packs._sensor_meta = lambda sid: dict(META, fetched="2026-11-04T03:00:00") if sid == "surf" else None
    assert packs.ahead_lines(la_now, LA) != [], "a naive stamp stays UTC: 03:00 UTC on the 4th is 19:00 on the 3rd there"
finally:
    os.environ.pop("TZ"); time.tzset()
assert lines_for([MANS], None) == [], "a sensor with no meta"
assert lines_for([MANS], dict(META, fetched=None)) == []
part = lines_for([MANS], {k: v for k, v in META.items() if "_es_" not in k})
assert part[0]["days"]["2026-11-04"] == {"en": "a" * 160, "id": "satu"}, "a locale the pack did not write is left out"
assert lines_for([MANS], {"fetched": META["fetched"]}) == [], "no text, no line"

BAD = [{"id": "Surf!", "title": MANS["ahead"]["title"], "sensor": "surf", "days": ["ahead_d1", "ahead_d2"]},
       {**MANS["ahead"], "title": {"en": "Surf"}},
       {**MANS["ahead"], "sensor": None},
       {**MANS["ahead"], "days": ["ahead_d1"]},
       {**MANS["ahead"], "days": ["ahead_d1", "ahead_d2", "ahead_d3"]},
       {**MANS["ahead"], "days": ["ahead_d1", 2]},
       {**MANS["ahead"], "days": ["d1", "d2"]},
       "surf"]
log = logging.getLogger("planetai.packs")
seen: list = []


class H(logging.Handler):
    def emit(self, r): seen.append(r.getMessage())


log.addHandler(H())
for i, bad in enumerate(BAD):
    seen.clear()
    packs._AHEAD_SAID.clear()
    assert lines_for([{"id": "surf", "ahead": bad}], META) == [] and lines_for([{"id": "surf", "ahead": bad}], META) == []
    assert len(seen) == 1 and "surf" in seen[0] and "ahead" in seen[0], (i, bad, seen)
seen.clear()
assert lines_for([{"id": "surf"}], META) == [] and seen == [], "no ahead: is no problem"

# a broken issue file must not cost /forecast its wind, rain and sea (the Wall reads it too)
os.environ.setdefault("DATABASE_URL", "postgresql://unused/never-connected")
try:
    import routes  # noqa: E402
except ImportError:
    print("  forecast days: routes check skipped (pip install -r app/requirements.txt)")
else:
    import issues  # noqa: E402
    real = issues.load
    def boom(*a, **k): raise ValueError("issue file does not parse")
    issues.load = boom
    try:
        assert routes._issue_lines() == {}, "no lines, so air and heat rows are left out and the rest is served"
    finally:
        issues.load = real
    assert set(routes._issue_lines()) == {"air", "heat"}

print("  forecast days: cuts, rows, territory, sources, ahead lines and the four whole answers hold")
sys.exit(0)
