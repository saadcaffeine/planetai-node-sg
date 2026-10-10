"""tools/replay_alerts.py on a synthetic two days: the old engine repeats on its cooldown, the event engine sends
one story. Needs duckdb. Run: PYTHONPATH=tests:app:tools python3 tests/test_replay.py

The PM series is node #1's real day replayed over sixteen (T.week); temperature and humidity are T.heat_days, the
synthetic profile shaped to node #1's published curve (the fixture holds no temperature, see test_kinded_rules.py).
On the last counted evening an indoor kit has a synthetic cooking hour (PM2.5 80 µg/m³, 18:00–19:30 local), so the event
engine has one story to tell and its action is chosen from what the node holds at that instant.
"""
import datetime as dt
import sys

try:
    import trustdb as T          # duckdb, dev only
except ImportError as e:
    print(f"  skipped: {e}")
    sys.exit(0)

import events as E
import replay_alerts as R        # outside the try: a missing tool is a failure, not a skip

# ---- bursts: three or more pushes inside one 60-minute span, not a chain of short gaps ----
T0 = dt.datetime(2026, 9, 1, 12, tzinfo=R.LOCAL)


def at(*mins):
    return [T0 + dt.timedelta(minutes=m) for m in mins]


assert R._bursts(at(0, 50, 100)) == (0, 0), "0/50/100 min: no three inside one hour"
assert R._bursts(at(0, 10, 20)) == (1, 3)
assert R._bursts(at(*range(0, 500, 50))) == (0, 0), "ten pushes 50 min apart are not a burst"
assert R._bursts(at(0, 10, 20, 200, 210, 220, 230)) == (2, 7)
print("  bursts: 3+ within 60 minutes; a chain of 50-minute gaps is not one")

# ---- the window: whole local days, the last one the data completes ----
s0, e0 = R.window(T.FIXTURE_NOW, 2)                          # FIXTURE_NOW is 7 Sep 21:14 WITA
assert (s0.astimezone(R.LOCAL), e0.astimezone(R.LOCAL)) == (dt.datetime(2026, 9, 5, tzinfo=R.LOCAL),
                                                            dt.datetime(2026, 9, 7, tzinfo=R.LOCAL)), (s0, e0)
print("  the window is two whole local days, 5 and 6 September")

# ---- timestamps without a zone are refused, not misread ----
try:
    R.replay(T.Node([]), [(dt.datetime(2026, 9, 1), "x", "pm25", 1.0)], [], [], s0, e0, 15,
             E.Policy(quiet=None, max_per_day=4, alert_level="warn"))
    raise AssertionError("a naive timestamp was accepted")
except ValueError as e:
    assert "time-zone-aware" in str(e), e

# ---- an old alert held by quiet hours still starts its cooldown (app/main.py writes the alerts row either way) ----
# A warn rule firing every step, cooldown 60. Replayed 05:30-06:45 local with the one-hour warm-up: held at 04:30
# and 05:30 (quiet), so 06:00 and 06:15 are inside the cooldown and 06:30 is the first push. Stamping the cooldown
# only on a send would push at 06:00.
always = {"id": "x/always", "level": "warn", "cooldown_minutes": 60, "sql": "SELECT 'k' AS sensor_id",
          "message": {"en": "x"}}
q = R.replay(T.Node([]), [], [always], [], dt.datetime(2026, 9, 1, 5, 30, tzinfo=R.LOCAL),
             dt.datetime(2026, 9, 1, 6, 45, tzinfo=R.LOCAL), 15, E.Policy(quiet=(22, 6), max_per_day=4, alert_level="warn"))
assert [f"{p['ts']:%H:%M}" for p in q["old"]["pushes"]] == ["06:30"], q["old"]["pushes"]
print("  a warn alert held in quiet hours starts its cooldown: first push 06:30, not 06:00")

indoor = [s[0] for s in T.sensors() if s[5] and s[6]]       # every kit that is indoor and local
rows = T.week(T.readings(), T.FIXTURE_NOW, days=16) + T.heat_days(indoor, T.FIXTURE_NOW, days=16)
start, end = R.window(T.FIXTURE_NOW, 2)                       # 5 and 6 September, local
cook = dt.datetime(2026, 9, 6, 18, tzinfo=R.LOCAL)
rows += [(cook + dt.timedelta(minutes=m), indoor[0], "pm25", 80.0) for m in range(0, 90, 5)]
pol = E.Policy(quiet=(22, 6), max_per_day=4, alert_level="warn")

# the replay never holds a reading later than its clock: stop it a day early and the last day is not in the node
early = T.Node([])
R.replay(early, rows, [], [], start=end - dt.timedelta(days=1, hours=1), end=end - dt.timedelta(days=1),
         step_min=15, policy=pol)
(last,) = early.con.execute("SELECT max(epoch(ts)) FROM readings").fetchone()
assert last <= (end - dt.timedelta(days=1)).timestamp(), (last, end)
print("  the node never holds a reading later than the replay clock")

res = R.replay(T.Node([]), rows, R.old_rules(), R.new_rules(), start=start, end=end, step_min=15, policy=pol)
old, new = res["old"], res["new"]
assert sorted(old["per_day"]) == sorted(new["per_day"]) == [dt.date(2026, 9, 5), dt.date(2026, 9, 6)], old["per_day"]
assert all(start <= p["ts"] < end for p in old["pushes"] + new["pushes"] + new["held"]), "the warm-up is not counted"
assert new["opens_escalates"] + new["clears"] == len(new["pushes"]) and old["clears"] == 0
assert not res["not_replayed"].keys() & {r["id"] for r in R.new_rules()}, res["not_replayed"]
assert old["pushes"], "the old engine sends something on node #1's days"
assert len(new["pushes"]) < len(old["pushes"]), (len(new["pushes"]), len(old["pushes"]))
night = [p for p in new["pushes"] if p["ts"].hour < 6 or p["ts"].hour >= 22]
assert all(p["kind"] == "danger" for p in night), f"only danger is sent at night: {night}"
assert new["night"] == 0, new["night"]
assert any(p["what"] == "air" and p["reason"] == "open" and p["action"] for p in new["pushes"]), new["pushes"]
print(f"replay: old {len(old['pushes'])} pushes, new {len(new['pushes'])} ({new['opens_escalates']} opens or "
      f"escalations, {new['clears']} all-clears) over two whole days; held {new['held_by']}; "
      f"not replayed {sorted(res['not_replayed'])}")
