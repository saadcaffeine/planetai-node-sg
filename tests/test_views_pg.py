"""stats, observations and the archive of silence on a real database: the same rows as the queries they replaced.

On 24 Oct 2026 the three were rewritten for speed (GET /issues spent most of its SQL in them on node #1): `stats`
aggregates on (sensor_id, metric) and joins the sensor after, `observations` and engine.SILENT_SQL walk
readings_lookup instead of sorting every row. This seeds the cases each one has to get right and holds every row to
the old definition, kept here as the reference. Needs a Postgres with init.sql applied, at RHO_PG_URL (CI's lint
job starts one); without it the suite skips.
Run: RHO_PG_URL=postgresql://planetai:x@127.0.0.1:5432/planetai PYTHONPATH=app PACKS_DIR=packs python3 tests/test_views_pg.py
"""
import os
import sys
from datetime import timedelta

url = os.getenv("RHO_PG_URL")
if not url:
    print("  - the views on a real database skipped (set RHO_PG_URL to a Postgres with init.sql applied)")
    sys.exit(0)
import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

sys.path.insert(0, "app")
src = open("app/issues/engine.py").read()
ns: dict = {}
exec(src[src.index("SILENT_DAYS = 30"):src.index("def _optional")], ns)   # the constant, without the engine's imports

OLD_STATS = """
SELECT r.sensor_id, r.metric, s.indoor, s.local, s.kind, s.scale, s.lat, s.lon, s.name,
       (array_agg(r.value ORDER BY r.ts DESC))[1] AS last, max(r.ts) AS last_ts,
       extract(epoch FROM now() - max(r.ts)) / 60 AS silent_minutes,
       avg(r.value) FILTER (WHERE r.ts > now() - interval '15 minutes') AS mean_15m,
       avg(r.value) FILTER (WHERE r.ts > now() - interval '1 hour') AS mean_1h,
       avg(r.value) FILTER (WHERE r.ts > now() - interval '24 hours') AS mean_24h
FROM readings r JOIN sensors s USING (sensor_id)
WHERE r.ts > now() - interval '24 hours' AND s.kind = 'sensor'
GROUP BY r.sensor_id, r.metric, s.indoor, s.local, s.kind, s.scale, s.lat, s.lon, s.name"""
OLD_OBS = """
SELECT DISTINCT ON (r.sensor_id, r.metric) r.sensor_id, r.metric, r.value, r.ts, s.name, s.kind, s.scale, s.local,
       s.cadence, s.meta::text AS meta
FROM readings r JOIN sensors s USING (sensor_id) WHERE s.kind <> 'sensor' AND r.ts <= now()   -- a forecast hour is not an observation yet
ORDER BY r.sensor_id, r.metric, r.ts DESC"""
OLD_SILENT = """
SELECT s.sensor_id, s.name, s.lat, s.lon, s.local, s.indoor, s.kind, max(r.ts) AS last_heard
FROM readings r JOIN sensors s USING (sensor_id)
WHERE s.kind = 'sensor' AND r.ts > now() - make_interval(days => %s)
GROUP BY 1, 2, 3, 4, 5, 6, 7 HAVING max(r.ts) <= now() - interval '24 hours'"""

con = psycopg.connect(url, row_factory=dict_row)          # one transaction, rolled back: nothing stays
cur = con.cursor()
q = lambda sql, *a: cur.execute(sql, a)                  # noqa: E731

# sensors: ours inside and out, somebody else's indoor kit in the ring, a model, a forecast, a portal, a child node,
# a station quiet for three days, one quiet for forty (outside the 30-day archive), and one that never spoke
for sid, kind, local, indoor in (("v-room", "sensor", True, True), ("v-yard", "sensor", True, False),
                                 ("v-ring-in", "sensor", False, True), ("v-model", "model", False, False),
                                 ("v-fc", "model", False, False), ("v-portal", "portal", False, False),
                                 ("v-child", "child", False, False), ("v-quiet", "sensor", False, False),
                                 ("v-gone", "sensor", False, False), ("v-mute", "sensor", True, False)):
    q("INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, kind, scale, meta) "
      "VALUES (%s, 'test', %s, -8.8, 115.1, %s, %s, %s, 'community', '{\"k\": 1}')", sid, sid.upper(), indoor, local, kind)

def rows(sid, metric, minutes_ago, values):
    """One reading a step apart, newest first, starting `minutes_ago` back (negative: the future)."""
    for i, v in enumerate(values):
        q("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (now() - make_interval(mins => %s), %s, %s, %s)",
          minutes_ago + i * 7, sid, metric, v)

rows("v-room", "pm25", 2, [9, 11, 30, 4, 5, 6, 7, 8, 12, 15])     # inside 15 min, the hour and the day
rows("v-room", "temp", 1, [29.5, 29.4])
rows("v-yard", "pm25", 3, [14, 13])
rows("v-yard", "pm25", 60 * 23, [99])                               # inside the day, outside the hour
rows("v-yard", "pm25", 60 * 30, [500])                              # outside the day: never in stats
rows("v-ring-in", "pm25", 5, [0.3])
rows("v-model", "pm25_model", 30, [18, 17, 16])
rows("v-model", "uv_index", 30, [9])
rows("v-fc", "fc_temp", -60 * 40, [31])                             # forecast rows are stamped in the future
rows("v-fc", "fc_temp", 60, [28])
rows("v-portal", "datasets_total", 60 * 24 * 60, [120])             # a portal heard two months ago still counts
rows("v-child", "pm25", 10, [6])
rows("v-quiet", "pm25", 60 * 24 * 3, [21, 22])
rows("v-quiet", "humidity", 60 * 24 * 4, [70])
rows("v-gone", "pm25", 60 * 24 * 40, [3])

def same(old, new, what):
    a = {tuple(sorted(r.items())) for r in old}
    b = {tuple(sorted(r.items())) for r in new}
    assert a == b and len(old) == len(new), f"{what} differs\n  old only: {sorted(a - b)}\n  new only: {sorted(b - a)}"

q(OLD_STATS); old = cur.fetchall()
q("SELECT * FROM stats"); new = cur.fetchall()
same(old, new, "stats")
assert {r["sensor_id"] for r in new} == {"v-room", "v-yard", "v-ring-in"}, "stats: sensors heard today, nothing else"
yard = next(r for r in new if r["sensor_id"] == "v-yard")
assert yard["last"] == 14 and round(yard["mean_24h"], 6) == round((14 + 13 + 99) / 3, 6) and yard["mean_1h"] == 13.5
print(f"  stats: {len(new)} rows, the same as the old view's, means and last value included")

q(OLD_OBS); old = cur.fetchall()
q("SELECT sensor_id, metric, value, ts, name, kind, scale, local, cadence, meta::text AS meta FROM observations")
new = cur.fetchall()
same(old, new, "observations")
fc = next(r for r in new if r["sensor_id"] == "v-fc")
assert fc["value"] == 28, "observations: a row stamped in the future is not an observation yet, the newest one that has happened is"
assert {r["sensor_id"] for r in new} == {"v-model", "v-fc", "v-portal", "v-child"} and len(new) == 5, new
print(f"  observations: {len(new)} rows, the same as DISTINCT ON's up to now, the future forecast row left out and the old portal row kept")

days = ns["SILENT_DAYS"]
q(OLD_SILENT, days); old = cur.fetchall()
q(ns["SILENT_SQL"], days); new = cur.fetchall()
same(old, new, "the archive of silence")
assert [r["sensor_id"] for r in new] == ["v-quiet"], new
print("  silence: the station quiet three days and nothing else, at the same time as the old query")

# the revision rule (app/store.py, docs/SPEC_next_days.md §3): a newer model run replaces a forecast hour that has not
# happened yet; nothing else is ever overwritten
from store import insert_readings  # noqa: E402
q("INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, kind, scale, meta) "
  "VALUES ('v-rev', 'test', 'V-REV', -8.8, 115.1, false, false, 'model', 'community', '{}')")
q("SELECT now() AS t"); t0 = cur.fetchone()["t"]
future, past = t0 + timedelta(hours=5), t0 - timedelta(hours=5)


def stored(metric, ts):
    q("SELECT value FROM readings WHERE sensor_id = 'v-rev' AND metric = %s AND ts = %s", metric, ts)
    return [r["value"] for r in cur.fetchall()]


insert_readings(cur, [(future, "v-rev", "fc_temp", 30.0)]); insert_readings(cur, [(future, "v-rev", "fc_temp", 31.0)])
assert stored("fc_temp", future) == [31.0], "a future fc_ row written twice keeps the second value: the newer run wins"
insert_readings(cur, [(past, "v-rev", "fc_rain", 1.0)]); insert_readings(cur, [(past, "v-rev", "fc_rain", 2.0)])
assert stored("fc_rain", past) == [1.0], "a past fc_ row keeps the first: it stays as it was when it last was the future"
insert_readings(cur, [(future, "v-rev", "uv_index", 8.0)]); insert_readings(cur, [(future, "v-rev", "uv_index", 9.0)])
assert stored("uv_index", future) == [8.0], "a future row that is not a forecast metric keeps the first: a measured clock is never rewritten"
insert_readings(cur, [(past, "v-rev", "fc_wind", 10.0), (future, "v-rev", "fc_wind", 40.0)])
q("SELECT value, ts FROM observations WHERE sensor_id = 'v-rev' AND metric = 'fc_wind'")
got = cur.fetchall()
assert [(r["value"], r["ts"]) for r in got] == [(10.0, past)], f"observations returns the past hour, not the future one: {got}"
print("  revisions: a future fc_ hour takes the newer run; a past one, a measured one and observations stay as they were")

con.rollback()
print("views: every check passed")
