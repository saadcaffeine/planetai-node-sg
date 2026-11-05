"""The things a home keeps (docs/SPEC_inventory.md step 2): the table, the routes, the three private counts per class.

Structural half reads init.sql and app/main.py (the routes are packs/things since 24 Oct 2026): the table is kept as captures are (never in pack SQL, never on a road
out), and its counts are declared `private`. Request half drives the routes with the database stubbed.

Run: PYTHONPATH=app python3 tests/test_things.py
"""
import logging
import os
import re
import time

SQL = open("init.sql").read()
SRC = open("app/main.py").read()

# ---------------------------------------------------------------- the table, kept as captures are
m = re.search(r"CREATE TABLE IF NOT EXISTS things \((.*?)\n\);", SQL, re.S)
assert m, "init.sql: no things table"
for c, check in (("used", "'weekly','monthly','yearly','never'"), ("condition", "'works','needs_repair','broken'"),
                 ("offer", "'no','lend','give'")):
    assert re.search(rf"^\s*{c}\s.*CHECK \({c} IN \({check}\)\)", m.group(1), re.M), f"things.{c} is a CHECK"
assert "REVOKE ALL ON things FROM planetai_ro" in SQL, "pack SQL must not read a household's inventory"
for road in ("def export", "def push_aggregates", "def aggregates"):
    body = SRC[SRC.index(road):SRC.index("\n\n\n", SRC.index(road))]
    assert "things" not in body, f"{road} must never name the things table"
print("schema: things kept as captures are; no road out names it")

# ---------------------------------------------------------------- the routes
logging.disable(logging.WARNING)
os.environ.update(ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok", NODE_NAME="bayu-2", NODE_LAT="-8.6478291",
                  NODE_LON="115.1385412", DATABASE_URL="postgresql://unused/never-connected")
import settings                                    # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"SHARE_LEVEL": "open"}}
import main                                       # noqa: E402
import packs                                      # noqa: E402
from fastapi.testclient import TestClient         # noqa: E402

assert "vehicle" in main.THING_CLASSES and "vehicle" in packs.ROUTES["eyes"].EYES_CLASSES, "cars, motorbikes and trucks have a class"
assert "vehicle" in open("app/static/doors-data.js").read(), "and the Data door can file a finding under it"
ROWS = [{"id": 2, "added_at": "2026-10-13T01:00:00+00:00", "class": "tool", "name": "cordless drill", "count": 1,
         "used": "yearly", "condition": "works", "offer": "lend", "capture_id": None, "note": None},
        {"id": 1, "added_at": "2026-10-13T00:00:00+00:00", "class": "furniture", "name": "chairs", "count": 4,
         "used": "weekly", "condition": "needs_repair", "offer": "no", "capture_id": None, "note": None}]
import db                                         # noqa: E402 — the things pack's routes read through db (packs/things)
db.q = main.q = lambda sql, *a: [dict(r) for r in ROWS] if "FROM things" in sql else []
DONE = []


class Cur:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=()):
        DONE.append((sql, params)); self.sql, self.params = sql, params
    def executemany(self, sql, seq):
        DONE.extend((sql, p) for p in seq)
    def fetchone(self):
        if self.sql.startswith("SELECT class FROM things"):
            return {"class": "tool"} if self.params[0] == 2 else None
        if "coalesce(sum(count)" in self.sql:
            return {"stock": 3, "idle": 1, "repair": 0}
        if self.sql.startswith("DELETE"):
            return {"class": "tool"} if self.params[0] == 2 else None
        if "RETURNING *" in self.sql:
            return {**ROWS[0], "class": "vehicle"}
        return None


class Con:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return Cur()


db.db = main.db = lambda: Con()
c = TestClient(main.app)
ADMIN, ACT = {"Authorization": "Bearer admin-tok"}, {"Authorization": "Bearer act-tok"}
assert c.get("/things").status_code in (401, 403) and c.get("/things", headers=ACT).status_code == 401, "admin only"
j = c.get("/things", headers=ADMIN).json()
assert j["summary"] == {"things": 5, "idle": 1, "repair": 4, "offered": 1}, j["summary"]
assert j["classes"] == list(main.THING_CLASSES)
for bad in ({"class": "spaceship", "name": "x"}, {"class": "tool", "name": "  "}, {"class": "tool", "name": "x", "count": 0},
            {"class": "tool", "name": "x", "used": "daily"}, {"class": "tool", "name": "x", "offer": "sell"}):
    assert c.post("/things", json=bad, headers=ADMIN).status_code == 422, bad
assert c.post("/things", json={"class": "tool", "name": "x"}, headers=ACT).status_code == 401
DONE.clear()
r = c.post("/things", json={"class": "vehicle", "name": "  the   family  motorbike ", "used": "weekly", "evil": "x"}, headers=ADMIN)
assert r.status_code == 200, r.text
ins = next(p for s, p in DONE if s.startswith("INSERT INTO things"))
assert ins == ("vehicle", "the family motorbike", "weekly"), f"only known fields, words tidied: {ins}"
wrote = {p[2]: p[3] for s, p in DONE if s.startswith("INSERT INTO readings")}
assert wrote == {"stock.vehicle": 3.0, "idle.vehicle": 1.0, "repair.vehicle": 0.0}, wrote
assert all(p[1] == "things:bayu-2" for s, p in DONE if s.startswith("INSERT INTO readings")), "on the node's survey sensor"
DONE.clear()
assert c.patch("/things/2", json={"class": "vehicle"}, headers=ADMIN).status_code == 200
assert {p[2].split(".")[1] for s, p in DONE if s.startswith("INSERT INTO readings")} == {"tool", "vehicle"}, \
    "a thing moved between classes rewrites both"
assert c.patch("/things/9", json={"name": "x"}, headers=ADMIN).status_code == 404
assert c.patch("/things/2", json={}, headers=ADMIN).status_code == 422
DONE.clear()
assert c.delete("/things/2", headers=ADMIN).status_code == 200
assert {p[2] for s, p in DONE if s.startswith("INSERT INTO readings")} == {"stock.tool", "idle.tool", "repair.tool"}
assert c.delete("/things/9", headers=ADMIN).status_code == 404 and c.delete("/things/2", headers=ACT).status_code == 401
print("routes: admin only; validated; every change rewrites stock, idle and repair for each class it touched")

# ---------------------------------------------------------------- the counts are private, wherever they could go
roles = []
packs_channels, packs.channels = packs.channels, lambda: []
main.db = lambda: type("C", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False,
                                 "cursor": lambda s: type("K", (), {"__enter__": lambda k: k, "__exit__": lambda k, *a: False,
                                                                    "execute": lambda k, *a: None,
                                                                    "executemany": lambda k, sql, rows: roles.extend(rows)})(),
                                 "transaction": lambda s: type("T", (), {"__enter__": lambda t: t, "__exit__": lambda t, *a: False})()})()
main.load_channel_roles()
packs.channels = packs_channels
assert len(roles) == len(main.THING_CLASSES) * 3 and all(r["source"] == "things" and r["role"] == "private" for r in roles)
assert {r["metric"] for r in roles} >= {"stock.vehicle", "idle.tool", "repair.furniture"}
SEEN = []
main.q = lambda sql, *a: (SEEN.append(sql), [])[1]
for h, hidden in (({}, True), (ACT, True), (ADMIN, False), ({**ADMIN, "X-Agent": "agent"}, True)):
    SEEN.clear(); c.get("/observations", headers=h)
    assert ("pc.role = 'private'" in SEEN[-1]) == hidden, (h, SEEN[-1])
print("private: the counts are declared private by core, and /observations shows them to the admin token only, never an agent")
# ---------------------------------------------------------------- from a photo (step 3)
JS = open("app/static/doors-data.js").read()
assert "capture_id: +id" in JS and "a.confirmed_by && TKEEP" in JS, "a confirmed finding becomes a thing with its photo linked"
assert "TKEEP.classes.includes(f.class)" in JS, "only the classes a home keeps are offered"
_ER = open("packs/eyes/routes.py").read()          # the captures routes are the eyes pack's since 24 Oct 2026
cd = _ER[_ER.index("def capture_delete"):_ER.index("@router.get(\"/captures/{cid}/file\")")]
assert "UPDATE things SET capture_id = NULL WHERE capture_id = %s" in cd, "a deleted photo leaves its things, unlinked"
print("from a photo: a confirmed finding in a household class adds a thing, linked; deleting the photo unlinks it")
# ---------------------------------------------------------------- a pack since 24 Oct 2026, and no node loses it
# update.sh step 5e: a node that lists its packs gets `things` added, because it was on for every node in the core.
import subprocess as _sp, tempfile as _tf  # noqa: E402
_u = open("update.sh").read()
_step = _u[_u.index("# 5e."):_u.index("# 6. rebuild and restart")]
_STUB = r"""
pq() {   # the settings table, as a key=value file
  if [[ "$1" == SELECT* ]]; then k="$(sed -E "s/.*key = '([A-Z_]+)'.*/\1/" <<< "$1")"; sed -n "s/^${k}=//p" "$DB"
  else add="$(sed -E "s/.*\|\| ',([a-z-]+)'.*/\1/" <<< "$1")"; sed -i.bak -E "s/^(PACKS_ENABLED=.+)$/\1,${add}/" "$DB"; rm -f "$DB.bak"; fi
}
"""
def _5e(db_, env):
    with _tf.TemporaryDirectory() as t:
        open(f"{t}/db", "w").write(db_); open(f"{t}/.env", "w").write(env)
        _sp.run(["bash", "-c", "set -euo pipefail\n" + _STUB + _step], cwd=t, env={**os.environ, "DB": f"{t}/db"},
                capture_output=True, text=True, check=True)
        return open(f"{t}/db").read(), open(f"{t}/.env").read()
_db, _ = _5e("PACKS_ENABLED=air-quality,heat\n", "")
assert _db == "PACKS_ENABLED=air-quality,heat,things,eyes\n", _db
assert _5e(_db, "")[0] == _db, "a second update changed the list again"
assert _5e("", "PACKS_ENABLED=heat\n")[1] == "PACKS_ENABLED=heat,things,eyes\n"
assert _5e("PACKS_ENABLED=\n", "PACKS_ENABLED=\n") == ("PACKS_ENABLED=\n", "PACKS_ENABLED=\n"), "an empty list is every pack"
print("update.sh 5e: a node that lists its packs gets things and eyes added, once")
print("things: every check passed")
