"""The custody gate: a peer across the street reaches no cell, however local it looks.

Written before the implementation and run failing first — at 9971a80 it reported

    _buckets   192 -> 204        a kind='peer' row with local=TRUE counted as this node's own data
    heat cell    0.0 -> 4.0      packs/heat/cells.yml read s.local with no kind filter

which is the only way to know a gate is wired to the thing it claims to guard. docs/SPEC_custody.md is the
argument; this file is what holds it.

`local` was written on 2 September 2026 for a node that was a house (74a8b64). `kind` arrived the next day
with the child push (15785db), and nothing reconciled them. `local` still means "ours AND here"
(app/sources.py::stamp_local) — custody is `local OR kind='child'`, and a peer is neither. See §1 and §2.

Method: build the same node twice, once with one extra peer row, and assert every number comes out identical.
Comparing two databases rather than naming packs means a pack written next year that reads a peer breaks this
without anyone remembering the spec. Nothing here asserts HOW custody is expressed, so the implementation is
free to choose the generated column, the CHECK, or the two-clause predicate.

    bash -c 'PYTHONPATH=app python3 tests/test_custody.py'
    pip install duckdb          # dev only, same dependency as test_nearby and test_shipped
"""
from __future__ import annotations

import datetime as dt
import glob
import inspect
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import duckdb
    import yaml
except ImportError:
    print("  - custody gate skipped (pip install duckdb pyyaml)")
    sys.exit(0)

import trustdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = trustdb.FIXTURE_NOW          # 7 Sep 2026 13:14:22 UTC, the last reading in the node #1 dump

# A stranger's node 40 m away: inside LOCAL_RADIUS_M (500 m), indoors, reporting three metrics right now, and
# written local=TRUE the way a hand-edited row or a restore from somebody else's dump would write it.
PEER = ("peer-1", "baliairdispatch", "Neighbour's node", -8.82744, 115.15741, True, True, "peer")


def _schema() -> str:
    """init.sql with line comments stripped — one of them ends in a semicolon (see trustdb._schema)."""
    sql = open(os.path.join(ROOT, "init.sql")).read()
    return "\n".join(re.sub(r"--.*$", "", line) for line in sql.splitlines())


def _generated(sql: str, table: str) -> list[str]:
    """Generated columns that init.sql adds by ALTER, as column definitions.

    DuckDB refuses "Adding generated columns after table creation", so they have to be spliced into the
    CREATE TABLE. The EXPRESSION is read out of init.sql and never retyped here: a copy would let the schema
    and the gate drift apart, and then the gate would be testing a predicate nobody ships. STORED -> VIRTUAL
    is the only edit, and it changes where the value is computed, not what it is.
    """
    return [f"{name} {typ} GENERATED ALWAYS AS ({expr}) VIRTUAL" for name, typ, expr in
            re.findall(rf"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS (\w+) (\w+)\s+"
                       r"GENERATED ALWAYS AS \((.*?)\) STORED", sql, re.S)]


def _ddl() -> str:
    """The tables and views a cell or rho can read. `observations` is here because several packs read it;
    it returns nothing under these fixtures, which is still an assertion worth making on both sides."""
    sql, out = _schema(), []
    for t in ("sensors", "readings", "channel_roles", "alerts", "actions", "events", "readings_1h_done"):
        ddl = (re.search(rf"CREATE TABLE IF NOT EXISTS {t} \(.*?\n\);", sql, re.S).group(0)
               .replace("JSONB", "JSON").replace("BIGSERIAL PRIMARY KEY", "BIGINT PRIMARY KEY"))
        for col in _generated(sql, t):
            ddl = ddl.replace("\n);", f",\n  {col}\n);")
        out.append(ddl)
    # rho also reads the event engine's tables (what was sent, and answers by event_id): empty here, which is the
    # rules node this gate is about, so only their shape matters.
    out.append("CREATE TABLE alert_events (id BIGINT, level TEXT);\n"
               "CREATE TABLE event_messages (ts TIMESTAMPTZ, event_id BIGINT, reason TEXT, sent BOOLEAN, mode TEXT);\n"
               "ALTER TABLE actions ADD COLUMN event_id BIGINT;")
    out.append(re.search(r"CREATE VIEW readings_1h AS.*?;", sql, re.S).group(0))
    # DuckDB merges a USING column, so the view's own r.sensor_id will not bind. An explicit ON is the same join.
    out.append(re.search(r"CREATE VIEW observations AS.*?;", sql, re.S).group(0)
               .replace("JOIN sensors s USING (sensor_id)", "JOIN sensors s ON s.sensor_id = r.sensor_id"))
    return "\n".join(out)


def _pg(sql: str) -> str:
    """Postgres as shipped -> what DuckDB can run at a fixed instant. now() and the session TimeZone only."""
    return (sql.replace("now()", f"TIMESTAMPTZ '{NOW.isoformat()}'")
               .replace("current_setting('TimeZone')", "'UTC'")
               .replace("JOIN sensors s USING (sensor_id)", "JOIN sensors s ON s.sensor_id = r.sensor_id"))


def node(with_peer: bool):
    """Node #1's five real kits and its real last 24 hours, optionally plus one peer."""
    con = duckdb.connect()
    con.execute(_ddl())
    who, rows = trustdb.sensors(), trustdb.day(trustdb.readings())
    if with_peer:
        who = who + [PEER]
        rows = rows + [(NOW - dt.timedelta(minutes=m), "peer-1", metric, value)
                       for m in range(0, 180, 10)
                       for metric, value in (("pm25", 99.0), ("temp", 34.0), ("humidity", 80.0))]
    con.executemany("INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, kind) VALUES (?,?,?,?,?,?,?,?)", who)
    seen = set()
    con.executemany("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (?,?,?,?)",
                    [r for r in rows if not (r[:3] in seen or seen.add(r[:3]))])
    return con


def one(con, sql):
    row = con.execute(_pg(sql)).fetchone()
    return row[0] if row else None


clean, peered = node(False), node(True)
failures = []

# ---- 1. the core's honesty check, read OUT OF app/index.py rather than pasted here. A copy of the SQL in this
# file would fail forever: the implementation would change and the gate would keep testing the old string.
def buckets_sql() -> str:
    import index
    src = inspect.getsource(index._buckets)
    m = re.search(r'cur\.execute\(\s*"""(.*?)"""', src, re.S)
    assert m, "app/index.py::_buckets no longer runs one triple-quoted statement — update this extractor"
    return m.group(1)


BUCKETS = buckets_sql()
a, b = one(clean, BUCKETS), one(peered, BUCKETS)
if a != b:
    failures.append(f"_buckets counts the peer: {a} -> {b}. A node that measures nothing new would be able to "
                    f"claim `live` off a stranger's sensor (app/index.py:52).")

# ---- 2. no pack cell may see it. Every cells.yml in the tree, both databases, same answer.
# Tolerance, not equality: air-quality's first cell filters kind='sensor' and is already correct, but its sum
# reassociates when a row it excludes is present, moving the 15th decimal. An exact test would cry wolf there.
for f in sorted(glob.glob(os.path.join(ROOT, "packs/*/cells.yml"))):
    pack = os.path.basename(os.path.dirname(f))
    for i, c in enumerate(yaml.safe_load(open(f)) or []):
        try:
            va, vb = one(clean, c["sql"]), one(peered, c["sql"])
        except Exception as e:  # noqa: BLE001
            failures.append(f"{pack}/cells.yml #{i} ({c['cell']}) would not run: {str(e).splitlines()[0]}")
            continue
        same = (va is None and vb is None) or (
            va is not None and vb is not None and math.isclose(float(va), float(vb), rel_tol=1e-9, abs_tol=1e-12))
        if not same:
            failures.append(f"{pack}/cells.yml #{i} ({c['cell']}) counts the peer: {va} -> {vb}. "
                            f"A neighbour's air is in this node's Index cell.")

# ---- 3. and the fix must not be "exclude everything": node #1's own five kits still count.
if a in (0, None):
    failures.append(f"node #1's own kits stopped counting: _buckets = {a} on a database holding five local kits")

print(f"custody: {'FAILED' if failures else 'ok'} — {len(failures)} leak(s); "
      f"_buckets {a} clean / {b} with one peer")
for msg in failures:
    print(f"    ✗ {msg}")
assert not failures, (
    "a kind='peer' row with local=TRUE reaches this node's numbers. This is the gate for "
    "docs/SPEC_custody.md and it is expected to fail until §2 and §4 are implemented.")
print("    a peer across the street reaches no cell, and node #1's own kits still do")


# ---- 4. rho pools a child's events with this node's own alerts (docs/SPEC_custody.md §4).
#
# Before this, push_aggregates() sent readings only, so a City node's Governance cell counted the alerts it
# raised itself while ten children below it measured rho every day. The check that matters is not that the
# number moved — it is that a node with NO children reads an empty `events` table and gets exactly what it
# got before, because that is the node everyone is already running.
def rho_at(alerts, actions, events):
    con = duckdb.connect()
    con.execute(_ddl())
    con.executemany("INSERT INTO alerts (id, ts, rule_id, level, text) VALUES (?,?,?,?,?)", alerts)
    con.executemany("INSERT INTO actions (ts, alert_id, stage) VALUES (?,?,?)", actions)
    if events:      # duckdb's executemany refuses an empty list, and "no children" is the case that matters
        con.executemany("""INSERT INTO events (child, alert_id, rule, level, raised_at, responded_at, acted_at)
                           VALUES (?,?,?,?,?,?,?)""", events)
    import index
    sql = re.search(r'cur\.execute\(\s*"""(.*?)"""', inspect.getsource(index.rho), re.S).group(1)
    sql = (sql.replace("%(back)s", "0").replace("make_interval(days => 0)", "interval '0 days'")
              .replace("split_part(rule_id, '/', 1) = ANY(%(rep)s::text[])", "FALSE")   # no pack replaced: a rules node
              .replace("now()", f"TIMESTAMPTZ '{NOW.isoformat()}'"))
    cur = con.execute(sql)
    return dict(zip([d[0] for d in cur.description], cur.fetchone()))


H = dt.timedelta(hours=1)
own_alerts  = [(1, NOW - 6 * H, "air-quality/indoor_pm25_high", "act", "x")]
own_actions = [(NOW - 5 * H, 1, "acted")]
child_events = [("mahon1", "7", "air-quality/indoor_pm25_high", "act", NOW - 8 * H, None,          NOW - 7 * H),
                ("mahon1", "9", "heat/indoor_hot",              "act", NOW - 4 * H, NOW - 3 * H,   None),
                ("ubud",   "2", "air-quality/indoor_pm25_high", "act", NOW - 2 * H, None,          None)]

alone = rho_at(own_alerts, own_actions, [])
if alone["alerts_act"] != 1 or alone["acted"] != 1:
    failures.append(f"a node with no children no longer reads its own rho: {alone}")

both = rho_at(own_alerts, own_actions, child_events)
if both["alerts_act"] != 4:
    failures.append(f"rho counts {both['alerts_act']} act-level alerts, expected 4 (1 own + 3 pushed)")
if both["acted"] != 3:
    failures.append(f"rho counts {both['acted']} answered, expected 3 — the child's un-answered alert must "
                    f"count against rho, not vanish from it: {both}")

# and the events table may not carry a household's sentence, whatever a future child pushes.
cols = {r[1] for r in duckdb.connect().execute(_ddl()).execute("PRAGMA table_info('events')").fetchall()}
for forbidden in ("text", "note", "actor", "sensor_id"):
    if forbidden in cols:
        failures.append(f"`events` has a `{forbidden}` column: 'shut the bedroom windows' describes a house "
                        f"and must not leave it (docs/SPEC_custody.md §4)")

print(f"rho: {both['acted']}/{both['alerts_act']} answered once a child pushes, {alone['acted']}/{alone['alerts_act']} alone")
assert not failures, "\n".join(failures)


# ---- 5. no peer and no model is pushed to a parent (AGENTS.md: "Peers never roll up").
#
# The parent stores every row it receives as kind='child', and kind='child' IS custody, so the push is the last
# place a peer can be stopped. Until 21 Oct 2026 it filtered only `private`, and node #1 would have pushed 178
# rows of other people's stations and Open-Meteo beside its own 94. The statement is read out of
# app/main.py::push_aggregates, never retyped, and run on the same two databases as above.
def push_sql() -> str:
    import ast
    import packs
    tree = ast.parse(open(os.path.join(ROOT, "app/main.py")).read())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "push_aggregates")
    call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "execute")
    return eval(compile(ast.Expression(call.args[0]), "push_aggregates", "eval"), {"packs": packs})


PUSH = push_sql()
ROWS_SQL = f"SELECT CAST(bucket AS TEXT), sensor_id, metric, mean FROM ({_pg(PUSH)}) p"   # no tz objects: no pytz
pushed_clean = sorted(clean.execute(ROWS_SQL).fetchall(), key=str)
pushed_peer = sorted(peered.execute(ROWS_SQL).fetchall(), key=str)
if pushed_clean != pushed_peer:
    failures.append(f"the push to a parent changes when a peer is added: {len(pushed_clean)} -> {len(pushed_peer)} rows")
if any(r[1] == "peer-1" for r in pushed_peer):
    failures.append("the peer's hourly means are pushed to the parent, which would count them as its own children's")
if not pushed_clean:
    failures.append("the push sends nothing from a database holding node #1's own kits")
if "indoor" not in PUSH:
    failures.append("the push no longer carries `indoor`: a parent would average the kitchen into outdoor air")
print(f"push: {len(pushed_clean)} rows clean, {len(pushed_peer)} with one peer, none of them the peer's")
assert not failures, "\n".join(failures)


# ---- 6. readings_1h is the same answer however far the hourly table has got (init.sql, main.refresh_hourly).
#
# The view reads finished hours from readings_1h_done and groups the rest live from where that table ends. An empty
# table, a full one, and a stale one refreshed for the last 26 hours must all give the hours a plain grouping of every
# reading gives. A view that went short when the table lagged would leave every cell and chart missing its history
# with no error anywhere. The two statements are read out of app/main.py, never retyped.
def hourly_sql() -> dict:
    import ast
    tree = ast.parse(open(os.path.join(ROOT, "app/main.py")).read())
    got = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in ("HOURLY_DELETE", "HOURLY_INSERT"):
            got[n.targets[0].id] = ast.literal_eval(n.value)
    return got


def hourly(con, since: str) -> None:
    for k in ("HOURLY_DELETE", "HOURLY_INSERT"):
        con.execute(_pg(HOURLY[k].replace("%(since)s::timestamptz", f"TIMESTAMPTZ '{since}'")))


HOURLY = hourly_sql()
PLAIN = ("SELECT CAST(date_trunc('hour', ts) AS TEXT), sensor_id, metric, round(avg(value), 9), min(value), max(value), "
         "count(*) FROM readings GROUP BY 1, 2, 3")
VIEW = "SELECT CAST(bucket AS TEXT), sensor_id, metric, round(mean, 9), min, max, n FROM readings_1h"
want = sorted(clean.execute(_pg(PLAIN)).fetchall(), key=str)
cases = {"empty": sorted(clean.execute(_pg(VIEW)).fetchall(), key=str)}
hourly(clean, "-infinity")
cases["full"] = sorted(clean.execute(_pg(VIEW)).fetchall(), key=str)
late = (NOW - dt.timedelta(hours=2)).replace(minute=7, second=0, microsecond=0)   # an hour the table already holds
clean.execute("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (?, ?, 'pm25', 500.0)", [late, trustdb.sensors()[0][0]])
want_late = sorted(clean.execute(_pg(PLAIN)).fetchall(), key=str)
stale = sorted(clean.execute(_pg(VIEW)).fetchall(), key=str)
# mid-hour, where there are readings: a refresh that cut at the minute instead of the hour fails here
hourly(clean, (NOW - dt.timedelta(hours=3, minutes=17)).isoformat())
cases["refreshed"] = sorted(clean.execute(_pg(VIEW)).fetchall(), key=str)
for name, got in cases.items():
    if got != (want_late if name == "refreshed" else want):
        failures.append(f"readings_1h with the hourly table {name} is not a plain grouping of the readings")
if not stale or stale == want_late:
    failures.append("a late reading reached readings_1h before any refresh, so the table is not what the view reads")
print(f"readings_1h: {len(want)} hours, the same with the hourly table empty, full and refreshed after a late reading")
assert not failures, "\n".join(failures)

