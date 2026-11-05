"""Rooms in the household's words (Tomas, 14 Oct 2026: node #1's K, L and S are Kids, Living Room and Studio).

Structural half reads init.sql: the room becomes the sensor's name in the database, whatever writes the row, and the
platform's name is kept. Request half drives PATCH /sensors/{sid} and GET /sensors with the database stubbed.

Run: PYTHONPATH=app python3 tests/test_rooms.py
"""
import logging
import os
import re
import time

SQL = open("init.sql").read()

# ---------------------------------------------------------------- the trigger: one place, every writer
m = re.search(r"CREATE OR REPLACE FUNCTION sensors_room_is_the_name\(\).*?END \$\$;", SQL, re.S)
assert m, "the room is made the name in the database, so a poll, a pack and core all keep it"
body = m.group(0)
assert "NEW.name := NEW.room" in body and "NEW.source_name := NEW.name" in body
assert "TG_OP = 'INSERT' OR NEW.name IS DISTINCT FROM OLD.room" in body, "a rename must not save the old room as the platform's name"
assert "BEFORE INSERT OR UPDATE ON sensors FOR EACH ROW" in SQL and "DROP TRIGGER IF EXISTS sensors_room ON sensors" in SQL
assert SQL.index("ADD COLUMN IF NOT EXISTS room TEXT") < SQL.index("CREATE TRIGGER sensors_room"), "the column exists before the trigger"
print("schema: a room is the sensor's name whatever writes the row; the platform's name is kept")

# ---------------------------------------------------------------- the routes
logging.disable(logging.WARNING)
os.environ.update(ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok", NODE_NAME="bayu-2", NODE_LAT="-8.6478291",
                  NODE_LON="115.1385412", DATABASE_URL="postgresql://unused/never-connected")
import settings                                    # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"SHARE_LEVEL": "open"}}
import main                                       # noqa: E402
from fastapi.testclient import TestClient         # noqa: E402

DONE = []
SENSORS = {"sc-1": {"sensor_id": "sc-1", "name": "K ROOM - BAYU HOLES", "room": None, "source_name": None}}


class Cur:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=()):
        DONE.append((sql, params)); self.params = params
    def fetchone(self):
        if len(self.params) == 1:                       # SELECT name: does the sensor exist, and what was it called
            s = SENSORS.get(self.params[0])
            return {"name": s["name"]} if s else None
        room, _, sid = self.params
        s = SENSORS.get(sid)
        if not s:
            return None
        # what the trigger and the CASE do, in Python: enough to check the route hands them the right values
        s["source_name"] = s["source_name"] or s["name"]
        s["room"], s["name"] = room, room or s["source_name"]
        return dict(s)


class Con:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return Cur()


main.db = lambda: Con()
c = TestClient(main.app)
ADMIN, ACT = {"Authorization": "Bearer admin-tok"}, {"Authorization": "Bearer act-tok"}
assert c.patch("/sensors/sc-1", json={"room": "Kids"}).status_code in (401, 403)
assert c.patch("/sensors/sc-1", json={"room": "Kids"}, headers=ACT).status_code == 401, "admin only: it renames what the house reads"
r = c.patch("/sensors/sc-1", json={"room": "  Kids  "}, headers=ADMIN)
assert r.status_code == 200 and r.json()["sensor"]["name"] == "Kids" and r.json()["sensor"]["source_name"] == "K ROOM - BAYU HOLES", r.text
assert any(q.startswith("UPDATE sensors") and p[0] == "Kids" for q, p in DONE), "trimmed before it is stored"
assert DONE[-1] == ("UPDATE alert_events SET rooms = array_replace(rooms, %s, %s) WHERE %s = ANY(rooms)",
                    ("K ROOM - BAYU HOLES", "Kids", "K ROOM - BAYU HOLES")), "the rename follows into the event episodes"
assert c.patch("/sensors/sc-1", json={"room": "x" * 80}, headers=ADMIN).json()["sensor"]["room"] == "x" * 40, "forty characters at most"
assert c.patch("/sensors/sc-1", json={"room": 3}, headers=ADMIN).status_code == 422
r = c.patch("/sensors/sc-1", json={"room": None}, headers=ADMIN)
assert r.json()["sensor"]["name"] == "K ROOM - BAYU HOLES" and DONE[-2][1][0] is None, "null gives the platform's name back"
assert c.patch("/sensors/nope", json={"room": "Kids"}, headers=ADMIN).status_code == 404

ROWS = [{"sensor_id": "sc-1", "source": "smartcitizen", "name": "Kids", "room": "Kids", "source_name": "K ROOM - BAYU HOLES",
         "lat": -8.81, "lon": 115.16, "indoor": True, "local": True, "custody": True, "kind": "sensor", "scale": "community",
         "cadence": "PT5M", "meta": {}}]
main.q = lambda sql, *a: [dict(x) for x in ROWS]
assert c.get("/sensors", headers=ADMIN).json()[0]["source_name"] == "K ROOM - BAYU HOLES"
pub = TestClient(main.app, client=("192.168.4.20", 5000)).get("/sensors").json()[0]
assert "room" not in pub and "source_name" not in pub, "which room is which is the household's, not a stranger's"
print("routes: admin names a room, trimmed and capped, null gives the platform's name back; a stranger never reads it")
print("rooms: every check passed")
