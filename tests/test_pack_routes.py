"""A pack serves its own routes (packs/<id>/routes.py), mounted by app/packs.py::routers() when main is imported.

GET /forecast and GET /nearby were core routes until 23 Oct 2026. They answer as before while their pack is on, 404
while it is off (PACKS_ENABLED can change in Set up without a restart), and a pack puts its own paths on the `open`
share list from pack.yaml. Importing main still opens no database.

    PACKS_DIR=packs PYTHONPATH=app python3 tests/test_pack_routes.py
"""
import os
import time

os.environ.update(PACKS_DIR="packs", ADMIN_TOKEN="admin-tok", NODE_LAT="-8.8", NODE_LON="115.1",
                  DATABASE_URL="postgresql://unused/never-connected")

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("pack routes: request checks skipped (pip install -r app/requirements.txt)")
    raise SystemExit(0)

import settings  # noqa: E402
ROWS = {"PACKS_ENABLED": "", "SHARE_LEVEL": "open"}
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}

import db  # noqa: E402
import main  # noqa: E402
import auth  # noqa: E402
assert db._pool is None, "importing main opened the database to mount the packs' routes"


class Cur:
    """Every query answers no rows: this is about which routes exist and who may reach them, not about data."""
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, *a): pass
    def fetchall(self): return []


class Con:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return Cur()


db.db = lambda: Con()
c = TestClient(main.app)
H = {"Authorization": "Bearer admin-tok"}

# ---- on: answered as before
r = c.get("/forecast", headers=H)
assert r.status_code == 200 and r.json()["hours"] == [] and r.json()["point"] == {"lat": -8.8, "lon": 115.1}, r.text
assert "BMKG" in r.json()["attribution"][0]
assert r.json()["schema"] == "forecast-v0" and r.json()["lines"] == [] and r.json()["openmeteo"] is False, r.text
assert [d["rows"] for d in r.json()["days"]] == [{}, {}, {}], "no rows at all is three empty days, not an error"
r = c.get("/nearby", headers=H)
assert r.status_code == 200 and r.json()["ring"] == [], r.text
print("  /forecast and /nearby answer from their packs while the packs are on")

# /earth and /earth/frame.png moved the same day, into earth and earth-engine
r = c.get("/earth", headers=H)
assert r.status_code == 200 and r.json()["years"] == [] and "hint" in r.json(), r.text
assert c.get("/earth/frame.png?year=2016", headers=H).status_code == 404, "no frame, the route's own 404"
ROWS["PACKS_ENABLED"] = "earth"
assert c.get("/earth", headers=H).json()["imagery"]["sentinel"] == [], "earth-engine off: no imagery listed"
assert "pack is off" in c.get("/earth/frame.png?year=2016", headers=H).json()["detail"]
ROWS["PACKS_ENABLED"] = ""
print("  /earth answers from the earth pack, /earth/frame.png from earth-engine")

# ---- off: 404, without a restart
ROWS["PACKS_ENABLED"] = "air-quality,heat"
for path in ("/forecast", "/nearby", "/earth", "/earth/year.png?year=2020"):
    r = c.get(path, headers=H)
    assert r.status_code == 404 and "pack is off" in r.json()["detail"], (path, r.status_code, r.text)
ROWS["PACKS_ENABLED"] = ""
assert c.get("/forecast", headers=H).status_code == 200, "back on, back"
print("  and 404 while their pack is off, with no restart")

# ---- the share list comes from the packs, and only from official ones
assert {"/forecast", "/nearby", "/earth", "/earth/change.png", "/earth/year.png", "/earth/frame.png"} <= auth._SHARE_OPEN[0], \
    "a pack's share: open adds its paths"
assert "/forecast" not in auth._SHARE_OFF[0] and "/forecast" not in open("app/auth.py").read(), "auth.py names no pack route"
r = c.get("/forecast")                                   # no token, from the test client's own address, at open
assert r.status_code == 200, r.text
print("  their paths join the open share list from pack.yaml, not from auth.py")

# ---- main no longer defines them
src = open("app/main.py").read()
assert not any(f'@app.get("{p}"' in src for p in ("/forecast", "/nearby", "/earth", "/earth/frame.png"))
print("pack routes: mounted from the packs, gated by PACKS_ENABLED, shared by pack.yaml")
