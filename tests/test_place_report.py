"""The Place report (docs/SPEC_place_report.md §4, §5, §6, §8): the sheet's grid in metres, its legend, the house blurred
to its res-10 cell, the pages after it and their count, and no text closer than the res-8 cell. app/static/doors-sheet.js
is required as it is, and doors-placemap.js and doors-place.js are booted in node with a map that does nothing and a deck
that records its layers, and #place/report drawn by report() itself, on node #1's capture
(app/issues/fixtures/node1-2026-10-06-figures.json). The capture goes in through stdin, never argv: Linux CI caps argv at
128 KB. Nothing here needs a browser; the print itself is the visual gate's `report` stage."""
import json
import math
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "app/issues/fixtures/node1-2026-10-06-figures.json"

PROG = r"""
const fs = require('fs'), vm = require('vm'), d3 = require('./app/static/d3.min.js');
const L = require('./app/static/doors-load.js');
const F = JSON.parse(fs.readFileSync(0, 'utf8')), D = L.buildD({ ...F, days: F.issues_days }, 'en'), D0 = L.buildD({ ...F, days: F.issues_days, earth: null }, 'en');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const src = ['doors-cake.js', 'doors-draw.js', 'doors-sheet.js', 'doors-placemap.js', 'doors-place.js'].map(f => fs.readFileSync('./app/static/' + f, 'utf8')).join('\n');
const pm = fs.readFileSync('./app/static/doors-placemap.js', 'utf8');
const HOME = D.geometry.ladder.find(l => l.res === 10).id, AWAY = '8a95a4c84ffffff';
/* node #1's res-8 cell as GET /geo/cell rings it: [id, lat, lng, …], six decimals */
const C8 = ['8895a4c843fffff', -8.812929, 115.160071, -8.817406, 115.159467, -8.82056, 115.16294, -8.819237, 115.167017, -8.814759, 115.167621, -8.811605, 115.164148];
const HOUSE = ['x', -8.8196, 115.1641, -8.8199, 115.1646, -8.8195, 115.1650, -8.8190, 115.1649, -8.8188, 115.1644, -8.8191, 115.1640];
/* the node's answers: which res-10 cell each point is in. sc-19874 and the model stack on the house's point are in the
   house's cell; sc-19236 and the sea model are not */
const cellOf = p => /lat=-8\.820080|lat=-8\.819052/.test(p) ? HOME : AWAY;
const CAPS = [{ id: 1, kind: 'phone', at: [-8.8191, 115.1645], cell: HOME, analysis: { confirmed_by: 'T', findings: [{ scientific: 'Hibiscus rosa-sinensis' }] } },
  { id: 2, kind: 'phone', at: [-8.8150, 115.1700], cell: AWAY, analysis: { confirmed_by: 'T', findings: [{ scientific: 'Plumeria rubra' }] } }];
const noop = () => {};
const el = () => ({ innerHTML: '', textContent: '', hidden: false, style: {}, dataset: {}, kids: [], className: '', attrs: {}, setAttribute(k, v) { this.attrs[k] = v; },
  getAttribute(k) { return this.attrs[k]; }, appendChild(x) { this.kids.push(x); }, append(...x) { this.kids.push(...x); }, querySelector: () => null, querySelectorAll: () => [],
  addEventListener: noop, remove: noop, focus: noop, closest: () => null, contains: () => false, getContext: () => ({ setTransform: noop, clearRect: noop }), clientWidth: 900, clientHeight: 560 });
/* GET /hydro, token-only on the node: the nearest river in the pack's sentence, and its attribution */
const HYDRO = { nearest: { dist_m: 3555 }, sentence: 'Tukad Mati, 3.6 km away', largest_sentence: '21.9 km to Tukad Badung', attribution: 'Rivers and basins: HydroSHEDS, as published in HydroATLAS v1.0 under CC-BY 4.0.' };
async function boot(tok, D) {
  const els = {}, map = el(), shots = [], styles = [];
  let last = [];
  const ask = p => {
    if (!tok && (L.DOORS_LOCKED.test(p) || p === '/hydro')) return Promise.resolve(new Response('{}', { status: 403 }));
    const b = p.startsWith('/geo/cell?id=' + HOME) ? { id: HOME, ring: HOUSE } : p === '/geo/cell?id=' + C8[0] ? { id: C8[0], ring: C8 } : p === '/hydro' ? HYDRO : p.startsWith('/geo/cell?lat=') ? { id: cellOf(p) }
      : p.startsWith('/captures') ? CAPS : p.startsWith('/species') ? { species: [{ name: 'Plumeria rubra', rank: 'SPECIES' }] } : p.startsWith('/place/maps') ? { maps: [], palette: {} } : {};
    return Promise.resolve(new Response(JSON.stringify(b), { status: 200 }));
  };
  const layer = function (props) { return { id: props && props.id, props }; };
  const c = { D, d3, console, Response, URL, doorsLocal: L.doorsLocal, setTimeout, clearTimeout, $: q => (els[q] ||= el()), DOORS_TOKEN: () => (tok ? 't' : ''), DOORS_AUTH: () => ({}),
    doorsFetch: ask, UNLOCK_AT: 'Set up › This screen', sign: id => `<svg data-s="${id}"></svg>`, lastRaw: () => null, plain: s => s, hhmm: s => s, when: s => s, scrollTo: noop,
    dLabel: s => s, dayOf: s => s, CLOCK: { reduced: () => true, on: noop, off: noop }, view: () => 'place', location: { origin: 'http://node', hash: '#place' }, devicePixelRatio: 1,
    localStorage: { getItem: () => null, setItem: noop }, requestAnimationFrame: f => setTimeout(f, 0),
    document: { documentElement: { dataset: {} }, body: { classList: { toggle: noop } }, querySelector: () => null, querySelectorAll: () => [], createElement: () => el(), getElementById: () => null, activeElement: null,
      fullscreenEnabled: true, fullscreenElement: null, addEventListener: noop },
    maplibregl: { ScaleControl: function () {}, Map: function (opts) { return Object.assign(map, { opts, on: noop, once: (t, f) => f(), addControl: noop, getContainer: () => map,
      triggerRepaint: noop, getLayer: () => null, loaded: () => true, resize: noop, setStyle: s => styles.push(s.layers[0].paint['background-color']),
      getCanvas: () => ({ width: 1800, height: 1120, clientWidth: 900, clientHeight: 560, toDataURL: () => { shots.push(last.map(l => ({ id: l.id, data: l.props.data }))); return 'data:image/png;base64,AAAA'; } }),
      touchZoomRotate: { disableRotation: noop }, doubleClickZoom: { enable: noop, disable: noop }, getZoom: () => 14.5, getCenter: () => ({ lng: 115.164, lat: -8.819 }),
      project: ([x, y]) => ({ x: x * 1e4, y: -y * 1e4 }), unproject: ([x, y]) => ({ lng: x / 1e4, lat: -y / 1e4 }), easeTo: noop }); } },
    deck: new Proxy({}, { get: (t, k) => k === 'MapboxOverlay' ? function () { return { _deck: {}, setProps: x => { if (x.layers) last = x.layers; } }; } : layer }) };
  c.window = c; vm.createContext(c);
  vm.runInContext(['esc', 'fmt', 'num', 'said', 'loc', 'wdhm', 'SAT', 'PROV', 'prov', 'ISSUES_DRAWN', 'VIEWS'].map(pick).join('\n') + '\n' + src + '\nwindow.placeMap()', c);
  await new Promise(r => setTimeout(r, 80));
  c.__PM.on.models = true; c.__PM.on.rings = true;   /* the model stack sits on the house's point; the rings are centred on it */
  const s = await c.placeSheet(true);
  /* then #place/report as the page draws it: the sheet and the pages after it */
  c.location.hash = '#place/report'; await c.report();
  return { s, shot: shots[0] || null, styles, after: { sheet: c.__PM.sheet, ids: last.map(l => l.id) },
    html: c.sheetHTML(D, { ...s, img: s.img ? 'data:image/png;base64,AAAA' : undefined }, C8), report: els['#psheets'].innerHTML };
}
(async () => {
  const S = require('./app/static/doors-sheet.js');
  const LAYERS = eval(pm.match(/const LAYERS = \[[\s\S]*?\n\];/)[0] + '; LAYERS');
  global.cakeSections = require('./app/static/doors-cake.js').cakeSections; vm.runInThisContext(pick('esc').replace('const esc', 'global.esc'));
  const odbl = S.reportPages(D, { date: '2026-11-16', figures: 'f', cake: [], change: null, credits: ['© OpenStreetMap contributors · Protomaps', 'Natural Earth', 'Natural Earth'] });
  const grid = [];
  for (let m = 50; m <= 40000; m *= 1.002) for (const [w, h] of [[900, 560], [560, 900], [1440, 640]]) {
    const g = S.gridLines(w, h, m / Math.max(w, h)); grid.push([m, g.step, (w >= h ? g.xs : g.ys).length]);
  }
  const on = { own: true, public: true, wind: false, satonly: true, street: true, mine: true, images: true, rivers: true, terrain: true, species: false };
  console.log(JSON.stringify({ grid, legend: S.sheetLegend(LAYERS, on, 13), legendFar: S.sheetLegend(LAYERS, on, 11), tok: await boot(true, D), locked: await boot(false, D), bare: await boot(true, D0), odbl,
    point: D.point, version: D.health.version, name: D.node.name, home: HOME }));
})();
"""

out = subprocess.run(["node", "-e", PROG], input=FIX.read_text(), capture_output=True, text=True, cwd=ROOT)
assert out.returncode == 0, out.stderr[-3000:]
R = json.loads(out.stdout)

# the grid: a round step with five to eight lines on the longer side, from 50 m to 40 km across, either way up
bad = [g for g in R["grid"] if not 5 <= g[2] <= 8]
assert not bad, f"{len(bad)} widths give a grid of other than five to eight lines, e.g. {bad[:4]}"
steps = {g[1] for g in R["grid"]}
assert all(round(s / 10 ** math.floor(math.log10(s)), 6) in (1, 2, 2.5, 5) for s in steps), sorted(steps)
print(f"  report: the grid gives five to eight lines on the longer side at every width from 50 m to 40 km ({len(steps)} round steps)")

# the legend: the layers on and in view, under their cake section, in the cake's order, each with its source
assert R["legend"] == [
    {"name": "microclimate", "rows": [{"name": "Outdoor kit", "src": "this house"}, {"name": "Stations", "src": "nearby"}]},
    {"name": "built", "rows": [{"name": "Satellite only", "src": "satellite"}]},
    {"name": "water", "rows": [{"name": "Rivers", "src": "HydroRIVERS"}]},
    {"name": "ground", "rows": [{"name": "Terrain", "src": "GLO-30"}]},
    {"name": "frame", "rows": [{"name": "Node cell", "src": "H3"}, {"name": "Street map", "src": "OSM"}, {"name": "Images", "src": "this house"}]},
], R["legend"]
assert [s["name"] for s in R["legendFar"]] == ["microclimate", "water", "ground", "frame"], "a layer out of its zoom is not in the legend"
print("  report: the legend lists the layers on, under their section of the cake, in its order, with their sources")

T = R["tok"]
shot = {l["id"]: l.get("data") for l in T["shot"]}   # a layer the stub gives no data (the seven cells: no /place/cells here) has none
house = R["home"]
assert "node" not in shot and shot.get("house") == [{"ring": [[115.1641, -8.8196], [115.1646, -8.8199], [115.165, -8.8195], [115.1649, -8.819], [115.1644, -8.8188], [115.164, -8.8191], [115.1641, -8.8196]]}], \
    ("on the sheet the house is its res-10 cell, filled, and not the ring at its point", shot.get("house"), list(shot))
assert [s["sensor_id"] for s in shot["own"]] == ["sc-19236"], ("no kit inside the house's res-10 cell is a point", shot["own"])
assert [c["id"] for c in shot["images"]] == [2] and [d["c"]["id"] for d in shot["species"]] == [2], "no image inside the house's cell is a point, nor its species"
assert all(g["ss"][0]["sensor_id"] == "marine-point" for g in shot["models"]) and shot["models"], ("the model stack on the house's point is left off", shot["models"])
assert "rings" not in shot and "measure" not in shot, "nothing drawn round the house's point"
assert T["styles"] == ["#DCE2E6", "#0E1012"] * 2 and T["after"]["sheet"] is None and "node" in T["after"]["ids"] and "house" not in T["after"]["ids"], \
    ("Paper draws the light palette for the picture, then the screen is black again and draws as before; twice, the second report()'s", T["styles"], T["after"])
assert [s["name"] for s in T["s"]["legend"]][:1] == ["microclimate"] and "Rings" not in json.dumps(T["s"]["legend"]), "the rings are not drawn on the sheet, so not in its legend"
print("  report: the sheet's layers hold no kit, model or image point inside the house's res-10 cell, only the cell, and the screen comes back")

# no text on the sheet holds the house's point, with the token, where /health gives this screen the point itself
lon, lat = R["point"]
html = T["html"]
for v in (lat, lon):
    for t in {f"{v}", f"{v:.3f}", f"{v:.4f}"}:
        assert t not in html, f"the sheet says {t}, the house's point"
assert "-8.8161, 115.1635" in html and "cell 8895a4c843fffff" in html and "Cell, res" in html, "the coordinates line is the res-8 cell's centre and id"
assert f"Made on PLANETAI {R['version']}" in html and "Natural Earth" in html, "the credits and the version"
assert re.search(r"\d+(\.\d+)? km across · grid \d", html), "the sheet's width and grid step"
print("  report: no text on the sheet is closer than the res-8 cell; the coordinates are its centre")

X = R["locked"]
assert X["shot"] is None and "img" not in X["s"] and "stays on this house’s own screens" in X["html"] and "<svg" not in X["html"], \
    ("without the token no picture is taken and the node's sentence stands where the map would be", X["html"][:300])
for v in (lat, lon):
    assert f"{v}" not in X["html"]
print("  report: without the token the sheet has no map, only the node's sentence")


# the pages after the sheet (§5): four with satellite years, each with its head line, and three without them, where What
# changed is left out and N counts the pages that are there
def pages(html):
    return re.findall(r'<article class="rpage"[^>]*>(.*?)</article>', html, re.S)
name, cite = R["name"], f"{R['name']}, Place report, cell 8895a4c843fffff, PLANETAI {R['version']}, made "
for k, n in (("tok", 4), ("locked", 4), ("bare", 3)):
    rep = R[k]["report"]
    P = pages(rep)
    assert rep.index('class="sheet"') < rep.index('class="rpage"') and len(P) == n, (k, len(P), rep[:300])
    assert re.findall(r'<p class="rhead">(.*?)</p>', rep) == [f"{name} · Place report · page {i} of {n}" for i in range(1, n + 1)], (k, re.findall(r'<p class="rhead">(.*?)</p>', rep))
    assert "the place in figures" in P[0] and "what the node holds about its place" in P[1] and "sources and how to cite" in P[-1], k
    assert ("what changed, year on year" in rep) == (n == 4), (k, "What changed is a page only with satellite years")
    assert re.search(re.escape(cite) + r"\d{4}-\d\d-\d\d\.</p>", P[-1]), (k, "the citation line", P[-1][-400:])
print("  report: the pages follow the sheet, each with its head line; without satellite years What changed is left out and N is 3")

T = pages(R["tok"]["report"])
cake = re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>", T[1])
sec = re.findall(r'<th colspan="4">(.*?)</th>', T[1])
assert sec == ["results", "microclimate", "flows", "built", "animals", "plants", "soil", "water", "ground", "frame"], sec
rows = {r[0]: r[1:] for r in cake}
assert rows["Terrain"] == ("GLO-30", "not yet", ""), rows["Terrain"]
assert rows["Rivers"][1:] == ("not yet", "<code>planetai run hydro fetch</code>"), ("an empty row says the command that fills it", rows["Rivers"])
assert rows["Satellite"][1:] == ("held in part", "<code>planetai run earth-engine basemap</code>"), ("Sentinel-2 years and no map layer", rows["Satellite"])
assert rows["Land change"][1][:12] == "held in part" and "comparisons · a count, not a shape" in rows["Land change"][2], rows["Land change"]
assert rows["Outdoor kit"] == ("this house", "held", "") and rows["Node cell"] == ("H3", "held", ""), rows
assert "pill pv-model" in T[0] and "Tukad Mati" in T[0] and "pill pv-model" in T[2], "each figure keeps its provenance word as prov() draws it"
# two distances from the house at 0.1 km, to two rivers, place it closer than its res-8 cell: a report says whole km
assert "Tukad Mati, 4 km away" in T[0] and "22 km to Tukad Badung" in T[0] and not re.search(r"\d\.\d km", T[0]), ("river distances on the report are whole km", T[0])
assert "Contains modified Copernicus Sentinel data" in T[3] and "AlphaEarth Foundations" in T[3] and "HydroSHEDS, as published in HydroATLAS" in T[3] and "Natural Earth" in T[3], T[3]
O = pages(R["odbl"])
assert len(O) == 3 and O[2].count("<p>Natural Earth</p>") == 1 and "<p>A map made from OpenStreetMap is a Produced Work under the ODbL, so it carries the credit and nothing more.</p>" in O[2], O[-1]
print("  report: page 2 is the cake, section by section, each row held, in part or not yet, with its source and the command that fills it; page 4 owes every credit once, and the ODbL line where OpenStreetMap is one")

X = pages(R["locked"]["report"])
xr = {r[0]: r[1:] for r in re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>", X[1])}
assert xr["Images"][:2] == ("token-only", "withheld") and xr["Species"][:2] == ("token-only", "withheld") and "Rivers<small>" not in X[0] and "HydroSHEDS, as published" not in X[3], \
    ("without the token the pages carry what a tokenless screen sees", xr)
print("  report: without the token the pages carry the cake's rows with their sources and the yearly figures, and no river")

# no page holds the house's point, nor the species the household confirmed
for k in ("tok", "locked", "bare"):
    rep = "".join(pages(R[k]["report"]))
    for v in (lat, lon):
        for t in {f"{v}", f"{v:.3f}", f"{v:.4f}", f"{v:.5f}"}:
            assert t not in rep, f"{k}: a page says {t}, the house's point"
    assert "Plumeria" not in rep and "Hibiscus" not in rep, f"{k}: a page names a species"
print("  report: no page holds the house's point or the species list")

# Arriving from Place itself (Download, the Tools row, Ask's button) finds the map up and its tiles still coming, so
# loaded() is false and 'load', which fires once, never comes again: the picture waited for ever (16 Nov). The gate's
# report stage walks that path; this holds the line in the source.
SRC = open("app/static/doors-placemap.js").read()
body = SRC[SRC.index("async function placeSheet"):SRC.index("async function mapFile")]
assert "once('load'" not in body and "once('idle'" in body, "placeSheet must not wait on a 'load' that has already fired"
print("  report: the picture is taken when the map is idle, so it comes from Place as well as from a fresh page")

# The energy layer labels the house's own cell with its roof when the token shows it. That is the household's, and a
# sheet leaves the house: on a sheet the cells carry the plants' MW only, and the rings stay off.
assert "cellMW(c, SH ? null : E.household)" in SRC and "if (L.rings && RINGS && !SH)" in SRC, \
    "on a sheet the energy cells must not carry the house's roof, and the rings must stay off"
print("  report: the energy cells on a sheet carry the plants' MW, never the house's roof")

# Node #1's print run, 16 Nov: the drone pin's label printed dark on its dark chip on Paper, and rivers() threw when the
# band was redrawn while /hydro was on its way.
PSRC = open("app/static/doors-place.js").read()
pins = SRC[SRC.index("id: 'drone-pins-l'"):SRC.index("id: 'drone-pins-l'") + 400]
assert "getColor: [249, 245, 242, 255]" in pins, "the drone pin's label must be light on its dark chip in both registers"
assert "if (H.nearest && go) go.onclick" in PSRC, "rivers() must not assume the link is still there after its fetch"
print("  report: the drone pin reads on Paper; the Rivers link survives a redraw")

# The grid's labels are pixels times metres a pixel, so 999.97 m came out "1000 m" beside "2 km" (node #1, 16 Nov).
lab = subprocess.run(["node", "-e", "const s=require('fs').readFileSync('app/static/doors-sheet.js','utf8');"
                      "eval(s.match(/const gridM = [^\\n]*/)[0].replace('const gridM','globalThis.gridM'));"
                      "console.log([999.97, 1000, 1999.96, 500, 2500].map(gridM).join('|'))"], capture_output=True, text=True)
assert lab.stdout.strip() == "1 km|1 km|2 km|500 m|2.5 km", lab.stdout + lab.stderr
print("  report: a grid label is rounded before it is called metres or km")

# The report is offered at the foot of Place, with what it is (Tomas, 17 Nov 2026: "more visible in the bottom of the
# place tab, explaining what the report does"). It is written for whoever reads it, so it names nobody.
HTML = open("app/static/doors.html").read()
assert HTML.index('class="plow"') < HTML.index('id="preportfoot"') < HTML.index('id="preport"'), "the block is the last thing on Place, before the report itself"
foot = HTML[HTML.index('id="preportfoot"'):HTML.index('id="preport"')]
for s in ("The Place report", "This place on paper, to hand to the neighbours, the council or a funder.",
          "A plan of the map as you have it on screen.", "Your browser prints it or saves it as a PDF.",
          'data-prf="paper"', 'data-prf="screen"', ">Open the report<", ">Dark version<", 'id="prfwho"'):
    assert s in foot, s
assert not re.search(r"mumford|mcharg|papanek|meadows|jacobs", foot, re.I)
assert "data-open-report" not in foot, "the Ask pane's button owns data-open-report; the gate presses it by that name"
assert "#preportfoot [data-prf]" in PSRC and "window.placeReport(b.dataset.prf)" in PSRC, "its buttons open the report in their register"
assert "window.placeNoMap = NOMAP" in SRC and "window.placeNoMap" in PSRC[PSRC.index("#prfhow"):PSRC.index("#prfhow") + 300], "without the token it says where the map of the house stays, in the sheet's own sentence"
print("  report: the foot of Place says what the report is and opens it")
