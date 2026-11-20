"""The energy pack's grid lookup, OSM parser, mix and daily series, offline: no network, no database.

Run: PYTHONPATH=/tmp/stub:app python3 tests/test_energy.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "packs/energy/tests/fixtures"
sys.path.insert(0, str(ROOT / "packs/energy"))

import grids as G  # noqa: E402
import mix as M  # noqa: E402
import osm as O  # noqa: E402
import ree as R  # noqa: E402

fails: list[str] = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


# ---------------------------------------------------------------- grids and OSM
g = G.load()
# Node #1's point is the centre of its public H3 cell 8895a4c843fffff, never the house.
check(G.grid_for(-8.8161, 115.1635, g)["id"] == "bali", "node #1's cell is on the Bali grid")
check(G.grid_for(39.9493, 4.0500, g)["id"] == "balearic", "mahon1 is on the Balearic grid")
check(G.grid_for(41.39, 2.17, g) is None, "Barcelona is on no grid in grids.yml: no figure, no fallback")
check(G.ring_for(39.9493, 4.0500, G.grid_for(39.9493, 4.0500, g)) == "city", "mahon1 sits in Menorca's city ring")
check(G.ring_for(-8.1975, 114.8536, G.grid_for(-8.8161, 115.1635, g)) == "region",
      "Celukan Bawang sits in Bali's region ring")
check("out tags center;" in O.QUERY.format(s=-8.9, w=114.4, n=-8.0, e=115.7), "QUERY formats s, w, n, e")
check(O.mw("380 MW") == 380.0 and O.mw("100 kW") == 0.1 and O.mw("1,5 MW") == 1.5, "MW units")
check(O.mw("yes") is None and O.mw(None) is None, "no capacity is None, never 0")
bali = O.parse(json.load(open(FIX / "overpass-bali-2026-11-08.json")))
plants = [s for s in bali if s["kind"] == "plant"]
check(len(plants) == 19, f"19 plants in Bali on 8 Nov, got {len(plants)}")
check(any(s["kind"] == "cable_head" and "Gilimanuk" in s["name"] for s in bali), "the Java cable head is a cable_head")
n = O.near(bali, -8.816082625619444, 115.16354382246635)
check(n[0]["name"] == "GIS Pecatu" and abs(n[0]["km"] - 2.4) < 0.1, "nearest is GIS Pecatu, 2.4 km")
big = next(s for s in n if s["kind"] == "plant" and (s["mw"] or 0) >= 100)
check("Pesanggaran" in big["name"] and abs(big["km"] - 12.0) < 0.2, "nearest large plant is Pesanggaran, 12 km")
men = O.parse(json.load(open(FIX / "overpass-menorca-2026-11-08.json")))
check(any(s["fuel"] == "oil" and s["mw"] == 270.0 and s["fossil"] for s in men), "Maó's oil plant, 270 MW, fossil")
check(sum(1 for s in men if s["kind"] == "plant" and s["fuel"] == "solar" and s["mw"] is None and s["fossil"] is False) == 4,
      "Menorca's four solar plants with output=yes stay listed with mw=None")
unk = O.parse({"elements": [{"type": "node", "lat": 0.0, "lon": 0.0,
                             "tags": {"power": "plant", "plant:source": "nuclear"}}]})
gen = O.parse({"elements": [{"type": "node", "lat": 0.0, "lon": 0.0,
                             "tags": {"power": "generator", "generator:source": "wind",
                                      "generator:output:electricity": "2 MW"}}]})
check(gen[0]["kind"] == "generator", "a generator is listed apart, so a plant's MW is never counted twice")
check(unk[0]["fuel"] is None and unk[0]["fossil"] is None, "unlisted fuel has fossil=None")

# ---------------------------------------------------------------- Bali's range (mix.py)
g_syn = {
    "polygon": [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]],
    "rings": {"city": [[0, 0], [0, 5], [5, 5], [5, 0], [0, 0]]},
    "capacity_factors": {"coal": 0.6, "solar": 0.2},
    "links": [{"rated_mw": 100, "fossil_share": 0.8, "ring": "beyond"}],
    "demand_mw": 400,
}
src = [
    {"kind": "plant", "fuel": "coal", "fossil": True, "mw": 300, "lat": 2, "lon": 2},
    {"kind": "plant", "fuel": "solar", "fossil": False, "mw": 100, "lat": 7, "lon": 7},
    {"kind": "plant", "fuel": "coal", "fossil": True, "mw": None, "lat": 3, "lon": 3},
    {"kind": "generator", "fuel": "solar", "fossil": False, "mw": 500, "lat": 2, "lon": 2},
]
e = M.estimate(src, g_syn)
check(abs(e["island"] - 180 / 200) < 1e-9, "island share is 180 of 200 MW-weighted (generators and null MW excluded)")
check(abs(e["import_max"] - 0.25) < 1e-9, "100 MW cable against 400 MW demand")
check(abs(e["low"] - 0.875) < 1e-9 and abs(e["high"] - 0.9) < 1e-9, "range 87.5–90%")
check(abs(e["mid"] - 0.8875) < 1e-9 and e["method"] == "capacity-factors" and e["kind"] == "estimated",
      "mid, method and kind")
check(abs(sum(e["split"].values()) - 1) < 1e-9, "the ring split sums to one")
g2 = dict(g_syn, demand_mw=None)
e2 = M.estimate(src, g2)
check(e2["import_max"] is None and e2["mid"] is None and e2["split"]["beyond"] is None,
      "an unknown cable rating gives no import share and no midpoint, never a guess")
check(abs(e2["low"] - 0.8) < 1e-9 and abs(e2["high"] - 0.9) < 1e-9,
      "unknown rating: the range runs from the island (90%) to the cable's own share (80%)")
g3 = dict(g_syn, links=[{"rated_mw": 100, "fossil_share": None, "ring": "beyond"}])
check(M.estimate(src, g3)["low"] is None, "a link with no known mix gives no figure")
e_empty = M.estimate([], g_syn)
check(e_empty["low"] is None and e_empty["island"] is None, "no known plants gives None, never 0 or 1")
e_bali = M.estimate(bali, G.grid_for(-8.8161, 115.1635, g))
check(e_bali["low"] is not None and 0.80 < e_bali["low"] < e_bali["high"] <= 1,
      f"node #1 Bali range sanity, got {e_bali['low']}–{e_bali['high']}")

# ---------------------------------------------------------------- Menorca measured (ree.py)
rows = R.parse(json.load(open(FIX / "ree-baleares-2026-05-10.json")))
check(len(rows) == 1 and rows[0][0] == date(2026, 5, 10), "one day is one row")
check(all(0 <= f <= t for _, f, t in rows), "fossil never exceeds total")
check(abs(R.share(rows) - 8612.125 / 11012.72) < 1e-6, "Balearic share on 2026-05-10")
check(R.share([]) is None, "empty rows give None, never 0")
pen_rows = R.parse(json.load(open(FIX / "ree-peninsular-2026-05-10.json")))
check(len(pen_rows) == 1 and abs(R.share(pen_rows) - 193713.6 / 555167.63) < 1e-6, "peninsular share on 2026-05-10")
linked = R.with_link(rows, pen_rows, {date(2026, 5, 10): 1000.0})
check(abs(linked[0][2] - 12012.72) < 1e-6 and abs(linked[0][1] - (8612.125 + 1000.0 * R.share(pen_rows))) < 1e-4,
      "each day's imports count at that day's peninsular share")
neg_doc = {"included": [
    {"attributes": {"type": "No-Renovable", "values": [{"value": 500.0, "datetime": "2026-05-10T00:00:00.000+02:00"}]}},
    {"attributes": {"type": "Renovable", "values": [{"value": 300.0, "datetime": "2026-05-10T00:00:00.000+02:00"}]}},
    {"attributes": {"type": "Almacenamiento", "values": [{"value": -50.0, "datetime": "2026-05-10T00:00:00.000+02:00"}]}},
    {"attributes": {"type": "total", "values": [{"value": 750.0, "datetime": "2026-05-10T00:00:00.000+02:00"}]}},
]}
neg_rows = R.parse(neg_doc)
check(neg_rows == [(date(2026, 5, 10), 450.0, 750.0)], "negative storage consumption is subtracted from fossil")
check(R.months_to_fetch(set(), date(2026, 11, 8))[0] == "2025-12", "the trailing year starts December 2025")
check(R.months_to_fetch({"2025-12", "2026-01"}, date(2026, 11, 8))[0] == "2026-02", "held months are skipped")


class Down:                       # REE down, as on 8 Nov
    def get(self, *a, **k):
        raise RuntimeError("502")


st = {"months": {"2026-10": [0.4, 600.0, 1500.0]}, "last": {"value": 0.4, "as_of": "2026-11-07T23:00Z"}}
out = R.fetch(Down(), st, date(2026, 11, 8))
check(out["stale"] and out["value"] == 0.4, "a failed fetch keeps the last figure and says it is stale, never 0")
check(out["months"] == 1, "headline says how many months it holds until twelve are in")
out_empty = R.fetch(Down(), {}, date(2026, 11, 8))
check(out_empty["stale"] and out_empty["value"] is None and out_empty["months"] == 0,
      "a failed first fetch with no state gives None, never 0")


class StubREE:
    def __init__(self, doc):
        self.doc = doc
        self.calls = []

    def get(self, url, params=None, **kw):
        self.calls.append((url, params))
        doc = self.doc
        return type("Resp", (), {"status_code": 200, "raise_for_status": lambda s: None, "json": lambda s: doc})()


class StubREE3:                   # mix, link, peninsula: a link of 1000 MWh a day in, as REE serves it
    def __init__(self):
        self.calls = []
        self.bal = json.load(open(FIX / "ree-baleares-2026-05-10.json"))
        self.pen = json.load(open(FIX / "ree-peninsular-2026-05-10.json"))

    def get(self, url, params=None, **kw):
        self.calls.append((url, params))
        if url == R.LINK_URL:
            doc = {"included": [{"attributes": {"values": [{"value": 1000.0, "datetime": "2026-05-10T00:00:00.000+02:00"}]}}]}
        else:
            doc = self.pen if params["geo_ids"] == "8741" else self.bal
        return type("Resp", (), {"raise_for_status": lambda s: None, "json": lambda s: doc})()


stub = StubREE3()
st_live: dict = {}
out_live = R.fetch(stub, st_live, date(2026, 11, 8))
check(len(stub.calls) == 9 and out_live["months"] == 3 and not out_live["stale"] and out_live["kind"] == "measured",
      "fetches at most 3 months per call, three requests each, and records a measured share")
check(stub.calls[0][1]["start_date"] == "2026-11-01T00:00" and stub.calls[0][1]["end_date"] == "2026-11-07T23:59",
      "the current month goes first and ends yesterday, so 'yesterday' is never a backfill day or today's part")
check(all(c[1]["time_trunc"] == "day" for c in stub.calls) and {c[1]["geo_ids"] for c in stub.calls} == {"8743", "8741"},
      "day resolution, geo_ids 8743 and 8741 from grids.yml")
check(abs(out_live["value"] - linked[0][1] / linked[0][2]) < 1e-9, "the headline counts the link at the peninsula's share")
check(abs(out_live["beyond"] - 1000.0 / 12012.72) < 1e-9, "beyond is the link's share of supply")
check(R.fetch(StubREE3(), {}, date(2026, 11, 1))["now"] is None, "on the 1st the month has no full day yet: no 'yesterday'")

g_bal = G.grid_for(39.9493, 4.0500, g)
men_plus_mal = men + [{"name": "Alcúdia", "kind": "plant", "fuel": "coal", "fossil": True,
                       "mw": 260.0, "lat": 39.81, "lon": 3.15}]
sp = R.ring_split(men_plus_mal, g_bal, beyond_share=0.2)
check(sp["kind"] == "estimated" and abs(sp["beyond"] - 0.2) < 1e-9 and abs(sp["city"] + sp["region"] + sp["beyond"] - 1.0) < 1e-9,
      "Menorca ring split uses OSM capacity for city vs region and marks the split estimated")

# ── Task 5: adapter.py and issue.yml ─────────────────────────────────────────
import os
import tempfile
import adapter as A
import issues


class StubHC:
    def __init__(self, osm_doc):
        self.osm_doc = osm_doc
        self.ree = StubREE3()

    def post(self, url, data=None, **kw):
        doc = self.osm_doc
        return type("Resp", (), {"status_code": 200, "raise_for_status": lambda s: None, "json": lambda s: doc})()

    def get(self, url, params=None, **kw):
        if "overpass" in url:
            return self.post(url, data=params, **kw)
        return self.ree.get(url, params=params, **kw)


with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "-8.8161", "115.1635"
    s_bali, r_bali = A.fetch(StubHC(json.load(open(FIX / "overpass-bali-2026-11-08.json"))))
    m_bali = {m: v for _, sid, m, v in r_bali if sid == "energy-grid"}
    check(len(s_bali) == 1 and s_bali[0]["sensor_id"] == "energy-grid" and s_bali[0]["kind"] == "model"
          and s_bali[0]["scale"] == "region" and not s_bali[0]["local"],
          "energy-grid sensor is a regional model sensor")
    check("fossil_share_low_pct" in m_bali and "fossil_share_high_pct" in m_bali
          and "fossil_share_pct" not in m_bali and "fossil_share_day_pct" not in m_bali,
          "node #1 returns fossil_share_low_pct and high_pct, with no fossil_share_pct")
    check(80 <= m_bali["fossil_share_low_pct"] <= m_bali["fossil_share_high_pct"] <= 100
          and m_bali["substation_km"] < 5 and 10 <= m_bali["large_plant_km"] <= 15
          and "import_share_max_pct" not in m_bali,
          f"node #1 readings match Bali range and distances, and omit unknown import_share_max_pct: {m_bali}")
    res_bali = A.result()
    # R25: two house points near opposite corners of one res-8 cell give the same km readings (derived, so they leave
    # without a token) and both carry the substation nearest the cell's middle, which a stranger's /energy names.
    import h3
    _cid = h3.latlng_to_cell(-8.8161, 115.1635, 8)
    _cc, _vs = h3.cell_to_latlng(_cid), h3.cell_to_boundary(_cid)
    # and a substation just outside each corner, so the house's own nearest differs between the two
    _doc = json.load(open(FIX / "overpass-bali-2026-11-08.json"))
    _doc["elements"] += [{"type": "node", "id": 9e9 + _k, "lat": _cc[0] + 1.3 * (_vs[_k][0] - _cc[0]),
                          "lon": _cc[1] + 1.3 * (_vs[_k][1] - _cc[1]),
                          "tags": {"power": "substation", "name": f"corner {_k}", "operator": "PLN"}} for _k in (0, 3)]
    _seen = []
    for _k in (0, 3):
        os.environ["NODE_LAT"], os.environ["NODE_LON"] = (str(_cc[i] + 0.9 * (_vs[_k][i] - _cc[i])) for i in (0, 1))
        os.environ["PACK_OUT"] = tempfile.mkdtemp(dir=tmp)       # no Overpass cache from the run before
        _, _r = A.fetch(StubHC(_doc))
        _subs = [x for x in A.result()["sources"] if x["kind"] == "substation"]
        _seen.append(({m: v for _, sid, m, v in _r if m in ("substation_km", "large_plant_km")},
                      min(_subs, key=lambda x: h3.great_circle_distance(_cc, (x["lat"], x["lon"])))["name"]))
    os.environ["NODE_LAT"], os.environ["NODE_LON"], os.environ["PACK_OUT"] = "-8.8161", "115.1635", tmp
    # the substation nearest the middle is picked by (km, name, point), never by the house-nearest order: five
    # substations 0.6 km beyond the house fill the house's nearest five, and two at one point 1 km the other side of the
    # middle tie for nearest the middle, "Zed" listed first. "Abe" is the one picked.
    _h = tuple(_cc[i] + 0.9 * (_vs[0][i] - _cc[i]) for i in (0, 1))
    _u = tuple(_h[i] - _cc[i] for i in (0, 1))
    _n = h3.great_circle_distance(_cc, _h, unit="km")
    _node = lambda nid, at, name: {"type": "node", "id": nid, "lat": at[0], "lon": at[1],  # noqa: E731
                                   "tags": {"power": "substation", "name": name, "operator": "PLN"}}
    _tie = tuple(_cc[i] - _u[i] / _n for i in (0, 1))
    _doc = {"elements": [_node(1, _tie, "Zed"), _node(2, _tie, "Abe")] + [
        _node(10 + k, tuple(_h[i] + _u[i] / _n * 0.6 + 0.0001 * k * (i == 1) for i in (0, 1)), f"near {k}")
        for k in range(5)]}
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = str(_h[0]), str(_h[1])
    os.environ["PACK_OUT"] = tempfile.mkdtemp(dir=tmp)
    A.fetch(StubHC(_doc))
    _names = {x["name"] for x in A.result()["sources"] if x["kind"] == "substation"}
    check("Abe" in _names and "Zed" not in _names, f"a tie for nearest the middle goes by name: {sorted(_names)}")
    os.environ["NODE_LAT"], os.environ["NODE_LON"], os.environ["PACK_OUT"] = "-8.8161", "115.1635", tmp
    check(_seen[0] == _seen[1] and all(float(v).is_integer() for v in _seen[0][0].values()),
          f"the km readings and the substation nearest the cell's middle stay put inside one cell: {_seen}")
    cable = next(b for b in res_bali["bar"] if b["hatched"])
    check(cable["share"] is None and cable["note"] == "share not published",
          "the Java cable's segment has no width while its share is unknown, never a guessed one")
    check("lat" not in res_bali and "lon" not in res_bali, "the body served at /energy carries no coordinates")
    check(res_bali.get("cell") == h3.latlng_to_cell(-8.8161, 115.1635, 8), "result.json says which cell it was picked for")
    check(res_bali.get("grid") == "bali" and res_bali.get("kind") == "estimated"
          and res_bali.get("sources", [{}])[0].get("kind") == "substation",
          "result() writes out/energy/result.json for Bali with nearest substation first")

    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "39.9493", "4.0500"
    s_men, r_men = A.fetch(StubHC(json.load(open(FIX / "overpass-menorca-2026-11-08.json"))))
    m_men = {m: v for _, sid, m, v in r_men if sid == "energy-grid"}
    check("fossil_share_pct" in m_men and "fossil_share_day_pct" in m_men
          and m_men["fossil_share_low_pct"] == m_men["fossil_share_high_pct"] == m_men["fossil_share_pct"]
          and m_men.get("grid_months") == 3.0,
          f"mahon1 returns fossil_share_pct, fossil_share_day_pct, and low == high: {m_men}")

    check(s_men[0]["meta"]["licence"] == "non-commercial" and s_bali[0]["meta"]["licence"] == "open",
          "REE on the Balearic grid is marked non-commercial, so the open export leaves it out; Bali's sources are open")
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "41.39", "2.17"
    check(A.fetch(StubHC({})) == ([], []), "Barcelona is outside grids.yml and returns ([], [])")

os.environ["PACKS_DIR"] = str(ROOT / "packs")
decl = issues.load()
check("energy" in decl and decl["energy"]["kind"] == "context" and decl["energy"]["line"] is None
      and decl["energy"]["metric"] == "fossil_share_low_pct",
      "issues.load() finds energy with kind == 'context' and line is None")

# ── Task 6: GET /energy (routes.py) ──────────────────────────────────────────
import logging
import time

sys.path = [p for p in sys.path if p != "/tmp/stub"]
sys.modules.pop("httpx", None)
logging.disable(logging.WARNING)
os.environ.update(
    PACKS_DIR=str(ROOT / "packs"),
    ADMIN_TOKEN="admin-tok",
    ACT_TOKEN="act-tok",
    NODE_LAT="-8.8161",
    NODE_LON="115.1635",
    DATABASE_URL="postgresql://unused/never-connected",
)
import settings  # noqa: E402
ROWS = {"PACKS_ENABLED": "", "SHARE_LEVEL": "open"}
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}
import db  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app)
ADMIN = {"Authorization": "Bearer admin-tok"}
ACT = {"Authorization": "Bearer act-tok"}

with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "-8.8161", "115.1635"
    A.fetch(StubHC(json.load(open(FIX / "overpass-bali-2026-11-08.json"))))

    ROWS["PACKS_ENABLED"] = "air-quality,heat"
    r_off = client.get("/energy", headers=ADMIN)
    check(r_off.status_code == 404 and "pack is off" in r_off.json().get("detail", ""),
          f"GET /energy is 404 while the pack is off, got {r_off.status_code}: {r_off.text}")

    ROWS["PACKS_ENABLED"] = ""
    HA_ROWS = [
        {"sensor_id": "energy-home", "metric": "home_roof_w", "value": 3120.0},
        {"sensor_id": "energy-home", "metric": "home_grid_w", "value": 400.0},
        {"sensor_id": "energy-home", "metric": "home_fossil_pct", "value": 24.25},
    ]
    db.q = main.q = lambda sql, *a: [dict(r) for r in HA_ROWS] if "energy-home" in sql else []

    r_anon = client.get("/energy")
    check(r_anon.status_code == 200, f"GET /energy is 200 on SHARE_LEVEL=open with the pack on, got {r_anon.status_code}")
    body = r_anon.json() if r_anon.status_code == 200 else {}
    want_keys = {"grid", "kind", "method", "months", "share", "bar", "sources", "today", "household", "attribution",
                 "counts", "cells"}
    check(set(body.keys()) == want_keys, f"GET /energy body keys match contract, got {set(body.keys())}")
    check(all(s["km"] is None or float(s["km"]).is_integer() for s in body.get("sources") or []),
          f"without the token the distances are whole km, never precise enough to place the house: {[s.get('km') for s in body.get('sources') or []]}")
    check(body.get("grid") == "bali" and body.get("kind") == "estimated" and body.get("method") == "capacity-factors",
          "GET /energy serves Bali grid metadata")
    check(set((body.get("share") or {}).keys()) == {"low", "high", "value", "now", "stale", "as_of"},
          "GET /energy share object has the contract keys")
    check(set((body.get("today") or {}).keys()) == {"sun_kwh_m2", "roof_kwh", "use_kwh", "measured", "panel_kw"},
          "GET /energy today object has the contract keys")
    srcs = body.get("sources") or []
    check(bool(srcs) and srcs[0].get("kind") == "substation" and srcs[0].get("name") == "GIS Pecatu"
          and sum(1 for s in srcs if s.get("kind") == "substation") == 1
          and all((s.get("mw") or 0) >= 1.0 for s in srcs if s.get("kind") == "plant")
          and srcs[-1].get("kind") == "link",
          "sources is cut to the nearest substation, then every plant with mw >= 1, then each link")
    check(body.get("household") is None, "household is null without the admin token even when HA rows exist")
    check(client.get("/energy", headers=ACT).json().get("household") is None,
          "household is null for the act token even when HA rows exist")
    check(client.get("/energy", headers={**ADMIN, "X-Agent": "agent"}).json().get("household") is None,
          "household is null for an agent even holding the admin token")
    r_adm = client.get("/energy", headers=ADMIN).json()
    check(any(s.get("km") is not None and not float(s["km"]).is_integer() for s in r_adm.get("sources") or []),
          "with the token the distances are as measured")
    check(isinstance(r_adm.get("household"), dict) and r_adm["household"].get("roof_w") == 3120.0,
          f"household is served to the admin token when HA rows exist: {r_adm.get('household')}")

    raw_res = json.loads((Path(tmp) / "energy/result.json").read_text())
    import wall  # noqa: E402
    import h3  # noqa: E402
    C = wall.cell_centre()
    check(C == tuple(reversed(h3.cell_to_latlng(h3.latlng_to_cell(-8.8161, 115.1635, 8)))), f"the res-8 cell's middle: {C}")
    E = lambda km: C[0] + km / (111.32 * 0.988)  # noqa: E731 — a point `km` east of the middle
    raw_res["sources"] = [
        # "Sub Near" is the nearest the house (km) and "Sub Mid" the nearest the cell's middle (its point)
        {"name": "Sub Far", "kind": "substation", "fuel": None, "mw": None, "km": 8.0, "ring": "region", "lat": C[1], "lon": E(8.2)},
        {"name": "Sub Near", "kind": "substation", "fuel": None, "mw": None, "km": 1.2, "ring": "city", "lat": C[1], "lon": E(3.1)},
        {"name": "Sub Mid", "kind": "substation", "fuel": None, "mw": None, "km": 1.4, "ring": "city", "lat": C[1], "lon": E(2.0)},
        {"name": "Small Solar", "kind": "plant", "fuel": "solar", "mw": 0.5, "km": 0.8, "ring": "city", "lat": C[1], "lon": E(0.9)},
        {"name": "Unknown MW", "kind": "plant", "fuel": "solar", "mw": None, "km": 0.9, "ring": "city", "lat": C[1], "lon": E(0.9)},
        {"name": "Big Plant", "kind": "plant", "fuel": "gas", "mw": 50.0, "km": 4.03, "ring": "city", "lat": -8.7123456, "lon": 115.2123456},
        {"name": "Java cable", "kind": "link", "fuel": None, "mw": None, "km": 100.0, "ring": "beyond", "lat": None, "lon": None},
    ]
    raw_res["household"] = {"roof_w": 2500.0, "grid_w": 100.0, "fossil_pct": 12.0}
    (Path(tmp) / "energy/result.json").write_text(json.dumps(raw_res))
    anon_s = client.get("/energy").json()["sources"]
    check([(s["name"], s["kind"]) for s in anon_s] == [
        ("Sub Mid", "substation"), ("Big Plant", "plant"), ("Java cable", "link")
    ], f"without the token: the substation nearest the cell's middle, plants >= 1 MW, then links: {anon_s}")
    check([s["km"] for s in anon_s] == [2, wall.km_from(C, 115.2123456, -8.7123456), None],
          f"without the token every km is whole and from the cell's middle, as /wall's, never the house's: {anon_s}")
    adm_s = client.get("/energy", headers=ADMIN).json()["sources"]
    check([(s["name"], s["km"]) for s in adm_s] == [("Sub Near", 1.2), ("Big Plant", 4.03), ("Java cable", 100.0)],
          f"with the token: the substation nearest the house, every km as measured from it: {adm_s}")
    # two substations whole 2 km from the middle, the farther listed first (the pack's house-nearest order) and first
    # by name: the nearer by its unrounded km is named; at an exact tie, the name decides, never the pack's order
    near_first = [dict(raw_res["sources"][2], name="Alpha 2.4", lon=E(2.4)), dict(raw_res["sources"][2], name="Beta 2.1",
                                                                                lon=E(2.1))] + raw_res["sources"][3:]
    for srcs_, want in ((near_first, "Beta 2.1"),
                        ([dict(near_first[0], name="Zed", lon=E(2.0)), dict(near_first[0], name="Abe", lon=E(2.0))], "Abe")):
        (Path(tmp) / "energy/result.json").write_text(json.dumps({**raw_res, "sources": srcs_}))
        got = client.get("/energy").json()["sources"][0]
        check(got["name"] == want and got["km"] == 2, f"the substation nearest the middle by its unrounded km: {got}")
    # a result computed for another res-8 cell holds the old house's nearest few: no substation until the next poll
    (Path(tmp) / "energy/result.json").write_text(json.dumps({**raw_res, "cell": h3.cell_to_parent(raw_res["cell"], 7)}))
    check([s["kind"] for s in client.get("/energy").json()["sources"]] == ["plant", "link"],
          "without the token, a result for another cell names no substation")
    check(client.get("/energy", headers=ADMIN).json()["sources"][0]["name"] == "Sub Near",
          "the household's own list is as the pack measured it")
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "0", "0"
    check([s["km"] for s in client.get("/energy").json()["sources"]] == [None, None],
          "a node with no place yet gives no km at all, and no substation, without the token")
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "-8.8161", "115.1635"
    (Path(tmp) / "energy/result.json").write_text(json.dumps(raw_res))
    check(client.get("/energy").json()["household"] is None,
          "household in result.json is also hidden without the admin token")
    check(client.get("/energy", headers=ADMIN).json()["household"]["roof_w"] == 2500.0,
          "household in result.json is served to the admin token")

# ── Task 8: the household through Home Assistant (ha.py) ──────────────────────
import sqlite3
from datetime import datetime as DT, timedelta as TD, timezone as TZ

import ha as H  # noqa: E402
import packs  # noqa: E402

HA = json.load(open(FIX / "ha-api-states.json"))


class StubHA:
    """Answers GET {url}/api/states/<entity> from the fixture, as Home Assistant does."""

    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, **kw):
        self.calls.append((url, dict(headers or {})))
        ent = url.rsplit("/api/states/", 1)[-1]
        if (headers or {}).get("Authorization") != "Bearer tok":
            rec = HA["unauthorized"]
        elif ent in HA["states"]:
            rec = {"status": 200, "body": HA["states"][ent]}
        else:
            rec = HA["not_found"]

        def _json(s, b=rec["body"]):
            if isinstance(b, str):
                raise ValueError("not JSON")
            return b
        return type("Resp", (), {"status_code": rec["status"], "json": _json})()


ha_hc = StubHA()
check(H.state(ha_hc, "http://ha.local:8123/", "tok", "sensor.solar_power") == 3120.0, 'state() reads "3120" as 3120.0')
check(ha_hc.calls[0] == ("http://ha.local:8123/api/states/sensor.solar_power", {"Authorization": "Bearer tok"}),
      f"state() asks {{url}}/api/states/{{entity}} with the Bearer token, got {ha_hc.calls[0]}")
check(H.state(ha_hc, "http://ha.local:8123", "tok", "sensor.grid_meter_offline") is None, '"unavailable" is None')
check(H.state(ha_hc, "http://ha.local:8123", "tok", "sensor.battery_power") is None, '"unknown" is None')
check(H.state(ha_hc, "http://ha.local:8123", "wrong", "sensor.solar_power") is None, "a 401 is None")
check(H.state(ha_hc, "http://ha.local:8123", "tok", "sensor.nobody") is None, "a 404 is None")
check(H.state(ha_hc, "http://ha.local:8123", "tok", "sensor.inverter_power_kw") == 3120.0,
      "an entity in kW is read in W, never as 3.12 W")
check(H.state(ha_hc, "http://ha.local:8123", "tok", "sensor.solar_energy_today") is None,
      "an energy entity (kWh) is not a power reading: None, never a W figure")


class Boom:
    def get(self, *a, **kw):
        raise OSError("no route to host")


check(H.state(Boom(), "http://ha.local:8123", "tok", "sensor.solar_power") is None, "an unreachable HA is None")

T0 = DT(2026, 11, 8, 5, 0, tzinfo=TZ.utc)
check(abs(H.kwh([(T0 + TD(minutes=i), 1000.0) for i in range(0, 61, 5)]) - 1.0) < 1e-9,
      "kwh() of a constant 1000 W over the hour is 1.0")
check(abs(H.share(3, 1, 0.97) - 0.2425) < 1e-12, "share(3, 1, 0.97) is 0.2425")
check(H.share(0, 0, 0.97) is None, "share(0, 0, 0.97) is None")
# Polls land on the 5-minute loop, not on the hour: the hour's edges are read between the samples either side.
off = [(T0 + TD(minutes=2 + 5 * i), 1000.0) for i in range(-1, 13)]
check(abs(H.kwh(H.clip(off, T0)) - 1.0) < 1e-9, "clip() puts the hour's edges between the polls either side")
check(H.clip([(t, w) for t, w in off if t > T0], T0) is None, "an hour the polls did not reach from its start is None")
check(H.clip(off[:6] + off[8:], T0) is None, "an hour with a 15-minute hole is None")
check(H.clip(off[:4] + [(off[4][0], None)] + off[5:], T0) is None, "an hour with a failed read is None")

# The adapter: _home() every 5 minutes, then the hour's lines on the first poll after it.
with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "39.9493", "4.0500"
    for k in ("ENERGY_HA_URL", "ENERGY_HA_TOKEN", "ENERGY_HA_SOLAR", "ENERGY_HA_GRID", "ENERGY_HA_BATTERY"):
        os.environ.pop(k, None)
    check(A._home(StubHA(), 0.41, T0) == ([], []), "no ENERGY_HA_URL: no household sensor and no line")
    os.environ.update(ENERGY_HA_URL="http://ha.local:8123", ENERGY_HA_TOKEN="tok", ENERGY_HA_SOLAR="sensor.solar_power",
                      ENERGY_HA_GRID="sensor.grid_power", ENERGY_HA_BATTERY="sensor.battery_power")
    polls = [T0 + TD(minutes=2 + 5 * i) for i in range(-1, 13)]
    out = [A._home(StubHA(), 0.97, t) for t in polls]
    hs, hr = out[1]
    check(len(hs) == 1 and hs[0]["sensor_id"] == "energy-home" and hs[0]["local"] is True and hs[0]["indoor"] is False
          and hs[0]["kind"] == "sensor" and hs[0]["source"] == "energy", f"energy-home is a local outdoor sensor: {hs}")
    check("tok" not in json.dumps(hs) and "ha.local" not in json.dumps(hs), "the sensor's meta carries no token and no URL")
    check({m: v for _, _, m, v in hr} == {"home_roof_w": 3120.0, "home_grid_w": 400.0},
          f'every 5 minutes the W lines, and no battery line while HA says "unknown": {hr}')
    hourly = {m: (ts, v) for _, (_, r) in enumerate(out) for ts, _, m, v in r if m.endswith(("kwh", "pct"))}
    check(set(hourly) == {"home_roof_kwh", "home_grid_kwh", "home_fossil_pct"}
          and all(ts == T0 for ts, _ in hourly.values()), f"one hourly line each, stamped at the hour: {hourly}")
    check(hourly["home_roof_kwh"][1] == 3.12 and hourly["home_grid_kwh"][1] == 0.4
          and abs(hourly["home_fossil_pct"][1] - 11.02) < 0.01,
          f"3120 W and 400 W for an hour: 3.12 and 0.4 kWh, 0.4/3.52 of a 97% grid: {hourly}")
    check(sum(1 for _, r in out for _, _, m, _ in r if m == "home_roof_kwh") == 1, "an hour is written once")

with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    out = []
    for i, t in enumerate(polls):
        os.environ["ENERGY_HA_GRID"] = "sensor.grid_meter_offline" if i == 6 else "sensor.grid_power"
        out.append(A._home(StubHA(), 0.97, t))
    got = {m for _, r in out for _, _, m, _ in r}
    check("home_roof_kwh" in got and "home_grid_kwh" not in got and "home_fossil_pct" not in got,
          f"HA unavailable for one poll: that hour has no household line, never a house on 100% grid: {got}")
    check(not any(m == "home_grid_w" for _, _, m, _ in out[6][1]), "and that poll writes no grid W")

with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    os.environ["ENERGY_HA_GRID"] = "sensor.grid_power"
    got = {m for _, r in [A._home(StubHA(), None, t) for t in polls] for _, _, m, _ in r}
    check("home_grid_kwh" in got and "home_fossil_pct" not in got,
          "Bali's grid is a range, so the household's kWh are written and its fossil share is not")

with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "-8.8161", "115.1635"
    s_all, r_all = A.fetch(type("HC", (StubHC,), {"get": lambda s, url, **kw: StubHA().get(url, **kw)
                                                    if "/api/states/" in url else StubHC.get(s, url, **kw)})(
        json.load(open(FIX / "overpass-bali-2026-11-08.json"))))
    check({s["sensor_id"] for s in s_all} == {"energy-grid", "energy-home"}
          and any(sid == "energy-home" and m == "home_roof_w" for _, sid, m, _ in r_all),
          "fetch() reads the house beside the grid when ENERGY_HA_URL is set")
    for k in ("ENERGY_HA_URL", "ENERGY_HA_TOKEN", "ENERGY_HA_SOLAR", "ENERGY_HA_GRID", "ENERGY_HA_BATTERY"):
        os.environ.pop(k, None)

# The channel role check: packs.public_sql on real rows (stdlib sqlite3 runs the same predicate).
private = {c["metric"] for c in packs.channels() if c["source"] == "energy" and c["role"] == "private"}
check(private == {"home_roof_w", "home_grid_w", "home_battery_w", "home_roof_kwh", "home_grid_kwh", "home_fossil_pct"},
      f"every household metric is role: private, got {private}")
pk = packs.read_yaml(ROOT / "packs/energy/pack.yaml")
check(pk.get("secrets") == ["ENERGY_HA_TOKEN"] and private <= set(pk["metrics"])
      and all(any(str(e).startswith(k + "=") for e in pk["env"]) for k in
              ("ENERGY_HA_URL", "ENERGY_HA_TOKEN", "ENERGY_HA_SOLAR", "ENERGY_HA_GRID", "ENERGY_HA_BATTERY")),
      "pack.yaml declares the five ENERGY_HA_ keys, the token as its secret, and the household metrics")
c = sqlite3.connect(":memory:")
c.execute("CREATE TABLE sensors (sensor_id TEXT, source TEXT)")
c.execute("CREATE TABLE channel_roles (source TEXT, metric TEXT, role TEXT)")
c.execute("CREATE TABLE readings (sensor_id TEXT, metric TEXT, value REAL)")
c.executemany("INSERT INTO sensors VALUES (?, ?)", [("energy-home", "energy"), ("energy-grid", "energy")])
c.executemany("INSERT INTO channel_roles VALUES (?, ?, ?)", [(x["source"], x["metric"], x["role"]) for x in packs.channels()])
c.executemany("INSERT INTO readings VALUES (?, ?, ?)", [("energy-home", "home_grid_kwh", 0.4),
                                                       ("energy-home", "home_roof_w", 3120.0),
                                                       ("energy-grid", "fossil_share_low_pct", 95.0)])
left = [m for (m,) in c.execute(f"SELECT metric FROM readings r WHERE {packs.public_sql('r')}")]
check(left == ["fossil_share_low_pct"], f"packs.public_sql leaves out home_grid_kwh and every household row, kept {left}")

# ── Task 9: today's sun on the roof (today.py) ───────────────────────────────
import today as T  # noqa: E402

for k in ("ENERGY_PANEL_KW", "ENERGY_HOUSE_KWH_DAY", "ENERGY_PANEL_PR"):
    os.environ.pop(k, None)
SUN = [0.0] * 6 + [1000.0] * 6 + [0.0] * 12
b = T.box(SUN, 2, 9, None)
check(b == {"sun_kwh_m2": 6.0, "roof_kwh": 9.0, "use_kwh": 9, "measured": False, "panel_kw": 2},
      f"six hours of 1000 W/m² is 6 kWh/m², and 2 kW of panels at PR 0.75 make 9.0 kWh: {b}")
b = T.box(SUN, 2, 9, 3.4)
check(b["roof_kwh"] == 3.4 and b["measured"] is True and b["sun_kwh_m2"] == 6.0, f"a measured roof wins: {b}")
b = T.box([], 2, 9, None)
check(b["sun_kwh_m2"] is None and b["roof_kwh"] is None and b["measured"] is False and b["use_kwh"] == 9,
      f"no forecast rows: no sun and no roof line, never 0, and the house's use still shows: {b}")
b = T.box(SUN, None, None, None)
check(b["sun_kwh_m2"] == 6.0 and b["roof_kwh"] is None and b["use_kwh"] is None and b["panel_kw"] is None,
      f"no panel size and no daily use set: the sun alone: {b}")
os.environ["ENERGY_PANEL_PR"] = "0.8"
check(T.box(SUN, 2, 9, None)["roof_kwh"] == 9.6, "ENERGY_PANEL_PR is the knob on the performance ratio")
os.environ.pop("ENERGY_PANEL_PR")
db_url = os.environ.pop("DATABASE_URL", None)
check(T.read() == ([], None), "no database to read: no sun and no measured roof")
if db_url:
    os.environ["DATABASE_URL"] = db_url
pk = packs.read_yaml(ROOT / "packs/energy/pack.yaml")
check(all(any(str(e) == v for e in pk["env"]) for v in
          ("ENERGY_PANEL_KW=2", "ENERGY_HOUSE_KWH_DAY=9", "ENERGY_PANEL_PR=0.75")),
      "pack.yaml declares the three Today settings with their placeholder values")

# Wired: what fetch() writes and GET /energy serves as `today` is box() on what read() found.
read_was = T.read
with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = "-8.8161", "115.1635"
    bali_hc = StubHC(json.load(open(FIX / "overpass-bali-2026-11-08.json")))
    T.read = lambda: (SUN, None)
    A.fetch(bali_hc)
    check(A.result().get("today") == T.box(SUN, 2.0, 9.0, None),
          f"fetch() writes box() as result.json's today: {A.result().get('today')}")
    td = client.get("/energy").json()["today"]
    check(td == {"sun_kwh_m2": 6.0, "roof_kwh": 9.0, "use_kwh": 9.0, "measured": False, "panel_kw": 2.0},
          f"GET /energy serves today with the panel size the label reads: {td}")
    T.read = lambda: ([], None)
    A.fetch(bali_hc)
    td = client.get("/energy").json()["today"]
    check(td["sun_kwh_m2"] is None and td["roof_kwh"] is None,
          f"GET /energy with no forecast rows: sun_kwh_m2 null and no roof line: {td}")
T.read = read_was

# ── Task 10: the Place map (adapter._cells, counts, lat/lon behind the household's token) ─────────────────────
import h3  # noqa: E402

PT = (-8.8161, 115.1635)
home8 = h3.latlng_to_cell(*PT, 8)
nb = next(c for c in h3.grid_disk(home8, 1) if c != home8)
check(A._cells([], *PT) is None, "no sources fetched: the seven cells are missing, never 0 MW")
cs = A._cells([{"kind": "plant", "mw": 5.0, "lat": PT[0], "lon": PT[1]},
               {"kind": "plant", "mw": 2.5, "lat": PT[0], "lon": PT[1]},
               {"kind": "generator", "mw": 9.0, "lat": PT[0], "lon": PT[1]},
               {"kind": "plant", "mw": None, "lat": h3.cell_to_latlng(nb)[0], "lon": h3.cell_to_latlng(nb)[1]},
               {"kind": "plant", "mw": 300.0, "lat": -8.72, "lon": 115.21}], *PT)
by = {c["id"]: c for c in cs}
check(len(cs) == 7 and set(by) == set(h3.grid_disk(home8, 1)), "the seven cells are the node's res-8 cell and its six neighbours")
check(by[home8]["mw"] == 7.5 and by[home8]["home"] and sum(c["home"] for c in cs) == 1,
      f"a cell's MW sums its plants, never a generator, and the node's own cell is marked: {by[home8]}")
check(by[nb]["mw"] is None, "a plant with no capacity leaves its cell's MW unknown, never 0")
check(all(c["mw"] == 0 for c in cs if c["id"] not in (home8, nb)), "a cell with no plant in it is 0 MW")
check(all(len(c["ring"]) == 7 and c["ring"][0] == c["ring"][-1] for c in cs), "each cell carries its closed outline from the node")

with tempfile.TemporaryDirectory() as tmp:
    os.environ["PACK_OUT"] = tmp
    os.environ["NODE_LAT"], os.environ["NODE_LON"] = str(PT[0]), str(PT[1])
    A.fetch(StubHC(json.load(open(FIX / "overpass-bali-2026-11-08.json"))))
    res = A.result()
    check(len(res["cells"]) == 7 and sum(c["mw"] for c in res["cells"]) == 0,
          f"no plant stands in node #1's seven cells on 8 Nov: 0 MW in each, {[c['mw'] for c in res['cells']]}")
    check(res["counts"] == {"plants": 9, "substations": 22},
          f"9 plants and 22 substations inside the Bali polygon (Nusa Penida and Java left out): {res['counts']}")
    check(not any("Kutampi" in s["name"] or "Nusa Penida" in s["name"] for s in res["sources"]),
          f"Nusa Penida's island grid is not listed as Bali's: {[s['name'] for s in res['sources']]}")
    check(all(s.get("lat") is not None for s in res["sources"] if s["kind"] != "link")
          and next(s for s in res["sources"] if s["kind"] == "link")["lat"] is not None,
          "every source carries its point, the link at its cable head")
    ROWS["PACKS_ENABLED"] = ""
    anon = client.get("/energy").json()
    act = client.get("/energy", headers=ACT).json()
    check(anon["cells"] is None and all("lat" not in s and "lon" not in s for s in anon["sources"]),
          "without the household's token: no cells and no points, so km and a plant's place never give the node's away")
    check(anon["counts"] == {"plants": 9, "substations": 22}, "the counts are served to anyone the route answers")
    check(len(act["cells"] or []) == 7 and act["sources"][0]["lat"] is not None,
          "the household's act token gets the seven cells and each source's point for the Place map")
    check(client.get("/energy", headers={**ADMIN, "X-Agent": "agent"}).json()["cells"] is None,
          "an agent never gets the cells, whatever token it holds")

if fails:
    print("\n".join(f"  ✗ {f}" for f in fails))
    sys.exit(1)
print("  ✓ energy: grids, OSM sources, Bali's range, Menorca's REE mix, adapter, issue, GET /energy and the Place map's cells")
sys.exit(0)
