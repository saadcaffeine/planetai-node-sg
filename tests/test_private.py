"""The `private` role (docs/decisions/2026-10-03-pack-design.md, point 2 (A)): a private reading never leaves the house.

One predicate, packs.public_sql, written once. This suite holds the decision's promise: a private row appears in none
of the daily export, the aggregates a parent receives (pushed or pulled), the report bundle, a read an agent makes,
or a raw read without the admin token; and readouts, sections, rules and cells are left as they were.

Structural half: every road out is written with the predicate. Request half: the routes, with the database stubbed.
Replay half: the predicate itself, on real rows, in duckdb.

Run: PYTHONPATH=app python3 tests/test_private.py
"""
import ast
import logging
import os
import re
import sys
import time

SQL = open("init.sql").read()
SRC = open("app/main.py").read()
REPORT = open("app/report.py").read()

# ---------------------------------------------------------------- the schema takes the word, fresh and on update
assert "'index','private')" in re.search(r"CREATE TABLE IF NOT EXISTS channel_roles \((.*?)\n\);", SQL, re.S).group(1)
assert re.search(r"DROP CONSTRAINT IF EXISTS channel_roles_role_check;\s*ALTER TABLE channel_roles ADD CONSTRAINT "
                 r"channel_roles_role_check\s*CHECK \(role IN \([^)]*'private'\)\)", SQL), \
    "a database made before 0.55 must accept the role too"
print("schema: private is a role, on a fresh database and an updated one")

# ---------------------------------------------------------------- every road out is written with the predicate
tree = ast.parse(SRC)
fn = {n.name: ast.get_source_segment(SRC, n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
for name in ("export", "push_aggregates", "aggregates"):
    assert 'packs.public_sql("r")' in fn[name] and "_shows_private" not in fn[name], \
        f"{name}: always public, whoever asks — it is what leaves the machine"
for name in ("readings", "history", "series", "sparks"):
    assert "_shows_private(request, authorization)" in fn[name], f"{name}: a raw read, private only to the admin token"
assert "_shows_private(request, authorization, raw=False)" in fn["stats"], "stats is a readout: the household's tokens and this machine"
for q_ in ("SERIES_SQL", "NOW_SQL"):
    body = re.search(rf'{q_} = """(.*?)\n"""', REPORT, re.S).group(1)
    assert "packs.public_sql(" in body, f"report.{q_}: the report is written by a model, so never private"
AGENT = open("app/agent.py").read()
assert re.search(r'def _get\(path: str\):\n(?:\s*#.*\n)?\s*r = httpx.get\(API \+ path, headers=\{"X-Agent": "agent"\}', AGENT), \
    "every agent read says it is an agent"
assert '"X-Agent": "agent"}, timeout=120)' in AGENT, "report_bundle says so too"
print("structure: export, both aggregate roads and the report always public; raw reads and agents by the rule")

# ---------------------------------------------------------------- the routes
logging.disable(logging.WARNING)
os.environ.update(ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok", NODE_LAT="-8.6478291", NODE_LON="115.1385412",
                  DATABASE_URL="postgresql://unused/never-connected")
import settings                                    # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"SHARE_LEVEL": "open"}}
import main                                       # noqa: E402
import packs                                      # noqa: E402
from fastapi.testclient import TestClient         # noqa: E402

assert "private" in packs.ROLES, "a pack may declare it"
P = packs.public_sql
SEEN = []
main.q = lambda sql, *a: (SEEN.append(sql), [])[1]
lan = TestClient(main.app)
ADMIN, ACT = {"Authorization": "Bearer admin-tok"}, {"Authorization": "Bearer act-tok"}
AGENT_ = {**ADMIN, "X-Agent": "agent"}
raw = ("/readings?metric=stock.tool", "/history?sensor_id=things:x&metric=stock.tool", "/series?metric=stock.tool",
       "/sparks?metric=stock.tool")


def filtered(path, headers):
    SEEN.clear()
    assert lan.get(path, headers=headers).status_code == 200, path
    return any("pc.role = 'private'" in s for s in SEEN)


for path in raw:
    assert filtered(path, {}), f"{path}: a reader with no token gets no private row"
    assert filtered(path, ACT), f"{path}: the act token is not the admin token"
    assert not filtered(path, ADMIN), f"{path}: the admin token reads the house's own"
    assert filtered(path, AGENT_), f"{path}: an agent never does, even holding the admin token"
# A readout answers them to the household (admin, act) and this machine, not to anyone the page answers at
# SHARE_LEVEL=open (14 Oct: the counts were on the network). TestClient arrives as "testclient", not this machine.
assert not filtered("/stats", ADMIN) and not filtered("/stats", ACT), "a readout for the household's own tokens"
assert filtered("/stats", {}), "a readout without the household's token gets no private row"
assert filtered("/stats", AGENT_) and filtered("/stats", {"X-Agent": "agent"}), "but not for an agent"
assert filtered("/aggregates?hours=2", ADMIN), "a parent's pull is public, whatever token"
print("routes: raw reads private only to the admin token; readouts unchanged; agents never; a parent's pull public")

# ---------------------------------------------------------------- the predicate, on real rows
try:
    import duckdb
except ImportError:
    print("replay: duckdb not installed  (skipped)")
    sys.exit(0)
c = duckdb.connect()
c.execute("CREATE TABLE sensors (sensor_id TEXT, source TEXT)")
c.execute("CREATE TABLE channel_roles (source TEXT, metric TEXT, role TEXT)")
c.execute("CREATE TABLE readings_1h (bucket TIMESTAMP, sensor_id TEXT, metric TEXT, mean DOUBLE)")
c.execute("INSERT INTO sensors VALUES ('things:bayu', 'things'), ('ag-1', 'airgradient')")
c.execute("INSERT INTO channel_roles VALUES ('things', 'stock.tool', 'private'), ('things', 'idle.tool', 'private'), "
          "('airgradient', 'pm25', 'ambient')")
c.execute("INSERT INTO readings_1h VALUES (now(), 'things:bayu', 'stock.tool', 31), (now(), 'things:bayu', 'idle.tool', 9), "
          "(now(), 'ag-1', 'pm25', 12), (now(), 'ag-1', 'unlisted', 1), (now(), 'things:bayu', 'undeclared', 2)")
left = sorted(c.execute(f"SELECT sensor_id, metric FROM readings_1h r WHERE {P('r')}").fetchall())
assert left == [("ag-1", "pm25"), ("ag-1", "unlisted"), ("things:bayu", "undeclared")], left
assert not c.execute(f"SELECT 1 FROM readings_1h WHERE {P('readings_1h')} AND metric LIKE '%.tool'").fetchall()
print("replay: a private pair never passes; an undeclared metric from the same source does, because the role is per pair")
print("private: every check passed")
