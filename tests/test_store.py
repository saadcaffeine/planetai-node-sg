"""A newer forecast replaces an older one; nothing else in `readings` is ever overwritten.

Run: PYTHONPATH=app python3 tests/test_store.py
Pure text checks. The row behaviour itself (future fc_ row updated, past one kept, a measured `temp` with a future
clock kept) is proved on a scratch PostGIS and pasted in the commit body, because that is the part only Postgres
can say. Two things here are easy to break and fail silently: a `%` in the LIKE that psycopg reads as a
placeholder, and a second INSERT site that quietly starts overwriting measurements.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402


def src(p):
    with open(os.path.join(ROOT, p)) as f:
        return f.read()


SQL = " ".join(store.READINGS_SQL.split())
assert "ON CONFLICT (sensor_id, metric, ts) DO UPDATE SET value = EXCLUDED.value" in SQL, SQL
where = SQL.split("DO UPDATE SET value = EXCLUDED.value", 1)[1]
assert "WHERE EXCLUDED.metric LIKE 'fc\\_%%'" in where, "the fc_ prefix, with the % doubled for psycopg: " + where
assert "AND EXCLUDED.ts > now()" in where, where
assert "DO NOTHING" not in SQL

# the % doubling is what lets psycopg run it with parameters: one placeholder per column, no stray one.
assert len(re.findall(r"(?<!%)%s", SQL)) == 4 and "%(" not in SQL
assert SQL.replace("%%", "").count("%") == 4, "a lone % would be read as a placeholder"

# the helper hands the rows to executemany and says how many rows it wrote
class Cur:
    rowcount = 3
    def executemany(s, q, rows): s.q, s.rows = q, rows
c = Cur()
assert store.insert_readings(c, [(1, 2, 3, 4)]) == 3 and c.q == store.READINGS_SQL and c.rows == [(1, 2, 3, 4)]
c.rowcount = -1
assert store.insert_readings(c, []) == 0, "rowcount can be -1 with nothing written"

# the two forecast writers use it...
main = src("app/main.py")
poll = main[main.index("for name, fn in sources.enabled(hc):"):main.index("def _store(sensors, readings)")]
assert "store.insert_readings(cur, readings)" in poll and "INSERT INTO readings" not in poll, "the poll insert"
assert "import store" in main
fetch = src("packs/forecast/fetch.py")
assert "insert_readings(cur, readings)" in fetch and "INSERT INTO readings" not in fetch
assert 'sys.path.insert(0, "/app")' in fetch and "import store" in fetch

# ...and nothing else does: MQTT, /readings, bootstrap, the backfills keep DO NOTHING. A measured reading with a
# future clock must never be overwritten, so no other site gets the revision rule.
sites = 0
for p in sorted(glob.glob(os.path.join(ROOT, "app", "*.py")) + glob.glob(os.path.join(ROOT, "app", "issues", "*.py"))
                + glob.glob(os.path.join(ROOT, "packs", "*", "*.py"))):
    if p.endswith("/store.py") or p.endswith("forecast/fetch.py"):
        continue
    for m in re.finditer(r"INSERT INTO readings \(ts, sensor_id, metric, value\)(.{0,200})", open(p).read(), re.S):
        tail = m.group(1)
        if "ON CONFLICT DO NOTHING" in tail:
            sites += 1
        else:       # the two that already overwrite on purpose: a child's hourly means and the things pack's counts
            assert "DO UPDATE SET value = EXCLUDED.value" in tail and "fc" not in tail, (p, tail[:120])
assert sites >= 4, f"expected the other DO NOTHING sites, found {sites}"

# the view stops at now: no reader of `observations` is handed a forecast hour as the latest value
init = src("init.sql")
view = init[init.index("CREATE VIEW observations AS"):]
view = view[:view.index(";\n")]
assert "ts <= now()" in view, view

print(f"test_store: ok — the revision rule, its % escaping, the two writers, {sites} sites still DO NOTHING, observations <= now()")
sys.exit(0)
