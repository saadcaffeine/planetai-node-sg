"""The core measures a kinded rule reads: recent_15m and usual_by_hour (docs/SPEC_alerts.md §3).

Run in DuckDB, the way tests/trustdb.py replays the trust rules. Needs duckdb. The fixture holds no temp or humidity,
so those two are the synthetic profile T.heat_days (shaped to the curve in SPEC §1), not readings.
Run: python3 tests/test_measures.py
"""
import datetime as dt
import sys

try:
    import trustdb as T
except ImportError as e:            # duckdb missing: the suite declares its skip
    print(f"  skipped: {e}")
    sys.exit(0)

K = "sc-19880"                       # an indoor, local kit in tests/data/node1-sensors.tsv
rows = T.readings()
at = T.FIXTURE_NOW
node = T.Node(T.week(rows, at, days=15) + T.heat_days([K], at, days=15))
node.refresh_usual(at)

q = lambda sql: node.con.execute(sql.replace("now()", f"TIMESTAMPTZ '{at.isoformat()}'")).fetchall()

r15 = node.recent(at)
buckets = {b for b, s, m, v in r15 if s == K and m == "temp"}
assert buckets, "an indoor kit has 15-minute temp buckets"
assert all(b.minute in (0, 15, 30, 45) for b in buckets), "buckets fall on quarter hours"
assert max(buckets) <= at and min(buckets) > at - dt.timedelta(hours=24, minutes=15), "only the last 24 h"
app = [v for b, s, m, v in r15 if s == K and m == "apparent"]
assert app and all(20 < v < 50 for v in app), f"apparent temperature is derived and plausible: {app[:3]}"
print(f"  recent_15m: {len(buckets)} quarter-hour temp buckets for {K}, and an apparent row beside each")

u = q(f"SELECT hour, median, p75, p90, n FROM usual_by_hour WHERE sensor_id = '{K}' AND metric = 'apparent' ORDER BY hour")
assert len(u) == 24, f"one row per local hour, got {len(u)}"
assert all(med <= p75 <= p90 for _, med, p75, p90, _ in u), "median <= p75 <= p90"
assert all(n >= 10 for *_, n in u), "fourteen days give each hour at least ten samples"
# Today never counts toward its own usual: exactly the fourteen complete local days before today, for every hour. A
# window ending at now() put today's partial hour in (hour 21 at 21:14 had 15 samples), so a long hot run today
# raised the very bar it was measured against.
assert all(n == 14 for *_, n in u), f"fourteen complete days before today, every hour: {[(h, n) for h, *_, n in u if n != 14]}"
day = {h: med for h, med, *_ in u}
assert day[16] > day[4], f"the room's afternoon is warmer than its night: 16h {day[16]:.1f} vs 04h {day[4]:.1f}"
print(f"usual_by_hour: 24 local hours for {K}; 04h {day[4]:.1f}, 16h {day[16]:.1f} °C apparent (median)")
