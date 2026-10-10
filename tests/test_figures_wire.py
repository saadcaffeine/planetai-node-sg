"""The wire part of docs/SPEC_dashboard_figures.md §3: the usual day, an open event's rooms, the stations that
stopped, and GET /issues/days. No database: a capture and hand-made rows.
Run: PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
os.environ.setdefault("PACKS_DIR", "packs")
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
sys.path.insert(0, str(ROOT / "app"))
import issues as I                # noqa: E402
from issues import engine          # noqa: E402


class Settings:
    def get(self, key, default=""):
        return default

    def num(self, key, default):
        return default


SNAP = json.loads((ROOT / "app/issues/fixtures/node1-2026-10-06-events.json").read_text())
DECL = I.load()


def fresh():
    return json.loads(json.dumps(SNAP))


# --- §3.1 the usual day --------------------------------------------------------------------------
ROWS = [{"sensor_id": "a", "metric": "apparent", "hour": 7, "median": 30.0, "p90": 31.0},
        {"sensor_id": "b", "metric": "apparent", "hour": 7, "median": 32.0, "p90": 35.0},
        {"sensor_id": "b", "metric": "temp", "hour": 7, "median": 99.0, "p90": 99.0},       # another metric
        {"sensor_id": "c", "metric": "apparent", "hour": 7, "median": 99.0, "p90": 99.0}]   # another distance
heat = {"metric": "apparent"}
block, why = engine._usual(heat, "room", {"sensors": ["a", "b"]}, ROWS)
assert why is None and block["window_days"] == 14 and block["distance"] == "room", (block, why)
assert len(block["hours"]) == 24 and [h["hour"] for h in block["hours"]] == list(range(24))
assert block["hours"][7] == {"hour": 7, "median": 31.0, "p90": 33.0}, block["hours"][7]
assert block["hours"][8] == {"hour": 8, "median": None, "p90": None}, "an hour with no history is null, not zero"
assert engine._usual(heat, "room", {"sensors": ["a"]}, None) == (None, "unread")
assert engine._usual(heat, "room", None, ROWS) == (None, "no_source")
assert engine._usual(heat, "room", {"sensors": ["z"]}, ROWS) == (None, "no_history")
print("  usual: the mean over the hero distance's sensors of each hour's median and p90, the issue's own metric")

rep = engine.replay(fresh(), Settings(), DECL)
for k, v in rep["issues"].items():
    assert "usual" in v and "usual_absent" in v, k
    if v.get("watched"):
        assert v["usual"] is None and v["usual_absent"] == "unread", (k, v["usual_absent"])
snap = fresh()
carried = {"window_days": 14, "distance": "room", "hours": [{"hour": h, "median": 30.0, "p90": 31.0} for h in range(24)]}
snap["issues"]["issues"]["heat"]["usual"], snap["issues"]["issues"]["heat"]["usual_absent"] = carried, None
assert engine.replay(snap, Settings(), DECL)["issues"]["heat"]["usual"] == carried, "a capture's usual replays verbatim"
print("  usual: a capture without it replays as unread; a capture with it replays it verbatim")

class Tx:
    """A connection.transaction() that records it was entered and left, as psycopg's savepoint does."""
    def __init__(self):
        self.entered = self.exited = False

    def __enter__(self):
        self.entered = True

    def __exit__(self, *exc):
        self.exited = True
        return False


class LiveCur:
    def __init__(self, fail):
        self.fail, self.tx = fail, Tx()
        self.connection = type("Conn", (), {"transaction": lambda _s: self.tx})()

    def execute(self, sql, args=()):
        if self.fail:
            raise RuntimeError("materialized view has not been populated")

    def fetchall(self):
        return [{"sensor_id": "a", "metric": "apparent", "hour": 7, "median": 30.0, "p90": 31.0}]


bad = LiveCur(True)
assert engine._optional(bad, engine.USUAL_SQL) is None and bad.tx.entered and bad.tx.exited, "a failing read is None, inside a savepoint"
good = LiveCur(False)
assert engine._optional(good, engine.USUAL_SQL) == good.fetchall() and good.tx.entered and good.tx.exited, "a good read is its rows, inside a savepoint"
print("  usual: the read runs in a savepoint of its own; an unpopulated view is None, not a failed /issues")

# --- §3.2 an open event's own rooms --------------------------------------------------------------
rep = engine.replay(fresh(), Settings(), DECL)
ev = rep["events"]["open"][0]
assert ev["issue"] == "air" and ev["series"]["rooms"] == sorted(ev["rooms"]), ev.get("series")
vals = ev["series"]["values"]
assert len(vals) == len(rep["issues"]["air"]["buckets"]), "on /issues' own buckets"
# The 08:00 bucket by hand: air combines its house as a mean of pm25, so the rooms' 08:00 pm25 means, averaged.
names = {r["sensor_id"]: r.get("name") for r in SNAP["stats"]}
at = rep["issues"]["air"]["buckets"].index("2026-10-06T08:00:00+08:00")
hand = [r["mean"] for r in SNAP["readings_1h"] if r["bucket"] == "2026-10-06T08:00:00+08:00" and r["metric"] == "pm25"
        and (names.get(r["sensor_id"]) in ev["rooms"] or r["sensor_id"] in ev["rooms"])]
assert hand and abs(vals[at] - sum(hand) / len(hand)) < 1e-4, (vals[at], hand)
# Heat combines each room's apparent temperature, then the median: two rooms, one hour.
B = dt.datetime(2026, 10, 6, 13, tzinfo=dt.timezone(dt.timedelta(hours=8)))
hourly = {B: [{"sensor_id": "k", "metric": "temp", "mean": 34.0}, {"sensor_id": "k", "metric": "humidity", "mean": 60.0},
              {"sensor_id": "l", "metric": "temp", "mean": 30.0}, {"sensor_id": "l", "metric": "humidity", "mean": 50.0},
              {"sensor_id": "x", "metric": "temp", "mean": 40.0}, {"sensor_id": "x", "metric": "humidity", "mean": 90.0}]}
got = engine._room_series(DECL["heat"], hourly, [B], {"k": "K ROOM", "l": "L ROOM"}, ["K ROOM", "L ROOM"])
want = (engine.apparent(34.0, 60.0) + engine.apparent(30.0, 50.0)) / 2           # median of two is their mean
assert got == {"rooms": ["K ROOM", "L ROOM"], "values": [round(want, 6)]}, (got, want)
assert engine._room_series(DECL["heat"], hourly, [B], {}, []) is None, "no rooms, no series"
assert engine._room_series(DECL["coast"], hourly, [B], {}, ["K ROOM"]) is None, "an issue with no room distance"
print("  event series: the event's rooms combined as the issue combines its house, on /issues' buckets")

# --- §3.3 the stations that stopped (node #1, 6 October 2026) -----------------------------------
def heard(i, name, lat, lon, local=False):
    return {"sensor_id": i, "name": name, "lat": lat, "lon": lon, "local": local, "indoor": False, "kind": "sensor",
            "metric": "pm25", "mean_15m": 5.0, "silent_minutes": 5}


def stopped(i, name, lat, lon, when, indoor=False):
    return {"sensor_id": i, "name": name, "lat": lat, "lon": lon, "local": False, "indoor": indoor, "kind": "sensor",
            "last_heard": when}


HEARD = [heard("sc-19874", "BAYU NEW ENCLOSURE ", -8.82008, 115.16669, True),
         heard("sc-19236", "Ungasan Kit - TEST", -8.81983, 115.16657, True),
         heard("sc-19898", "Suluban Entrance - AIR", -8.81645, 115.09271),
         heard("bad-ag-197980", "Padang2 Uluwatu (AirGradient)", -8.81121, 115.10252),
         heard("bad-sc-19768", "Bayu Sensor by Fab Lab - Kios Serangan (Smart Citizen)", -8.72582, 115.23585)]
STOPPED = [stopped("bad-sc-19874", "BAYU NEW ENCLOSURE (Smart Citizen)", -8.82008, 115.16669, "2026-10-04T15:00:37+00:00"),
           stopped("bad-sc-19236", "Ungasan Kit - TEST (Smart Citizen)", -8.81983, 115.16657, "2026-10-04T15:00:37+00:00"),
           stopped("bad-sc-19898", "Suluban Entrance - AIR (Smart Citizen)", -8.81645, 115.09271, "2026-10-01T20:30:26+00:00"),
           stopped("bad-oq-6432409", "Padang2 Uluwatu (OpenAQ)", -8.81121, 115.10252, "2026-09-07T23:00:42+00:00"),
           stopped("bad-sc-19995", "Bayu Sensor Demo Test Lora (Smart Citizen)", -8.72591, 115.23600, "2026-10-03T22:45:24+00:00"),
           stopped("bad-iqs-jimbaran-s", "Jimbaran (IQAir)", -8.79122, 115.16740, "2026-09-07T22:07:41+00:00", True),
           stopped("bad-pa-36601", "Jimbaran by Lumi Clinic (PurpleAir)", -8.79122, 115.16740, "2026-09-07T23:00:42+00:00", True),
           stopped("bad-ag-208245", "Suluban (AirGradient)", -8.81882, 115.08806, "2026-10-03T09:45:22+00:00")]
out = engine._stations(HEARD, [], -8.8190516, 115.1644423, True, STOPPED)
gone = sorted(s["name"] for s in out if s.get("last_heard"))
# Four of the eight are relays (bad-sc-*, OpenAQ) of kits heard today at the same point: they are not listed.
assert gone == ["Bayu Sensor Demo Test Lora (Smart Citizen)", "Jimbaran (IQAir)",
                "Jimbaran by Lumi Clinic (PurpleAir)", "Suluban (AirGradient)"], gone
one = next(s for s in out if s["sensor_id"] == "bad-ag-208245")
assert one["read"] == {} and one["series"] == {} and one["last_heard"] == "2026-10-03T09:45:22+00:00" and one["km"] > 0
assert not any(s.get("last_heard") for s in engine._stations(HEARD, [], -8.8, 115.16, True, None)), "none given, none listed"
print("  silent stations: four of node #1's eight are kept; four are relays of kits heard today, at the same point")

rep = engine.replay(fresh(), Settings(), DECL)
assert rep["stations_silent"] == {"read": False, "within_days": 30, "stations": []}, rep["stations_silent"]
assert not any(s.get("last_heard") for s in rep["stations"]), "`stations` holds only the stations heard in the last day"
snap = fresh()
snap["issues"]["stations_silent"] = {"read": True, "within_days": 30,
                                     "stations": [{**STOPPED[-1], "read": {}, "series": {}}]}
again = engine.replay(snap, Settings(), DECL)
assert again["stations_silent"]["read"] is True
assert [s["name"] for s in again["stations_silent"]["stations"]] == ["Suluban (AirGradient)"]
assert not any(s.get("last_heard") for s in again["stations"]), "a stopped station never lands in `stations`"
print("  silent stations: a capture says whether it read them, and replays the ones it carried")

# A station that stopped is published for the fold, never counted as one this node reads now (§3.3).
quiet = {"sensor_id": "bad-sc-0", "name": "Stopped, 60 m away", "lat": -8.8195, "lon": 115.1650, "local": False,
         "indoor": False, "kind": "sensor", "read": {}, "series": {}, "last_heard": "2026-09-20T10:00:00+00:00"}
base = engine.replay(fresh(), Settings(), DECL)
snap = fresh()
snap["issues"]["stations_silent"] = {"read": True, "within_days": 30, "stations": [quiet]}
more = engine.replay(snap, Settings(), DECL)
assert more["stations"] == base["stations"], "`stations` is the stations heard in the last day, unchanged"
assert [s["name"] for s in more["stations_silent"]["stations"]] == ["Stopped, 60 m away"], "the silent one is published"
assert more["digest"] == base["digest"], "the digest counts only stations heard in the last day"
assert more["geometry"] == base["geometry"], "the grain table sees only stations heard in the last day"
print("  silent stations: published, but neither the digest nor the grain table counts them")

# A cell's `sensors` are positions in the published `stations`: each one names a station inside that cell.
import h3  # noqa: E402
cells = more["geometry"]["nav"]["cells"]
assert cells and any(c["sensors"] for c in cells.values()), "the capture puts stations in cells"
wrong = [cid for cid, c in cells.items() for i in c["sensors"]
         if not 0 <= i < len(more["stations"])
         or h3.latlng_to_cell(more["stations"][i]["lat"], more["stations"][i]["lon"], c["res"]) != cid]
assert not wrong, f"{len(wrong)} of {len(cells)} cells name a station outside them"
print("  silent stations: every cell's sensors are positions in the published stations, inside that cell")

# --- §3.4 GET /issues/days ----------------------------------------------------------------------
class Cur:
    """Answers days()'s three reads from the capture: the session zone, readings_1h from a bucket on, alert_events."""
    def __init__(self, snap, events=(), tz="Asia/Makassar"):
        self.snap, self.events, self.tz, self.rows = snap, list(events), tz, []

    def execute(self, sql, args=()):
        if "current_setting('TimeZone')" in sql:
            self.rows = [{"tz": self.tz}]
        elif "FROM readings_1h" in sql:
            self.rows = [dict(r, bucket=dt.datetime.fromisoformat(r["bucket"])) for r in self.snap["readings_1h"]
                         if dt.datetime.fromisoformat(r["bucket"]) >= args[0]]
        elif "FROM alert_events" in sql:
            self.rows = list(self.events)
        else:
            raise LookupError(sql[:60])

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


NOW = dt.datetime.fromisoformat(SNAP["as_of"])                     # 09:00 in Bali; the capture's last hour is 08:00
EV = [{"id": 2, "issue": "air", "kind": "danger", "level": "act",
       "opened_at": dt.datetime(2026, 10, 5, 23, 18, tzinfo=dt.timezone.utc), "cleared_at": None}]
one = engine.days(Cur(SNAP, EV), Settings(), DECL, 1, now=NOW)
rep = engine.replay(fresh(), Settings(), DECL)
assert one["schema"] == "days-v0" and one["days"] == 1 and one["tz"] == "Asia/Makassar"
assert len(one["buckets"]) == 24 and one["buckets"][-1] == "2026-10-06T09:00:00+08:00", one["buckets"][-1]
for k, v in one["issues"].items():
    r = rep["issues"][k]
    if v["distance"] is None:
        assert not any(r["series"].values()), f"{k}: /issues has a series that /issues/days lost"
        continue
    want = dict(zip(r["buckets"], r["series"][v["distance"]]))
    got = dict(zip(one["buckets"], v["series"][v["distance"]]))
    assert all(got[b] == want[b] for b in want), f"{k}: one day of /issues/days is not /issues' own 24 values"
    assert got["2026-10-06T09:00:00+08:00"] is None, "an hour with no rows is a null, never a skipped column"
    assert sum(p["of"] for p in v["per_day"]) == 24
    vals = [x for x in v["series"][v["distance"]] if x is not None]
    assert sum(p["read"] for p in v["per_day"]) == len(vals)
    assert sum(p["over"] for p in v["per_day"]) == sum(1 for x in vals if x > v["line"]["value"]), k
    assert v["provenance"][v["distance"]] == ("live" if v["distance"] in ("room", "yard") else "partial")
assert [p["date"] for p in one["issues"]["air"]["per_day"]] == ["2026-10-05", "2026-10-06"], "local days, not UTC"
assert one["events"] == [{"id": 2, "issue": "air", "kind": "danger", "level": "act",
                          "opened_at": "2026-10-05T23:18:00+00:00", "cleared_at": None}]
assert engine.days(Cur(SNAP), Settings(), DECL, 0, now=NOW)["days"] == 1
assert engine.days(Cur(SNAP), Settings(), DECL, 500, now=NOW)["days"] == engine.DAYS_MAX == 90
print("  /issues/days: one day is /issues' own 24 values; the node counts hours over per local day; 1 to 90 days")

# Across a daylight-saving change the buckets are stepped in UTC and shown in the node's zone: Madrid's 25 October holds
# 25 hours, none skipped; and a +5:30 zone's buckets still fall on its own local whole hours.
mad = engine.days(Cur({"readings_1h": []}, tz="Europe/Madrid"), Settings(), DECL, 2,
                  now=dt.datetime(2026, 10, 26, 3, 10, tzinfo=dt.timezone.utc))
ts = [dt.datetime.fromisoformat(b).timestamp() for b in mad["buckets"]]
assert len(ts) == 48 and all(b - a == 3600 for a, b in zip(ts, ts[1:])), "48 distinct instants, an hour apart"
assert sum(b.startswith("2026-10-25") for b in mad["buckets"]) == 25, "the fall-back day holds 25 hours"
kol = {"readings_1h": [{"bucket": "2026-10-06T09:00:00+05:30", "sensor_id": "k1", "metric": "pm25", "mean": 17.0,
                        "indoor": True, "local": True, "kind": "sensor"}]}
ind = engine.days(Cur(kol, tz="Asia/Kolkata"), Settings(), DECL, 1, now=dt.datetime(2026, 10, 6, 4, 10, tzinfo=dt.timezone.utc))
assert ind["buckets"][-1] == "2026-10-06T09:00:00+05:30", ind["buckets"][-1]
assert ind["issues"]["air"]["series"]["room"][-1] == 17.0, "a +5:30 node's row lands on its local whole hour"
print("  /issues/days: a daylight-saving day holds 25 hours, none dropped; a +5:30 node's buckets are its whole hours")

print("figures_wire: the usual day")
