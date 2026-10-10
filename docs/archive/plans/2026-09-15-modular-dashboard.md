# Modular dashboard (direction H) — Phase 2 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship direction H — the dial, the loop, and the pack section contract — as node #1's production dashboard: three static files, every number computed by the node and published on `GET /issues`, one change per commit, gates green.

**Architecture:** The node computes, the page draws. `app/issues/geometry.py` (new, pure, h3) computes the plates, the footprints, the grain table and the radio from the node's coordinates and settings; `engine.compute()` publishes them on `/issues` beside per-station readings, the asks ledger and the declared metrics, for live data and for fixture replay alike. The page is the prototype's shell, kits and ten modules hand-assembled into the three files the static allowlist already serves — `index.html`, `dashboard.js`, `dashboard.css` — with `window.SNAP`/`window.H3`/`window.PLAN` replaced by one `boot()` that reads `/issues` and `/place/geojson`. Nothing in `app/main.py` changes.

**Tech Stack:** Python 3 / FastAPI / psycopg (existing), `h3==4.*` (already in `app/requirements.txt`), vanilla JS classic scripts (no build, no framework, no CDN), Playwright via `planetai-design/node_modules` for the visual gates only.

**Spec:** `docs/design/DIRECTIONS_2026-09.md` Part Three, section *H, revised again* and *H, revised · the ground under the dial*; `docs/archive/handoffs/HANDOFF_dashboard_directions.md` section *If the answer is H, the modular one*; the prototype at `planetai-design/prototypes/dashboard-directions/` (`kit-page.js` is the contract; `h/index.html` the shell; `h/mods/*.js` the ten sections; `h/wall.js` the wall). Decisions taken 15 Sep 2026: **per-station values are published**; **live tiles are off by default and opt-in in Set up** (`MAP_TILES`); **Now keeps ground · stations · claims · grain · asks · measure; satellite · reticulum · meshtastic · hardware go to Network**; h3 is already a dependency.

## Global Constraints

- Node #1 is READ-ONLY (binds 127.0.0.1); node #2 (`mahon1`, Lucas) and any node #3/#4 are never touched. Prove on `pai-clean` only.
- NEVER print, paste or commit a token, key, chat id or `.env` value. A fixture carries 15-minute means, alert texts and sensor names — never raw readings.
- Three static files: `app/static/index.html`, `app/static/dashboard.js`, `app/static/dashboard.css`. No build step, no framework, no CDN, no new Python dependency, no new container. `tools/check_ui.py` enforces the file set and that every load is under `static/` and on the COMPANIONS allowlist.
- `app/main.py` is not touched. `/issues` is extended inside `app/issues/`; no new endpoint.
- STOP and ask before: any change to a pack's rules or cells; ρ's definition; `/actions`; `SHARE_LEVEL`'s levels or `_SHARE_OFF`; deleting a view; a new endpoint; anything failed three times.
- The frozen layer: `app/static/planetai-theme.css` and `tokens.css` are byte-identical to `planetai-design`; `tools/check_theme.py` fails otherwise. Colour is a role from a token; state is weight/fill/dash, never hue; orange means only what the satellite alone knows; square corners; no gauges.
- One change per commit; `make lint && make test` green before each; message says what changed and for whom; end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. No PR to main — Tomas reads the branch `dashboard-redesign-2026-09`.
- Every numeral carries `data-num` and `data-cmp`; every component `data-component` and a `data-ref` in or out; card kinds are `readout · stack · series · row` only; explanations live in a section's `notes()`, printed folded at the foot.
- The gate for the page is the same script as Phase 1: `tests/visual/measure.mjs`. No-regression thresholds against the prototype's measured values (Task 10), not the unreached 30 %/20 %.

---

## File structure

| file | responsibility |
|---|---|
| `app/issues/geometry.py` (create) | pure functions over `(lat, lon, settings, stations)`: `ladder()`, `plates()`, `grain_table()`, `publication()`, `claims()`, `radio()`, `metres()`; the H3 the node already has, published as shapes |
| `app/issues/engine.py` (modify) | `_read()` gathers alerts, actions, presence; `compute()` adds `stations`, `asks`, `metrics`, `geometry` to the body; `Replay` serves the same tables from a fixture |
| `app/issues/fixtures/node1-2026-09-06.json` (unchanged) | the replay source; the new keys compute from it |
| `app/settings.py` (modify) | `MAP_TILES` joins `PUBLIC` with validation `off|on`, default `off` |
| `app/static/index.html` (rewrite) | the shell: dial, lead, stage bands, views Now · Network · Set up · Wall; loads the two companions |
| `app/static/dashboard.js` (rewrite) | `boot()`, the kits (`K`, `KH`, `KN`, `KMAP`, `PAI`), the ten sections, the wall; one file, banners between parts |
| `app/static/dashboard.css` (rewrite) | kit.css + the shell's CSS + every module's CSS block (no JS-injected styles in production) |
| `tools/check_ui.py` (modify, minimal) | the stats-view field list gains the columns the page now reads |
| `tests/test_issues_geometry.py` (create) | the geometry against h3geo.org's table and `kilometre-cells.json` |
| `tests/test_issues_engine.py` (modify) | the new keys, from the fixture |
| `tests/test_settings.py` (modify) | `MAP_TILES` refuses anything but `off`/`on` |
| `tests/test_dashboard.py` (modify) | the three files hold the shell, the contract and the ten sections |
| `tests/all` (modify) | registers `test_issues_geometry` |
| `tests/visual/gate.sh` (create) | renders the production page from the fixture and fails on regression |
| `docs/PACKS.md` (modify) | the section contract, for a pack author |
| `docs/archive/handoffs/HANDOFF_dashboard_directions.md` (modify) | points at this plan and at what shipped |

---

### Task 1: `geometry.py` — the ladder, the plates, the grain, the publication grain

**Files:**
- Create: `app/issues/geometry.py`
- Create: `tests/test_issues_geometry.py`
- Modify: `tests/all` (register the suite beside `test_issues_engine`)

**Interfaces:**
- Consumes: `h3` (installed), `settings.num(key, default)` / `settings.get(key, default)` from `app/settings.py`.
- Produces:
  - `ladder(lat, lon) -> list[dict]` — 14 rows, res 0..13: `{res, id, edge_m, area_m2, cells, own_area_m2, pentagon}`
  - `plates(lat, lon, stations, res_min=2, res_max=12, steps=2) -> dict` — `{res_min, res_max, steps, chain: {res: id}, plates: {res: {res, centre, cells: [id], cells_ll: [[id, lat, lng, …]]}}, cells: {id: {res, parent, parent_outside, children_total, children_here, neighbours, neighbours_total, area_m2, edge_m, pentagon, sensors: [index]}}, cell_count}`
  - `grain_table(lat, lon, stations, floor_res, publication_res) -> list[dict]` — res 2..12: `{res, home, area_m2, edge_m, occupied, in_my_cell, mine_in_my_cell, may_leave, finer_than_published}`
  - `publication() -> dict` — `{decimals: 3, metres: 110, res, why}`
  - `contains(metres) -> int` — the finest resolution whose cell is at least that wide
  - `station` is any mapping with `lat`, `lon`, `local` (bool)

- [ ] **Step 1: Write the failing test**

```python
"""The H3 geometry the node publishes, checked against the numbers h3geo.org and the design repo already commit.

  · the ladder matches h3geo.org's resolution table: res 2 edge 182,513 m over 5,882 cells; res 8 area 737,328 m²
  · node #1's cells at 7, 8, 9 match planetai-design/assets/h3/kilometre-cells.json exactly
  · a plate is nineteen cells, its centre is the node's cell, and every cell's parent is in the plate above or flagged
  · the grain table: fourteen stations fall in 1 cell at res 4, 9 at res 8; three own sensors share one cell everywhere
  · publication: three decimals is about 110 m, and the resolution that holds it is 10

Run: PYTHONPATH=app python3 tests/test_issues_geometry.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "app"))

try:
    import h3  # noqa: F401
except ImportError:
    print("skipped: h3 is not installed (pip install -r app/requirements.txt)")
    sys.exit(0)

from issues import geometry as G  # noqa: E402

fails = []
snap = json.loads((ROOT / "app/issues/fixtures/node1-2026-09-06.json").read_text())
LAT, LON = snap["health"]["lat"], snap["health"]["lon"]
STATIONS = []
seen = set()
for r in snap["stats"]:
    if r["lat"] is None or r["sensor_id"] in seen:
        continue
    seen.add(r["sensor_id"])
    STATIONS.append({"sensor_id": r["sensor_id"], "lat": r["lat"], "lon": r["lon"], "local": bool(r["local"])})
STATIONS.sort(key=lambda s: (s["lat"], s["lon"]))

# --- the ladder against h3geo.org's table -----------------------------------------------------
L = G.ladder(LAT, LON)
if len(L) != 14 or L[2]["edge_m"] != 182513 or L[2]["cells"] != 5882:
    fails.append(f"res 2 should be 182,513 m over 5,882 cells, got {L[2]}")
if abs(L[8]["area_m2"] - 737328) > 1:
    fails.append(f"res 8 area should be 737,328 m², got {L[8]['area_m2']}")

# --- the design repo's committed cells ---------------------------------------------------------
KC = ROOT.parent / "planetai-design/assets/h3/kilometre-cells.json"
if KC.exists():
    kc = json.loads(KC.read_text())
    want = {7: kc.get("res7"), 8: kc.get("res8"), 9: kc.get("res9")}
    for res, cell in want.items():
        if cell and L[res]["id"] != cell:
            fails.append(f"res {res}: {L[res]['id']} != kilometre-cells.json {cell}")

# --- plates ---------------------------------------------------------------------------------------
P = G.plates(LAT, LON, STATIONS)
if sorted(P["plates"]) != list(range(2, 13)):
    fails.append(f"plates should cover 2..12, got {sorted(P['plates'])}")
for res, plate in P["plates"].items():
    if len(plate["cells"]) != 19:
        fails.append(f"plate {res} has {len(plate['cells'])} cells, not 19")
    if plate["centre"] != P["chain"][res]:
        fails.append(f"plate {res} centre is not the node's cell")
    for cid in plate["cells"]:
        c = P["cells"][cid]
        if res > 2 and not (c["parent"] or c["parent_outside"]):
            fails.append(f"{cid} at {res} has neither a parent in the plate above nor the flag")
        if len(c["neighbours"]) > c["neighbours_total"]:
            fails.append(f"{cid} lists more neighbours than it has")
own = [i for i, s in enumerate(STATIONS) if s["local"]]
if P["cells"][P["chain"][8]]["sensors"] != own:
    fails.append(f"the node's res-8 cell should hold exactly the own stations {own}, got {P['cells'][P['chain'][8]]['sensors']}")
if P["cell_count"] != 209:
    fails.append(f"11 plates × 19 cells is 209, got {P['cell_count']}")

# --- the grain table -----------------------------------------------------------------------------
T = {g["res"]: g for g in G.grain_table(LAT, LON, STATIONS, floor_res=6, publication_res=10)}
if T[4]["occupied"] != 1 or T[8]["occupied"] != 9:
    fails.append(f"occupied cells: res 4 {T[4]['occupied']} (want 1), res 8 {T[8]['occupied']} (want 9)")
if any(T[r]["mine_in_my_cell"] != 3 for r in range(2, 13)):
    fails.append("the three own stations carry one coordinate and must share one cell at every resolution")
if not T[6]["may_leave"] or T[7]["may_leave"]:
    fails.append("may_leave is true up to the floor (6) and false past it")
if T[10]["finer_than_published"] or not T[11]["finer_than_published"]:
    fails.append("finer_than_published starts past the publication resolution (10)")

# --- publication ---------------------------------------------------------------------------------
pub = G.publication()
if pub["decimals"] != 3 or pub["metres"] != 110 or pub["res"] != 10:
    fails.append(f"publication should be 3 dp ≈ 110 m → res 10, got {pub}")
if G.contains(110) != 10 or G.contains(10) != 12:
    fails.append(f"contains(110)={G.contains(110)} contains(10)={G.contains(10)}; want 10 and 12")

for f in fails:
    print("FAIL", f)
print("ok" if not fails else f"{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=app python3 tests/test_issues_geometry.py`
Expected: `ImportError: cannot import name 'geometry'` (or `ModuleNotFoundError`).

- [ ] **Step 3: Write `app/issues/geometry.py`**

```python
"""The H3 geometry this node publishes: the shapes the dashboard navigates by, computed here so the page never has to.

The node already has h3 (app/ground.py, the presence announce). Nothing here is a capability it gains — only a
shape it publishes. Every function is pure: coordinates, settings and station rows in; JSON-ready dicts out. The
same functions answer for live data and for a fixture replayed at the hour it was captured.

Design provenance: planetai-design/prototypes/dashboard-directions/make-h3.mjs, which computed these for the
Phase 1 drawings with h3-js and checked them against h3geo.org's resolution table and the design repo's
kilometre-cells.json. This is the Python of the same arithmetic; tests/test_issues_geometry.py keeps the two
agreeing.

One vocabulary note. A *distance* — room, yard, ring, region — is custody, not scale (DIRECTIONS_2026-09.md
finding 1). Nothing here maps a distance to a resolution. What is published is the grid itself, and the page
says which custody a reading carries.
"""
from __future__ import annotations

import math

import h3

NAV_MIN, NAV_MAX, NAV_STEPS = 2, 12, 2


def contains(metres: float) -> int:
    """The finest resolution whose cell is at least `metres` across (two edge lengths)."""
    for res in range(15, -1, -1):
        if h3.average_hexagon_edge_length(res, unit="m") * 2 >= metres:
            return res
    return 0


def publication() -> dict:
    """The finest grain a coordinate this node publishes may honestly be drawn at.

    GET /health rounds lat and lon to three decimals (app/main.py), about 110 m at this latitude; a cell narrower
    than that is a claim of precision the node did not make.
    """
    return {"decimals": 3, "metres": 110, "res": contains(110),
            "why": "GET /health rounds lat and lon to three decimals, which is about 110 m — app/main.py"}


def ladder(lat: float, lon: float) -> list[dict]:
    """Every resolution this place can be named at, with what H3 says a cell is there, and the cell it stands in."""
    out = []
    for res in range(0, 14):
        cell = h3.latlng_to_cell(lat, lon, res)
        out.append({
            "res": res, "id": cell,
            "edge_m": round(h3.average_hexagon_edge_length(res, unit="m")),
            "area_m2": round(h3.average_hexagon_area(res, unit="m^2")),
            "cells": h3.get_num_cells(res),
            "own_area_m2": round(h3.cell_area(cell, unit="m^2")),
            "pentagon": h3.is_pentagon(cell),
        })
    return out


def _cell_of(station: dict, res: int) -> str:
    return h3.latlng_to_cell(station["lat"], station["lon"], res)


def plates(lat: float, lon: float, stations: list[dict], res_min: int = NAV_MIN, res_max: int = NAV_MAX,
           steps: int = NAV_STEPS) -> dict:
    """One plate per resolution: the node's cell and `steps` rings around it, with every cell's parent, neighbours,
    size and contents. A page navigates only inside what is published — a child or neighbour outside the plate is a
    count, not a door. A dashboard is not a map of the planet."""
    chain = {res: h3.latlng_to_cell(lat, lon, res) for res in range(res_min, res_max + 1)}
    plates_ = {}
    for res in range(res_min, res_max + 1):
        centre = chain[res]
        ids = h3.grid_disk(centre, steps)
        plates_[res] = {"res": res, "centre": centre, "cells": ids,
                        "cells_ll": [[cid] + [round(v, 6) for pt in h3.cell_to_boundary(cid) for v in pt]
                                     for cid in ids]}
    in_plate = lambda res, cid: res_min <= res <= res_max and cid in plates_[res]["cells"]  # noqa: E731
    cells = {}
    for res in range(res_min, res_max + 1):
        for cid in plates_[res]["cells"]:
            parent = h3.cell_to_parent(cid, res - 1) if res > res_min else None
            kids = h3.cell_to_children(cid, res + 1) if res < res_max else []
            try:
                around = h3.grid_ring(cid, 1)
            except Exception:  # noqa: BLE001 — a pentagon's ring is undefined; the disk minus the centre is the answer
                around = [x for x in h3.grid_disk(cid, 1) if x != cid]
            cells[cid] = {
                "res": res,
                "parent": parent if parent and in_plate(res - 1, parent) else None,
                "parent_outside": bool(parent and not in_plate(res - 1, parent)),
                "children_total": len(kids),
                "children_here": sum(1 for k in kids if in_plate(res + 1, k)),
                "neighbours": [n for n in around if in_plate(res, n)],
                "neighbours_total": len(around),
                "area_m2": round(h3.cell_area(cid, unit="m^2")),
                "edge_m": round(h3.average_hexagon_edge_length(res, unit="m")),
                "pentagon": h3.is_pentagon(cid),
                "sensors": [i for i, s in enumerate(stations) if _cell_of(s, res) == cid],
            }
    return {"res_min": res_min, "res_max": res_max, "steps": steps, "chain": chain,
            "plates": plates_, "cells": cells, "cell_count": len(cells)}


def grain_table(lat: float, lon: float, stations: list[dict], floor_res: int, publication_res: int) -> list[dict]:
    """What every grain is worth: one cell's size, how many cells the stations fall in, and which side of the two
    lines the product already draws it is on."""
    out = []
    for res in range(NAV_MIN, NAV_MAX + 1):
        home = h3.latlng_to_cell(lat, lon, res)
        cells = {_cell_of(s, res) for s in stations}
        mine = [s for s in stations if _cell_of(s, res) == home]
        out.append({
            "res": res, "home": home,
            "area_m2": round(h3.cell_area(home, unit="m^2")),
            "edge_m": round(h3.average_hexagon_edge_length(res, unit="m")),
            "occupied": len(cells),
            "in_my_cell": len(mine),
            "mine_in_my_cell": sum(1 for s in mine if s.get("local")),
            "may_leave": res <= floor_res,
            "finer_than_published": res > publication_res,
        })
    return out


def metres(cid: str, lat: float, lon: float) -> list[float]:
    """A cell's boundary in metres east and south of the node, in the dashboard's own local frame —
    NODE_DASHBOARD_PLAN_SPEC.md rule 1, measured within 0.015 px of geoAzimuthalEqualArea over node #1's plan."""
    k = math.cos(math.radians(lat)) * 111320
    out = []
    for plat, plng in h3.cell_to_boundary(cid):
        out += [round((plng - lon) * k, 1), round(-(plat - lat) * 111320, 1)]
    return out
```

- [ ] **Step 4: Register the suite and run it**

In `tests/all`, find the line that runs `test_issues_engine` and add directly after it:

```bash
run test_issues_geometry "PYTHONPATH=app python3 tests/test_issues_geometry.py"
```

Run: `PYTHONPATH=app python3 tests/test_issues_geometry.py`
Expected: `ok`. If `kilometre-cells.json` has keys other than `res7/res8/res9`, read it (`python3 -c "import json;print(json.load(open('../planetai-design/assets/h3/kilometre-cells.json')).keys())"`) and fix the test's `want` mapping — never the geometry.

- [ ] **Step 5: Gates and commit**

Run: `make lint && make test`
Expected: `ok` and `34 suites: 34 passed`.

```bash
git add app/issues/geometry.py tests/test_issues_geometry.py tests/all
git commit -m "$(cat <<'EOF'
issues: the H3 geometry the page navigates by, computed by the node

For the dashboard that turns a dial: the ladder, one plate per resolution with
every cell's parent, neighbours, size and contents, the grain table and the
publication grain. Pure functions over coordinates, settings and station rows,
so a fixture replays through the same code as live data.

Checked the way Phase 1 checked its drawings: res 2 is 182,513 m over 5,882
cells and res 8 is 737,328 m² against h3geo.org's table; node #1's cells at
7, 8 and 9 match the design repo's kilometre-cells.json exactly.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `geometry.py` — the claims and the radio

**Files:**
- Modify: `app/issues/geometry.py`
- Modify: `tests/test_issues_geometry.py`

**Interfaces:**
- Consumes: `settings.num("LOCAL_RADIUS_M", 500)`, `settings.num("BAD_RADIUS_KM", 15)`, `settings.num("COAST_MAX_KM", 30)`, `settings.num("EARTH_RADIUS_M", 5000)`, `settings.num("PLACE_RADIUS_M", 1000)`, `settings.num("RETICULUM_PRESENCE_RES", 3)`; `PRESENCE_RES_FLOOR = 6` (the constant in `app/main.py`, copied here as `FLOOR_RES = 6` with a comment naming its source).
- Produces:
  - `claims(lat, lon, settings) -> list[dict]` sorted by `area_km2` desc: `{key, name, what, footprint_m, shape, declared, where, note, native (or None): {res, cells, compact, by_res, saving}, drawn: {base_res, cells, compact, by_res}, area_km2, cells: [ids], cells_at: {res: n}}`
  - `radio(lat, lon, settings, peers) -> dict` — `{res, mine, candidates: [ids], peer_km, edge_m, area_m2, cells: [ids]}` where `peers` is a list of `{cell, res, km}` (the presence table) and `candidates` is the cells of `grid_disk(mine, 2)` whose distance range from the node contains a peer's km, or the peer's own announced cell when it is known.
  - `cells_at(cells, res) -> int`

- [ ] **Step 1: Extend the test**

Append before the `for f in fails:` line:

```python
# --- the claims: every footprint a number the product already declares ----------------------------------------
class S:  # the settings module's two readers, over the preset node #1 was captured under
    _v = {"LOCAL_RADIUS_M": 500, "BAD_RADIUS_KM": 8, "COAST_MAX_KM": 30, "EARTH_RADIUS_M": 5000,
          "PLACE_RADIUS_M": 1000, "RETICULUM_PRESENCE_RES": 3}
    @staticmethod
    def num(k, d):
        return S._v.get(k, d)
    @staticmethod
    def get(k, d=""):
        return str(S._v.get(k, d))

C = {c["key"]: c for c in G.claims(LAT, LON, S)}
if list(c["key"] for c in G.claims(LAT, LON, S)) != ["coast", "ring", "region", "place", "yard", "room"]:
    fails.append("claims are ordered widest first: coast, ring, region, place, yard, room")
if not (2800 < C["coast"]["area_km2"] < 2830) or not (195 < C["ring"]["area_km2"] < 205):
    fails.append(f"coast ≈ 2,813 km² and ring ≈ 200 km²; got {C['coast']['area_km2']}, {C['ring']['area_km2']}")
reg = C["region"]
if reg["native"] is None or reg["native"]["res"] != 12:
    fails.append("the earth pack's square is 10 m a pixel, which is resolution 12")
elif not (370000 < reg["native"]["cells"] < 380000) or reg["native"]["saving"] < 80:
    fails.append(f"374,551 cells at res 12 should compact about 92×; got {reg['native']}")
if C["room"]["native"]["res"] != 10:
    fails.append("the room's grain is the publication grain, resolution 10")
if C["coast"]["cells_at"][8] < 4000 or C["room"]["cells_at"][8] != 1:
    fails.append(f"at res 8 the sea's word covers ~4,396 cells and a probe covers 1; got {C['coast']['cells_at'][8]}, {C['room']['cells_at'][8]}")
if any(len(c["cells"]) > 140 for c in C.values()):
    fails.append("a drawn covering is at most 140 cells")

# --- the radio: a peer is a cell and a distance, never a point -------------------------------------------------
R = G.radio(LAT, LON, S, peers=[{"cell": None, "res": 3, "km": 61}])
if R["res"] != 3 or R["mine"] != L[3]["id"]:
    fails.append("the node announces its res-3 cell")
if not (1 <= len(R["candidates"]) <= 6) or R["mine"] in R["candidates"]:
    fails.append(f"61 km from a res-3 cell is one of its neighbours, not itself: {R['candidates']}")
R2 = G.radio(LAT, LON, S, peers=[{"cell": R["candidates"][0], "res": 3, "km": 61}])
if R2["candidates"] != [R["candidates"][0]]:
    fails.append("a peer whose cell is known is drawn in that cell and no other")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=app python3 tests/test_issues_geometry.py`
Expected: `AttributeError: module 'issues.geometry' has no attribute 'claims'`.

- [ ] **Step 3: Implement**

Append to `app/issues/geometry.py`:

```python
FLOOR_RES = 6            # PRESENCE_RES_FLOOR in app/main.py: the finest any node may announce


def _circle(lat: float, lon: float, r_m: float, n: int = 90) -> list[list[float]]:
    d_lat = lambda m: m / 111320  # noqa: E731
    d_lon = lambda m: m / (111320 * math.cos(math.radians(lat)))  # noqa: E731
    ring = [[lat + d_lat(r_m * math.cos(a)), lon + d_lon(r_m * math.sin(a))]
            for a in (2 * math.pi * i / n for i in range(n))]
    return ring + [ring[0]]


def _square(lat: float, lon: float, half_m: float) -> list[list[float]]:
    dl, dn = half_m / 111320, half_m / (111320 * math.cos(math.radians(lat)))
    c = [[lat - dl, lon - dn], [lat - dl, lon + dn], [lat + dl, lon + dn], [lat + dl, lon - dn]]
    return c + [c[0]]


def _by_res(cells) -> dict:
    out: dict = {}
    for c in cells:
        out[h3.get_resolution(c)] = out.get(h3.get_resolution(c), 0) + 1
    return out


def cells_at(cells: list[str], res: int) -> int:
    """How many cells of `res` a compacted covering amounts to. Exact in the index: seven children per step down,
    distinct ancestors going up."""
    n, up = 0, set()
    for c in cells:
        r = h3.get_resolution(c)
        if res >= r:
            n += 7 ** (res - r)
        else:
            up.add(h3.cell_to_parent(c, res))
    return n + len(up)


def _claim(lat, lon, *, key, name, what, footprint_m, shape, declared, where, note, native_res, base_res) -> dict:
    poly = _square(lat, lon, footprint_m) if shape == "square" else _circle(lat, lon, footprint_m)
    shape_ = h3.LatLngPoly(poly)
    out = {"key": key, "name": name, "what": what, "footprint_m": footprint_m, "shape": shape,
           "declared": declared, "where": where, "note": note, "native": None}
    if native_res is not None:
        native = h3.polygon_to_cells(shape_, native_res)
        comp = h3.compact_cells(native)
        out["native"] = {"res": native_res, "cells": len(native), "compact": len(comp),
                         "by_res": _by_res(comp), "saving": round(len(native) / max(1, len(comp)))}
    # the set the page can draw: step the base grain back until the compacted covering fits in one drawing
    base = native_res if native_res is not None else base_res
    cells, comp = [], []
    for r in range(min(base, 11), -1, -1):
        cells = h3.polygon_to_cells(shape_, r)
        comp = h3.compact_cells(cells)
        if 0 < len(comp) <= 140:
            base = r
            break
    out["drawn"] = {"base_res": base, "cells": len(cells), "compact": len(comp), "by_res": _by_res(comp)}
    out["area_km2"] = round(sum(h3.cell_area(c, unit="m^2") for c in comp) / 1e4) / 100
    out["cells"] = sorted(comp)
    out["cells_at"] = {res: cells_at(out["cells"], res) for res in range(NAV_MIN, NAV_MAX + 1)}
    return out


def claims(lat: float, lon: float, settings) -> list[dict]:
    """What each source's word covers, as the compacted cell set that covers it. Every footprint is a number a pack or
    a preset already declares; each names the file it came from. Ordered widest first."""
    pub = publication()
    out = [
        _claim(lat, lon, key="coast", name="The sea", what="waves and sea-surface temperature at the nearest ocean cell",
               footprint_m=settings.num("COAST_MAX_KM", 30) * 1000, shape="circle", native_res=None, base_res=7,
               declared=f"COAST_MAX_KM={settings.num('COAST_MAX_KM', 30)}", where="packs/coast/pack.yaml",
               note="the pack refuses if the nearest ocean cell is further than this; the model cell it reads is not "
                    "declared anywhere, so the refusal radius is the only footprint there is"),
        _claim(lat, lon, key="ring", name="The street", what="public stations this node is allowed to read",
               footprint_m=settings.num("BAD_RADIUS_KM", 15) * 1000, shape="circle", native_res=None, base_res=8,
               declared=f"BAD_RADIUS_KM={settings.num('BAD_RADIUS_KM', 15)}", where=".env / presets",
               note=""),
        _claim(lat, lon, key="region", name="The square this node keeps", what="AlphaEarth satellite embeddings, year against year",
               footprint_m=settings.num("EARTH_RADIUS_M", 5000), shape="square", native_res=contains(10), base_res=9,
               declared=f"EARTH_RADIUS_M={settings.num('EARTH_RADIUS_M', 5000)}, at 10 m a pixel", where="packs/earth/pack.yaml",
               note="the only source whose own grain is finer than a household sensor, and the only one whose footprint is a square"),
        _claim(lat, lon, key="place", name="The kilometre it draws", what="the plan: buildings, water, green, from OpenStreetMap",
               footprint_m=settings.num("PLACE_RADIUS_M", 1000), shape="circle", native_res=None, base_res=10,
               declared=f"PLACE_RADIUS_M={settings.num('PLACE_RADIUS_M', 1000)}", where="packs/place/pack.yaml", note=""),
        _claim(lat, lon, key="yard", name="The wall outside", what="this node's own ground",
               footprint_m=settings.num("LOCAL_RADIUS_M", 500), shape="circle", native_res=None, base_res=11,
               declared=f"LOCAL_RADIUS_M={settings.num('LOCAL_RADIUS_M', 500)}", where=".env", note=""),
        _claim(lat, lon, key="room", name="This room", what="the probes in this house",
               footprint_m=pub["metres"], shape="circle", native_res=pub["res"], base_res=pub["res"],
               declared="lat and lon rounded to three decimals", where="app/main.py, GET /health",
               note="not a radius anybody chose: it is how precisely this node is willing to say where it is, and no "
                    "reading from it may be drawn finer"),
    ]
    return sorted(out, key=lambda c: -c["area_km2"])


def radio(lat: float, lon: float, settings, peers: list[dict]) -> dict:
    """What the radio says about where: this node's announce cell, and for each peer either the cell it announced or
    — when only a distance survived — the cells around this one that distance could be in. Never a point."""
    res = min(int(settings.num("RETICULUM_PRESENCE_RES", 3)), FLOOR_RES)
    mine = h3.latlng_to_cell(lat, lon, res)
    around = h3.grid_disk(mine, 2)

    def rng(cid):
        ds = [h3.great_circle_distance((lat, lon), pt, unit="km") for pt in h3.cell_to_boundary(cid)]
        return min(ds), max(ds)

    cands: list[str] = []
    km = None
    for p in peers or []:
        km = p.get("km", km)
        if p.get("cell"):
            if p["cell"] not in cands:
                cands.append(p["cell"])
        elif p.get("km") is not None:
            for cid in around:
                lo, hi = rng(cid)
                if cid != mine and lo <= p["km"] <= hi and cid not in cands:
                    cands.append(cid)
    return {"res": res, "mine": mine, "candidates": cands, "peer_km": km,
            "edge_m": round(h3.average_hexagon_edge_length(res, unit="m")),
            "area_m2": round(h3.cell_area(mine, unit="m^2")), "cells": around}
```

- [ ] **Step 4: Run the test**

Run: `PYTHONPATH=app python3 tests/test_issues_geometry.py`
Expected: `ok`. `polygon_to_cells` at res 12 over the 10 km square takes about a second; if the suite takes longer than five seconds, cache `claims()` with `functools.lru_cache` keyed on `(lat, lon)` and the five numbers — not on the settings object.

- [ ] **Step 5: Gates and commit**

Run: `make lint && make test` → `ok`, all suites passed.

```bash
git add app/issues/geometry.py tests/test_issues_geometry.py
git commit -m "$(cat <<'EOF'
issues: what each source's word covers, and what the radio says about where

Six footprints, every one a number a pack or a preset already declares, as the
compacted cell set that covers it: the sea, the street, the square this node
keeps, the kilometre it draws, the wall outside, this room. The earth pack's
square at its own 10 m grain is 374,551 cells and compacts to 4,063 - the same
ground exactly, 92 times smaller.

The radio publishes this node's announce cell and, for a peer, the cell it
announced or the cells a distance could be in. Never a point.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `/issues` publishes `stations`, `metrics` and `asks`

**Files:**
- Modify: `app/issues/engine.py` (`_read()` ~line 565–600; the return dict at ~703; `Replay` class)
- Modify: `tests/test_issues_engine.py`

**Interfaces:**
- Consumes: the `stats` view columns already read at `engine.py:570` (`sensor_id, metric, indoor, local, kind, scale, lat, lon, name, mean_15m, silent_minutes, …`); the `alerts` and `actions` tables the engine already reads for `_asks()`; the hourly buckets `readings_1h` the fixture carries.
- Produces, on the `/issues` body:
  - `stations: list[dict]` — `{sensor_id, name, lat, lon, local, indoor, kind, source, url, attribution, km, read: {metric: {value, unit, dp, silent_minutes}}, series: {metric: [{t, mean, min, max, n}]}}`, sorted by `km`; only stations with coordinates.
  - `metrics: dict` — `{metric: {unit, dp, issue, label}}` for `pm25 pm10 pm1 aqi temp humidity pressure noise light gas_resistance battery_v`.
  - `asks: dict` — `{acts: [{id, ts, rule_id, sensor_id, text}], actions: [{alert_id, stage, actor, ts}], levels: {act, warn, info}}` where `text` is the first line, ≤160 chars.
  - `mesh: dict|None` — `{root_topic, gateway, packets, last, device: {sensor_id, name, indoor}, reads: [{metric, mean_15m, silent_minutes}]}` from `/health`'s `mesh` and the `msh-*` stats rows.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_issues_engine.py` before its final `sys.exit`:

```python
# --- the keys the modular dashboard reads ---------------------------------------------------------------------
snap = json.loads((ROOT / "app/issues/fixtures/node1-2026-09-06.json").read_text())
body = engine.replay(snap, _Settings(), I.load())   # _Settings is the suite's existing settings stub

st = body.get("stations")
if not st or len(st) != 14:
    fails.append(f"stations: 14 with coordinates in the fixture, got {len(st or [])}")
else:
    sc = next(s for s in st if s["sensor_id"] == "sc-19849")
    if sc["source"] != "smartcitizen" or sc["url"] != "https://smartcitizen.me/kits/19849":
        fails.append(f"a Smart Citizen kit links to its page: {sc['source']} {sc['url']}")
    if "pm25" not in sc["read"] or sc["read"]["pm25"]["unit"] != "µg/m³":
        fails.append(f"a station's read carries the declared unit: {sc['read'].get('pm25')}")
    bad = next(s for s in st if s["sensor_id"].startswith("bad-"))
    if bad["attribution"] != "Bali Air Dispatch, baliairdispatch.com":
        fails.append("Bali Air Dispatch rows carry the attribution the observatory requires")
    traced = [s["sensor_id"] for s in st if s["series"]]
    if sorted(traced) != ["bad-sc-19774", "sc-19880"]:
        fails.append(f"the fixture has an hourly series for exactly two stations, got {traced}")
    if st != sorted(st, key=lambda s: s["km"]):
        fails.append("stations are ordered by distance")

m = body.get("metrics", {})
if m.get("pm25", {}).get("issue") != "air" or m.get("temp", {}).get("dp") != 1:
    fails.append(f"metrics declare unit, places and issue: {m.get('pm25')} {m.get('temp')}")

a = body.get("asks", {})
if len(a.get("acts", [])) != 21 or len(a.get("actions", [])) != 11 or a.get("levels", {}).get("warn") != 9:
    fails.append(f"asks: 21 acts, 11 actions, 9 warn in the fixture; got {len(a.get('acts', []))}, "
                 f"{len(a.get('actions', []))}, {a.get('levels')}")
if any("\n" in x["text"] or len(x["text"]) > 160 for x in a.get("acts", [])):
    fails.append("an ask's text is its first line, at most 160 characters")

mesh = body.get("mesh")
if not mesh or mesh["gateway"] != "!8f491db0" or mesh["packets"] != 12:
    fails.append(f"mesh: the gateway and its packets come from /health: {mesh}")
if not mesh or not any(r["metric"] == "battery_v" for r in mesh["reads"]):
    fails.append("mesh: the device's own 15-minute means ride with it")
```

If the suite has no settings stub named `_Settings`, use the one it already passes to `engine.replay` elsewhere in the file (search `replay(`); reuse that name.

- [ ] **Step 2: Run to verify it fails**

Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues_engine.py`
Expected: `FAIL stations: 14 with coordinates in the fixture, got 0` (and the others).

- [ ] **Step 3: Implement in `engine.py`**

Add near the top of `engine.py`, after the existing constants:

```python
# The metrics a station may show on the dashboard, with the unit, the places and the issue each belongs to. A
# 15-minute mean is the coarsest thing a snapshot carries and the finest a page may show per station.
METRICS = {
    "pm25": {"unit": "µg/m³", "dp": 1, "issue": "air", "label": "PM2.5"},
    "pm10": {"unit": "µg/m³", "dp": 1, "issue": "air", "label": "PM10"},
    "pm1": {"unit": "µg/m³", "dp": 1, "issue": "air", "label": "PM1"},
    "aqi": {"unit": "AQI", "dp": 0, "issue": "air", "label": "AQI"},
    "temp": {"unit": "°C", "dp": 1, "issue": "heat", "label": "temperature"},
    "humidity": {"unit": "%", "dp": 0, "issue": "heat", "label": "humidity"},
    "pressure": {"unit": "hPa", "dp": 0, "issue": None, "label": "pressure"},
    "noise": {"unit": "dB", "dp": 0, "issue": None, "label": "noise"},
    "light": {"unit": "lux", "dp": 0, "issue": None, "label": "light"},
    "gas_resistance": {"unit": "kΩ", "dp": 0, "issue": None, "label": "gas resistance"},
    "battery_v": {"unit": "V", "dp": 2, "issue": None, "label": "battery"},
}


def _source_of(sensor_id: str, name: str | None) -> dict:
    """Where a station's data comes from, read off its id the way app/sources.py assigns them."""
    if sensor_id.startswith("sc-"):
        return {"source": "smartcitizen", "url": f"https://smartcitizen.me/kits/{sensor_id[3:]}",
                "attribution": "Smart Citizen, smartcitizen.me"}
    if sensor_id.startswith("bad-"):
        return {"source": "baliairdispatch", "url": "https://baliairdispatch.com",
                "attribution": "Bali Air Dispatch, baliairdispatch.com"}
    if sensor_id.startswith("msh-"):
        return {"source": "meshtastic", "url": None, "attribution": None}
    return {"source": "unknown", "url": None, "attribution": None}


def _stations(stats: list[dict], hourly: list[dict], lat: float, lon: float) -> list[dict]:
    """Every station with a coordinate, its own 15-minute means for the metrics the page may show, and the hourly
    series the node has for it. Nothing here is averaged across stations: the street stays a fenced median in the
    stack, and this is the thing the median hides, published beside it by decision of 15 September 2026."""
    import h3  # noqa: PLC0415 — only this path needs it, and geometry.py already requires it
    by: dict[str, dict] = {}
    for r in stats:
        if r.get("lat") is None or r.get("lon") is None:
            continue
        s = by.setdefault(r["sensor_id"], {
            "sensor_id": r["sensor_id"], "name": r.get("name"), "lat": r["lat"], "lon": r["lon"],
            "local": bool(r.get("local")), "indoor": bool(r.get("indoor")), "kind": r.get("kind") or "sensor",
            **_source_of(r["sensor_id"], r.get("name")),
            "km": round(h3.great_circle_distance((lat, lon), (r["lat"], r["lon"]), unit="km"), 1),
            "read": {}, "series": {}})
        m = METRICS.get(r.get("metric"))
        if m and r.get("mean_15m") is not None:
            s["read"][r["metric"]] = {"value": round(float(r["mean_15m"]), 2), "unit": m["unit"], "dp": m["dp"],
                                      "silent_minutes": None if r.get("silent_minutes") is None else round(r["silent_minutes"])}
    for h in hourly or []:
        s = by.get(h.get("sensor_id"))
        if s is None:
            continue
        s["series"].setdefault(h["metric"], []).append(
            {"t": h["bucket"] if isinstance(h["bucket"], str) else h["bucket"].isoformat(),
             "mean": h["mean"], "min": h["min"], "max": h["max"], "n": h["n"]})
    for s in by.values():
        for k in s["series"]:
            s["series"][k].sort(key=lambda x: x["t"])
    return sorted(by.values(), key=lambda s: s["km"])


def _asks_ledger(alerts: list[dict], actions: list[dict]) -> dict:
    """The act stage's ledger: every alert that asked a person to do something, first line only, and every answer."""
    def first(t):
        return str(t or "").split("\n")[0][:160]
    return {
        "acts": [{"id": a["id"], "ts": a["ts"] if isinstance(a["ts"], str) else a["ts"].isoformat(),
                  "rule_id": a["rule_id"], "sensor_id": a.get("sensor_id"), "text": first(a.get("text"))}
                 for a in alerts if a.get("level") == "act"],
        "actions": [{"alert_id": x["alert_id"], "stage": x.get("stage"), "actor": x.get("actor"),
                     "ts": x["ts"] if isinstance(x["ts"], str) else x["ts"].isoformat()} for x in actions],
        "levels": {lvl: sum(1 for a in alerts if a.get("level") == lvl) for lvl in ("act", "warn", "info")},
    }


def _mesh(health: dict | None, stats: list[dict]) -> dict | None:
    """The LoRa mesh in this house: the gateway /health knows, the device the stats know, its own means."""
    m = (health or {}).get("mesh")
    if not m:
        return None
    dev = next((r for r in stats if str(r.get("sensor_id", "")).startswith("msh-")), None)
    reads = [{"metric": r["metric"], "mean_15m": round(float(r["mean_15m"]), 2),
              "silent_minutes": None if r.get("silent_minutes") is None else round(r["silent_minutes"])}
             for r in stats if str(r.get("sensor_id", "")).startswith("msh-") and r.get("mean_15m") is not None]
    return {**m, "device": None if dev is None else {"sensor_id": dev["sensor_id"], "name": dev.get("name"),
                                                     "indoor": bool(dev.get("indoor"))}, "reads": reads}
```

In `_read(cur)` (the function returning the `stats`/`obs`/… dict at ~line 565), add three rows so both the live cursor and `Replay` answer them — `Replay.execute` maps a query's table name to the snapshot's key, so name the tables plainly:

```python
        "hourly": _rows(cur, "SELECT bucket, sensor_id, metric, mean, min, max, n FROM readings_1h ORDER BY bucket"),
        "health": _one(cur, "SELECT * FROM health"),
        "presence": _rows(cur, "SELECT cell, res, km FROM presence"),
```

Read `Replay` (search `class Replay`) and make it answer `readings_1h` from `snapshot["readings_1h"]`, `health` from `snapshot["health"]` (one row) and `presence` from `snapshot.get("presence", [])` (the fixture has none; the peer's km comes from the design snapshot and Task 4 handles the fallback). If `_one` does not exist, add `def _one(cur, sql): rows = _rows(cur, sql); return rows[0] if rows else None`. If the live database has no `presence` view or `readings_1h` table under those names, find the real ones (`grep -n "CREATE.*VIEW\|CREATE TABLE" app/*.py | grep -i "presence\|readings_1h\|hourly"`) and use them; the fixture key names stay.

In `compute()`'s return dict add, after `"issues": out,`:

```python
            # what the modular dashboard reads beside the issues — 15 September 2026's decisions
            "stations": _stations(data["stats"], data.get("hourly"), lat, lon),
            "metrics": METRICS,
            "asks": _asks_ledger(data["alerts"], data["actions"]),
            "mesh": _mesh(data.get("health"), data["stats"]),
```

where `lat, lon` are the node's coordinates: `float(settings.get("NODE_LAT", 0) or 0)`, `float(settings.get("NODE_LON", 0) or 0)` for live; for a replay, `Replay` must expose the snapshot's `health.lat/lon` — add to `compute()` right after `data = _read(cur)`:

```python
    health = data.get("health") or {}
    lat = float(health.get("lat") if health.get("lat") is not None else (settings.get("NODE_LAT", 0) or 0))
    lon = float(health.get("lon") if health.get("lon") is not None else (settings.get("NODE_LON", 0) or 0))
```

Check the names `data["alerts"]` / `data["actions"]` against what `_read` actually calls them (`grep -n '"alerts"\|"actions"' app/issues/engine.py`) and use those.

- [ ] **Step 4: Run the test**

Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues_engine.py`
Expected: `ok` (all earlier assertions still pass; the new block passes).

- [ ] **Step 5: Gates and commit**

Run: `make lint && make test`. `tools/check_docs.py` may ask that a metric named in code be declared — it scans adapters, not the engine; if it complains about `METRICS`, read its message and follow it.

```bash
git add app/issues/engine.py tests/test_issues_engine.py
git commit -m "$(cat <<'EOF'
issues: publish each station, the declared metrics, the asks ledger and the mesh

Tomas decided on 15 September that the dashboard shows one station's own
15-minute mean beside the street's fenced median rather than instead of it.
So /issues now carries every station with a coordinate - where its data comes
from and the link to it, its own means for the metrics the page may show, and
the hourly series the node has for it, which in the fixture is two of fourteen.

Also the declared metrics with unit and places, the act stage's ledger - every
alert that asked a person for something, first line only, and every answer -
and the LoRa mesh in the house. A fixture replays through the same code.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `/issues` publishes `geometry`

**Files:**
- Modify: `app/issues/engine.py` (`compute()` return dict)
- Modify: `tests/test_issues_engine.py`

**Interfaces:**
- Consumes: Task 1–2's `geometry.plates / grain_table / publication / ladder / claims / radio`, Task 3's `stations`.
- Produces: `geometry: {publication, ladder, nav, grain_table, claims, radio, settings: {LOCAL_RADIUS_M, BAD_RADIUS_KM, EARTH_RADIUS_M, PLACE_RADIUS_M, RETICULUM_PRESENCE_RES, PRESENCE_RES_FLOOR}, source: "h3 <version>, computed by this node"}` — the same names the prototype's `h3.js` used, so the page's kits port unchanged.

- [ ] **Step 1: Extend the test**

Append before `sys.exit` in `tests/test_issues_engine.py`:

```python
g = body.get("geometry")
if not g:
    fails.append("geometry is on the body")
else:
    if g["nav"]["chain"][8] != "8895a4c86bfffff" or g["nav"]["cell_count"] != 209:
        fails.append(f"geometry.nav: node #1's res-8 cell and 209 published cells; got {g['nav']['chain'].get(8)}, {g['nav']['cell_count']}")
    if [c["key"] for c in g["claims"]][0] != "coast":
        fails.append("geometry.claims are widest first")
    if g["radio"]["res"] != 3:
        fails.append("geometry.radio announces at RETICULUM_PRESENCE_RES, 3 under the fixture's settings")
    if g["publication"]["res"] != 10 or g["settings"]["PRESENCE_RES_FLOOR"] != 6:
        fails.append(f"geometry carries the two lines: {g['publication']} {g['settings']}")
    own_cell = g["nav"]["cells"][g["nav"]["chain"][8]]
    if [body["stations"][i]["sensor_id"] for i in own_cell["sensors"]] != ["sc-19849", "sc-19880", "sc-19897"]:
        fails.append("the plate's sensor indices index into the published stations")
```

- [ ] **Step 2: Run to verify it fails**

Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues_engine.py` → `FAIL geometry is on the body`.

- [ ] **Step 3: Implement**

In `engine.py` import the module at the top (`from . import geometry`) and add to `compute()`'s return dict after `"mesh": …,`:

```python
            "geometry": _geometry(lat, lon, settings, stations, data.get("presence") or [], snapshot_peer=None),
```

where `stations` is the list computed for `"stations"` (compute it once into a local before the dict), and add:

```python
def _geometry(lat: float, lon: float, settings, stations: list[dict], presence: list[dict], snapshot_peer) -> dict:
    """The H3 shapes the dashboard navigates by, computed here so the page never has to. The plates alone are 3 kB per
    resolution; the whole object is published because the page turns a dial and asking per stop would be eleven
    round trips for one drawing."""
    import h3  # noqa: PLC0415
    from . import geometry as G  # noqa: PLC0415
    floor = G.FLOOR_RES
    pub = G.publication()
    peers = [{"cell": p.get("cell"), "res": p.get("res"), "km": p.get("km")} for p in presence]
    return {
        "publication": pub,
        "ladder": G.ladder(lat, lon),
        "nav": G.plates(lat, lon, stations),
        "grain_table": G.grain_table(lat, lon, stations, floor_res=floor, publication_res=pub["res"]),
        "claims": G.claims(lat, lon, settings),
        "radio": G.radio(lat, lon, settings, peers),
        "settings": {k: settings.num(k, d) for k, d in (("LOCAL_RADIUS_M", 500), ("BAD_RADIUS_KM", 15),
                                                         ("EARTH_RADIUS_M", 5000), ("PLACE_RADIUS_M", 1000),
                                                         ("RETICULUM_PRESENCE_RES", 3))} | {"PRESENCE_RES_FLOOR": floor},
        "source": f"h3 {h3.__version__}, computed by this node",
    }
```

`settings.num` is `app/settings.py:201`; if the suite's settings stub lacks `num`, add it to the stub (`def num(k, d): return int(...)`) — the stub is the test's, not production's.

- [ ] **Step 4: Run the test, then time the endpoint**

Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues_engine.py` → `ok`.
Then: `PYTHONPATH=app python3 -c "import time,json;from issues import engine as E, load as L; import sys; sys.path.insert(0,'tests'); snap=json.load(open('app/issues/fixtures/node1-2026-09-06.json')); t=time.time(); b=E.replay(snap, __import__('test_issues_engine')._Settings(), L()); print(round(time.time()-t,2),'s', round(len(json.dumps(b))/1024),'kB')"`
Expected: under 3 s and under 400 kB. If the claims' `polygon_to_cells` at res 12 dominates, memoise `claims()` on `(round(lat,6), round(lon,6), tuple of the five settings)` with `functools.lru_cache(maxsize=4)` — the node's coordinates do not change between requests.

- [ ] **Step 5: Gates and commit**

```bash
make lint && make test
git add app/issues/engine.py tests/test_issues_engine.py
git commit -m "$(cat <<'EOF'
issues: publish the geometry the dial turns on

The plates, the grain table, the publication grain, the six footprints and
the radio, computed by the node from its own coordinates and settings and
published under the names the Phase 1 kits already read, so the page ports
without a rename. A fixture replays through the same functions.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `MAP_TILES` — live tiles are a setting, off by default

**Files:**
- Modify: `app/settings.py:115` (`PUBLIC`), and the validation table below it (search `# Values a key refuses`)
- Modify: `tests/test_settings.py`

**Interfaces:**
- Produces: setting `MAP_TILES` ∈ `{"off", "on"}`, default `off`, public (readable at `SHARE_LEVEL=open`, on `/settings`), so the page can read it and Set up can write it through the existing `/settings` routes.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_settings.py` in the suite's own style (it uses `fails.append`; read its header to match the runner):

```python
# --- MAP_TILES: live tiles leave the house, so they are off until a keeper says otherwise --------------------
if "MAP_TILES" not in S.PUBLIC:
    fails.append("MAP_TILES is a public setting, so the page can read it")
try:
    S.validate("MAP_TILES", "sometimes")
    fails.append("MAP_TILES accepted 'sometimes'; it is off or on")
except (ValueError, KeyError):
    pass
if S.get("MAP_TILES", "off") != "off":
    fails.append("MAP_TILES defaults to off")
```

Use the suite's existing import name for `app/settings.py` (`grep -n "^import settings\|as S" tests/test_settings.py`) and its validation helper's real name (`grep -n "^def " app/settings.py`); if validation is a dict of allowed values rather than a function, assert on the dict instead.

- [ ] **Step 2: Run to verify it fails** — `PYTHONPATH=app python3 tests/test_settings.py` → `FAIL MAP_TILES is a public setting`.

- [ ] **Step 3: Implement** — add `"MAP_TILES"` to `PUBLIC`, and to the refusal table add `"MAP_TILES": {"off", "on"}` in whatever form that table takes (read the two entries above it and copy their shape). Add to `.env.example`, above the key as the file's rule requires:

```
# dashboard: live map tiles (satellite and street) under the cells. Each tile request tells a tile server which square of
# the planet this house is looking at, so this is off until a keeper turns it on in Set up. off | on
MAP_TILES=off
```

- [ ] **Step 4: Run the test** → `ok`.

- [ ] **Step 5: Gates and commit**

```bash
make lint && make test
git add app/settings.py tests/test_settings.py .env.example
git commit -m "$(cat <<'EOF'
settings: MAP_TILES, off until a keeper turns it on

Tomas asked for a live map with a satellite view and was told what it costs: a
page that fetches tiles tells the tile server which square of the planet a
household is looking at, every time anybody opens it. His decision on 15
September: off by default, a switch in Set up. This is the switch.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: the three files — shell, kits, contract, and the core sections

**Files:**
- Rewrite: `app/static/index.html`, `app/static/dashboard.js`, `app/static/dashboard.css`
- Modify: `tools/check_ui.py` only where its field list must learn the new columns (`r.<field>` rule at ~line 86)
- Modify: `tests/test_dashboard.py`, `tests/test_check_ui.py` (whatever asserts the old page's structure)

**Interfaces:**
- Consumes: `/issues` (Tasks 3–4), `/health`, `/settings` (public keys incl. `MAP_TILES`), `/place/geojson`.
- Produces: `window.PAI` (the contract from `kit-page.js`, unchanged), `window.K/KH/KN/KMAP`, and `boot()`:

```js
/* The page's one fetch sequence. /issues carries everything the sections read; /health names the node;
 * /settings says what the keeper allowed; /place/geojson is the plan. A failure leaves the global null and
 * the section whose `needs` names it prints one honest line (kit-page.js) — never a blank, never a retry loop. */
async function boot() {
  const q = new URLSearchParams(location.search);
  const fixture = q.get('fixture');
  const [issues, health, settings] = await Promise.all([
    api(fixture ? `/issues/fixtures/${encodeURIComponent(fixture)}` : '/issues'),
    api('/health'), api('/settings').catch(() => ({})),
  ]);
  window.SNAP = { issues, health, base: { captured_utc: issues.as_of }, rho: issues.rho || health.rho,
    funnel: issues.funnel, peer: issues.peer || null };
  window.H3 = { ...issues.geometry, sensors: issues.stations, metrics: issues.metrics, asks: issues.asks,
    radio: { ...issues.geometry.radio, mesh: issues.mesh, mesh_sensor: issues.mesh && issues.mesh.device,
      mesh_reads: issues.mesh ? issues.mesh.reads : [] }, node: { lat: health.lat, lon: health.lon, name: health.node } };
  window.SETTINGS = settings;
  window.PLAN = await plan(health).catch(() => null);
}
```

and `plan(health)` — `/place/geojson` projected in the browser with the node's own formula (`NODE_DASHBOARD_PLAN_SPEC.md` rule 1; the same eight lines `make-plan.mjs` runs), producing the `PLAN` shape `kit-map.js` reads: `{buildings: [[x,y,…]], roads: [[class, x,y,…]], green, sat: [[conf, x,y,…]], poi, bbox_m, span_m, counts}`.

- [ ] **Step 1: Write the failing test**

In `tests/test_dashboard.py` (read its header for the runner pattern) add:

```python
# --- the modular page: three files, one contract, ten sections --------------------------------------------------
h = open("app/static/index.html").read()
js = open("app/static/dashboard.js").read()
css = open("app/static/dashboard.css").read()
for must in ('src="static/dashboard.js"', 'href="static/dashboard.css"', 'id="page"'):
    if must not in h:
        fails.append(f"index.html lacks {must}")
if "window.PAI = { STAGES, register, render, wall, sections, problems, has }" not in js:
    fails.append("dashboard.js carries the page contract (kit-page.js) verbatim")
for sec in ("'ground'", "'sensors'", "'satellite'", "'reticulum'", "'meshtastic'", "'hardware'",
            "'claims'", "'grain'", "'asks'", "'measure'"):
    if f"id: {sec}" not in js:
        fails.append(f"dashboard.js registers the section {sec}")
if "async function boot()" not in js or "/issues/fixtures/" not in js:
    fails.append("dashboard.js boots from /issues and can replay a fixture with ?fixture=")
if "<style" in js or "createElement('style')" in js:
    fails.append("no JS-injected styles in production: every module's CSS is in dashboard.css")
if "tile.openstreetmap.org" in js and "MAP_TILES" not in js:
    fails.append("live tiles are gated on the MAP_TILES setting")
```

- [ ] **Step 2: Run to verify it fails** — `python3 tests/test_dashboard.py` → the five `lacks/registers` failures.

- [ ] **Step 3: Assemble the three files**

This is a hand assembly, done once, committed as the artifact; the prototype stays the design reference. From `planetai-design/prototypes/dashboard-directions/`:

`app/static/dashboard.css` = concatenation, each part under a banner comment `/* ==== <source file> ==== */`, of: `kit.css`; the `<style>` block of `h/index.html` (everything between `<style>` and `</style>`, minus the direction comment); the `CSS` template literal of `h/wall.js`; the `css.textContent` literal of `h/mods/ground.js`; the `<style id="css-sensors">` content of `h/mods/sensors.js`. Replace every `../static/` URL with `static/` (check_ui rule 9: `url()` inside `app/static/*.css` is relative to `/static/` already, so a bare name — read the rule's comment at `tools/check_ui.py:250` and follow it). The `${DWELL_MS}` in the wall's keyframe becomes `8000ms`.

`app/static/index.html` = the prototype shell's `<head>` (title `PLANETAI · <node>`, the two `<link>`s to `static/tokens.css`, `static/planetai-theme.css`, `static/dashboard.css`), `<div id="page"></div>`, one `<script src="static/dashboard.js"></script>`. No inline `<style>`, no inline script.

`app/static/dashboard.js` = concatenation under banners of: `kit.js` with its `const S = window.SNAP; …` top-level reads moved inside a `function init()`; `kit-h3.js`; `kit-nav.js`; `kit-map.js`; `kit-page.js` verbatim; the ten `h/mods/*.js` with each `document.createElement('style')` block deleted; `h/wall.js` with its `style()` function deleted; then the shell's script from `h/index.html` wrapped as `function main()`; then `boot()` and `plan()` from this task's Interfaces; and last:

```js
boot().then(() => { init(); main(); }).catch(e => {
  document.getElementById('page').innerHTML = `<div class="wrap"><p class="note">This node did not answer: `
    + `${String(e.message || e).replace(/[<>&]/g, '')}. A failure is not an answer, so nothing is cached; reload to try again.</p></div>`;
});
```

Three substitutions across the concatenation, then no others: every `'../static/'` → `'static/'`; `H.settings.PRESENCE_RES_FLOOR` and `H.settings.RETICULUM_PRESENCE_RES` read from `H.settings` as published by Task 4 (same names — verify with grep, expect no edits); the ground module's default `autoBase(res)` becomes

```js
const autoBase = (res, settings) => ((settings || {}).MAP_TILES === 'on' && res < PLAN_FROM) ? 'sat' : 'plan';
```

with `window.SETTINGS` passed at the two call sites — the plan is the default everywhere unless the keeper turned tiles on, and then only coarser than 9 (Tomas's rule).

The section split (decision 3): in the shell's `main()`, the Now view renders `PAI.render(ctx, lead(), { only: ['ground','sensors','claims','grain','asks','measure'] })` and the Network view renders `PAI.render(ctx, '', { only: ['satellite','reticulum','meshtastic','hardware'] })` — add the optional third argument to `PAI.render` in the contract:

```js
function render(ctx, lead, opts = {}) {
  const keep = opts.only ? new Set(opts.only) : null;
  const ordered = sections.filter(s => !keep || keep.has(s.id)).slice().sort(…same sort…);
```

(the `only` filter is the whole change; the notes band then lists only the sections on that view). The Set up view renders the sections box from `h/index.html` plus the `MAP_TILES` switch as a real control: a form posting to the existing `/settings` route the current page already uses for `UI_LAYOUT` — copy that request exactly (`grep -n "UI_LAYOUT" app/static/dashboard.js` in the old file before overwriting: keep a copy at `/tmp/dashboard-v0.53.js` for reference). Arrange stays as the old page's `arrangeControls()` moved verbatim.

- [ ] **Step 4: Make `check_ui` and the suites pass**

Run: `python3 tools/check_ui.py`. Expect complaints from three rules and fix each in the page, not the tool: (a) `page reads r.<field>` — the stats-view field list at `tools/check_ui.py:86` must include `mean_15m`, `silent_minutes`, `lat`, `lon`, `local`, `indoor`, `name`, `kind`: add the missing ones to that list (they are columns of the view — confirm with `grep -n "CREATE.*VIEW stats" app/*.py`); (b) `page calls /x, which app/main.py does not define` — every `api('/…')` must be `/issues`, `/issues/fixtures/…`, `/health`, `/settings`, `/place/geojson`, `/settings` POST as the old page did; (c) `text-transform: uppercase` on anything the node's words reach — the `.k` labels are the page's own words; if the rule fires, wrap the node's words in `.said` as the old page does.

Run: `python3 tests/test_dashboard.py` → `ok`; `python3 tests/test_check_ui.py` — it asserts against the old markup; update its expectations to the new file (read each failing assertion; it is describing structure, not design).

- [ ] **Step 5: Render the production page from the fixture and look**

Run from `planetai-design/prototypes/dashboard-directions/`: `PAI_STATIC="$HOME/Documents/Claude/Projects/FAB CITY/planetai-node/app/static" PAI_Q="?fixture=node1-2026-09-06" node ../../../planetai-node/tests/visual/measure.mjs render now_populated_1440 now_populated_390 wall_populated_1920_dark && PAI_STATIC=… PAI_Q=… node …/measure.mjs shots now_populated_1440 now_populated_390 wall_populated_1920_dark && PAI_OUT=… node …/measure.mjs targets` with `PAI_OUT` set to a scratch folder. Expected: T1 five legs at 390 and 1440, T4 0, T5 0, no "did not render" in the JSON's lines. Open the `_fold.jpg`. `measure.mjs` intercepts `/issues` and serves the fixture through the node's own engine only when a node is running; if it cannot, run the node on `pai-clean` (`~/planetai`, per `pai-clean-proving-workflow`) and point `PAI_LIVE=1` at it — never at node #1.

- [ ] **Step 6: Gates and commit**

```bash
make lint && make test
git add app/static/index.html app/static/dashboard.js app/static/dashboard.css tools/check_ui.py tests/test_dashboard.py tests/test_check_ui.py
git commit -m "$(cat <<'EOF'
the dashboard is a shell, a contract and ten sections, in the three files it always was

Direction H, picked by Tomas on 15 September, in production shape: index.html
is the shell, dashboard.js carries the kits, the page contract and the ten
sections a pack registers with it, dashboard.css carries every style. No build
step, no framework, nothing loaded from anywhere but static/. The page boots
from /issues, which now computes everything it draws, and replays a fixture
with ?fixture= the way the old page did.

Now keeps the ground, the stations, the claims, the grain, the asks and the
measure; the satellite, the two radios and the hardware are the Network view.
Live tiles are the plan unless MAP_TILES is on, and then only coarser than 9.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: the wall, and the Set up switch that is real

**Files:**
- Modify: `app/static/dashboard.js` (the wall part, the Set up view), `app/static/dashboard.css`
- Modify: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `window.WALL.render(ctx)/start(ctx)` from Task 6's assembly; `/settings` POST as the old page's `layoutSave()` used it (`grep -n "fetch('/settings'\|api('/settings'" /tmp/dashboard-v0.53.js`).
- Produces: `#hash` view routing as the old page did (`VIEWS = ['now','network','setup','wall']`, `location.hash`) so `/#wall` is the wall; the Set up view's `MAP_TILES` control writes the setting and re-renders.

- [ ] **Step 1: Write the failing test**

```python
if "'wall'" not in js or "prefers-reduced-motion" not in js:
    fails.append("the wall turns by itself and stands still under reduced motion")
if "MAP_TILES" not in js or "'/settings'" not in js:
    fails.append("Set up writes MAP_TILES through /settings")
if "location.hash" not in js:
    fails.append("views are #now #network #setup #wall, as before")
```

- [ ] **Step 2: Run to verify it fails** — `python3 tests/test_dashboard.py`.

- [ ] **Step 3: Implement** — in `main()`, resolve the view from `location.hash` first and `?view=` second (the old page's `viewFromHash()` at `/tmp/dashboard-v0.53.js:2164` — copy it). The Set up view's tiles switch:

```js
function tilesSwitch() {
  const on = (window.SETTINGS || {}).MAP_TILES === 'on';
  return `<div class="ctlstrip" role="group" aria-label="live map tiles">`
    + `<a href="#setup" class="${on ? '' : 'on'}" data-tiles="off">plan only · nothing leaves</a>`
    + `<a href="#setup" class="${on ? 'on' : ''}" data-tiles="on">live tiles coarser than resolution 9</a></div>`
    + `<p class="cap">A tile request tells the tile server which 2.4 km square this house is looking at. `
    + `The plan is this node's own and sends nothing.</p>`;
}
document.addEventListener('click', async e => {
  const a = e.target.closest && e.target.closest('[data-tiles]');
  if (!a) return;
  e.preventDefault();
  await api('/settings', { method: 'POST', body: JSON.stringify({ MAP_TILES: a.dataset.tiles }) });
  window.SETTINGS = await api('/settings');
  main();
});
```

using exactly the request shape the old `layoutSave()` used (method, headers, body key) — if it posted `{key, value}` rather than an object, post that.

- [ ] **Step 4: Run the test and render the wall**

`python3 tests/test_dashboard.py` → `ok`. Render `wall_populated_1920_dark` as in Task 6 step 5 with `PAI_Q="?fixture=node1-2026-09-06#wall"` (if `measure.mjs` drops hashes, use `?view=wall` and keep `?view=` as the second resolver). Expected: `doc.h` 1080; T7 issue line ≥ 9 mm, ρ ≥ 9 mm.

- [ ] **Step 5: Gates and commit**

```bash
make lint && make test
git add app/static/dashboard.js app/static/dashboard.css tests/test_dashboard.py
git commit -m "$(cat <<'EOF'
the wall is the grid, and Set up's tile switch is real

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: the visual gate

**Files:**
- Create: `tests/visual/gate.sh`
- Modify: `tests/visual/measure.mjs` only if `PAI_STATIC` + `?fixture=` cannot serve `/issues` without a node (then add an `issues` interception that runs `python3 -c "…engine.replay…"` once and serves the JSON — ≤ 30 lines, beside the existing `/place/geojson` interception)

**Interfaces:**
- Produces: `bash tests/visual/gate.sh` exits non-zero if the production page, rendered from the fixture, regresses against the prototype's measured values.

- [ ] **Step 1: Write the gate**

```bash
#!/usr/bin/env bash
# The visual gate for the production dashboard: the same script that measured Phase 1, run against app/static
# with the committed fixture, and compared with the numbers the picked direction measured when it was picked.
#
#   bash tests/visual/gate.sh
#
# Not in tests/all: Playwright lives in planetai-design's node_modules, not this repo's. Run before shipping.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
DESIGN="${PAI_DESIGN_REPO:-../planetai-design}"
[ -d "$DESIGN/node_modules/playwright" ] || { echo "  playwright is not in $DESIGN/node_modules; npm install there"; exit 2; }
OUT="${PAI_OUT:-/tmp/pai-gate}"; mkdir -p "$OUT"
export PAI_STATIC="$PWD/app/static" PAI_OUT="$OUT" PAI_DESIGN_REPO="$DESIGN" PAI_Q="?fixture=node1-2026-09-06"
node tests/visual/measure.mjs render now_populated_1440 now_populated_390 >/dev/null
PAI_Q="?fixture=node1-2026-09-06&view=wall" node tests/visual/measure.mjs render wall_populated_1920_dark >/dev/null
node tests/visual/measure.mjs shots now_populated_1440 now_populated_390 wall_populated_1920_dark >/dev/null
node - <<'JS'
const fs = require('fs'), out = process.env.PAI_OUT;
const j = n => JSON.parse(fs.readFileSync(`${out}/${n}.json`, 'utf8'));
const fails = [];
for (const n of ['now_populated_1440', 'now_populated_390']) {
  const d = j(n);
  const orphanNums = d.els.filter(e => e.dnum && !e.dcmp).length;
  const ids = new Set(d.els.map(e => e.id).filter(Boolean));
  const inbound = new Set(d.els.filter(e => e.dref && ids.has(e.dref)).map(e => e.dref));
  const orphanComps = d.els.filter(e => e.dc && !(e.dref && ids.has(e.dref)) && !inbound.has(e.id)).length;
  const broken = (d.lines || []).map(x => typeof x === 'string' ? x : x.text || '').filter(x => /did not render|has nothing here yet/.test(x));
  if (orphanNums) fails.push(`${n}: ${orphanNums} numerals with no comparison`);
  if (orphanComps) fails.push(`${n}: ${orphanComps} components with no link in or out`);
  if (broken.length) fails.push(`${n}: ${broken.join(' | ')}`);
}
const w = j('wall_populated_1920_dark');
if (w.doc.h > 1080) fails.push(`wall is ${w.doc.h} px on a 1,080 px screen`);
for (const f of fails) console.log('FAIL', f);
console.log(fails.length ? `${fails.length} regression(s)` : 'ok');
process.exit(fails.length ? 1 : 0);
JS
```

- [ ] **Step 2: Run it** — `bash tests/visual/gate.sh`. Expected: `ok`. If `measure.mjs` cannot answer `/issues` from `PAI_STATIC` alone, add the interception described in Files (it already intercepts the document and companions from the static tree; `/issues` becomes one more route served from `python3 -c` output written once to `$OUT/issues.json`).

- [ ] **Step 3: Add the T1 leg check** — in the node script above, after `orphanComps`, add `if (!(d.t1 && d.t1.every(Boolean))) fails.push(`${n}: T1 legs ${JSON.stringify(d.t1)}`)` if the JSON carries the T1 array under that name (`grep -n "t1" tests/visual/measure.mjs`); if T1 lives only in `targets`' table, call `node tests/visual/measure.mjs targets` and grep its 390 row for five ✓.

- [ ] **Step 4: Gates and commit**

```bash
chmod +x tests/visual/gate.sh && make lint && make test && bash tests/visual/gate.sh
git add tests/visual/gate.sh tests/visual/measure.mjs
git commit -m "$(cat <<'EOF'
the visual gate: the production page against the numbers it was picked on

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: prove on `pai-clean`, never on node #1

**Files:**
- none in the repo; a note in `docs/archive/handoffs/HANDOFF_dashboard_directions.md` (Task 10)

- [ ] **Step 1: Deploy the branch to the VM** — per `pai-clean-proving-workflow`: the VM's node is at `~/planetai`, the repo is mounted; `git fetch && git checkout dashboard-redesign-2026-09 && planetai restart` inside the VM (the exact commands the memory records). Node #1 is not touched.

- [ ] **Step 2: Measure live** — from the design folder, `PAI_LIVE=1 PAI_STATIC=… node tests/visual/measure.mjs render now_populated_1440` against the VM's port with the token the VM's page needs (localhost inside the VM still needs it). Check the ground row says `0 requests` with `MAP_TILES=off`, that turning it on in Set up shows tiles only at resolutions 2–8, and that the wall steps after eight seconds.

- [ ] **Step 3: Record** — the measured numbers go in Task 10's handoff section. If anything differs from the fixture render, that difference is the finding; do not tune the page against the VM.

---

### Task 10: the pack author's contract, and the handoff

**Files:**
- Modify: `docs/PACKS.md` (new section *A dashboard section*), `docs/archive/handoffs/HANDOFF_dashboard_directions.md` (*Shipped* section), `README.md` if its docs index needs a line (only for new top-level `docs/*.md`, which this plan does not add)

- [ ] **Step 1: Write the contract section in `docs/PACKS.md`**

```markdown
## A dashboard section

A pack can put a section on the dashboard. It registers one object with the page contract and the page renders
it in the stage it belongs to — observe, decide, act, measure — in the order the loop runs, and folds its
explanations at the foot:

    window.PAI.register({
      id: 'meshtastic',        // unique; becomes the band's DOM id
      pack: 'meshtastic',      // your pack's id
      stage: 'observe',        // observe · decide · act · measure
      title: 'The mesh in this house',
      order: 41,               // position within the stage; lower first
      needs: ['H3.radio.mesh'],// what it reads off the page's data; absent → one honest line, never a blank
      controls(ctx) { … },     // optional: a control strip (a toggle, a selector)
      render(ctx) { … },       // the body: captions yes, explanations no
      wall(ctx) { … },         // optional: what it shows on the wall at ctx.RES
      notes(ctx) { … },        // the explanations: [{ id, text }]
    });

What a section may not do: invent a fifth card kind (readout · stack · series · row are the four); colour a state
by hue; print a numeral without `data-num`/`data-cmp`; leave a component with no `data-ref`; explain itself in its
body. `tests/visual/gate.sh` measures all of it.

Today a section lives in `app/static/dashboard.js`, because the node serves three static files and nothing
else; the ten shipped sections are the reference. Serving a pack's own `dashboard.js` needs a route the node does
not have yet, and that is the next phase. Proposing a section back is sending the file with its notes and a
render.
```

- [ ] **Step 2: Handoff** — add a section *Shipped, 15–16 September* to `docs/archive/handoffs/HANDOFF_dashboard_directions.md` with: the branch's commit list for Phase 2; the gate's numbers from Task 8; the VM's numbers from Task 9; the three things deliberately not built (a pack-served `dashboard.js`, the open hardware manager, per-section switches in Set up) and the STOP each would touch.

- [ ] **Step 3: Gates and commit**

```bash
make lint && make test
git add docs/PACKS.md docs/archive/handoffs/HANDOFF_dashboard_directions.md
git commit -m "$(cat <<'EOF'
docs: the section contract for a pack author, and what shipped

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Spec coverage.** Live tiles → Task 5 + Task 6 (`autoBase`, off by default, Set up switch in Task 7). Modular contract → Task 6 (`kit-page.js` verbatim, `only` filter) + Task 10 (pack author's doc). The loop → Task 6 (stages). Notes at the foot → Task 6 (contract unchanged). Wall H3, interactive, animated → Task 7. Stations with graphics, selector, source links → Task 3 (`stations`, `metrics`) + Task 6 (sensors module). Hardware hook and propose-back → Task 6 (hardware module, sections box). Per-station decision → Task 3. h3 in image → already declared, no task. Sections split → Task 6. Gates → Task 8. Never node #1 → Task 9. Not covered, deliberately: a pack-served dashboard file (new route, STOP), per-section switches (later), the open hardware manager (a pack that does not exist).

**Placeholder scan.** Task 3 and Task 5 name real functions in `app/settings.py` and `engine.py` by their known line numbers and tell the implementer to `grep` where a name might differ — that is verification, not a placeholder. Task 6's assembly is a procedure with exact source files and exact substitutions; the code that is new (`boot`, `plan`, `autoBase`, the `only` filter, `tilesSwitch`) is written out.

**Type consistency.** `stations` is the list published on `/issues` and the list `geometry.plates(lat, lon, stations)` indexes into; the page maps it to `H3.sensors` in `boot()`. `H3.metrics`, `H3.asks`, `H3.radio.mesh/mesh_sensor/mesh_reads` are built in `boot()` from `issues.metrics / issues.asks / issues.mesh` to the names the modules already read. `settings.num(key, default)` is used in Tasks 2, 4 and 5 and exists at `app/settings.py:201`.
