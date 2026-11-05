"""The ring: which Bali Air Dispatch stations are this node's neighbours, and which are its own kit read twice.

Run: PYTHONPATH=/tmp/stub:app python3 tests/test_nearby.py
Against tests/data/bad_*_2026-09-07.json — the archive as it answered on 7 September 2026, saved whole, not
numbers typed into a test. Every exclusion below fires on a real station; none of them needed a crafted case.
"""
import importlib.util
import json
import os

import sources

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the archive's adapter lives in its pack (packs/bali-air-dispatch) since the release after v0.82.3
_spec = importlib.util.spec_from_file_location("bad_adapter", os.path.join(ROOT, "packs/bali-air-dispatch/adapter.py"))
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
LAT, LON = -8.8271, 115.15709          # node #1, bayu-2, Ungasan
# the Smart Citizen kits node #1 polls itself: SC_USER=tomasdiez, state has_published, seen in the last 3 days
POLLED = {"sc-19898", "sc-19880", "sc-19849", "sc-19874", "sc-19897", "sc-19236"}


def fixture(name):
    with open(os.path.join(ROOT, "tests/data", name)) as f:
        return json.load(f)


latest = fixture("bad_latest_2026-09-07.json")["readings"]
stations = {s["station_id"]: s for s in fixture("bad_stations_2026-09-07.json")["stations"]}
assert len(latest) == 84 and len(stations) == 87, "the fixture is the archive as it stood, 84 of 87 with a reading"

v = dict((r["station_id"], w) for r, w in B.verdicts(latest, LAT, LON, 15.0, POLLED))

# ---- identity. sc-19236 is "Ungasan Kit", 1.3 km away: no distance rule would ever catch it, and the node reads
# it directly, so the ring would be this node arguing with itself.
assert v["sc-19236"].startswith("excluded: identity"), v["sc-19236"]
assert v["sc-19898"].startswith("excluded: identity"), "a kit of ours 7 km away is still a kit we read twice"

# ---- proximity. sc-19835 ("Bayu Kit") sits 10 m from the node and is NOT on the account the node polls, so
# identity misses it entirely. This is the rule that catches it, and it is why identity alone is not enough.
assert v["sc-19835"].startswith("excluded: proximity"), v["sc-19835"]
assert "sc-19835" not in POLLED, "the case only means something while this kit is not one we poll"

# ---- by hand
byhand = dict((r["station_id"], w) for r, w in B.verdicts(latest, LAT, LON, 15.0, POLLED, {"sc-19760"}))
assert byhand["sc-19760"] == "excluded: by hand (BAD_EXCLUDE)", byhand["sc-19760"]
assert v["sc-19760"] == "included", "and without the hand list it is a neighbour, not a duplicate"

# ---- quality flags, each on the station that actually carries it. Ownership and radius are decided first, so
# the only station flagged malfunctioning (33 km away) is read from the wide view.
wide = dict((r["station_id"], w) for r, w in B.verdicts(latest, LAT, LON, 50.0, POLLED))
assert wide["iq-kopernik"] == "excluded: suspected_malfunctioning", wide["iq-kopernik"]
assert v["iqs-jimbaran-s"] == "excluded: suspected_indoor", v["iqs-jimbaran-s"]
assert v["sc-19618"].startswith("excluded: stale"), v["sc-19618"]
assert v["pa-46949"] == "excluded: beyond the radius", "42 km is not this node's ring"

# ---- one device, one row. The archive does NOT dedupe OpenAQ against AirGradient: 23 units appear twice, same
# coordinates, same name. A ring median over both rows weights those devices double.
assert wide["ag-197980"] == "included", "keep the direct network"
assert wide["oq-6432409"] == "excluded: same device as ag-197980", wide["oq-6432409"]
mirrors = [k for k, w in wide.items() if w.startswith("excluded: same device")]
assert len(mirrors) >= 20, f"only {len(mirrors)} mirrors collapsed; the archive had 23 on 7 Sep"
assert all(m.startswith(B.MIRROR_PREFIXES) for m in mirrors), "the mirror is dropped, never the direct row"
# not only OpenAQ: AQICN republishes an IQAir station at Sempidi under its own id.
assert wide["aq--519205"] == "excluded: same device as iqs-kabupaten-badung-sempidi", wide["aq--519205"]

# three Smart Citizen kits sit 25 m apart at Kios Utak Atik under different names. Same place, different devices:
# collapsing them would delete real sensors, which is why the rule needs the name and not just the distance.
assert not wide["sc-19762"].startswith("excluded: same device"), wide["sc-19762"]

# ---- an external station is never `local`, at any distance. sc-19835 ("Bayu Kit") sits at node #1's exact
# coordinates and stopped reporting on 16 August; whatever it is, the node must never count it as its own
# measurement. Pinned where `local` is actually decided: stamp_local only ever narrows, so a row the adapter
# did not claim cannot be widened into the house by being close.
ring = {"station_id": "x-40m", "name": "forty metres away", "source": "IQAir",
        "latitude": LAT + 40 / 111_320.0, "longitude": LON,
        "observed_at": "2026-09-07T13:00:00Z", "stale": False, "pm25": 9.1}


class _R:
    def __init__(self, j): self.j = j
    def raise_for_status(self): pass
    def json(self): return self.j


class _HC:
    def __init__(self, j): self.j = j
    def get(self, url, timeout=None): return _R(self.j)


s, r = B.ring(_HC({"readings": [ring]}), LAT, LON, 15.0, min_separation_m=10.0)
assert len(s) == 1 and s[0]["local"] is False, "a station 40 m away is a neighbour, not this node's own kit"
assert 39 < sources.metres(LAT, LON, ring["latitude"], ring["longitude"]) < 41
sources.stamp_local(s, LAT, LON, 500.0)
assert s[0]["local"] is False, "stamp_local only ever narrows: an unclaimed sensor never becomes local"
assert [m for _, _, m, _ in r] == ["pm25"] and s[0]["meta"]["attribution"].startswith("Bali Air Dispatch")

# ---- what the ring at node #1 actually is. This is the finding, pinned so it cannot quietly change.
inc = [k for k, w in v.items() if w == "included"]
assert len(inc) == 6, f"node #1 had 6 real neighbours at 15 km on 7 Sep, got {len(inc)}"
near = min(sources.km(LAT, LON, stations[k]["latitude"], stations[k]["longitude"]) for k in inc)
assert 3.7 < near < 3.9, f"the nearest neighbour was 3.81 km, got {near:.2f}"

print("test_nearby: ok —", len(inc), "included,", len(latest) - len(inc), "excluded at 15 km")


# ---------------------------------------------------------------- the three rules, over real air
# Node #1's own readings (tests/data/node1-*.tsv) against its six real neighbours' hourly PM2.5 for the same days
# (tests/data/ring_hourly_2026-09-07.json, straight out of the archive). Both sides measured; neither typed.
import datetime as dt  # noqa: E402
import sys  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import trustdb
except ImportError:
    print("  - ring rule replay skipped (pip install duckdb)")
else:
    AT = trustdb.FIXTURE_NOW
    RULES = trustdb.rules("nearby")
    _st = {s["station_id"]: s for s in fixture("bad_stations_2026-09-07.json")["stations"]}
    _ring = fixture("ring_hourly_2026-09-07.json")
    _keys = list(_ring)

    def _who(keys):
        return trustdb.sensors() + [(f"bad-{k}", "baliairdispatch", _st[k]["name"], _st[k]["latitude"],
                                     _st[k]["longitude"], False, False, "sensor") for k in keys]

    def _ringrows(keys, value=None):
        return [(dt.datetime.fromisoformat(t.replace("Z", "+00:00")), f"bad-{k}", "pm25",
                 float(value if value is not None else v))
                for k in keys for t, v in _ring[k] if dt.datetime.fromisoformat(t.replace("Z", "+00:00")) <= AT]

    _local = [r for r in trustdb.readings() if r[0] <= AT]

    def _run(rule, rows, keys, at=AT):
        return trustdb.Node(rows, _who(keys)).run(RULES[rule], at, -8.8271, 115.15709)

    # ---- over the real week, all three are silent. A rule that fires more than about twice a week is wrong.
    _start = min(r[0] for r in _local)
    _hours = int((AT - _start).total_seconds() // 3600)
    _all = _local + _ringrows(_keys)
    _fired = {k: 0 for k in RULES}
    for _h in range(0, _hours + 1, 6):                     # every sixth hour: 22 instants over five days
        _at = _start + dt.timedelta(hours=_h)
        _n = trustdb.Node([r for r in _all if r[0] <= _at], _who(_keys))   # only what the node could have known
        for _k in RULES:
            if _n.run(RULES[_k], _at, -8.8271, 115.15709):
                _fired[_k] += 1
    assert _fired == {"only_here": 0, "everywhere": 0, "alone": 0}, \
        f"node #1's real week was clean air with six neighbours; nothing should have fired: {_fired}"

    # ---- and each one still fires when the thing it exists for happens.
    _smoke = [(ts, s, m, 40.0) if (s == "sc-19874" and m == "pm25" and ts > AT - dt.timedelta(hours=1))
              else (ts, s, m, v) for ts, s, m, v in _local]
    _hit = _run("only_here", _smoke + _ringrows(_keys), _keys)
    assert _hit and _hit[0]["name"] == "BAYU NEW ENCLOSURE" and _hit[0]["stations"] == 6, _hit
    assert float(_hit[0]["nearest"]) == 3.8, "and it names how far the nearest neighbour is"

    # the ring's own spread is not a gate. On 7 September these six, in clean air with a median of 8.8, were
    # 9.3 ug/m3 apart between p25 and p75 — 4 to 15 km apart across the Bukit is simply what the air does here.
    # Any fixed agreement gate tight enough to mean the word would have made only_here dead. It measures against
    # the ring's p75 instead, so a wide ring demands a bigger excursion and a tight one fires sooner.
    assert _run("only_here", _smoke + _ringrows(_keys, 30.0), _keys) == [], \
        "a node at 40 with the whole ring at 30 is not a local source; that is what `everywhere` is for"

    assert _run("everywhere", _local + _ringrows(_keys, 45.0), _keys)[0]["stations"] == 6
    assert _run("everywhere", _local + _ringrows(_keys), _keys) == [], "clean air is not an event"

    _thin = _run("alone", _local + _ringrows(_keys[:1]), _keys[:1])
    assert _thin and _thin[0]["stations"] == 1, "one neighbour is an anecdote, and the report has to say so"
    assert _run("alone", _local + _ringrows(_keys), _keys) == [], "six neighbours is a ring"

    # ---- `NOT local` is not the ring. Node #1's own kits sit 1.1 km from its coordinates, so at
    # LOCAL_RADIUS_M=500 they are the operator's but not this node's, and `local` is FALSE on both. Scoping the
    # ring by `NOT local` alone counted them as neighbours: the node comparing itself against its own hardware,
    # the same duplicate the pack exists to refuse, one layer down in the SQL. The ring is the archive, by name.
    _own_far = [(sid, src, nm, la, lo, ind, False, k) for sid, src, nm, la, lo, ind, _l, k in trustdb.sensors()]
    _n = trustdb.Node(_local + _ringrows(_keys[:1]), _own_far
                      + [(f"bad-{_keys[0]}", "baliairdispatch", _st[_keys[0]]["name"],
                          _st[_keys[0]]["latitude"], _st[_keys[0]]["longitude"], False, False, "sensor")])
    _r = _n.run(RULES["alone"], AT, -8.8271, 115.15709)
    assert _r and _r[0]["stations"] == 1, \
        f"five kits of the operator's own, all local=false, must not become five neighbours: {_r}"

    print("test_nearby: the three rules stayed silent through node #1's real week, and fire when they should")
