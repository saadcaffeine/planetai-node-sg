"""The area pull's pure half (app/area.py): a selection covered at res 8 under AREA_CAP, its bbox, and the own and
peers blocks — own readings only inside the node's own cells, peers only where they have a point.

Run: PYTHONPATH=app python3 tests/test_area.py
"""
import sys
from datetime import datetime, timedelta, timezone

import h3

import area
import cells

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


def raises(fn, *a):
    try:
        fn(*a)
    except ValueError as e:
        return str(e)
    return None


HOME = "8895a4c843fffff"
RING = cells.ring(HOME)
N1, N2, N3 = RING[1], RING[2], RING[3]
FAR = next(c for c in h3.grid_disk(HOME, 3) if h3.grid_distance(c, HOME) == 3)

check(area.AREA_CAP == 500, f"AREA_CAP is 500, got {area.AREA_CAP}")

# ---------------------------------------------------------------- cover: cells
check(area.cover({"cells": [N2, HOME, N1, HOME]}) == sorted({HOME, N1, N2}), "res-8 ids come back deduplicated and sorted")
p7 = h3.cell_to_parent(HOME, 7)
check(area.cover({"cells": [p7]}) == sorted(h3.cell_to_children(p7, 8)), "a res-7 id is covered by its 7 res-8 children")
p5 = h3.cell_to_parent(HOME, 5)
check(len(area.cover({"cells": [p5]})) == h3.cell_to_children_size(p5, 8), "a res-5 id is covered at res 8 (343 cells, under the cap)")
kid = h3.cell_to_children(HOME, 10)[0]
check(area.cover({"cells": [kid, h3.cell_to_children(HOME, 9)[0]]}) == [HOME], "finer ids go up to their res-8 parent")
two5 = [p5, next(c for c in h3.grid_disk(p5, 1) if c != p5)]
_real = area.h3.cell_to_children
area.h3.cell_to_children = lambda *a: fails.append("cover() expanded cells past the cap before refusing") or []
check(str(area.AREA_CAP) in (raises(area.cover, {"cells": two5}) or ""), "two res-5 cells (686 res-8) are refused, naming the cap")
area.h3.cell_to_children = _real
check(raises(area.cover, {"cells": [h3.cell_to_parent(HOME, 4)]}) is not None, "res 4 is refused")
check(raises(area.cover, {"cells": [h3.cell_to_children(HOME, 11)[0]]}) is not None, "res 11 is refused")
check(raises(area.cover, {"cells": ["not-a-cell"]}) is not None, "a bad id is refused")
check(raises(area.cover, {"cells": []}) is not None, "an empty cell list is refused")
check(raises(area.cover, {"cells": "8895a4c843fffff"}) is not None, "cells as a string, not a list, is refused")

# ---------------------------------------------------------------- cover: selection shape
check(raises(area.cover, {}) is not None, "a selection with no key is refused")
check(raises(area.cover, {"cells": [HOME], "polygon": {}}) is not None, "a selection with two keys is refused")
check(raises(area.cover, {"mark_id": 3}) is not None, "mark_id reaching cover() unresolved is refused (the route resolves it)")


# ---------------------------------------------------------------- cover: polygon
def square(lat, lon, d):
    return [[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]


LAT, LON = h3.cell_to_latlng(HOME)
poly = {"type": "Polygon", "coordinates": [square(LAT, LON, 0.02)]}
got = area.cover({"polygon": poly})
check(got == sorted(h3.geo_to_cells(poly, 8)) and HOME in got and len(got) > 7, f"a polygon is covered at res 8, got {len(got)}")
multi = {"type": "MultiPolygon", "coordinates": [[square(LAT, LON, 0.01)], [square(LAT + 0.1, LON, 0.01)]]}
gm = area.cover({"polygon": multi})
check(HOME in gm and set(h3.geo_to_cells({"type": "Polygon", "coordinates": [square(LAT + 0.1, LON, 0.01)]}, 8)) <= set(gm),
      "a MultiPolygon covers both parts")
# a garden-sized area off the cell's centre: h3 covers it with nothing, because no cell centre falls inside it
tiny = {"type": "Polygon", "coordinates": [square(LAT + 0.001, LON + 0.001, 0.0003)]}
check(h3.geo_to_cells(tiny, 8) == [], "fixture: the tiny area holds no cell centre")
check(area.cover({"polygon": tiny}) == [HOME], "an area smaller than a cell is covered by the cell it lies in, not by nothing")
huge = {"type": "Polygon", "coordinates": [square(LAT, LON, 0.5)]}
_real = area.h3.geo_to_cells
area.h3.geo_to_cells = lambda *a: fails.append("cover() computed a covering past the cap before refusing") or []
msg = raises(area.cover, {"polygon": huge})
area.h3.geo_to_cells = _real
check(msg is not None and str(area.AREA_CAP) in msg, "a polygon of ~12 000 km² is refused before covering, naming the cap")
for bad, why in [({"type": "Point", "coordinates": [LON, LAT]}, "a Point"),
                 ({"type": "Polygon", "coordinates": [[[LON, LAT], [LON + 0.01, LAT]]]}, "a ring of two points"),
                 ({"type": "Polygon", "coordinates": "x"}, "coordinates as a string"),
                 ({"type": "Polygon", "coordinates": [square(95, LON, 0.01)]}, "a latitude past 90"),
                 ({"type": "Polygon"}, "no coordinates"),
                 ("POLYGON((0 0))", "WKT instead of GeoJSON")]:
    check(raises(area.cover, {"polygon": bad}) is not None, f"{why} is refused")

# ---------------------------------------------------------------- bbox
w, s, e, n = area.bbox([HOME])
pts = h3.cell_to_boundary(HOME)
check((w, s, e, n) == (min(p[1] for p in pts), min(p[0] for p in pts), max(p[1] for p in pts), max(p[0] for p in pts)),
      "bbox is west, south, east, north of the cells' boundaries")
w2, s2, e2, n2 = area.bbox(RING)
check(w2 < w and s2 < s and e2 > e and n2 > n, "the ring's bbox contains the home cell's")
check(raises(area.bbox, []) is not None, "bbox of no cells is refused")

# ---------------------------------------------------------------- summarise
NOW = datetime.now(timezone.utc)


def ago(h):
    return NOW - timedelta(hours=h)


rows = [{"metric": "pm25", "ts": ago(30), "value": 99.0},     # older than 24 h: not in the mean, not the latest
        {"metric": "pm25", "ts": ago(2), "value": 10.0},
        {"metric": "pm25", "ts": ago(1), "value": 20.0},
        {"metric": "pm25", "ts": NOW + timedelta(hours=5), "value": 500.0},   # a forecast row: never a reading
        {"metric": "temp", "ts": ago(48), "value": 31.0}]
sm = area.summarise(rows)
check(set(sm) == {"pm25", "temp"}, f"one entry per metric, got {sorted(sm)}")
check(sm["pm25"]["latest"] == 20.0 and sm["pm25"]["latest_at"] == ago(1).isoformat(), f"latest is the newest past reading: {sm['pm25']}")
check(sm["pm25"]["mean_24h"] == 15.0 and sm["pm25"]["n"] == 2, f"mean_24h over the last 24 h only: {sm['pm25']}")
check(sm["temp"]["latest"] == 31.0 and sm["temp"]["mean_24h"] is None and sm["temp"]["n"] == 0,
      f"nothing in 24 h: the mean stays missing, never 0: {sm['temp']}")
check(area.summarise([]) == {}, "no rows, no metrics")
check("pm1" not in area.summarise([{"metric": "pm1", "ts": NOW + timedelta(hours=1), "value": 3.0}]),
      "a metric with only future rows is absent")
two = area.summarise([{"metric": "pm25", "ts": ago(1), "value": 10.0}, {"metric": "pm25", "ts": ago(1), "value": 30.0}])
check(two["pm25"]["latest"] == 20.0, f"two sensors at the same newest moment: their mean, not whichever came first: {two}")
st = area.summarise([{"metric": "pm25", "ts": ago(1).isoformat(), "value": 7.0}])
check(st["pm25"]["latest"] == 7.0 and st["pm25"]["mean_24h"] == 7.0, "a capture's string timestamp reads like a datetime")
nv = area.summarise([{"metric": "pm25", "ts": ago(1), "value": None}])
check(nv == {}, f"a row with no value is no reading: {nv}")


# ---------------------------------------------------------------- own
def pt(c):
    return h3.cell_to_latlng(c)


def sensor(sid, kind, custody, c=None):
    lat, lon = pt(c) if c else (None, None)
    return {"sensor_id": sid, "kind": kind, "custody": custody, "lat": lat, "lon": lon}


SENSORS = [sensor("home-1", "sensor", True, HOME),
           sensor("n1-1", "sensor", True, N1),          # in a held neighbour
           sensor("n3-1", "sensor", True, N3),          # in an open neighbour: never read as own
           sensor("far-1", "sensor", True, FAR),        # local yesterday, far away: not in the ring
           sensor("street-1", "portal", False, HOME),   # a public reference in home: not custody
           sensor("peer-home", "peer", False, HOME),
           sensor("peer-n3", "peer", False, N3),
           sensor("peer-radio", "peer", False),         # a radio peer with only a distance
           sensor("child-a", "child", True),
           sensor("child-b", "child", True),
           sensor("own-nopoint", "sensor", True)]       # an own sensor with no coordinates: never guessed into a cell
READ = [{"sensor_id": sid, "metric": "pm25", "ts": ago(1), "value": v}
        for sid, v in [("home-1", 10.0), ("n1-1", 20.0), ("n3-1", 1000.0), ("far-1", 1000.0), ("street-1", 1000.0),
                       ("peer-home", 40.0), ("peer-n3", 60.0), ("peer-radio", 1000.0), ("child-a", 1000.0),
                       ("own-nopoint", 1000.0)]]
OWN_CELLS = {HOME, N1, N2}

o = area.own(SENSORS, READ, set(RING), OWN_CELLS)
check(o["sensors"] == 2, f"own counts the custody sensors in selection ∩ own cells: home-1 and n1-1, got {o['sensors']}")
check(o["metrics"]["pm25"]["latest"] == 15.0 and o["metrics"]["pm25"]["n"] == 2,
      f"own never reads an open neighbour, a portal, a peer, a child or a sensor with no point: {o['metrics']}")
check(o["children_unplaced"] == 2, f"two children with no cell, got {o['children_unplaced']}")
check(o["cells"] == sorted(OWN_CELLS), f"own names the cells it read: selection ∩ own cells, got {o['cells']}")
o1 = area.own(SENSORS, READ, {N1, N3}, OWN_CELLS)
check(o1["sensors"] == 1 and o1["metrics"]["pm25"]["latest"] == 20.0 and o1["cells"] == [N1],
      f"a selection that only touches one own cell reads only that cell: {o1}")
o0 = area.own(SENSORS, READ, {N3, FAR}, OWN_CELLS)
check(o0["sensors"] == 0 and o0["metrics"] == {} and o0["cells"] == [] and o0.get("why"),
      f"a selection with no own cells gives an empty own block that says so: {o0}")
check("pm25" not in o0["metrics"], "and no number is made up for it")
oe = area.own(SENSORS, READ, {N2}, OWN_CELLS)
check(oe["sensors"] == 0 and oe["metrics"] == {} and oe["cells"] == [N2] and oe.get("why") and oe["why"] != o0["why"],
      f"an own cell with no sensor in it says that, differently: {oe}")
check(not o.get("why"), "a block with numbers carries no 'why'")
check(o.get("unplaced") == 1 and o0.get("unplaced") == 1,
      f"an own sensor with no point is counted as unplaced, whatever the selection, never silently dropped: {o.get('unplaced')}")

# ---------------------------------------------------------------- peers
p = area.peers(SENSORS, READ, set(RING))
check(p["sensors"] == 2 and p["metrics"]["pm25"]["latest"] == 50.0, f"peers in the selection: peer-home and peer-n3: {p}")
check(p["unplaced"] == 1, f"the radio peer with only a distance is unplaced, never guessed into a cell: {p['unplaced']}")
pn = area.peers(SENSORS, READ, {N3})
check(pn["sensors"] == 1 and pn["metrics"]["pm25"]["latest"] == 60.0, f"peers only where they have a point: {pn}")
p0 = area.peers(SENSORS, READ, {FAR})
check(p0["sensors"] == 0 and p0["metrics"] == {} and p0.get("why") and p0["unplaced"] == 1, f"no peers here, said so: {p0}")
check(not p.get("why"), "a peers block with numbers carries no 'why'")

# ---------------------------------------------------------------- the route: POST /area (Task 8)
# Driven through the app with the database faked, as tests/test_cells.py drives /place/cells. Packs are fakes written
# to a temporary PACKS_DIR, so each reason a pack gives nothing is reached without a network.
import logging  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

logging.disable(logging.WARNING)
LAT, LON = h3.cell_to_latlng(HOME)
os.environ.update(ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok", DATABASE_URL="postgresql://unused/never-connected",
                  NODE_LAT=str(LAT), NODE_LON=str(LON))
import settings  # noqa: E402
ROWS = {"SHARE_LEVEL": "open", "BACKUP_TOKEN": "backup-tok", "PACKS_ALLOW_CODE": "1",
        "PACKS_ENABLED": "alpha,beta,gamma,delta,zeta,broken", "BETA_ON": "0"}
settings._cache = {"at": time.time() + 1e9, "rows": dict(ROWS)}
import auth  # noqa: E402
import main  # noqa: E402 — importing the app starts nothing
import packs  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PD = Path(tempfile.mkdtemp())
FAKE = {
    "alpha": 'def area(cells, bbox):\n    return {"pack": "alpha", "source": "A", "licence": "CC0", "rows": [len(cells)], "as_of": "2026-11-15T00:00:00+00:00"}\n',
    "beta": 'AREA_SWITCH = ("BETA_ON", "1")\ndef area(cells, bbox):\n    return {"pack": "beta", "source": "B", "licence": "CC0", "rows": [], "as_of": None}\n',
    "gamma": 'def area(cells, bbox):\n    return None\n',
    "delta": 'def area(cells, bbox):\n    raise RuntimeError("boom")\n',
    "eps": 'def area(cells, bbox):\n    return {"pack": "eps", "rows": []}\n',          # left out of PACKS_ENABLED
    "zeta": 'def on_readings(rows):\n    return None\n',                                  # no area hook: not listed
    "broken": 'import no_such_module\ndef area(cells, bbox):\n    return None\n',         # its code does not load
}
for name, code in FAKE.items():
    (PD / name).mkdir()
    (PD / name / "pack.yaml").write_text(f"id: {name}\n")
    (PD / name / "hooks.py").write_text(code)
packs.PACKS_DIR = PD


def setting(**kw):
    ROWS.update(kw)
    settings._cache.update(at=time.time() + 1e9, rows=dict(ROWS))
    packs._HOOKS["at"] = 0.0


SENSORS_DB = SENSORS + [sensor("n2-1", "sensor", True, N2)]      # in a claimed neighbour with no reading in 24 h
READ_DB = READ + [{"sensor_id": "n2-1", "metric": "pm25", "ts": ago(30), "value": 1000.0}]
MARKS = {7: {"kind": "area", "agent": None, "from_node": None,
             "geometry": {"type": "Polygon", "coordinates": [[list(reversed(p)) for p in h3.cell_to_boundary(HOME)]
                                                              + [list(reversed(h3.cell_to_boundary(HOME)[0]))]]}},
         8: {"kind": "line", "agent": None, "from_node": None, "geometry": {"type": "LineString", "coordinates": [[LON, LAT], [LON + .01, LAT]]}},
         9: {"kind": "area", "agent": "claude", "from_node": None, "geometry": None},
         10: {"kind": "area", "agent": None, "from_node": "node-2", "geometry": None}}


class Cur:
    def __init__(self):
        self.cells = {HOME: "home", N1: "keeper", N2: "keeper"}     # adopted already; N2 claimed, never held
        self.recent = {"home-1", "n1-1"}                             # sensors with a reading in the last 24 h
        self.sql, self._last, self.rowcount = [], [], 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, q, params=()):
        u = " ".join(q.split())
        self.sql.append(u)
        if "FROM node_cells" in u and "WHERE cell" in u:
            self._last = [{"cell": params[0], "claimed_by": self.cells[params[0]]}] if params[0] in self.cells else []
        elif "FROM node_cells" in u:
            self._last = [{"cell": c} for c in self.cells]
        elif "EXISTS (SELECT 1 FROM readings" in u:                  # cells._seen
            self._last = [{"lat": s["lat"], "lon": s["lon"]} for s in SENSORS_DB if s["sensor_id"] in self.recent]
        elif "FROM place_marks" in u:
            check("k.kind = 'area'" in u and "p.agent IS NULL" in u and "p.from_node IS NULL" in u,
                  "a mark_id resolves to the household's own drawn area only")
            m = MARKS.get(params[0])
            ok = m and m["kind"] == "area" and not m["agent"] and not m["from_node"]
            self._last = [{"geometry": m["geometry"]}] if ok else []
        elif "FROM sensors" in u:
            self._last = [dict(s) for s in SENSORS_DB]
        elif "FROM readings" in u:
            check("interval '24 hours'" in u and "ts <= now()" in u, "the pull reads the last 24 h, none from the future")
            self._last = [r for r in READ_DB if r["sensor_id"] in params[0]]
        else:
            self._last = []

    def fetchall(self):
        return list(self._last)

    def fetchone(self):
        return self._last[0] if self._last else None


class Con:
    def __init__(self, cur):
        self.cur = cur

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def transaction(self):
        return self

    def cursor(self):
        return self.cur


CUR = Cur()
cells._db = lambda: Con(CUR)
c = TestClient(main.app)
local = TestClient(main.app, client=("127.0.0.1", 51000))
H = {"Authorization": "Bearer act-tok"}

for level in ("off", "open"):
    exact, prefixes = auth._SHARE[level]
    check("/area" not in exact and not any("/area".startswith(pre) for pre in prefixes), f"/area is on no SHARE_LEVEL allowlist ({level})")
check(c.post("/area", json={"cells": [HOME]}).status_code in (401, 403), "a pull with no token is refused, even at SHARE_LEVEL=open")
check(c.post("/area", json={"cells": [HOME]}, headers={"Authorization": "Bearer backup-tok"}).status_code == 401,
      "the NAS's backup token passes SHARE_LEVEL and is still refused here")
check(not CUR.sql, f"a refused pull reads nothing: {CUR.sql}")
check(local.post("/area", json={"cells": [HOME]}).status_code == 200, "this machine pulls without a token")

r = c.post("/area", json={"cells": RING}, headers=H)
b = r.json() if r.status_code == 200 else {}
check(r.status_code == 200, f"POST /area over the seven is 200, got {r.status_code} {r.text[:300]}")
check(b.get("cells") == 7 and b.get("res") == 8 and set(b) == {"cells", "res", "own", "peers", "open"}, f"the answer's shape: {sorted(b)}")
ow = b.get("own", {})
check(ow.get("cells") == sorted({HOME, N1}), f"own reads home and held cells only, never a claimed one with no reading: {ow.get('cells')}")
check(ow.get("sensors") == 2 and ow.get("metrics", {}).get("pm25", {}).get("latest") == 15.0,
      f"own: home-1 and n1-1, not n2-1 in the claimed cell: {ow}")
check(ow.get("unplaced") == 1 and ow.get("children_unplaced") == 2, f"own counts what it could not place: {ow}")
pe = b.get("peers", {})
check(pe.get("sensors") == 2 and pe.get("unplaced") == 1, f"peers by point, the radio one unplaced: {pe}")
rd = [u for u in CUR.sql if "FROM readings" in u and "EXISTS" not in u]
check(rd and "channel_roles" not in rd[-1], "the household reads its private metrics too")

op = {o["pack"]: o for o in b.get("open", [])}
check(sorted(op) == ["alpha", "beta", "broken", "delta", "eps", "gamma"],
      f"one entry per pack with an area hook, on or off; zeta has none: {sorted(op)}")
check(op.get("alpha", {}).get("rows") == [7] and op["alpha"].get("source") == "A", f"a pack's answer goes through whole: {op.get('alpha')}")
check(op.get("beta", {}).get("off") is True and "BETA_ON=1" in op["beta"].get("why", "") and "rows" not in op["beta"],
      f"a pack whose own switch is off says so, and is not asked: {op.get('beta')}")
check(op.get("eps", {}).get("off") is True and "PACKS_ENABLED" in op["eps"].get("why", ""), f"left out of PACKS_ENABLED: {op.get('eps')}")
check(op.get("gamma", {}).get("off") is False and op["gamma"].get("why") and "off" not in op["gamma"]["why"],
      f"a pack that is on and has nothing says that, not that it is off: {op.get('gamma')}")
check(op.get("delta", {}).get("error") and "boom" not in op["delta"]["error"], f"a pack that fails says so in a sentence: {op.get('delta')}")
check(op.get("broken", {}).get("error"), f"a pack whose code did not load says so: {op.get('broken')}")
check(all(len(o.get("why", "x").split(". ")) == 1 for o in op.values()), "each reason is one sentence")
setting(PACKS_ALLOW_CODE="0")
op = {o["pack"]: o for o in c.post("/area", json={"cells": [HOME]}, headers=H).json().get("open", [])}
check(op.get("alpha", {}).get("off") is True and "PACKS_ALLOW_CODE" in op["alpha"].get("why", ""),
      f"with pack code not allowed, a code pack is off and says which setting: {op.get('alpha')}")
setting(PACKS_ALLOW_CODE="1", BETA_ON="1")
op = {o["pack"]: o for o in c.post("/area", json={"cells": [HOME]}, headers=H).json().get("open", [])}
check(op.get("beta", {}).get("source") == "B", f"switched on, it answers: {op.get('beta')}")
setting(BETA_ON="0")

r = c.post("/area", json={"cells": [FAR]}, headers=H)
ow = r.json()["own"] if r.status_code == 200 else {}
check(ow.get("sensors") == 0 and ow.get("metrics") == {} and ow.get("why"), f"a selection away from the node reads none of its own: {ow}")

for bad, why in (({"cells": ["nope"]}, "not an H3 cell"), ({}, "exactly one"), ({"cells": [HOME], "polygon": {}}, "exactly one"),
                 ({"cells": sorted(h3.grid_disk(h3.cell_to_parent(HOME, 5), 1))[:2]}, "more than 500")):
    r = c.post("/area", json=bad, headers=H)
    check(r.status_code == 400 and why in str(r.json().get("detail")), f"{bad} is 400 with the sentence, got {r.status_code} {r.text[:200]}")
r = c.post("/area", json={"mark_id": 7}, headers=H)
check(r.status_code == 200 and r.json().get("cells", 0) >= 1, f"a drawn area of the household's pulls its cells: {r.status_code} {r.text[:200]}")
for mid, why in ((99, "unknown"), (8, "a line"), (9, "an agent's map"), (10, "a child's map")):
    check(c.post("/area", json={"mark_id": mid}, headers=H).status_code == 404, f"mark_id of {why} is 404")
for mid in ("7", True, 7.5):
    check(c.post("/area", json={"mark_id": mid}, headers=H).status_code == 400, f"mark_id {mid!r} is not an id: 400")

CUR.sql.clear()
c.post("/area", json={"cells": RING}, headers={**H, "X-Agent": "claude"})
rd = [u for u in CUR.sql if "FROM readings" in u and "EXISTS (SELECT 1 FROM readings" not in u]
check(rd and "channel_roles" in rd[-1], "an agent's pull never reads a private metric (packs.public_sql)")

os.environ.pop("NODE_LAT")
r = c.post("/area", json={"cells": [HOME]}, headers=H)
ow = r.json()["own"] if r.status_code == 200 else {}
check(r.status_code == 200 and ow.get("cells") == [] and ow.get("why"), f"a node with no place has no own cells, and still pulls: {r.status_code} {ow}")
os.environ["NODE_LAT"] = str(LAT)

if fails:
    print("\n".join(f"  ✗ {f}" for f in fails))
print("  ✓ area: cover by cells and polygon under AREA_CAP, bbox, summarise, own only in own cells, peers by point, POST /area" if not fails else f"  ✗ {len(fails)} failure(s)")
sys.exit(1 if fails else 0)
