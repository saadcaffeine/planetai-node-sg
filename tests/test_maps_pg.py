"""Place maps on a real database: the two tables, their CHECKs, the cascade and the widened actions stage.

On 4 Nov 2026 the light GIS put place_maps and place_marks in core, with init.sql enabling PostGIS ahead of them.
This holds the schema's own rules where they live, in the database: a mark is a marker, line, area or note, a colour
is 1 to 6, deleting a map takes its drawings with it, and the actions ledger accepts the stage `place`. The routes of app/maps.py are driven through the app: tokens, PostGIS's
own measures, the ledger's one row per minute, a drawing tied to an issue, an agent's map refused, and a shared
map's trip upstream: the warning, one put per change, one delete, the hold on the house, and the parent's read-only copy. Needs a
Postgres with init.sql applied, at RHO_PG_URL (CI's lint job starts one, on the PostGIS image); without it the
suite skips.
Run: RHO_PG_URL=postgresql://planetai:x@127.0.0.1:5432/planetai PYTHONPATH=app PACKS_DIR=packs python3 tests/test_maps_pg.py
"""
import os
import sys

url = os.getenv("RHO_PG_URL")
if not url:
    print("  - maps on a real database skipped (set RHO_PG_URL to a Postgres with init.sql applied)")
    sys.exit(0)
import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

con = psycopg.connect(url, row_factory=dict_row)          # one transaction, rolled back: nothing stays
cur = con.cursor()


def table_exists(name):
    cur.execute("SELECT to_regclass(%s) AS t", (name,))
    return cur.fetchone()["t"] is not None


def count(name):
    cur.execute(f"SELECT count(*) AS n FROM {name}")
    return cur.fetchone()["n"]


def raises(sql, *args):
    """True if the statement is refused by a constraint; a savepoint keeps the outer transaction alive."""
    try:
        with con.transaction():
            cur.execute(sql, args)
    except (psycopg.errors.CheckViolation, psycopg.errors.IntegrityError):
        return True
    return False


assert table_exists("place_maps") and table_exists("place_marks"), "init.sql creates both tables"
assert table_exists("place_maps_unshared"), "init.sql keeps the deletes still owed to the node upstream"
assert table_exists("node_cells"), "init.sql creates node_cells"
cur.execute("SELECT 1 FROM schema_version WHERE version = '0.65'")
assert cur.fetchone(), "init.sql records schema_version 0.65"
cur.execute("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
assert cur.fetchone(), "init.sql enabled PostGIS"
print("  both tables exist and PostGIS is on")

cur.execute("INSERT INTO place_maps (name) VALUES ('t') RETURNING id")
mid = cur.fetchone()["id"]
cur.execute("SELECT shared, held, from_node, remote_id, pushed_at, push_tried_at FROM place_maps WHERE id = %s", (mid,))
row = cur.fetchone()
assert row == {"shared": False, "held": False, "from_node": None, "remote_id": None, "pushed_at": None, "push_tried_at": None}, row
cur.execute("""INSERT INTO place_marks (map_id, kind, geom) VALUES
  (%s, 'area', ST_GeomFromText('POLYGON((115.167 -8.819,115.168 -8.819,115.168 -8.818,115.167 -8.819))',4326))""", (mid,))
cur.execute("SELECT colour FROM place_marks WHERE map_id = %s", (mid,))
assert cur.fetchone()["colour"] == 1, "colour defaults to 1"
cur.execute("INSERT INTO actions (stage, actor, note, choice) VALUES ('place','t','x','drew')")   # the check allows it
print("  a map, an area on it and a `place` action are accepted")

for bad in ("INSERT INTO place_marks (map_id, kind, geom) VALUES (%s,'circle',ST_Point(0,0,4326))",
            "INSERT INTO place_marks (map_id, kind, geom, colour) VALUES (%s,'marker',ST_Point(0,0,4326),7)",
            "INSERT INTO place_marks (map_id, kind, geom, colour) VALUES (%s,'marker',ST_Point(0,0,4326),0)"):
    assert raises(bad, mid), bad          # kind and colour CHECKs hold
assert raises("INSERT INTO place_marks (map_id, kind, geom) VALUES (999999999,'marker',ST_Point(0,0,4326))"), "a mark needs its map"
assert raises("INSERT INTO actions (stage, actor, note) VALUES ('nonsense','t','x')"), "the old stages still guard the ledger"
for stage in ("acknowledged", "acted", "measured", "settings", "decided", "dismissed"):
    cur.execute("INSERT INTO actions (stage, actor, note) VALUES (%s,'t','x')", (stage,))   # none of them was dropped
print("  kind, colour, the map reference and the action stages hold")

cur.execute("INSERT INTO place_maps (name, from_node, remote_id) VALUES ('a', 'n1', 5)")
assert raises("INSERT INTO place_maps (name, from_node, remote_id) VALUES ('b', 'n1', 5)"), "UNIQUE (from_node, remote_id)"
cur.execute("INSERT INTO place_maps (name) VALUES ('c'), ('d')")            # NULLs are drawn-here maps and never collide
print("  a pulled map is unique per node and remote id; maps drawn here are not")

cur.execute("DELETE FROM place_maps WHERE id = %s", (mid,))
cur.execute("SELECT count(*) AS n FROM place_marks WHERE map_id = %s", (mid,))
assert cur.fetchone()["n"] == 0, "deleting a map takes its drawings"
print("  deleting a map deletes its drawings")

import cells  # noqa: E402
os.environ.update(NODE_LAT="-8.8190516", NODE_LON="115.1644423")
cur.execute("INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, kind) "
            "VALUES ('sc-19236', 'smartcitizen', 'Ungasan', -8.81983, 115.16657, false, true, 'sensor')")
hc = cells.home(-8.8190516, 115.1644423)
assert cells.load(cur, hc) == {hc, "8895a4c809fffff"}, "cells.load adopts sc-19236's neighbour cell on first run"
cur.execute("DELETE FROM node_cells WHERE cell = '8895a4c809fffff'")
assert cells.load(cur, hc) == {hc}, "releasing adopted cell does not re-adopt while home row is present"
print("  node_cells: adopt and load hold on Postgres")

# The seen query: only this node's own sensors (custody AND kind = 'sensor'), only a reading in the last 24 h, never one
# timestamped ahead (forecast rows are). sc-19236 read an hour ago in 8895a4c809fffff; each other row misses one rule.
import h3  # noqa: E402
ring = cells.ring(hc)
def at(c):
    return h3.cell_to_latlng(c)
for sid, c, local, kind in (("cells-old", ring[2], True, "sensor"), ("cells-peer", ring[3], True, "peer"),
                            ("cells-theirs", ring[4], False, "sensor"), ("cells-model", ring[5], True, "model"),
                            ("cells-ahead", ring[6], True, "sensor")):
    cur.execute("INSERT INTO sensors (sensor_id, source, lat, lon, local, kind) VALUES (%s, 't', %s, %s, %s, %s)",
                (sid, *at(c), local, kind))
cur.execute("""INSERT INTO readings (ts, sensor_id, metric, value) VALUES
  (now() - interval '1 hour', 'sc-19236', 'pm25', 9), (now() - interval '25 hours', 'cells-old', 'pm25', 9),
  (now() - interval '1 hour', 'cells-peer', 'pm25', 9), (now() - interval '1 hour', 'cells-theirs', 'pm25', 9),
  (now() - interval '1 hour', 'cells-model', 'pm25', 9), (now() + interval '2 hours', 'cells-ahead', 'pm25', 9)""")
seen = cells._seen(cur)
assert "8895a4c809fffff" in seen and not seen & set(ring[2:]), seen
print("  the seen query: own sensors, last 24 h, nothing ahead; a peer, a model, a stranger and an old reading hold nothing")

# POST /area's SQL (app/area.py): a mark_id is the household's own drawn area only, and the readings are the last 24 h,
# nothing ahead. Its Python is tested with a fake cursor in tests/test_area.py.
import area  # noqa: E402
os.environ.setdefault("CHANNELS_PATH", "config/channels.yml")   # packs reads it at import; set late, the private test below loads no core roles
import packs  # noqa: E402
lat, lon = at(hc)
sq = f"ST_GeomFromText('POLYGON(({lon} {lat},{lon + .002} {lat},{lon + .002} {lat + .002},{lon} {lat}))', 4326)"
cur.execute("INSERT INTO place_maps (name) VALUES ('ours'), ('theirs'), ('child') RETURNING id")
ours, theirs, child = [r["id"] for r in cur.fetchall()]
cur.execute("UPDATE place_maps SET agent = 'ask' WHERE id = %s", (theirs,))
cur.execute("UPDATE place_maps SET from_node = 'n9', remote_id = 1 WHERE id = %s", (child,))
cur.execute(f"""INSERT INTO place_marks (map_id, kind, geom) VALUES (%s, 'area', {sq}), (%s, 'line', ST_MakeLine(ST_Point({lon}, {lat}, 4326), ST_Point({lon + .002}, {lat}, 4326))),
                (%s, 'area', {sq}), (%s, 'area', {sq}) RETURNING id""", (ours, ours, theirs, child))
a_ours, a_line, a_theirs, a_child = [r["id"] for r in cur.fetchall()]
cur.execute(area._MARK, (a_ours,))
g = cur.fetchone()["geometry"]
assert g["type"] == "Polygon" and area.cover({"polygon": g}), g
for k in (a_line, a_theirs, a_child):
    cur.execute(area._MARK, (k,))
    assert cur.fetchone() is None, f"mark {k} is not the household's drawn area"
cur.execute(area._READINGS, (["sc-19236", "cells-old", "cells-ahead"],))
assert {r["sensor_id"] for r in cur.fetchall()} == {"sc-19236"}, "the pull reads the last 24 h, nothing ahead"
cur.execute(area._READINGS + " AND " + packs.public_sql("r"), (["sc-19236"],))
cur.fetchall()
cur.execute(area._SENSORS)
assert {"cells-peer", "sc-19236"} <= {r["sensor_id"] for r in cur.fetchall()}
print("  POST /area's SQL: a mark is the household's own drawn area, readings the last 24 h, private ones filterable")

con.rollback()

# ---------------------------------------------------------------- the routes (app/maps.py), through the app
# TestClient's peer is "testclient", not loopback: every request here is a client on the house WiFi, so each carries
# a token unless the token is the subject. These requests commit; what they wrote is deleted at the end.
import logging  # noqa: E402
import time  # noqa: E402

logging.disable(logging.WARNING)                         # httpx logs every request at INFO

os.environ.update(DATABASE_URL=url, ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok")
os.environ.setdefault("CHANNELS_PATH", "config/channels.yml")   # the daily count is private by this file
import settings  # noqa: E402

SET = {"BACKUP_TOKEN": "backup-tok"}
settings._cache.update(at=time.time() + 1e9, rows=SET)     # the settings table, held still for the test
import main  # noqa: E402 — importing the app starts nothing (main.start)
from fastapi.testclient import TestClient  # noqa: E402

c = TestClient(main.app)
H = {"Authorization": "Bearer admin-tok"}
ac = psycopg.connect(url, row_factory=dict_row, autocommit=True)


def one(sql, *args):
    return ac.execute(sql, args).fetchone()


assert c.get("/place/maps").status_code in (401, 403), "a stranger on the WiFi reads no maps"
assert c.get("/place/maps", headers={"Authorization": "Bearer backup-tok"}).status_code == 401, \
    "the NAS's read token passes SHARE_LEVEL, and it must not draw"
assert c.get("/place/maps", headers={"Authorization": "Bearer act-tok"}).status_code == 200
print("  maps answer the household's tokens only")

r = c.post("/place/maps", json={"name": "  ", "actor": "Tomas"}, headers=H)
assert r.status_code == 422 and r.json()["detail"] == "A map needs a name.", r.text
r = c.post("/place/maps", json={"name": "Garden plan", "owner": "Tomas", "actor": "Tomas"}, headers=H)
assert r.status_code == 200, r.text
mid = r.json()["map"]["id"]
RING = [[115.167, -8.819], [115.168, -8.819], [115.168, -8.818], [115.167, -8.818], [115.167, -8.819]]


def draw(kind, gtype, coords, **props):
    return c.post(f"/place/maps/{mid}/marks", headers=H, json={"type": "Feature", "actor": "Tomas",
                  "properties": {"kind": kind, **props}, "geometry": {"type": gtype, "coordinates": coords}})


r = draw("area", "Polygon", [RING], label="Rain garden", colour=3)
assert r.status_code == 200, r.text
mark = r.json()["mark"]
kid = mark["id"]
real = one("SELECT ST_Area(geom::geography) AS a FROM place_marks WHERE id = %s", kid)["a"]
assert abs(mark["area_m2"] - real) / real < 0.01 and mark["length_m"] is None, (mark, real)
assert mark["drawn_by"] == "Tomas" and mark["colour"] == 3 and mark["geometry"]["type"] == "Polygon", mark
r = draw("line", "LineString", [[115.167, -8.819], [115.168, -8.819]])
assert r.status_code == 200 and 105 < r.json()["mark"]["length_m"] < 115, r.text      # 0.001° of longitude at 8.8° S
r = draw("area", "Polygon", [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]])
assert r.status_code == 422 and r.json()["detail"] == "That area crosses itself. Draw its corners in order around it."
assert draw("marker", "Point", [115.167, -8.819], colour=7).json()["detail"] == "A colour is a number from 1 to 6."
assert c.post("/place/maps/999999999/marks", headers=H, json={}).status_code == 404
r = draw("marker", "Point", [115.167, -8.819], image=999999999)
assert r.status_code == 404 and r.json()["detail"] == "That picture is not on this node.", r.text
print("  a drawing is stored with PostGIS's own area and length; a crossed area and a seventh colour are refused")

# the screen reads a map's drawings back with their ids, and reading is not a ledger row (a download is)
n_rows = one("SELECT count(*) AS n FROM actions WHERE stage = 'place'")["n"]
r = c.get(f"/place/maps/{mid}/marks", headers=H)
assert r.status_code == 200, r.text
got = r.json()["marks"]
assert [k["id"] for k in got][:1] == [kid] and got[0]["geometry"]["type"] == "Polygon" and got[0]["label"] == "Rain garden", got[:1]
assert abs(got[0]["area_m2"] - real) / real < 0.01 and len(got) == 2, got
assert one("SELECT count(*) AS n FROM actions WHERE stage = 'place'")["n"] == n_rows, "reading a map writes nothing"
assert c.get("/place/maps/999999999/marks", headers=H).status_code == 404
assert c.get(f"/place/maps/{mid}/marks").status_code in (401, 403), "a stranger reads no drawing"
print("  a map's drawings read back with their ids and PostGIS's measures, and reading writes no ledger row")

for label in ("Rain garden, west", "Rain garden, west edge"):
    r = c.patch(f"/place/marks/{kid}", json={"label": label, "actor": "Tomas"}, headers=H)
    assert r.status_code == 200 and r.json()["mark"]["label"] == label, r.text
rows = ac.execute("SELECT choice, note FROM actions WHERE stage = 'place' AND right(note, %s) = %s ORDER BY ts",
                  (len(f"(mark {kid})"), f"(mark {kid})")).fetchall()
assert [x["choice"] for x in rows] == ["drew", "changed"], rows
r = c.patch(f"/place/marks/{kid}", json={"geometry": {"type": "Polygon", "coordinates": [RING[:3] + [RING[0]]]},
                                         "actor": "Tomas"}, headers=H)
assert abs(r.json()["mark"]["area_m2"] - real / 2) / real < 0.01, "a new outline is measured again"
print("  the same drawing changed inside a minute is one `changed` row in the ledger; a new outline is measured again")

A = one("INSERT INTO alerts (ts, rule_id, sensor_id, level, text) VALUES (now(), 't', 'sc-1', 'act', 'x') RETURNING id")["id"]
r = c.patch(f"/place/marks/{kid}", json={"issue": {"alert_id": A}, "words": " ", "actor": "Tomas"}, headers=H)
assert r.status_code == 422 and r.json()["detail"] == "Say what you did, in your own words.", r.text
r = c.patch(f"/place/marks/{kid}", json={"issue": {"alert_id": A}, "words": "dug the swale"},
            headers={**H, "X-Agent": "claude"})
assert r.status_code == 403, "only a person ties a drawing to an issue"
r = c.patch(f"/place/marks/{kid}", json={"issue": {"alert_id": A}, "words": "dug the swale", "actor": "Tomas"}, headers=H)
assert r.status_code == 200 and r.json()["mark"]["alert_id"] == A, r.text
acted = lambda: ac.execute("SELECT alert_id, event_id, actor, note FROM actions WHERE stage = 'acted' AND choice = %s",  # noqa: E731
                           (f"place.mark:{kid}",)).fetchall()
assert acted() == [{"alert_id": A, "event_id": None, "actor": "Tomas", "note": "dug the swale"}], acted()
c.patch(f"/place/marks/{kid}", json={"issue": {"alert_id": A}, "words": "dug the swale, planted vetiver", "actor": "Tomas"}, headers=H)
assert [x["note"] for x in acted()] == ["dug the swale, planted vetiver"], "tying again replaces the row, never a second"
# the act happened when it was first tied: words edited later keep its time, so it stays in ρ's 24 h window
ac.execute("UPDATE actions SET ts = now() - interval '20 hours' WHERE stage = 'acted' AND choice = %s", (f"place.mark:{kid}",))
was_ts = one("SELECT ts FROM actions WHERE stage = 'acted' AND choice = %s", f"place.mark:{kid}")["ts"]
c.patch(f"/place/marks/{kid}", json={"issue": {"alert_id": A}, "words": "dug the swale, planted vetiver and lemongrass", "actor": "Tomas"}, headers=H)
row_ = one("SELECT ts, note FROM actions WHERE stage = 'acted' AND choice = %s", f"place.mark:{kid}")
assert row_["ts"] == was_ts and row_["note"].endswith("lemongrass"), ("re-tying to the same issue moved the act's time", row_, was_ts)
r = c.patch(f"/place/marks/{kid}", json={"issue": None, "actor": "Tomas"}, headers=H)
assert r.status_code == 200 and r.json()["mark"]["alert_id"] is None and acted() == [], "untying deletes the row"
assert c.patch(f"/place/marks/{kid}", json={"issue": {"alert_id": 999999999}, "words": "x"}, headers=H).status_code == 404
E = one("INSERT INTO alert_events (issue, kind, level, opened_at, last_seen_at) VALUES ('heat', 'sustained', 'act', now(), now()) RETURNING id")["id"]
c.patch(f"/place/marks/{kid}", json={"issue": {"alert_id": A}, "words": "dug the swale", "actor": "Tomas"}, headers=H)
ac.execute("UPDATE actions SET ts = now() - interval '20 hours' WHERE stage = 'acted' AND choice = %s", (f"place.mark:{kid}",))
c.patch(f"/place/marks/{kid}", json={"issue": {"event_id": E}, "words": "shaded the west wall", "actor": "Tomas"}, headers=H)
assert acted() == [{"alert_id": None, "event_id": E, "actor": "Tomas", "note": "shaded the west wall"}], acted()
assert one("SELECT ts > now() - interval '1 minute' AS new FROM actions WHERE stage = 'acted' AND choice = %s", f"place.mark:{kid}")["new"], \
    "a tie to a different issue is a new act, at its own time"
assert c.delete(f"/place/marks/{kid}?actor=Tomas", headers=H).status_code == 200
assert len(acted()) == 1, "deleting the drawing keeps the act: the person did act"
print("  tying: needs the person's words, writes the Done row, keeps its time when the words change, untying deletes it, deleting the drawing keeps it")

SET["DECISION_REQUIRED"] = "1"
A2 = one("INSERT INTO alerts (ts, rule_id, sensor_id, level, text) VALUES (now(), 't', 'sc-1', 'act', 'x') RETURNING id")["id"]
k2 = draw("marker", "Point", [115.167, -8.819]).json()["mark"]["id"]
tied = c.patch(f"/place/marks/{k2}", json={"issue": {"alert_id": A2}, "words": "closed the windows", "actor": "Tomas"}, headers=H)
done = c.post("/actions", json={"alert_id": A2, "stage": "acted", "actor": "Tomas", "note": "closed the windows"}, headers=H)
assert tied.status_code == done.status_code == 409 and tied.json()["detail"] == done.json()["detail"], (tied.text, done.text)
assert "DECISION_REQUIRED" in tied.json()["detail"]
SET["DECISION_REQUIRED"] = "0"
print("  where the Done button needs a decision first, tying is refused with the same status and sentence")

AG = one("INSERT INTO place_maps (name, agent) VALUES ('Shade study', 'ask') RETURNING id")["id"]
r = c.patch(f"/place/maps/{AG}", json={"name": "mine now"}, headers=H)
assert r.status_code == 403 and r.json()["detail"] == "This is ask's map.", r.text
assert c.post(f"/place/maps/{AG}/marks", json={"type": "Feature", "properties": {"kind": "marker"},
              "geometry": {"type": "Point", "coordinates": [0, 0]}}, headers=H).json()["detail"] == "This is ask's map."
print("  an agent's map is refused to the household's edits")

r = c.patch(f"/place/maps/{mid}", json={"name": "Garden", "actor": "Tomas"}, headers=H)
assert r.status_code == 200 and r.json()["map"]["name"] == "Garden"
g = c.get("/place/maps", headers=H).json()
assert set(g["palette"]) == {"1", "2", "3", "4", "5", "6"} and g["palette"]["3"].startswith("#"), g["palette"]
m = next(x for x in g["maps"] if x["id"] == mid)
assert set(m) == {"id", "name", "owner", "agent", "shared", "held", "share_error", "from_node", "marks", "updated_at"}, m
assert m["marks"] == 2 and m["owner"] == "Tomas", m
r = c.delete(f"/place/maps/{mid}?confirm=garden", headers=H)
assert r.status_code == 409 and r.json()["detail"] == "Deleting needs the map's name.", r.text
assert c.delete(f"/place/maps/{mid}?confirm=Garden&actor=Tomas", headers=H).status_code == 200
assert one("SELECT count(*) AS n FROM place_marks WHERE map_id = %s", mid)["n"] == 0
assert one("SELECT choice FROM actions WHERE stage = 'place' AND note LIKE %s ORDER BY ts DESC LIMIT 1", f"%(map {mid})")["choice"] == "deleted"
print("  the list carries counts and the palette; deleting a map needs its name and takes its drawings")

# ---------------------------------------------------------------- the downloads
# The node's own point picks the UTM zone: 8.8 S, 115.2 E is zone 50 south (EPSG 32750), central meridian 117 E.
os.environ.update(NODE_NAME="bayu-ungasan", NODE_LAT="-8.8271", NODE_LON="115.15709")
DL = c.post("/place/maps", json={"name": "Rain & Garden / plan", "actor": "Tomas"}, headers=H).json()["map"]["id"]
for kind, gtype, coords, props in (("area", "Polygon", [RING], {"label": "Rain garden", "colour": 3}),
                                   ("line", "LineString", [[115.167, -8.819], [115.168, -8.819]], {}),
                                   ("marker", "Point", [115.167, -8.819], {"label": "Pozo"}),
                                   ("note", "Point", [115.1675, -8.8185], {"note": "Water is here"})):
    assert c.post(f"/place/maps/{DL}/marks", headers=H, json={"type": "Feature", "actor": "Tomas",
                  "properties": {"kind": kind, **props}, "geometry": {"type": gtype, "coordinates": coords}}).status_code == 200

r = c.get(f"/place/maps/{DL}.geojson", headers=H)
assert r.status_code == 200 and r.headers["content-type"].startswith("application/geo+json"), r.headers
assert r.headers["content-disposition"] == f'attachment; filename="bayu-ungasan-rain-garden-plan-{time.strftime("%Y-%m-%d", time.gmtime())}.geojson"', r.headers
fc = r.json()
assert fc["schema"] == "planetai.place.map/v0" and fc["node"] == "bayu-ungasan" and fc["map"] == "Rain & Garden / plan"
assert len(fc["features"]) == 4 and fc["features"][0]["properties"]["area_m2"] > 1000, fc["features"][0]
assert fc["features"][0]["properties"]["drawn_by"] == "Tomas", "the household's own download keeps who drew it"

r = c.get(f"/place/maps/{DL}.kml", headers=H)
assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.google-earth.kml+xml")
assert r.headers["content-disposition"].endswith('.kml"')
import xml.etree.ElementTree as ET  # noqa: E402
assert len(ET.fromstring(r.text).findall(".//{http://www.opengis.net/kml/2.2}Placemark")) == 4

r = c.get(f"/place/maps/{DL}.dxf", headers=H)
assert r.status_code == 200 and r.headers["content-disposition"].endswith('.dxf"') and r.text.startswith("999\nEPSG:32750, metres")
assert r.text.count("\nPOLYLINE\n") == 2 and r.text.count("\nPOINT\n") == 2 and r.text.count("\nTEXT\n") == 3
want = one("SELECT ST_X(g) AS x, ST_Y(g) AS y FROM (SELECT ST_Transform(ST_SetSRID(ST_Point(115.167, -8.819), 4326), 32750) AS g) t")
body = r.text.split("\nPOINT\n")[1].split("\n")                 # 8 layer, MARKERS, 62, ACI, 10, x, 20, y …
x, y = float(body[body.index("10") + 1]), float(body[body.index("20") + 1])
assert abs(x - want["x"]) < 0.01 and abs(y - want["y"]) < 0.01, (x, y, want)
assert abs(y - 9.02e6) < 0.05e6 and abs(x - 300000) < 10000, "metres on the node's own zone: 117 E is 500000, this is 1.9 degrees west"
assert c.get(f"/place/maps/{DL}.pdf", headers=H).status_code == 404
assert c.get("/place/maps/999999999.dxf", headers=H).status_code == 404
assert c.get(f"/place/maps/{DL}.dxf").status_code in (401, 403), "a download is the household's alone"
assert c.get(f"/place/maps/{DL}.dxf", headers={"Authorization": "Bearer backup-tok"}).status_code == 401
assert c.get(f"/place/maps/{DL}.dxf", headers=H).status_code == 200      # a second one, inside the minute
assert c.get(f"/place/maps/{DL}.kml?actor=Tomas", headers=H).status_code == 200
assert one("SELECT choice, actor FROM actions WHERE stage = 'place' AND note LIKE %s ORDER BY ts DESC LIMIT 1", f"%(map {DL})") \
    == {"choice": "downloaded:kml", "actor": "Tomas"}
assert one("SELECT count(*) AS n FROM actions WHERE choice = 'downloaded:dxf' AND note LIKE %s", f"%(map {DL})")["n"] == 1, "two dxf downloads in a minute are one row"
AGD = one("INSERT INTO place_maps (name, agent) VALUES ('Shade', 'ask') RETURNING id")["id"]
assert c.get(f"/place/maps/{AGD}.geojson", headers=H).status_code == 200, "the household may read an agent's map, only not edit it"
ac.execute("DELETE FROM place_maps WHERE id IN (%s, %s)", (DL, AGD))
print("  a map downloads as GeoJSON, KML and DXF, in UTM metres on the node's zone, one ledger row each")

# ---------------------------------------------------------------- sharing upstream (§5)
# The child's posts go to a recorder, never a real node; the same app then plays the parent for /place/maps/received.
import httpx  # noqa: E402
import maps  # noqa: E402

sent, answer, real_post = [], [200], httpx.post


def recorder(url, json=None, headers=None, timeout=None, content=None):
    body = json if content is None else __import__("json").loads(content)     # identity.post sends the bytes it signed
    sent.append({"url": url, "body": body, "auth": (headers or {}).get("Authorization")})
    return httpx.Response(answer[0], request=httpx.Request("POST", url))


httpx.post = recorder
WARN_TEXT = ("Sharing sends every drawing in this map, at its exact place, with its labels, notes and measures, to the node "
        "upstream, where the people holding its token can see it. A photo on a drawing goes as what you wrote about it "
        "and the day it was taken, and the picture stays here. Press Share again to send it.")
WARN = {"code": "share_warning", "text": WARN_TEXT}
HOUSE = "This drawing touches the cell the house stands in. Press Share again to send the map with it."
TOKEN = "The node upstream did not take this node's token. Set PARENT_TOKEN in Set up to the one it gave you."
NOT_YET = "The node upstream does not take maps yet."
SH = c.post("/place/maps", json={"name": "Walk to the beach", "actor": "Tomas"}, headers=H).json()["map"]["id"]
share = lambda body, mid=SH: c.patch(f"/place/maps/{mid}", json={"actor": "Tomas", **body}, headers=H)  # noqa: E731
row = lambda mid=SH: one("SELECT shared, held, share_error, push_tried_at, updated_at FROM place_maps WHERE id = %s", mid)  # noqa: E731


def push():
    sent.clear()
    maps.push_maps()
    return [(s["body"]["op"], s["body"]["map_id"]) for s in sent]


r = share({"shared": True, "confirm": "exact"})
assert r.status_code == 409 and r.json()["detail"] == "There is no node upstream to share with. Set PARENT in Set up first.", r.text
assert "share_warning" not in r.text, "no node upstream is a plain refusal: the page must not arm the second press on it"
assert push() == [], "no PARENT, nothing sent"
SET.update(PARENT_API_URL="http://parent.test", PARENT_TOKEN="kid-tok")
r = share({"shared": True})
assert r.status_code == 409 and r.json()["detail"] == WARN, r.text
assert row()["shared"] is False and push() == [], "the warning sends nothing"
r = share({"shared": True, "confirm": "exact"})
assert r.status_code == 200 and r.json()["map"]["shared"] is True, r.text
assert one("SELECT choice FROM actions WHERE stage = 'place' AND note LIKE %s ORDER BY ts DESC LIMIT 1", f"%(map {SH})")["choice"] == "shared"
print("  sharing needs a node upstream, then a second press after the warning")

SK = c.post(f"/place/maps/{SH}/marks", headers=H, json={"type": "Feature", "actor": "Tomas", "properties": {"kind": "line"},
            "geometry": {"type": "LineString", "coordinates": [[115.167, -8.819], [115.168, -8.819]]}}).json()
assert "warn" not in SK, "a drawing away from the house warns of nothing"
SK = SK["mark"]["id"]
c.patch(f"/place/marks/{SK}", json={"label": "Path", "actor": "Tomas"}, headers=H)
assert push() == [("put", SH)], sent
s = sent[0]
assert s["url"] == "http://parent.test/place/maps/received" and s["auth"] == "Bearer kid-tok", s
assert set(s["body"]) == {"schema", "node", "map_id", "op", "geojson"} and s["body"]["schema"] == "planetai.place.map/v0"
assert s["body"]["node"] == "bayu-ungasan" and s["body"]["geojson"]["map"] == "Walk to the beach"
assert [f["properties"]["label"] for f in s["body"]["geojson"]["features"]] == ["Path"], "both changes in the one put"
assert all("drawn_by" not in f["properties"] for f in s["body"]["geojson"]["features"]), "no name goes upstream"
assert "Tomas" not in str([f["properties"] for f in s["body"]["geojson"]["features"]]), "who drew it stays here"
assert push() == [], "nothing changed since: nothing sent"
print("  a shared map changed twice goes up once, whole, with the parent's token")

before = row()["updated_at"]
n_changed = one("SELECT count(*) AS n FROM actions WHERE choice = 'changed'")["n"]
r = c.patch(f"/place/marks/{SK}", json={"actor": "Tomas"}, headers=H)
assert r.status_code == 200 and r.json()["mark"]["label"] == "Path", r.text
assert row()["updated_at"] == before and one("SELECT count(*) AS n FROM actions WHERE choice = 'changed'")["n"] == n_changed
assert push() == [], "a PATCH that changes nothing writes nothing and resends nothing"
print("  an empty drawing PATCH writes nothing")

answer[0] = 404
c.patch(f"/place/marks/{SK}", json={"note": "low tide only", "actor": "Tomas"}, headers=H)
assert push() == [("put", SH)]
assert row()["shared"] is True and row()["share_error"] == NOT_YET, row()
assert push() == [], "a refused map waits an hour"
ac.execute("UPDATE place_maps SET push_tried_at = now() - interval '61 minutes' WHERE id = %s", (SH,))
answer[0] = 200
assert push() == [("put", SH)] and row()["share_error"] is None, row()
print("  a parent that predates maps is said so; the map stays shared and is tried again after an hour")

for code in (401, 403):
    answer[0] = code
    c.patch(f"/place/marks/{SK}", json={"note": f"refused {code}", "actor": "Tomas"}, headers=H)
    assert push() == [("put", SH)] and row()["share_error"] == TOKEN, (code, row())
    ac.execute("UPDATE place_maps SET push_tried_at = now() - interval '61 minutes' WHERE id = %s", (SH,))
answer[0] = 200
assert push() == [("put", SH)] and row()["share_error"] is None, row()
print("  a parent that refuses this node's token says to fix PARENT_TOKEN, not to wait")

r = c.post(f"/place/maps/{SH}/marks", headers=H, json={"type": "Feature", "actor": "Tomas", "properties": {"kind": "marker"},
           "geometry": {"type": "Point", "coordinates": [115.15709, -8.8271]}})          # the node's own point
assert r.status_code == 200 and r.json()["warn"] == HOUSE, r.text
assert row()["held"] is True and push() == [], "a drawing on the house holds the map"
m = next(x for x in c.get("/place/maps", headers=H).json()["maps"] if x["id"] == SH)
assert m["held"] is True and m["share_error"] == HOUSE, m
ac.execute("UPDATE place_maps SET push_tried_at = now() - interval '2 hours' WHERE id = %s", (SH,))
assert push() == [], "the hour's retry never releases a held map"
# The hold is a flag, not the sentence: a row whose words were written by an older release, and a sentence reworded
# since, both stay held.
ac.execute("UPDATE place_maps SET share_error = 'an older wording of the warning' WHERE id = %s", (SH,))
was, maps.ON_HOUSE = maps.ON_HOUSE, "Reworded: this drawing is on the house."
assert push() == [], "a held map stays held whatever its share_error says"
m = next(x for x in c.get("/place/maps", headers=H).json()["maps"] if x["id"] == SH)
assert m["share_error"] == "Reworded: this drawing is on the house.", "the sentence is rendered from the flag"
maps.ON_HOUSE = was
assert share({"shared": True}).json()["detail"] == WARN
r = share({"shared": True, "confirm": "exact"}).json()["map"]
assert r["share_error"] is None and r["held"] is False, r
assert push() == [("put", SH)] and len(sent[0]["body"]["geojson"]["features"]) == 2
# a drawing drawn away from the house and then moved onto its cell holds the map the same way
ac.execute("DELETE FROM place_marks WHERE map_id = %s AND kind = 'marker'", (SH,))
import geo  # noqa: E402
import h3  # noqa: E402
lat, lon = h3.cell_to_latlng(geo.home_cell(10))
r = c.patch(f"/place/marks/{SK}", json={"geometry": {"type": "LineString", "coordinates": [[115.167, -8.819], [lon, lat]]},
                                        "actor": "Tomas"}, headers=H)
assert r.status_code == 200 and r.json().get("warn") == HOUSE, r.text
assert row()["held"] is True and push() == [], "moved onto the house, the map is held and nothing goes up"
ac.execute("UPDATE place_maps SET push_tried_at = now() - interval '2 hours' WHERE id = %s", (SH,))
assert push() == [], "the hour's retry never releases it"
assert share({"shared": True, "confirm": "exact"}).json()["map"]["held"] is False
assert push() == [("put", SH)], "Share pressed again sends it"
print("  a drawing on the house's own cell holds a shared map until Share is pressed again, drawn there or moved there")

r = share({"shared": False})
assert r.status_code == 200 and r.json()["map"]["shared"] is False
assert one("SELECT choice FROM actions WHERE stage = 'place' AND note LIKE %s ORDER BY ts DESC LIMIT 1", f"%(map {SH})")["choice"] == "unshared"
answer[0] = 401
assert push() == [("delete", SH)] and push() == [], "a refused token: the delete waits"
assert one("SELECT count(*) AS n FROM place_maps_unshared WHERE map_id = %s", SH)["n"] == 1, "a delete the parent refused stays owed"
ac.execute("UPDATE place_maps_unshared SET tried_at = now() - interval '61 minutes' WHERE map_id = %s", (SH,))
answer[0] = 200
assert push() == [("delete", SH)] and sent[0]["body"]["geojson"] is None, sent
assert push() == [], "one delete"
SD = c.post("/place/maps", json={"name": "Gone soon", "actor": "Tomas"}, headers=H).json()["map"]["id"]
share({"shared": True, "confirm": "exact"}, SD)
assert push() == [("put", SD)]
c.delete(f"/place/maps/{SD}?confirm=Gone soon&actor=Tomas", headers=H)
assert push() == [("delete", SD)] and push() == [], "deleting a shared map sends one delete"
print("  unsharing or deleting a shared map sends one delete")

# The same app as the parent: AGGREGATE_TOKEN is what its children hold.
SET["AGGREGATE_TOKEN"] = "agg-tok"
AGG = {"Authorization": "Bearer agg-tok"}
FEAT = lambda label, x: {"type": "Feature", "properties": {"kind": "marker", "label": label, "colour": 2, "image": 41},  # noqa: E731
                         "geometry": {"type": "Point", "coordinates": [x, -8.8]}}
doc = {"schema": "planetai.place.map/v0", "node": "kid", "map_id": 7, "op": "put",
       "geojson": {"type": "FeatureCollection", "map": "Kid's garden", "owner": "Ana", "features": [FEAT("a", 115.1), FEAT("b", 115.2)]}}
recv = lambda d, h=AGG: c.post("/place/maps/received", json=d, headers=h)  # noqa: E731
assert recv(doc, H).status_code == 401, "a household token is not a child's"
assert recv(doc, {}).status_code == 401
assert recv({**doc, "geojson": {**doc["geojson"], "features": [{"type": "Feature", "properties": {"kind": "line"},
            "geometry": {"type": "Point", "coordinates": [0, 0]}}]}}).status_code == 422
r = recv(doc)
assert r.status_code == 200, r.text
RV = one("SELECT id, name, owner FROM place_maps WHERE from_node = 'kid' AND remote_id = 7")
assert RV["name"] == "Kid's garden" and RV["owner"] == "kid", RV   # a name a child sends as owner is not kept: the node owns it
assert one("SELECT count(*) AS n FROM place_marks WHERE map_id = %s AND capture_id IS NULL", RV["id"])["n"] == 2, \
    "the child's picture numbers mean nothing here"
named = {**doc, "geojson": {**doc["geojson"], "features": [{**FEAT("n", 115.1), "properties": {**FEAT("n", 115.1)["properties"], "drawn_by": "Ana"}}]}}
assert recv(named).status_code == 200
assert one("SELECT count(*) AS n FROM place_marks WHERE map_id = %s AND drawn_by IS NOT NULL", RV["id"])["n"] == 0, "a parent keeps no name"
# a child's map has a ceiling, checked before any outline is compared with itself; a bad colour is refused, never a 500
big = lambda feats: {**doc, "geojson": {**doc["geojson"], "features": feats}}  # noqa: E731
r = recv(big([FEAT(str(i), 115.1) for i in range(2001)]))
assert r.status_code == 413 and r.json()["detail"] == "A shared map holds 2,000 drawings and 20,000 points at most.", r.text
line = lambda n: {"type": "Feature", "properties": {"kind": "line"},  # noqa: E731
                  "geometry": {"type": "LineString", "coordinates": [[115 + i * 1e-5, -8.8] for i in range(n)]}}
r = recv(big([line(1000)] * 21))
assert r.status_code == 413 and r.json()["detail"] == "A shared map holds 2,000 drawings and 20,000 points at most.", r.text
r = recv(big([line(1001)]))
assert r.status_code == 422 and r.json()["detail"] == "A drawing has 1,000 points at most.", r.text
r = recv(big([{**FEAT("x", 115.1), "properties": {"kind": "marker", "colour": [2]}}]))
assert r.status_code == 422 and r.json()["detail"] == "A colour is a number from 1 to 6.", r.text
assert one("SELECT count(*) AS n FROM place_marks WHERE map_id = %s", RV["id"])["n"] == 1, "a refused put changes nothing"
r = recv({**doc, "geojson": {**doc["geojson"], "features": [FEAT("c", 115.3)]}})
assert r.status_code == 200 and one("SELECT id FROM place_maps WHERE from_node = 'kid' AND remote_id = 7")["id"] == RV["id"]
assert [x["label"] for x in ac.execute("SELECT label FROM place_marks WHERE map_id = %s", (RV["id"],)).fetchall()] == ["c"]
m = next(x for x in c.get("/place/maps", headers=H).json()["maps"] if x["id"] == RV["id"])
assert m["from_node"] == "kid" and m["marks"] == 1, m
RO = "This map came from kid; it is read-only here."
assert share({"name": "mine"}, RV["id"]).json() == {"detail": RO}
assert share({"name": "mine"}, RV["id"]).status_code == 403
assert c.post(f"/place/maps/{RV['id']}/marks", json=FEAT("d", 115.4), headers=H).json()["detail"] == RO
RK = one("SELECT id FROM place_marks WHERE map_id = %s", RV["id"])["id"]
assert c.patch(f"/place/marks/{RK}", json={"label": "x"}, headers=H).json()["detail"] == RO
assert c.get(f"/place/maps/{RV['id']}.geojson", headers=H).status_code == 200, "a received map downloads"
assert recv({**doc, "op": "delete", "geojson": None}).status_code == 200
assert one("SELECT count(*) AS n FROM place_maps WHERE from_node = 'kid'")["n"] == 0
# signed (docs/SPEC_identity.md §8): the child's key is pinned to its name, its ID owns the map, another key is refused
import json as _json  # noqa: E402
import identity  # noqa: E402


def signed_recv(seed, d):
    os.environ["NODE_KEY"] = seed
    identity._private.cache_clear()
    raw = _json.dumps(d).encode()
    h = {**AGG, "Content-Type": "application/json", **identity.headers("/place/maps/received", raw)}
    nid = identity.node_id()
    os.environ["NODE_KEY"] = ""
    identity._private.cache_clear()
    return c.post("/place/maps/received", content=raw, headers=h), nid


r, kid2 = signed_recv("66" * 32, {**doc, "node": "kid2", "map_id": 8})
assert r.status_code == 200, r.text
assert one("SELECT owner FROM place_maps WHERE from_node = 'kid2' AND remote_id = 8")["owner"] == kid2, "the node's ID owns it"
r, _ = signed_recv("77" * 32, {**doc, "node": "kid2", "map_id": 8, "op": "delete", "geojson": None})
assert r.status_code == 409 and f"kid2 is pinned here to node {kid2}" in r.json()["detail"], r.text
assert one("SELECT count(*) AS n FROM place_maps WHERE from_node = 'kid2'")["n"] == 1, "another key deletes nothing"
assert recv({**doc, "node": "kid2", "op": "delete", "geojson": None, "map_id": 8}).status_code == 401, "nor does no key"
httpx.post = real_post
print("  the parent keeps a child's map whole, read-only, and lets it go on delete; a signed map is its node's")

# ---------------------------------------------------------------- photos on demand (§14)
# The same app is child and parent: the child's posts are handed to it as the parent, and its NODE_NAME is the child's
# name on the parent's side. The child's picture is a real file in a throwaway captures folder, written with a GPS
# block, so the parent's copy can be checked for one.
import io  # noqa: E402
import json as _json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
from PIL import Image  # noqa: E402

PICS = tempfile.mkdtemp()
os.environ["PLANETAI_CAPTURES"] = PICS
SET.update(PARENT_API_URL="http://parent.test", PARENT_TOKEN="agg-tok", AGGREGATE_TOKEN="agg-tok")
im = Image.new("RGB", (64, 48), (40, 120, 60))
ex = Image.Exif()
ex[0x8825] = {1: "S", 2: (8.0, 46.0, 39.0), 3: "E", 4: (115.0, 13.0, 20.0)}
buf = io.BytesIO()
im.save(buf, "JPEG", exif=ex.tobytes())
open(os.path.join(PICS, "p1.jpg"), "wb").write(buf.getvalue())
CAP = one("""INSERT INTO captures (ts, kind, cell, lat, lon, actor, note, meta, file, sha256, bytes, mime)
             VALUES ('2026-11-05 10:00+00', 'phone', '8a8f1a3a6a4ffff', -8.7777, 115.2222, 'Tomas', 'the swale after rain',
                     '{"plant": "vetiver"}', 'p1.jpg', 'photos-test-sha', %s, 'image/jpeg') RETURNING id""", len(buf.getvalue()))["id"]

sent.clear()


def parent(url, json=None, headers=None, timeout=None, content=None):
    sent.append({"url": url, "body": json if content is None else _json.loads(content)})
    return c.post(url.replace("http://parent.test", ""), json=json, content=content, headers=headers)


def key(seed):                                             # the child signs with this key from here on ("" for none)
    os.environ["NODE_KEY"] = seed
    identity._private.cache_clear()


httpx.post = parent
PH = c.post("/place/maps", json={"name": "Swale", "actor": "Tomas"}, headers=H).json()["map"]["id"]
assert c.patch(f"/place/maps/{PH}", json={"shared": True, "confirm": "exact", "actor": "Tomas"}, headers=H).status_code == 200
PK = c.post(f"/place/maps/{PH}/marks", headers=H, json={"type": "Feature", "actor": "Tomas", "properties": {
    "kind": "marker", "label": "Rain garden", "image": CAP}, "geometry": {"type": "Point", "coordinates": [115.167, -8.819]}}).json()["mark"]["id"]
sent.clear()
maps.push_maps()
put = next(x["body"] for x in sent if x["url"].endswith("/place/maps/received"))
f0 = put["geojson"]["features"][0]["properties"]
assert f0["image"] == CAP and f0["photo"] == {"kind": "phone", "note": "the swale after rain", "meta": {"plant": "vetiver"},
                                              "taken": "2026-11-05"}, f0
wire = _json.dumps(put)
for secret in ("8.7777", "115.2222", "Tomas", "p1.jpg", "photos-test-sha", "8a8f1a3a6a4ffff"):
    assert secret not in wire, f"{secret} went upstream with a shared photo"
RX = one("SELECT id FROM place_maps WHERE from_node = 'bayu-ungasan' AND remote_id = %s", PH)["id"]
rk = c.get(f"/place/maps/{RX}/marks", headers=H).json()["marks"][0]
assert rk["photo"] == {"ref": CAP, "kind": "phone", "note": "the swale after rain", "meta": {"plant": "vetiver"},
                       "taken": "2026-11-05", "ask": None}, rk["photo"]
assert rk["capture_id"] is None, "the child's number is never the parent's picture"
bad = {"schema": "planetai.place.map/v0", "node": "kid", "map_id": 8, "op": "put", "geojson": {"map": "x", "features": [
    {"type": "Feature", "properties": {"kind": "marker", "image": 3, "photo": {"kind": "selfie"}}, "geometry": {"type": "Point", "coordinates": [0, 0]}}]}}
r = c.post("/place/maps/received", json=bad, headers={"Authorization": "Bearer agg-tok"})
assert r.status_code == 422 and "photo" in r.json()["detail"], r.text
print("  a shared photo goes up as its kind, note, words and day; never its place, its taker or its file")

rk = rk["id"]
assert c.post(f"/place/marks/{rk}/ask", json={"actor": "Ana"}).status_code in (401, 403), "a stranger asks for nothing"
assert c.post(f"/place/marks/{PK}/ask", json={"actor": "Ana"}, headers=H).status_code == 409, "a drawing of this node's own"
r = c.post(f"/place/marks/{rk}/ask", json={"actor": "Ana"}, headers=H)
assert r.status_code == 200 and r.json()["ask"]["state"] == "asked" and r.json()["ask"]["asked_by"] == "Ana", r.text
AK = r.json()["ask"]["id"]
assert c.post(f"/place/marks/{rk}/ask", json={"actor": "Ana"}, headers=H).json()["ask"]["id"] == AK
LEDGER = lambda verb: ac.execute("SELECT actor, note FROM actions WHERE stage = 'place' AND choice = %s ORDER BY ts", (verb,)).fetchall()  # noqa: E731
assert [x["actor"] for x in LEDGER("photo:asked")] == ["Ana"], "one ask, one ledger row"
print("  the parent asks once a photo, by a person's name, and only for a child's drawing")

agg = c.post("/aggregates", json={"schema": "aggregates-v0", "node": "bayu-ungasan", "rows": []}, headers={"Authorization": "Bearer agg-tok"}).json()
assert [(a["id"], a["image"], a["by"]) for a in agg["photo_asks"]] == [(AK, CAP, "Ana")], agg
assert c.post("/aggregates", json={"node": "someone-else", "rows": []}, headers={"Authorization": "Bearer agg-tok"}).json()["photo_asks"] == []
sent.clear()
main.NODE = os.environ["NODE_NAME"]                       # read at import, before this suite named the node
main.push_aggregates()                                     # the child's hourly push: the ask comes back in the answer
main.push_aggregates()
IN = lambda: ac.execute("SELECT id, answer, answered_by, sent_at FROM place_photo_asks_in ORDER BY id").fetchall()  # noqa: E731
assert len(IN()) == 1 and IN()[0]["answer"] is None, IN()
assert [x["actor"] for x in LEDGER("photo:asked")] == ["Ana", "bayu-ungasan"], "the child's ledger has the ask once, by the parent's name"
got = c.get("/place/photos/asks", headers=H).json()["asks"]
assert len(got) == 1 and got[0]["asked_by"] == "Ana" and got[0]["node"] == "bayu-ungasan", got
assert got[0]["drawings"] == [{"mark": PK, "label": "Rain garden", "kind": "marker", "map": "Swale"}], got
assert c.get("/place/photos/asks").status_code in (401, 403)
print("  the ask goes down in the answer to the child's hourly push, once, and shows on the child's Place")

IA = got[0]["id"]
assert c.post(f"/place/photos/asks/{IA}", json={"answer": "maybe"}, headers=H).status_code == 422
assert c.post(f"/place/photos/asks/{IA}", json={"answer": "send"}, headers={**H, "X-Agent": "claude"}).status_code == 403, \
    "only a person at home sends a photo"
assert c.post(f"/place/photos/asks/{IA}", json={"answer": "no", "actor": "Tomas"}, headers=H).status_code == 200
assert c.post(f"/place/photos/asks/{IA}", json={"answer": "send", "actor": "Tomas"}, headers=H).status_code == 409
assert c.get("/place/photos/asks", headers=H).json()["asks"] == []
sent.clear()
maps.push_maps()
ans = [x for x in sent if x["url"].endswith("/place/photos/received")]
assert len(ans) == 1 and ans[0]["body"]["answer"] == "no" and ans[0]["body"]["picture"] is None, ans
OUT = lambda: one("SELECT state, file, asked_by FROM place_photo_asks WHERE id = %s", AK)  # noqa: E731
assert OUT()["state"] == "no" and IN()[0]["sent_at"], (OUT(), IN())
sent.clear()
maps.push_maps()
assert not [x for x in sent if "photos" in x["url"]], "an answer goes once"
assert [x["actor"] for x in LEDGER("photo:no")] == ["Tomas", "bayu-ungasan"], LEDGER("photo:no")
print("  No is a person's, kept at once, sent once, and the parent's ask closes")

r = c.post(f"/place/marks/{rk}/ask", json={"actor": "Ana"}, headers=H)
assert r.json()["ask"]["id"] == AK and r.json()["ask"]["state"] == "asked", "after a No the same ask opens again"
main.push_aggregates()
assert len(IN()) == 1 and IN()[0]["answer"] is None, ("a reopened ask waits for an answer again", IN())
assert c.post(f"/place/photos/asks/{IA}", json={"answer": "send", "actor": "Tomas"}, headers=H).status_code == 200
key("88" * 32)                                             # the child signs from here, and its name is pinned to this key
sent.clear()
maps.push_maps()
ans = [x for x in sent if x["url"].endswith("/place/photos/received")]
assert len(ans) == 1 and ans[0]["body"]["answer"] == "sent" and ans[0]["body"]["picture"], ans
assert set(ans[0]["body"]) == {"schema", "node", "ask", "image", "answer", "picture"}
assert one("SELECT node_id FROM children WHERE name = 'bayu-ungasan'")["node_id"] == identity.node_id(), "pinned by the signed answer"
o = OUT()
assert o["state"] == "sent" and o["file"], o
kept = os.path.join(PICS, "received", o["file"])
back = Image.open(kept)
assert back.size == (64, 48) and not back.getexif().get_ifd(0x8825), "the parent's copy carries no GPS"
r = c.get(f"/place/marks/{rk}/photo", headers=H)
assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content == open(kept, "rb").read()
assert c.get(f"/place/marks/{rk}/photo").status_code in (401, 403), "a stranger sees no child's photo"
assert c.get(f"/place/marks/{rk}/photo", headers={"Authorization": "Bearer backup-tok"}).status_code == 401
assert c.get(f"/place/maps/{RX}/marks", headers=H).json()["marks"][0]["photo"]["ask"]["state"] == "sent"
sent.clear()
maps.push_maps()
assert not [x for x in sent if "photos" in x["url"]], "the file goes once"
assert [x["actor"] for x in LEDGER("photo:sent")] == ["Tomas"] and [x["actor"] for x in LEDGER("photo:received")] == ["bayu-ungasan"]
r = c.post("/place/photos/received", json={"node": "someone-else", "ask": AK, "image": CAP, "answer": "no"},
           headers={"Authorization": "Bearer agg-tok"})
assert r.status_code == 404, "another child cannot answer this child's ask"
assert c.post("/place/photos/received", json={"node": "bayu-ungasan", "ask": AK, "image": CAP, "answer": "no"},
              headers=H).status_code == 401, "a household token is not a child's"
r = c.post("/place/photos/received", json={"node": "bayu-ungasan", "ask": AK, "image": CAP, "answer": "no"},
           headers={"Authorization": "Bearer agg-tok"})
assert r.status_code == 401 and "signs its pushes here" in r.json()["detail"], "an unsigned answer under a signed name"
assert c.post("/place/photos/received", json={"node": "bayu-ungasan", "ask": AK, "image": CAP, "answer": "sent", "picture": "**"},
              headers={"Authorization": "Bearer agg-tok"}).status_code == 422, "a picture that is not base64"
print("  Send uploads the file once; the parent re-writes it with no GPS and shows it to its own token holders only")

assert c.patch(f"/place/maps/{PH}", json={"shared": False, "actor": "Tomas"}, headers=H).status_code == 200
sent.clear()
maps.push_maps()
assert OUT()["state"] == "gone" and OUT()["file"] is None and not os.path.exists(kept), "unshared: the parent's copy is deleted"
assert c.get(f"/place/marks/{rk}/photo", headers=H).status_code == 404
assert LEDGER("photo:gone")[-1]["actor"] == "bayu-ungasan"
print("  unsharing the map deletes the parent's copy of its photo")

# shared again and asked again; then the photo is deleted at home before anybody answers
assert c.patch(f"/place/maps/{PH}", json={"shared": True, "confirm": "exact", "actor": "Tomas"}, headers=H).status_code == 200
maps.push_maps()
rk = one("SELECT k.id FROM place_marks k JOIN place_maps m ON m.id = k.map_id WHERE m.from_node = 'bayu-ungasan' AND m.remote_id = %s", PH)["id"]
assert c.post(f"/place/marks/{rk}/ask", json={"actor": "Ana"}, headers=H).json()["ask"]["state"] == "asked"
main.push_aggregates()
assert c.get("/place/photos/asks", headers=H).json()["asks"], "the ask is back on the child's Place"
r = c.patch(f"/captures/{CAP}", json={"note": "after the rain"}, headers=H)
if r.status_code == 404:                                   # the eyes pack is off in this app: do what its routes do
    ac.execute("UPDATE place_maps SET updated_at = now() WHERE id IN (SELECT map_id FROM place_marks WHERE capture_id = %s)", (CAP,))
    ac.execute("UPDATE captures SET note = 'after the rain' WHERE id = %s", (CAP,))
    print("  - the eyes pack's routes are not loaded here: the photo's edit and delete are done in SQL")
sent.clear()
maps.push_maps()
puts = [x["body"] for x in sent if x["url"].endswith("/place/maps/received")]
assert puts and puts[0]["geojson"]["features"][0]["properties"]["photo"]["note"] == "after the rain", "a new note goes up on the next put"
r = c.delete(f"/captures/{CAP}", headers=H)
if r.status_code == 404:
    ac.execute("UPDATE place_maps SET updated_at = now() WHERE id IN (SELECT map_id FROM place_marks WHERE capture_id = %s)", (CAP,))
    ac.execute("DELETE FROM captures WHERE id = %s", (CAP,))
sent.clear()
maps.push_maps()
puts = [x["body"] for x in sent if x["url"].endswith("/place/maps/received")]
assert puts and "photo" not in puts[0]["geojson"]["features"][0]["properties"], "the deleted photo is gone from the next put"
assert c.get("/place/photos/asks", headers=H).json()["asks"] == [] and IN()[-1]["answer"] == "gone", IN()
assert OUT()["state"] == "gone", "the parent's ask is closed by the put, and the child's gone is taken as done"
assert [x for x in sent if x["url"].endswith("/place/photos/received")][0]["body"]["answer"] == "gone"
assert IN()[-1]["sent_at"], "a gone the parent had already closed is done, not retried"
print("  a photo's new words go up with the next put; a deleted photo answers its ask gone, by the node")

# another key under the child's name: the parent refuses the answer, and the child keeps it, saying why, to try again
key("99" * 32)
ac.execute("""INSERT INTO place_photo_asks_in (parent, ask_id, node, capture_id, answer, answered_at)
              VALUES ('http://parent.test', 4242, 'bayu-ungasan', %s, 'no', now())""", (CAP,))
maps._answers()
x = one("SELECT error, sent_at FROM place_photo_asks_in WHERE ask_id = 4242")
assert x["sent_at"] is None and "bayu-ungasan is pinned here to node" in x["error"], x
key("")
print("  an answer signed by another key is refused, and kept with the parent's sentence")

httpx.post = real_post
os.environ.pop("PLANETAI_CAPTURES")
shutil.rmtree(PICS)
ac.execute("DELETE FROM place_maps WHERE id = %s OR from_node = 'bayu-ungasan'", (PH,))
ac.execute("DELETE FROM place_photo_asks")
ac.execute("DELETE FROM place_photo_asks_in")
ac.execute("DELETE FROM children WHERE name = 'bayu-ungasan'")
ac.execute("DELETE FROM captures WHERE id = %s", (CAP,))
for k in ("PARENT_API_URL", "PARENT_TOKEN", "AGGREGATE_TOKEN"):
    SET.pop(k, None)

ac.execute("DELETE FROM place_maps WHERE id = %s", (SH,))
ac.execute("DELETE FROM actions WHERE stage = 'place' OR choice LIKE 'place.mark:%%' OR alert_id IN (%s, %s)", (A, A2))
ac.execute("DELETE FROM place_maps WHERE id IN (%s, %s)", (mid, AG))
ac.execute("DELETE FROM alerts WHERE id IN (%s, %s)", (A, A2))
ac.execute("DELETE FROM alert_events WHERE id = %s", (E,))
# ---------------------------------------------------------------- the daily count
import index  # noqa: E402
import packs  # noqa: E402

main.load_channel_roles()                                 # the table the private test selects through; main.start() fills it on a node
SENSOR = lambda: ac.execute("SELECT count(*) AS n FROM sensors WHERE sensor_id = 'place-gis'").fetchone()["n"]  # noqa: E731
READ = lambda: ac.execute("SELECT metric, value FROM readings WHERE sensor_id = 'place-gis' "   # noqa: E731
                          "AND ts = date_trunc('day', now()) ORDER BY metric").fetchall()
assert one("SELECT count(*) AS n FROM place_marks k JOIN place_maps m ON m.id = k.map_id WHERE m.agent IS NULL AND m.from_node IS NULL")["n"] == 0
maps.daily_readings()
assert SENSOR() == 0 and READ() == [], "a node that never drew has no place-gis sensor and no zeros"
HM = c.post("/place/maps", json={"name": "Count me", "actor": "Tomas"}, headers=H).json()["map"]["id"]
maps.daily_readings()
assert SENSOR() == 0, "a map with nothing drawn on it is not a drawing"
for lon in (115.167, 115.169):
    ring = [[lon, -8.819], [lon + .001, -8.819], [lon + .001, -8.818], [lon, -8.819]]
    assert c.post(f"/place/maps/{HM}/marks", headers=H, json={"type": "Feature", "actor": "Tomas",
                  "properties": {"kind": "area"}, "geometry": {"type": "Polygon", "coordinates": [ring]}}).status_code == 200
AGM = one("INSERT INTO place_maps (name, agent) VALUES ('Agent count', 'ask') RETURNING id")["id"]
KM = one("INSERT INTO place_maps (name, from_node, remote_id) VALUES ('Kid count', 'kid', 99) RETURNING id")["id"]
for m_ in (AGM, KM):
    ac.execute("INSERT INTO place_marks (map_id, kind, geom, area_m2) VALUES (%s, 'area', ST_GeomFromText("
               "'POLYGON((0 0,0 1,1 1,0 0))',4326), 5000)", (m_,))
area = one("SELECT sum(area_m2) AS a FROM place_marks WHERE map_id = %s", HM)["a"]
maps.daily_readings()
maps.daily_readings()
got = {x["metric"]: x["value"] for x in READ()}
assert len(READ()) == 2, "a second call the same day updates the row, never a second one"
assert got["marks"] == 2, got
assert abs(got["marked_area_m2"] - area) < 1, "an agent's map and a child's map are not the household's"
assert SENSOR() == 1 and one("SELECT count(*) AS n FROM sensors WHERE sensor_id = 'place-gis' AND source = 'place' AND local AND NOT indoor")["n"] == 1
leak = ac.execute("SELECT metric FROM readings WHERE sensor_id = 'place-gis' AND " + packs.public_sql("readings")).fetchall()
assert leak == [], "both counts are private: nothing reads them through public_sql"

# The Index cell gate counts in-custody sensors, and place-gis is local, so it has custody. A private reading is no
# instrument: one real outdoor sensor plus the drawing count is still one sensor, and so still thin.
ac.execute("""INSERT INTO sensors (sensor_id, source, name, indoor, local, kind) VALUES ('sc-ix-1', 'smartcitizen', 'ix', FALSE, TRUE, 'sensor')""")
ac.execute("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (now() - interval '10 minutes', 'sc-ix-1', 'pm25', 8)")
ac.execute("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (now() - interval '10 minutes', 'place-gis', 'marks', 2)")
counts = index._buckets(ac.cursor())
assert counts["sensors"] == 1, ("the drawing count made one sensor read as two", counts)
assert counts["sensors"] < 2, "so a non-community node's cell stays partial, one kitchen is one kitchen"
ac.execute("DELETE FROM readings WHERE sensor_id = 'sc-ix-1'")
ac.execute("DELETE FROM sensors WHERE sensor_id = 'sc-ix-1'")

ac.execute("DELETE FROM place_maps WHERE id = %s", (HM,))
maps.daily_readings()
assert {x["metric"]: x["value"] for x in READ()} == {"marks": 0, "marked_area_m2": 0}, "a node that drew and erased it all records zero"
ac.execute("DELETE FROM place_maps WHERE id IN (%s, %s)", (AGM, KM))
ac.execute("DELETE FROM readings WHERE sensor_id = 'place-gis'")
ac.execute("DELETE FROM sensors WHERE sensor_id = 'place-gis'")
print("  the drawing count: nothing before the first drawing, then one private row a day; it never lifts an Index cell off one sensor")

# ---------------------------------------------------------------- init.sql without PostGIS
# A database where PostGIS cannot be created stops init.sql at its first statement, with the step that fixes it and
# Postgres's own reason beside it. A role that may not create extensions is the faithful case: postgis is not trusted.
import re  # noqa: E402
from pathlib import Path  # noqa: E402
block = re.search(r"DO \$\$ BEGIN\n  CREATE EXTENSION IF NOT EXISTS postgis;.*?END \$\$;", Path("init.sql").read_text(), re.S).group(0)
ac.execute("DROP DATABASE IF EXISTS pai_no_postgis")
ac.execute("DROP ROLE IF EXISTS pai_no_postgis")
ac.execute("CREATE ROLE pai_no_postgis")
ac.execute("CREATE DATABASE pai_no_postgis")
bare = psycopg.connect(psycopg.conninfo.make_conninfo(url, dbname="pai_no_postgis"), autocommit=True)
bare.execute("SET ROLE pai_no_postgis")
try:
    bare.execute(block)
    raise AssertionError("init.sql went on without PostGIS")
except psycopg.errors.RaiseException as e:
    said = e.diag.message_primary
    assert "docker compose up -d db" in said and "planetai update" in said, said
    assert "permission denied" in (e.diag.message_detail or ""), ("Postgres's own reason is hidden", e.diag.message_detail)
bare.close()
ac.execute("DROP DATABASE pai_no_postgis")
ac.execute("DROP ROLE pai_no_postgis")
print("  without PostGIS, init.sql stops first, says to bring up the db image, then update, and keeps Postgres's reason")

print("maps: every check passed")
sys.exit(0)
