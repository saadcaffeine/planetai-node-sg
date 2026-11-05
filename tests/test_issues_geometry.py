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
# kilometre-cells.json's top-level keys are node/cells/res9_covering_kilometre/boundaries/counts, not
# res7/res8/res9 directly (task-1-brief.md's Step 1 draft assumed the latter). The node's res 7/8/9
# cell ids live one level down, under "cells" — that is what is checked here. The h3geo.org table
# assertions above are the ones that pin the arithmetic either way.
KC = ROOT.parent / "planetai-design/assets/h3/kilometre-cells.json"
if KC.exists():
    kc = json.loads(KC.read_text())
    want = {7: (kc.get("cells") or {}).get("res7"), 8: (kc.get("cells") or {}).get("res8"),
            9: (kc.get("cells") or {}).get("res9")}
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

RING = {"pack": "bali-air-dispatch", "radius": "BAD_RADIUS_KM"}   # what packs.stations() gives with the pack on
# The pack claims are the packs' own `footprint:` (pack.yaml) since 23 Oct 2026, read while the pack is on.
import packs as _packs  # noqa: E402
_fp = {f["pack"]: f["key"] for f in _packs.footprints()}
if _fp != {"coast": "coast", "earth": "region", "place": "place"}:
    fails.append(f"coast, earth and place declare the three pack footprints; got {_fp}")
if [c["key"] for c in G.claims(LAT, LON, S, footprints=[])] != ["yard", "room"]:
    fails.append("with no pack footprint on, only the core's own two claims are drawn")
C = {c["key"]: c for c in G.claims(LAT, LON, S, RING)}
if [c["key"] for c in G.claims(LAT, LON, S)] != ["coast", "region", "place", "yard", "room"]:
    fails.append("no stations pack on, no ring claimed")
if list(c["key"] for c in G.claims(LAT, LON, S, RING)) != ["coast", "ring", "region", "place", "yard", "room"]:
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
# The dashboard draws a claim as the cells that cover it, and the browser has no h3 to turn an id into a ring.
# So every claim carries its own boundaries, in the same shape and to the same six decimals plates() uses:
# one row per compacted cell, its id first, then lat, lng, lat, lng round the ring.
for _k, _c in C.items():
    if len(_c["cells_ll"]) != len(_c["cells"]):
        fails.append(f"{_k}: one boundary per compacted cell; got {len(_c['cells_ll'])} for {len(_c['cells'])}")
    elif _c["cells"] and ([r[0] for r in _c["cells_ll"]] != _c["cells"]
                          or len(_c["cells_ll"][0]) not in (13, 15)     # id + 6 or 7 vertices as lat, lng
                          or abs(_c["cells_ll"][0][1]) > 90 or abs(_c["cells_ll"][0][2]) > 180):
        fails.append(f"{_k}: cells_ll rows are [id, lat, lng, ...] in the order cells declares; got "
                     f"{_c['cells_ll'][0][:5]}")

# --- the radio: a peer is a cell and a distance, never a point -------------------------------------------------
R = G.radio(LAT, LON, S, peers=[{"cell": None, "res": 3, "km": 61}])
if R["res"] != 3 or R["mine"] != L[3]["id"]:
    fails.append("the node announces its res-3 cell")
if not (1 <= len(R["candidates"]) <= 6) or R["mine"] in R["candidates"]:
    fails.append(f"61 km from a res-3 cell is one of its neighbours, not itself: {R['candidates']}")
R2 = G.radio(LAT, LON, S, peers=[{"cell": R["candidates"][0], "res": 3, "km": 61}])
if R2["candidates"] != [R["candidates"][0]]:
    fails.append("a peer whose cell is known is drawn in that cell and no other")

# --- a footprint of zero is a source declaring no ground, not a crash --------------------------------------------
class S0:  # a copy of S with BAD_RADIUS_KM set to 0 — S's own methods close over S._v by name, not by class, so
           # this cannot be a subclass of S with an overridden _v
    _v = dict(S._v, BAD_RADIUS_KM=0)
    @staticmethod
    def num(k, d):
        return S0._v.get(k, d)
    @staticmethod
    def get(k, d=""):
        return str(S0._v.get(k, d))

try:
    C0 = {c["key"]: c for c in G.claims(LAT, LON, S0, RING)}
except Exception as e:  # noqa: BLE001 — the assertion is that nothing raises
    fails.append(f"a zero radius must not raise: {e!r}")
else:
    z = C0["ring"]
    if z["cells"] != [] or z["area_km2"] != 0 or z["native"] is not None or z["cells_at"][8] != 0:
        fails.append(f"BAD_RADIUS_KM=0 should draw nothing for ring; got {z}")
    for key in ("coast", "region", "place", "yard", "room"):
        if C0[key] != C[key]:
            fails.append(f"a zero radius on ring must not change the {key} claim")

# --- a row that names one cell reports THAT cell's edge ------------------------------------------------------
#
# `h3.average_hexagon_edge_length(res)` is the average over the globe and is about 7% above what
# node #1's own cells measure at every resolution. The grain table, the plates and the radio row all
# published `cell_area(<a specific cell>)` beside that table value: at resolution 8, this cell's
# 639,778 m² next to a 531 m edge, when the cell measures 497 and an ideal hexagon of that area has
# one of 496. Two different cells on one row, and the dashboard's grain rail was about to draw the
# table's number beside the right area.
#
# Checked as this file checks everything else — against numbers that are known — rather than by a
# geometric identity. H3 has twelve pentagons and the cells around them are distorted enough that
# "edge implied by area" is out by a quarter on some plate cells, so that identity is not true of
# every row and a test asserting it would be asserting something false.
_g8 = [r for r in G.grain_table(LAT, LON, STATIONS, floor_res=6, publication_res=10) if r["res"] == 8][0]
if _g8["edge_m"] != 497:
    fails.append(f"node #1's own cell at resolution 8 measures 497 m to an edge; grain_table says "
                 f"{_g8['edge_m']}")
if _g8["edge_m"] == round(G.h3.average_hexagon_edge_length(8, unit="m")):
    fails.append("grain_table is quoting h3's global average edge again (531 m at res 8) instead of "
                 "measuring the cell whose area it publishes beside it")

import ground as _ground                     # noqa: E402
_caption = _ground.facts(LAT, LON)
if _caption["edge_m"] != _g8["edge_m"]:
    fails.append(f"/health's caption says {_caption['edge_m']} m to an edge and the grain table says "
                 f"{_g8['edge_m']} m, for the one cell this node stands in")

# The radio row and the plate centre name the same cell as the grain table's res-8 home, so all
# three have to agree about it. This is the check that would have caught the original divergence.
_pc = G.plates(LAT, LON, STATIONS)
_centre = (_pc.get("cells") or {}).get(_g8["home"])
if _centre and _centre["edge_m"] != _g8["edge_m"]:
    fails.append(f"the plate's centre cell and the grain table disagree about one cell's edge: "
                 f"{_centre['edge_m']} m and {_g8['edge_m']} m")

# The coverings are cached (geometry._covering, 24 Oct 2026): a second call is the same answer, a claim the caller
# changes does not change the next one. A changed radius is a new key: S0's zero-radius ring above is that case.
_a = G.claims(LAT, LON, S, RING)
_b = __import__("copy").deepcopy(G.claims(LAT, LON, S, RING))       # a snapshot, not the same lists
if _a != _b:
    fails.append("two calls to claims() with the same settings gave different coverings")
_a[0]["cells"].append("not-a-cell"); _a[0]["drawn"]["cells"] = -1
if G.claims(LAT, LON, S, RING) != _b:
    fails.append("changing one claims() result changed the next: the cached covering is shared, not copied")
if G._covering.cache_info().hits == 0:
    fails.append("claims() never hit its covering cache: every request pays for h3 again")

for f in fails:
    print("FAIL", f)
print("ok" if not fails else f"{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
