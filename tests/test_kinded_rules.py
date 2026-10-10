"""Kinded rules over node #1's readings (docs/SPEC_alerts.md §3): they return the columns the engine reads, and
the heat rules do not fire on the room's ordinary afternoon. Needs duckdb.

Temperature and humidity are the SYNTHETIC profile (T.heat_days, shaped to node #1's published daily curve): the
fixture tests/data/node1-readings.tsv holds light, pm1 and pm25 only, and a real day of a household's temperature
would put private data in a public repository. The PM series is node #1's real one, replayed over the fifteen days.
Run: PYTHONPATH=tests:app python3 tests/test_kinded_rules.py
"""
import datetime as dt
import sys

try:
    import trustdb as T
except ImportError as e:
    print(f"  skipped: {e}")
    sys.exit(0)

heat, air = T.rules("heat"), T.rules("air-quality")
NEW_HEAT = ("heat_unusual", "heat_sustained", "heat_extreme")
NEW_AIR = ("air_spike", "air_unusual", "air_sustained", "air_extreme")
for name, rs in ((NEW_HEAT, heat), (NEW_AIR, air)):
    for r in name:
        assert rs[r].get("kind") in ("spike", "unusual", "sustained", "danger"), r
print("  seven kinded rules, each declaring its kind")

rows = T.readings()
indoor = [s[0] for s in T.sensors() if s[5] and s[6]]   # every kit that is indoor and local
assert indoor, "the fixture has indoor local kits"
node = T.Node(T.week(rows, T.FIXTURE_NOW, days=15) + T.heat_days(indoor, T.FIXTURE_NOW, days=15))
node.refresh_usual(T.FIXTURE_NOW)
for r in NEW_AIR:                                    # before the loop: the loop deletes the future of each instant
    for row in node.run(air[r], T.FIXTURE_NOW):
        assert {"sensor_id", "name", "value", "line", "over", "where"} <= set(row), (r, row)
fired = {r: 0 for r in NEW_HEAT}
for h in range(24):                                  # one ordinary replayed day, hour by hour, going back in time
    at = T.FIXTURE_NOW - dt.timedelta(hours=h)
    # the node holds readings up to FIXTURE_NOW; at an earlier instant a rule must not see them (`stats` has no
    # upper bound). usual_by_hour was refreshed above, from the whole fifteen days, as the app's hourly refresh does.
    node.con.execute(f"DELETE FROM readings WHERE ts > TIMESTAMPTZ '{at.isoformat()}'")
    for r in NEW_HEAT:
        out = node.run(heat[r], at)
        for row in out:
            assert {"sensor_id", "name", "value", "line", "over"} <= set(row), (r, row)
            if r == "heat_sustained":
                assert {"hours", "usual_hours"} <= set(row), row
        fired[r] += sum(1 for row in out if row["over"])
assert fired["heat_extreme"] == 0, "nothing on node #1's ordinary day is 40 °C apparent"
assert fired["heat_unusual"] == 0, "a replayed ordinary day is never above its own p90 + 2"
print(f"  an ordinary day replayed: unusual {fired['heat_unusual']}, extreme {fired['heat_extreme']}, "
      f"sustained {fired['heat_sustained']} hours over")

# ---- positive cases: each rule CAN fire, at the instant it should, on hand-made rows ----
WITA = dt.timezone(dt.timedelta(hours=8))
AT = dt.datetime(2026, 9, 7, 13, 10, tzinfo=WITA)    # 13:10 local: the last 15-minute bucket is 13:00-13:10
WHO = [("in1", "x", "Indoor", -8.8, 115.1, True, True, "sensor"),
       ("out1", "x", "Outdoor", -8.8, 115.1, False, True, "sensor")]


def built(fn, days=14, every=5):
    """A fresh node from fn(local_time, ts_utc, minutes_ago) -> rows, usual_by_hour refreshed at AT."""
    rows = []
    for m in range(0, days * 1440, every):
        ts = AT - dt.timedelta(minutes=m)
        rows += fn(ts.astimezone(WITA), ts, m)
    n = T.Node(rows, who=WHO)
    n.refresh_usual(AT)
    return n


def fires(n, rule, sensor, **want):
    hit = [r for r in n.run(rule, AT) if r["sensor_id"] == sensor and r["over"]]
    assert hit, (rule["id"], n.run(rule, AT))
    for k, v in want.items():
        assert hit[0][k] == v, (rule["id"], k, hit[0])
    return hit[0]


# air: PM flat 8 for fourteen days, 140 for the last 75 minutes
pm = built(lambda l, ts, m: [(ts, s, "pm25", 140.0 if m < 75 else 8.0) for s in ("in1", "out1")])
for r in ("air_unusual", "air_sustained", "air_extreme"):
    fires(pm, air[r], "out1", where="outside")
    fires(pm, air[r], "in1", where="inside")
# spike: flat 8, then only the latest bucket at 40 (line = max(8 + 12, p90 + 10) = 20)
spike = built(lambda l, ts, m: [(ts, "out1", "pm25", 40.0 if ts >= AT.replace(minute=0) else 8.0),
                                (ts, "in1", "pm25", 8.0)])
fires(spike, air["air_spike"], "out1", where="outside", line=20.0)
assert not [r for r in spike.run(air["air_spike"], AT) if r["sensor_id"] == "in1" and r["over"]]
print("  air: spike, unusual, sustained and extreme each fire where they should")

# heat: indoor, humidity 50 %. History hot (apparent >= 35) 13:00-15:00 only; today hot from 08:00, five hours.
def hot(l, ts, m):
    today = l.date() == AT.date()
    return [(ts, "in1", "temp", 32.5 if (8 <= l.hour if today else 13 <= l.hour < 15) else 28.0),
            (ts, "in1", "humidity", 50.0)]


h = built(hot, every=10)
row = fires(h, heat["heat_sustained"], "in1")
assert row["hours"] >= 3 and row["hours"] > row["usual_hours"], row
print(f"  heat: sustained {row['hours']} h against a usual {row['usual_hours']} h")

# unusual: usual afternoons 28, the last hour 33 (p90 of the hour 28, line 30); extreme: latest bucket 45 apparent
def rise(v):
    return lambda l, ts, m: [(ts, "in1", "temp", v if m < 60 else 28.0), (ts, "in1", "humidity", 50.0)]


fires(built(rise(33.0), every=10), heat["heat_unusual"], "in1")
row = fires(built(rise(40.0), every=10), heat["heat_extreme"], "in1")
assert row["value"] >= 40, row
print("  heat: unusual and extreme each fire where they should")

# a Meshtastic radio indoors reports its own box (config/channels.yml: meshtastic temp is `enclosure`), not the room:
# no heat rule may read it as a room, however hot the box gets. in1's source declares no role and is kept.
BOX = ("box1", "meshtastic", "Box", -8.8, 115.1, True, True, "sensor")
def boxed(v):
    return lambda l, ts, m: [(ts, s, "temp", v if m < 60 else 28.0) for s in ("in1", "box1")] + \
                            [(ts, s, "humidity", 50.0) for s in ("in1", "box1")]
rows = []
for m in range(0, 14 * 1440, 10):
    ts = AT - dt.timedelta(minutes=m)
    rows += boxed(40.0)(ts.astimezone(WITA), ts, m)
bx = T.Node(rows, who=WHO + [BOX])
bx.refresh_usual(AT)
for r in ("heat_unusual", "heat_sustained", "heat_extreme"):
    assert not [row for row in bx.run(heat[r], AT) if row["sensor_id"] == "box1"], (r, "read the box as a room")
fires(bx, heat["heat_extreme"], "in1")
print("  heat: a radio's enclosure temperature is never read as a room")
print("kinded rules: the engine's columns, no heat event on an ordinary day, and each rule can fire")
