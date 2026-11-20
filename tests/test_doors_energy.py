"""The energy panel on Now (app/static/doors-now.js :: drawEnergy): estimated range with hatched cable segment,
measured share with right-now figure, unknown cable share (import_max == null), and no grid (empty sources).

JSON goes through a temp file, never argv, because of the 128 KB E2BIG limit on Linux CI.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

fails: list[str] = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


if not shutil.which("node"):
    print("  ✓ doors-energy: node not installed (skipped)")
    sys.exit(0)

CASES = {
    "estimated": {
        "grid": "bali",
        "kind": "estimated",
        "method": "capacity-factors",
        "months": None,
        "import_max": 0.25,
        "share": {"low": 0.95, "high": 0.98, "value": None, "now": None, "stale": False, "as_of": "2026-11-08T06:00:00+00:00"},
        "bar": [
            {"label": "coal", "fossil": True, "share": 0.31, "hatched": False},
            {"label": "gas & oil", "fossil": True, "share": 0.42, "hatched": False},
            {"label": "Java–Bali 150 kV submarine cables", "fossil": True, "share": 0.25, "hatched": True, "note": "share not published"},
            {"label": "solar", "fossil": False, "share": 0.02, "hatched": False},
        ],
        "sources": [
            {"name": "GIS Pecatu", "kind": "substation", "fuel": None, "mw": None, "km": 2.4, "ring": "city", "fossil": None},
            {"name": "PLTDG Pesanggaran", "kind": "plant", "fuel": "gas", "mw": 336.0, "km": 12.0, "ring": "city", "fossil": True},
            {"name": "PLTU Celukan Bawang", "kind": "plant", "fuel": "coal", "mw": 380.0, "km": 77.0, "ring": "region", "fossil": True},
            {"name": "Java–Bali 150 kV submarine cables", "kind": "link", "fuel": None, "mw": None, "km": 95.8, "ring": "beyond", "fossil": True},
        ],
        "today": {"sun_kwh_m2": 5.8, "roof_kwh": 8.7, "use_kwh": 9.0, "measured": False},
        "household": None,
        "attribution": ["© OpenStreetMap contributors, ODbL, via Overpass", "Ember Yearly Electricity Data (CC BY 4.0)"],
    },
    "measured": {
        "grid": "balearic",
        "kind": "measured",
        "method": "ree-balearic",
        "months": 12,
        "share": {"low": None, "high": None, "value": 0.41, "now": 0.38, "stale": False, "as_of": "2026-11-08T06:00:00+00:00"},
        "bar": [
            {"label": "Combined cycle", "fossil": True, "share": 0.33, "hatched": False},
            {"label": "Diesel engines", "fossil": True, "share": 0.08, "hatched": False},
            {"label": "Mallorca–Menorca link", "fossil": False, "share": 0.47, "hatched": False, "tone": "sky"},
            {"label": "Solar PV", "fossil": False, "share": 0.12, "hatched": False},
        ],
        "sources": [
            {"name": "SE Es Mercadal", "kind": "substation", "fuel": None, "mw": None, "km": 14.2, "ring": "city", "fossil": None},
            {"name": "CT Mahón", "kind": "plant", "fuel": "gas", "mw": 245.0, "km": 1.8, "ring": "city", "fossil": True},
            {"name": "Son Salomó PV", "kind": "plant", "fuel": "solar", "mw": 50.0, "km": 32.0, "ring": "city", "fossil": False},
            {"name": "Peninsula–Mallorca–Menorca link", "kind": "link", "fuel": None, "mw": None, "km": 38.0, "ring": "beyond", "fossil": False},
        ],
        "today": {"sun_kwh_m2": 3.9, "roof_kwh": 2.7, "use_kwh": None, "measured": False},
        "household": {"roof_w": 3120.0, "grid_w": 0.0, "battery_w": 1200.0, "fossil_pct": 18.0},
        "attribution": ["Red Eléctrica de España · apidatos.ree.es", "© OpenStreetMap contributors, ODbL, via Overpass"],
    },
    "unknown_cable": {
        "grid": "bali",
        "kind": "estimated",
        "method": "capacity-factors",
        "months": None,
        "import_max": None,
        "share": {"low": 0.8419, "high": 0.9896, "value": None, "now": None, "stale": False, "as_of": "2026-11-08T06:00:00+00:00"},
        "bar": [
            {"label": "gas", "fossil": True, "share": 0.56, "hatched": False},
            {"label": "coal", "fossil": True, "share": 0.42, "hatched": False},
            {"label": "Java–Bali 150 kV submarine cables", "fossil": True, "share": None, "hatched": True, "note": "share not published"},
            {"label": "solar", "fossil": False, "share": 0.01, "hatched": False},
        ],
        "sources": [
            {"name": "GIS Pecatu", "kind": "substation", "fuel": None, "mw": None, "km": 2.4, "ring": "city", "fossil": None},
            {"name": "PLTDG Pesanggaran", "kind": "plant", "fuel": "gas", "mw": 336.0, "km": 12.0, "ring": "city", "fossil": True},
            {"name": "Java–Bali 150 kV submarine cables", "kind": "link", "fuel": None, "mw": None, "km": 95.8, "ring": "beyond", "fossil": True},
        ],
        "today": {"sun_kwh_m2": 5.4, "roof_kwh": 3.8, "use_kwh": None, "measured": False},
        "household": None,
        "attribution": ["© OpenStreetMap contributors, ODbL, via Overpass", "Ember Yearly Electricity Data (CC BY 4.0)"],
    },
    "none": {
        "grid": None,
        "kind": None,
        "method": None,
        "months": None,
        "share": {"low": None, "high": None, "value": None, "now": None, "stale": False, "as_of": "2026-11-08T06:00:00+00:00"},
        "bar": [],
        "sources": [],
        "today": {"sun_kwh_m2": None, "roof_kwh": None, "use_kwh": None, "measured": False},
        "household": None,
        "attribution": [],
    },
}

with tempfile.TemporaryDirectory() as tmp:
    in_path = Path(tmp) / "cases.json"
    # the Today box: no sun forecast keeps the use and says why; a roof Home Assistant measured is not called modelled
    CASES["nosun"] = {**CASES["estimated"], "today": {"sun_kwh_m2": None, "roof_kwh": None, "use_kwh": 9.0, "measured": False, "panel_kw": 2.0}}
    CASES["roofmeasured"] = {**CASES["estimated"], "today": {"sun_kwh_m2": 5.8, "roof_kwh": 3.4, "use_kwh": 9.0, "measured": True, "panel_kw": 2.0}}
    in_path.write_text(json.dumps(CASES))
    prog = f"""
const fs = require('fs'), vm = require('vm');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8');
const now = fs.readFileSync('./app/static/doors-now.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const fn = (src, n) => {{
  const m = src.match(new RegExp('function ' + n + '[\\\\s\\\\S]*?\\\\n}}\\\\n'));
  return m ? m[0] : '';
}};
const cases = JSON.parse(fs.readFileSync({json.dumps(str(in_path))}, 'utf8'));
const els = {{}};
const ctx = {{
  D: {{
    now: 0,
    buckets: ['2026-11-08T06:00:00+08:00'],
    dates: ['2026-11-08'],
    at: {{ '2026-11-08|6': 0 }},
    order: ['air', 'energy'],
    labels: {{ room: 'house', yard: 'street', ring: 'ring', region: 'model' }},
    buttons: {{ done: 'Done', not_now: 'Not now', doesnt_fit: 'Doesn’t fit' }},
    events: [],
    node: {{ name: 'node1', place: 'bali' }},
    health: {{ cell: {{}} }},
    geometry: {{ ladder: [] }},
    energy: cases.estimated,
    issues: {{
      air: {{ name: 'Air', state: 'quiet', dp: 0, unit: 'µg/m³', line: 15, hero_distance: 'room',
              sentence: 'Clean air.', stack: {{ room: {{ value: 8, provenance: 'live', source: 's1' }} }},
              series: {{ room: [8] }}, per_day: [], provenance: {{ room: 'live' }}, asking: [] }},
      energy: {{ name: 'Energy', state: 'partial', dp: 0, unit: '%', line: null, hero_distance: 'region',
                 sentence: 'Around 95–98% of the grid’s electricity is from fossil fuels.',
                 tagline: 'Estimated from installed capacity · 4 sources mapped',
                 stack: {{ region: {{ value: 96.5, provenance: 'partial', source: 'energy-grid' }} }},
                 series: {{ room: null, yard: null, ring: null, region: null }}, per_day: [], provenance: {{ region: 'model' }}, asking: [] }},
    }},
  }},
  S: {{ issue: 'energy', i: 0 }},
  innerWidth: 1280,
  $: q => (els[q] ||= {{ innerHTML: '', textContent: '', hidden: true, style: {{ setProperty() {{}} }} }}),
  document: {{ querySelectorAll: () => [] }},
  doorsLocal: iso => '2026-11-08T06:00',
  stateWord: s => s,
  kindWord: s => s,
  rampHTML: () => '',
  dayWeek: () => {{ els._dayWeekCalled = true; }},
  doorsFetch: () => Promise.resolve({{ ok: true, json: () => Promise.resolve(cases.estimated) }}),
}};
vm.createContext(ctx);
vm.runInContext(
  ['esc', 'WD', 'loc', 'dayOf', 'dLabel', 'fmt', 'said', 'num', 'NODE', 'sign', 'PROV', 'prov', 'ISSUES_DRAWN'].map(pick).join('\\n')
  + '\\nlet NOWL = null, ENERGY = undefined; function nowRemember() {{}} function evAt() {{ return []; }} function answerWords() {{ return {{}}; }} function val() {{ return null; }} function stripFold() {{}}\\n'
  + ['usualLine', 'loadEnergy', 'drawEnergy', 'drawNow', 'readout', 'decision', 'rows', 'rowsValues'].map(n => fn(now, n)).join('\\n'),
  ctx
);
if (typeof ctx.drawEnergy !== 'function') {{
  console.log(JSON.stringify({{ error: 'drawEnergy not defined' }}));
  process.exit(0);
}}
const out = {{}};
for (const [k, body] of Object.entries(cases)) {{
  const el = {{ innerHTML: '', hidden: true }};
  ctx.drawEnergy(el, body);
  out[k] = el.innerHTML;
}}
ctx.rows();
ctx.drawNow();
out._now = {{
  energyHidden: els['#energy'].hidden,
  svgDisplay: els['#svg'].style.display,
  dayWeekCalled: !!els._dayWeekCalled,
  energyHTML: els['#energy'].innerHTML,
  rowsHTML: els['#rows'].innerHTML,
}};
const mob = fs.readFileSync('./app/static/mobile.js', 'utf8');
const mctx = {{}};
vm.createContext(mctx);
vm.runInContext(['esc', 'fmt', 'num'].map(pick).join('\\n') + '\\n' + fn(mob, 'energyHTML'), mctx);
out._mobile = typeof mctx.energyHTML === 'function' ? mctx.energyHTML(cases.estimated) : '';
console.log(JSON.stringify(out));
"""
    proc = subprocess.run(["node"], input=prog, capture_output=True, text=True, check=True)
    res = json.loads(proc.stdout)

if "error" in res:
    check(False, f"drawEnergy missing: {res['error']}")
else:
    est = res.get("estimated", "")
    check("95–98%" in est, f"estimated body renders 95–98%: {est[:200]}")
    check('class="hatch"' in est or " hatch" in est, f"estimated body renders a hatched segment: {est[:400]}")
    check("pv-model" in est, f"estimated body provenance is model: {est[-300:]}")
    check(bool(re.search(r'data-num="[^"]+"\s+data-cmp="[^"]+"', est)), "estimated body numerals carry data-num and data-cmp")

    meas = res.get("measured", "")
    check("41%" in meas and "–" not in meas.split("</div>")[0], f"measured body renders one figure (41%): {meas[:200]}")
    check("right now" in meas.lower() and "38%" in meas, f"measured body renders 'right now' with 38%: {meas[:300]}")
    check("pv-live" in meas, f"measured body provenance is live: {meas[-300:]}")
    check("3,120" in meas or "3120" in meas, f"measured body renders household roof_w when present: {meas}")

    unk = res.get("unknown_cable", "")
    check("84–99%" in unk, f"body with import_max == null renders 84–99%: {unk[:200]}")
    check("how much comes from java is not known" in unk.lower(),
          f"body with import_max == null says how much comes from Java is not known: {unk}")

    none_html = res.get("none", "")
    check("on no grid the energy pack knows yet" in none_html and "packs/energy/grids.yml" in none_html,
          f"empty sources renders the none sentence: {none_html}")
    check('class="mixbar"' not in none_html, f"empty sources renders no bar: {none_html}")
    # the bar is not called "bar": that is the top bar's class, whose padding drew the mix as an empty box on node #1
    check('class="mixbar"' in est and 'class="bar"' not in est, f"the mix bar has its own class: {est[:400]}")

    check("uses about" in est and "9.0" in est, f"the Today box draws the house's use: {est[-700:]}")
    ns = res.get("nosun", "")
    check("No forecast of the sun today" in ns and "uses about" in ns and "kW of roof panels" not in ns,
          f"no sun forecast: the use stays, the roof goes, and it says why: {ns[-700:]}")
    rm = res.get("roofmeasured", "")
    check("measured by Home Assistant" in rm and "modelled from" not in rm, f"a measured roof is not called modelled: {rm[-700:]}")

    nw = res.get("_now") or {}
    check(nw.get("energyHidden") is False and nw.get("svgDisplay") == "none" and not nw.get("dayWeekCalled"),
          f"drawNow on energy shows #energy in place of dayWeek on #svg: {nw}")
    check('data-k="energy"' in (nw.get("rowsHTML") or ""),
          f"the energy issue row in #rows stays: {nw.get('rowsHTML')}")

    mob_html = res.get("_mobile") or ""
    check("95–98%" in mob_html and "GIS Pecatu" in mob_html,
          f"mobile.js energyHTML renders range and sources: {mob_html}")

# ── Task 10: the Place map's energy row (app/static/doors-placemap.js :: energyRows, cellMW, creditList) ─────────
SRC = [{"name": "GIS Pecatu", "kind": "substation", "fuel": None, "mw": None, "km": 2.4, "ring": "city", "lat": -8.80, "lon": 115.14},
       {"name": "PLTG Pesanggaran", "kind": "plant", "fuel": "gas", "mw": 200.0, "km": 12.0, "ring": "city", "lat": -8.72, "lon": 115.21}]
PLACE = {
    "held": {**CASES["estimated"], "sources": SRC, "counts": {"plants": 9, "substations": 22}, "cells": []},
    "locked": {**CASES["estimated"], "sources": [{k: v for k, v in s.items() if k not in ("lat", "lon")} for s in SRC],
               "counts": {"plants": 9, "substations": 22}, "cells": None},
    "nogrid": {"grid": None, "sources": [], "counts": None, "cells": None},
    "off": None,
}
with tempfile.TemporaryDirectory() as tmp:
    in_path = Path(tmp) / "place.json"
    in_path.write_text(json.dumps(PLACE))
    pprog = f"""
const fs = require('fs'), vm = require('vm'), pm = fs.readFileSync('./app/static/doors-placemap.js', 'utf8');
const lift = n => pm.match(new RegExp('^function ' + n + '\\\\([\\\\s\\\\S]*?\\\\n}}\\\\n', 'm'))[0];
const cases = JSON.parse(fs.readFileSync({json.dumps(str(in_path))}, 'utf8')), out = {{}};
for (const [k, E] of Object.entries(cases)) {{
  const c = {{ PM: {{ on: {{ energy: true }}, energy: E, map: null, meta: null }}, SAT_MAX: 15 }};
  vm.createContext(c);
  vm.runInContext(pm.match(/const LAYERS = \\[[\\s\\S]*?\\n\\];/)[0] + '\\n' + lift('energyRows') + lift('creditList')
    + pm.match(/^const cellMW = .*$/m)[0] + '\\nenergyRows(); this.row = LAYERS.find(l => l.id === "energy"); this.credits = creditList();'
    + 'this.cell = [cellMW({{ mw: 0, home: true }}, {{ roof_w: 3120 }}), cellMW({{ mw: 0, home: false }}, {{ roof_w: 3120 }}), cellMW({{ mw: null }}, null), cellMW({{ mw: 7.5, home: true }}, null)];', c);
  out[k] = {{ row: c.row, credits: c.credits, cell: c.cell }};
}}
console.log(JSON.stringify(out));
"""
    pres = json.loads(subprocess.run(["node"], input=pprog, capture_output=True, text=True, check=True).stdout)

h = pres["held"]["row"]
check(h["cake"] == "built" and h["on"] is False, f"the energy row sits in the cake's built section and is off at first (five on): {h}")
check(h["sub"] == "9 plants, 22 substations on this grid · nearest 2.4 km" and not h["empty"] and not h.get("locked"),
      f"the built row's line, from the body: {h['sub']}")
check("power grid: © OpenStreetMap contributors, ODbL, via Overpass" in pres["held"]["credits"],
      f"the OSM credit is on the map while the layer is: {pres['held']['credits']}")
check(pres["held"]["cell"] == ["0 MW · roof 3.1 kW", "0 MW", "MW not tagged", "7.5 MW"],
      f"a cell's MW, the house's roof kW on its own cell only, and an untagged plant says so: {pres['held']['cell']}")
check(pres["locked"]["row"]["locked"] and pres["locked"]["row"]["empty"], "no token: the row is token-only, nothing drawn")
check(pres["nogrid"]["row"]["empty"] and "grids.yml" in (pres["nogrid"]["row"].get("none") or ""),
      f"a node on no grid says so, with no figure: {pres['nogrid']['row']}")
check(pres["off"]["row"]["empty"] and pres["off"]["row"]["why"] == "planetai run energy fetch"
      and not any("Overpass" in c for c in pres["off"]["credits"]), f"no /energy: an empty row and no credit: {pres['off']}")

if fails:
    print("\n".join(f"  ✗ {f}" for f in fails))
else:
    print("  ✓ doors-energy: estimated, measured, unknown cable share, no grid, and the Place map's energy row")
sys.exit(1 if fails else 0)
