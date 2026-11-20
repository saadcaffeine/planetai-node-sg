"""The Wall map's pure half (app/static/doors-wallmap.js): hour lookup, wind and swell motion maths, station features.
Run under node from here; nothing is drawn, so nothing needs a browser."""
import json
import math
import re
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

out = subprocess.run(["node", "-e", """
const W = require('./app/static/doors-wallmap.js');
const segs = W.crestSegments(800, 600, 204, 0), t = W.toward(204);
const st = [{lat: -8.7, lon: 115.2, pm25: [10, null, 40]}, {lat: -8.8, lon: 115.1, pm25: [null, null, null]}];
console.log(JSON.stringify({
  at: [W.atHour([null, null, 3, null], 0), W.atHour([1, null, null], 2), W.atHour([null, null], 1), W.atHour([5, null, 7], 1), W.atHour([1, 2, 3], 1), W.atHour([1, 2, 3], 23), W.atHour([null, 4], 23)],
  /* the dim's rings, signed area in lon/lat: the outer one and each hole */
  wind: (() => { const area = r => r.slice(1).reduce((a, [x, y], i) => a + (r[i][0] * y - x * r[i][1]), 0) / 2;
    const cells = JSON.parse(require('fs').readFileSync('tests/fixtures/wall-node1.json', 'utf8')).scales[0].cells;
    const circ = W.circleRing([115.17, -8.8], 1050);
    return { raw: cells.map(c => area(c.ring)), mask: W.maskRings(cells.map(c => c.ring)).map(area), n: W.maskRings(cells.map(c => c.ring)).length,
      circle: area(circ), hole: area(W.maskRings([circ])[1]), closed: circ[0].join() === circ[circ.length - 1].join(),
      metres: circ.map(([x, y]) => Math.hypot((x - 115.17) * 111320 * Math.cos(-8.8 * Math.PI / 180), (y + 8.8) * 110574)) }; })(),
  south: W.toward(180), n350: W.toward(350), unit: Math.hypot(W.toward(37).ux, W.toward(37).uy),
  n: segs.length, t,
  dot: segs.map(([x1, y1, x2, y2]) => (x2 - x1) * t.ux + (y2 - y1) * t.uy),
  len: segs.map(([x1, y1, x2, y2]) => Math.hypot(x2 - x1, y2 - y1)),
  gap: segs.slice(1).map((s, i) => ((s[0] + s[2]) / 2 - (segs[i][0] + segs[i][2]) / 2) * t.ux + ((s[1] + s[3]) / 2 - (segs[i][1] + segs[i][3]) / 2) * t.uy),
  shifted: W.crestSegments(800, 600, 204, 10).map(s => ((s[0] + s[2]) / 2 - 400) * t.ux + ((s[1] + s[3]) / 2 - 300) * t.uy),
  small: W.crestSegments(800, 600, 204, 0, 100).length,
  phase: [W.crestPhase(8.6, 8.6), W.crestPhase(4.3, 8.6), W.crestPhase(4.3, 8.6, 10), W.crestPhase(12.9, 8.6)],
  streak: [W.streak(10), W.streak(0)],
  feat: [0, 1, 2].map(h => W.stationFeatures(st, h, 15)), noLine: [null, undefined, NaN].map(l => W.stationFeatures(st, 2, l).features[0].properties), onWindow: typeof window,
  /* /wall's hours and /issues' buckets are two reads: joined by instant, whatever the string's offset */
  join: W.slotJoin(['2026-11-18T10:00:00+08:00', '2026-11-18T03:00:00Z', '2026-11-18T04:00:00+00:00'], [1, 2, 3], ['2026-11-18T02:00:00Z', '2026-11-18T03:00:00+00:00', '2026-11-18T12:00:00+08:00', '2026-11-18T05:00:00Z']),
  joinNone: W.slotJoin(undefined, undefined, ['2026-11-18T02:00:00Z']), joinNull: W.slotJoin(['2026-11-18T02:00:00Z'], [null], ['2026-11-18T02:00:00Z']),
  fit: [W.fitBox([[179.99, -16.1], [-179.98, -16.0], [179.97, -16.2]], 179.99), W.fitBox([[-179.99, 1], [179.99, 2]], -179.99), W.fitBox([[115.1, -8.8], [115.3, -8.6]], 115.2)],
}));
"""], capture_output=True, text=True, check=True)
R = json.loads(out.stdout)

assert R["at"] == [3, 1, None, 5, 2, 3, 4], ("a short day still has its last reading at hour 23", R["at"])
w = R["wind"]
assert w["n"] == 8 and all(a > 0 for a in w["raw"]) and w["mask"][0] > 0, ("the world and the h3 rings wind the same way", w)
assert all(a < 0 for a in w["mask"][1:]), ("each hole winds against the outer ring, or MapLibre draws it as a polygon", w)
assert w["circle"] > 0 and w["hole"] < 0 and w["closed"] and all(abs(m - 1050) < 2 for m in w["metres"]), ("the roofs' circle: closed, wound as the world, 1050 m round", w["circle"], w["hole"], min(w["metres"]), max(w["metres"]))
assert R["join"] == [1, 2, 3, None], ("joined by instant: 10:00+08 is 02:00Z, 12:00+08 is 04:00Z, 05:00Z is no slot of the series", R["join"])
assert R["joinNone"] == [None] and R["joinNull"] == [None]
_f = R["fit"]
assert _f[0] == [[179.97, -16.2], [180.02, -16.0]], ("cells either side of the antimeridian are one short span", _f[0])
assert _f[1] == [[-180.01, 1], [-179.99, 2]] and _f[2] == [[115.1, -8.8], [115.3, -8.6]], _f
assert abs(R["south"]["ux"]) < 1e-9 and abs(R["south"]["uy"] + 1) < 1e-9, R["south"]
assert R["n350"]["uy"] > 0.98 and 0 < R["n350"]["ux"] < 0.2, R["n350"]   # from the north, so down the screen, a little right
assert abs(R["unit"] - 1) < 1e-9
print("  wallmap: hours and directions")

assert R["n"] > 10 and all(abs(d) < 1e-9 for d in R["dot"]), "every crest is square to the way the swell goes"
assert all(abs(g - 26) < 1e-9 for g in R["gap"]), R["gap"][:3]
assert all(l >= (800 ** 2 + 600 ** 2) ** .5 - 1e-6 for l in R["len"]), "each line spans the box whatever the angle"
assert R["small"] < R["n"], "wider spacing, fewer crests"
assert any(abs((o - 10) % 26) < 1e-9 or abs((o - 10) % 26 - 26) < 1e-9 for o in R["shifted"]), "phase shifts the lines along the direction"
assert R["phase"][0] == 0 and abs(R["phase"][1] - 13) < 1e-9 and abs(R["phase"][2] - 5) < 1e-9 and abs(R["phase"][3] - 13) < 1e-9, R["phase"]
assert R["streak"] == [{"v": 58, "tail": 35}, {"v": 8, "tail": 10}], R["streak"]
print("  wallmap: crests, phase and streaks")

f0, f1, f2 = R["feat"]
assert f0["type"] == "FeatureCollection" and len(f0["features"]) == 2
p = lambda f, i: f["features"][i]["properties"]
assert (p(f0, 0)["v"], p(f0, 0)["over"]) == (10, False) and (p(f2, 0)["v"], p(f2, 0)["over"]) == (40, True)
assert (p(f1, 0)["v"], p(f1, 0)["over"]) == (-1, False), "a station with no reading is -1 and never over the line"
assert (p(f0, 1)["v"], p(f0, 1)["over"]) == (-1, False)
assert [(x["v"], x["over"]) for x in R["noLine"]] == [(40, False)] * 3, ("no clean-air line, no station red", R["noLine"])
assert f0["features"][0]["geometry"] == {"type": "Point", "coordinates": [115.2, -8.7]}
assert R["onWindow"] == "undefined"
print("  wallmap: stations as features")

# ---------------------------------------------------------------- the story: which chapters each scale has
# W is a /wall body (tests/fixtures/wall-node1.json, coarse values, hand-built in /wall's shape) and D the doors' /issues
# on node #1's capture, with the readouts the capture lacks added for the all-present case.
out = subprocess.run(["node", "-e", """
let M = require('./app/static/doors-wallmap.js'); const fs = require('fs');
const W0 = JSON.parse(fs.readFileSync('tests/fixtures/wall-node1.json', 'utf8'));
const cap = JSON.parse(fs.readFileSync('app/issues/fixtures/node1-2026-10-06-figures.json', 'utf8')).issues.issues;
const rd = (metric, value, unit, provenance = 'model') => ({ metric, value, unit, provenance });
const mkD = more => { const I = {}; for (const [k, it] of Object.entries(cap)) I[k] = { ...it, line: (it.line || {}).value ?? null }; return { issues: { ...I, ...more } }; };
const D0 = mkD({});
const D1 = mkD({
  heat: { ...cap.heat, line: null, readouts: [rd('lst', 34.2, '°C'), rd('lst_delta', 4.2, '°C'), rd('lst_night', 27.1, '°C')] },
  water: { readouts: [rd('rain_24h_mm', 3.4, 'mm'), rd('terrain_upslope_ha', 1.8, 'ha')] } });
const clone = o => JSON.parse(JSON.stringify(o));
const nul = ks => { const w = clone(W0); ks.forEach(k => w[k] = null); return w; };
const ks = story => story.map(s => s.chapters.map(c => c.k));
/* the node's street tiles: Buildings and the Sun light the roofs in them */
const V = { vector: true }, M0 = M; M = { ...M0, wallStory: (w, d, g = V) => M0.wallStory(w, d, g) };
const all = ['stations', 'island', 'roofs', 'lab', 'rivers', 'basin', 'river', 'grid', 'change'];
const noWater = nul(['rivers', 'basin', 'river']);
const empty = { ...nul(all), hours: { ...W0.hours } };
const noIsland = nul(['island']);
const noSun = clone(W0); noSun.grid.sun = null;
const noWave = clone(W0); delete noWave.hours.wave_from;
const genset = clone(W0); genset.grid.plants.unshift({ name: 'PLTD Genset', fuel: 'diesel', mw: 1.2, lat: -8.8, lon: 115.19, km: 2, large: false });
const noLarge = clone(W0); noLarge.grid.plants = [genset.grid.plants[0]];
console.log(JSON.stringify({
  full: M.wallStory(W0, D1), cap: ks(M.wallStory(W0, D0)), noWater: ks(M.wallStory(noWater, D1)),
  empty: M.wallStory(empty, { issues: {} }).map(s => [s.k, s.chapters.length, s.res, s.km2]), capOnly: ks(M.wallStory(empty, mkD({}))),
  noIsland: ks(M.wallStory(noIsland, D1))[2], noTiles: [ks(M0.wallStory(W0, D1))[0], ks(M0.wallStory(W0, D1, { imagery: true }))[0]], noSun: ks(M.wallStory(noSun, D1))[0], noWave: M.wallStory(noWave, D1)[2].chapters.find(c => c.k === 'sea').says,
  genset: M.wallStory(genset, D1)[2].chapters[0], noLarge: M.wallStory(noLarge, D1)[2].chapters[0],
  at: [M.chapterAt(23, 4), M.chapterAt(0, 5), M.chapterAt(23, 5), M.chapterAt(5, 4), M.chapterAt(6, 4), M.chapterAt(12, 1), M.chapterAt(24, 3)],
  names: JSON.parse(fs.readFileSync('app/issues/fixtures/node1-2026-10-06-figures.json', 'utf8')).sensors.map(s => s.name.trim()).filter(n => n.length > 3),
  lab: W0.lab.name,
  /* one fresh ring station: the engine sets the ring's source to that sensor's own name (engine.py _from_stats) */
  ring1: M.wallStory(W0, mkD({ air: { ...cap.air, line: 15, stack: { ...cap.air.stack, ring: { ...cap.air.stack.ring, n: 1, source: 'K ROOM - BAYU HOLES' } } } })),
  /* every name the node holds, put where a source or a title could carry it */
  named: (() => { const names = JSON.parse(fs.readFileSync('app/issues/fixtures/node1-2026-10-06-figures.json', 'utf8')).sensors.map(s => s.name);
    return names.map(n => M.wallStory(W0, mkD({ air: { ...cap.air, line: 15, stack: { room: { ...cap.air.stack.room, source: n }, yard: { ...cap.air.stack.yard, source: n },
      ring: { ...cap.air.stack.ring, source: n } } } }))); })(),
}));
"""], capture_output=True, text=True, check=True)
S = json.loads(out.stdout)

full = S["full"]
CH = lambda s, k: next(c for c in full[s]["chapters"] if c["k"] == k)
assert [x["k"] for x in full] == ["base", "community", "city"] and [x["res"] for x in full] == [8, 7, 6], [x["k"] for x in full]
assert [[c["k"] for c in x["chapters"]] for x in full] == [
    ["air", "built", "sun", "heat", "rain"], ["air", "change", "lab", "rivers"], ["grid", "basin", "sea", "city-air"]]
assert [x["km2"] for x in full] == [4.5, 31.4, 219.4], "the scale's own size, from /wall"
assert not [c for x in full for c in x["chapters"] if c["k"] == "rice"], "no rice chapter: that pack is not on the Wall"
assert all(set(c) >= {"k", "hue", "title", "n", "word", "says", "src", "layers"} for x in full for c in x["chapters"])
assert all(c["hue"].startswith("--") and isinstance(c["layers"], list) and len(c["n"]) == 2 for x in full for c in x["chapters"])
assert all(c["word"] in ("live", "partial", "model", "cached", "example") for x in full for c in x["chapters"]), "one of the five"
print("  story: 5 / 4 / 4 chapters in order, the five words, hues are custom property names")

assert [c["layers"] for c in full[0]["chapters"]] == [["own-air"], ["roofs", "roofs-mask"], ["roofs-sun", "roofs-mask"], ["own-heat"], ["own-water"]]
assert [c["layers"] for c in full[1]["chapters"]] == [["stations"], ["change"], ["lab"], ["rivers"]]
assert [c["layers"] for c in full[2]["chapters"]] == [["grid"], ["basin", "rivers"], [], ["island"]], "the island list holds the ring"
assert [c["fit"] for c in full[2]["chapters"] if "fit" in c] == [[[115.237, -8.716]], full[2]["chapters"][1]["fit"], [[115.178, -8.625]]]
assert len(CH(2, "basin")["fit"]) == 5 and "fit" not in CH(2, "sea") and "fit" not in CH(0, "air")
assert CH(2, "city-air")["official"] == {"lon": 115.178, "lat": -8.625, "label": "Sempidi · government"}, CH(2, "city-air")["official"]
assert CH(0, "air")["n"] == [7.8, "µg/m³"] and CH(0, "air")["word"] == "live" and CH(1, "air")["word"] == "partial"
assert CH(0, "sun")["n"] == [6.4, "kWh/m²"] and "2.0 kW panel" in CH(0, "sun")["says"] and "9.6 kWh" in CH(0, "sun")["says"]
assert CH(0, "built")["n"] == [91, "%"] and CH(0, "heat")["n"] == [34.2, "°C"] and CH(0, "rain")["n"] == [3.4, "mm"]
assert CH(1, "change")["n"] == [129, "ha"] and CH(1, "lab")["n"] == [4, "km"] and CH(1, "rivers")["n"] == [4, "km"]
assert CH(2, "grid")["n"] == [84, "%"] and CH(2, "basin")["n"] == [42, "km²"] and CH(2, "sea")["n"] == [1.7, "m"]
assert CH(2, "city-air")["n"] == [6.7, "µg/m³"] and CH(1, "lab")["word"] == "partial"
print("  story: layer names, fits, the official station's label, the figures")

says = " ".join(c["says"] for x in full for c in x["chapters"])
mine = [n for n in S["names"] if n != S["lab"]]       # the lab is a public place W names itself; no house kit or room is
assert mine and not [n for n in mine if n in says], [n for n in mine if n in says]
assert not re.search(r"\d\.\d+\s*km\b", says), "a distance is a whole km"
assert "Pesanggaran" in CH(2, "grid")["says"] and "12 km" in CH(2, "grid")["says"] and "gas" in CH(2, "grid")["says"]
assert "22 km" in CH(2, "basin")["says"] and "10.6" in CH(2, "basin")["says"] and "4 km" in CH(1, "rivers")["says"]
assert "Fab Lab Bali" in CH(1, "lab")["says"] and "4 km" in CH(1, "lab")["says"] and "2025" in CH(1, "change")["says"]
assert "Sempidi" in CH(2, "city-air")["says"] and "south-west" in CH(2, "sea")["says"]
assert "from the" not in S["noWave"], "no direction hour, no direction said"
ring1 = next(c for c in S["ring1"][1]["chapters"] if c["k"] == "air")
assert ring1["src"] == "stations around", ("one fresh ring station: its name never reaches the Wall", ring1["src"])
assert CH(1, "air")["src"] == "9 sensors", "a count of sensors is said as it is"
held = [n.strip() for n in S["names"] if n.strip() != S["lab"]]
for story in S["named"]:
    shown = " ".join(c["src"] + " " + c["title"] for x in story for c in x["chapters"])
    assert not [n for n in held if n in shown], [n for n in held if n in shown]
print("  story: captions read W in whole km and name no sensor, in no source and no title either")
g = S["genset"]
assert "Pesanggaran" in g["says"] and "Genset" not in g["says"] and g["fit"] == [[115.237, -8.716]], ("the nearest large plant, never a genset", g)
assert "plant" not in S["noLarge"]["says"] and "fit" not in S["noLarge"], S["noLarge"]
print("  story: the nearest large plant is the energy pack's 100 MW cut, never the nearest genset")

assert S["cap"] == [["air", "built", "sun"], ["air", "change", "lab", "rivers"], ["grid", "basin", "sea", "city-air"]], \
    ("the capture holds no heat or water readouts, so those chapters are absent; the sun is W's", S["cap"])
assert S["noWater"] == [["air", "built", "sun", "heat", "rain"], ["air", "change", "lab"], ["grid", "sea", "city-air"]], S["noWater"]
assert S["noIsland"] == ["grid", "basin", "sea"]
assert S["noSun"] == ["air", "built", "heat", "rain"], "the sun is W.grid.sun, and absent with it"
assert S["noTiles"] == [["air", "heat", "rain"]] * 2, ("no street tiles, no roofs to light: no Buildings and no Sun, satellite or not", S["noTiles"])
assert S["empty"] == [["base", 0, 8, 4.5], ["community", 0, 7, 31.4], ["city", 0, 6, 219.4]], S["empty"]
assert S["capOnly"] == [["air"], [], ["sea"]], "every /wall block null: only what the doors' own issues hold is left"
print("  story: a missing block drops its chapter, a scale with none still stands")

assert S["at"] == [3, 0, 4, 0, 1, 0, 2], S["at"]
print("  story: chapterAt splits the day evenly and never runs past the last chapter")


# ---- the DOM half: the mount, on a fake MapLibre that records what the map is told ----
# A size changes at hour 0 (the hour before was 23, the widest frame of the size before): the camera makes one 2.6 s glide
# to chapter 0's frame of the new size, never first to its last chapter's frame. A chapter changing inside a size glides
# 1.6 s. Reduced motion turned on while the Wall shows takes the wind and the crests off the clock (CLOCK.on refuses then,
# but keeps a key already on), and destroy() lets the map go. The roofs are lit inside the circle /wall counted them in
# (mapped_radius_m round the cell's middle), and the house's cell is red at an hour its own dust, joined by instant, is
# over the line.
mount = json.loads(subprocess.run(["node", "-e", r"""
const fs = require('fs'), vm = require('vm');
const W = JSON.parse(fs.readFileSync('./tests/fixtures/wall-node1.json', 'utf8'));
const fits = [], layers = new Set(), sources = {}, fills = []; let removed = 0;
class FakeMap {
  constructor() { this.ev = {}; FakeMap.last = this; }
  on(e, f) { (this.ev[e] ||= []).push(f); } fire(e) { (this.ev[e] || []).forEach(f => f()); }
  addSource(id, src) { sources[id] = src; } addLayer(l) { layers.add(l.id); } getLayer(id) { return layers.has(id); } addControl() {}
  setLayoutProperty() {} setPaintProperty(id, k, v) { if (id === 'own-air') fills.push(v); } getSource() { return { setData() {} }; } fitBounds(b, o) { fits.push({ b, d: o.duration }); }
  getCenter() { return { toArray: () => [0, 0] }; } getZoom() { return 10; } querySourceFeatures() { return []; } project() { return { x: 0, y: 0 }; }
  remove() { removed++; }
}
const subs = new Map(); let reduced = false;
const CLOCK = { subs, reduced: () => reduced, on(id, fn) { if (reduced) return false; subs.set(id, fn); return true; }, off(id) { subs.delete(id); } };
const el = { innerHTML: '', firstChild: {}, lastChild: { getContext: () => null }, getBoundingClientRect: () => ({ width: 800, height: 600 }) };
const ctx = { maplibregl: { Map: FakeMap, Marker: class { setLngLat() { return this; } addTo() { return this; } remove() {} }, AttributionControl: class {} },
  CLOCK, view: () => 'wall', performance, devicePixelRatio: 1, console, W, el, location: { origin: 'http://n' },
  /* the house's dust over the line at the last hour only, on the same 24 hours as /wall */
  D: { buckets: W.hours.buckets, issues: { air: { line: 15, series: { room: [...Array(23).fill(5), 40] } } } },
  getComputedStyle: () => ({ getPropertyValue: k => k }),   /* each hue is its own name */ document: { createElement: () => ({}) } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('./app/static/doors-wallmap.js', 'utf8'), ctx);
ctx.story = vm.runInContext(`wallStory(W, { issues: { air: { line: 15, stack: { room: { value: 5, provenance: 'live', n: 3 }, ring: { value: 9, provenance: 'partial', source: 'x' } } },
  land: { readouts: [{ metric: 'built_frac', value: 91, provenance: 'model' }] }, coast: { readouts: [{ metric: 'swell_height_m', value: 1.6, provenance: 'model' }] } } }, { vector: true })`, ctx);
const S = ctx.story, M = vm.runInContext('wallMapMount(el, W, story, { vector: true })', ctx);
const box = pts => pts.reduce((b, [x, y]) => [[Math.min(b[0][0], x), Math.min(b[0][1], y)], [Math.max(b[1][0], x), Math.max(b[1][1], y)]], [[180, 90], [-180, -90]]);
const frame = (s, ch) => box([...S[s].cells.flatMap(c => c.ring), ...((ch && ch.fit) || [])]);
const out = {};
M.go(0, true); M.hour(23); FakeMap.last.fire('load');          // a redraw at hour 23: one cut, the base size's last chapter
out.first = fits.splice(0);
M.hour(0); out.chapter = fits.splice(0);                       // the day starts again: a chapter change inside the size
M.go(2); out.goAlone = fits.splice(0);                          // the size changes as the wallTick does it ...
M.hour(0); out.size = fits.splice(0);                           // ... and takes effect at its first hour
out.want = { first: frame(0, S[0].chapters[S[0].chapters.length - 1]), chapter: frame(0, S[0].chapters[0]), size: frame(2, S[2].chapters[0]),
  last2: frame(2, S[2].chapters[S[2].chapters.length - 1]) };
out.fxOn = subs.has('wall-fx');
reduced = true; subs.get('wall-fx')(performance.now()); out.fxReduced = subs.has('wall-fx');   // reduced motion turned on mid-run
reduced = false; M.hour(1); out.fxBack = subs.has('wall-fx');
M.destroy(); out.fxGone = !subs.has('wall-fx'); out.removed = removed;
out.mask = sources.mask.data.features[0].geometry.coordinates; out.centre = W.centre; out.radius = W.roofs.mapped_radius_m;
/* the dust's own hours: at 23 over the line, at 22 not; with /issues an hour ahead of /wall, the 40 is an hour no slot has */
const red = h => { fills.length = 0; FakeMap.last.fire('load'); M2.hour(h); return fills.pop(); };
let M2 = vm.runInContext('wallMapMount(el, W, story, { vector: true })', ctx); out.fill = [red(23), red(22)];
ctx.D.buckets = W.hours.buckets.map(b => new Date(Date.parse(b) + 3600e3).toISOString());
M2 = vm.runInContext('wallMapMount(el, W, story, { vector: true })', ctx); out.ahead = [red(23), red(22)];
/* the same cells moved onto the antimeridian, the cell's middle at 179.995: the camera frames a few km, round W.centre */
const shift = x => { const y = x - W.centre[0] + 179.995; return y > 180 ? y - 360 : y; };
const Wx = { ...W, centre: [179.995, W.centre[1]], scales: W.scales.map(sc => ({ ...sc, cells: sc.cells.map(c => ({ ...c, ring: c.ring.map(([x, y]) => [shift(x), y]) })) })),
  stations: [], island: null, roofs: null, lab: null, rivers: null, basin: null, river: null, grid: null, change: null };
ctx.Wx = Wx; ctx.storyX = vm.runInContext('wallStory(Wx, { issues: {} }, {})', ctx); fits.length = 0;
const MX = vm.runInContext('wallMapMount(el, Wx, storyX, {})', ctx); FakeMap.last.fire('load'); MX.go(0, true); MX.hour(0);
out.anti = { fit: fits.pop().b, sides: [...new Set(Wx.scales[0].cells.flatMap(c => c.ring.map(([x]) => Math.sign(x))))] };
console.log(JSON.stringify(out));
"""], capture_output=True, text=True, check=True).stdout)
_a = mount["anti"]
assert _a["sides"] == [1, -1] or _a["sides"] == [-1, 1], ("the moved cells do not straddle the antimeridian", _a)
assert 179.9 < _a["fit"][0][0] < 180 < _a["fit"][1][0] < 180.1, ("the camera frames the world, not the cells round W.centre", _a["fit"])
print("  mount: cells either side of the antimeridian are framed as one, round the cell's middle")
assert len(mount["first"]) == 1 and mount["first"][0]["d"] == 0 and mount["first"][0]["b"] == mount["want"]["first"], mount["first"]
assert len(mount["chapter"]) == 1 and mount["chapter"][0]["d"] == 1600 and mount["chapter"][0]["b"] == mount["want"]["chapter"], mount["chapter"]
assert mount["goAlone"] == [], "go() moved the camera before the size's first hour"
assert len(mount["size"]) == 1 and mount["size"][0]["d"] == 2600 and mount["size"][0]["b"] == mount["want"]["size"] != mount["want"]["last2"], mount["size"]
print("  mount: a size change is one 2.6 s glide to its first chapter's frame; a chapter inside it 1.6 s; a redraw cuts")
assert mount["fxOn"] and not mount["fxReduced"] and mount["fxBack"] and mount["fxGone"] and mount["removed"] == 1, mount
print("  mount: reduced motion turned on mid-run takes the wind and the crests off the clock; destroy lets the map go")
_c, _hole = mount["centre"], mount["mask"][1]
_m = [((x - _c[0]) * 111320 * math.cos(math.radians(_c[1]))) ** 2 + ((y - _c[1]) * 110574) ** 2 for x, y in _hole]
assert len(mount["mask"]) == 2 and all(abs(v ** .5 - mount["radius"]) < 2 for v in _m), ("the roofs are lit in the circle /wall counted them in", len(mount["mask"]))
assert mount["fill"] == ["--signal-worse", "--d-air"], ("the house's cell is red at the hour its dust is over the line", mount["fill"])
assert mount["ahead"] == ["--d-air", "--d-air"], ("/issues an hour ahead: the cell read another hour's dust by index", mount["ahead"])
print("  mount: the roofs are lit in /wall's own circle round the cell's middle; the cell is red at its own dust's instant")

# ---- the sea under the crests, and a lost GPU context ----
# The crests are clipped to the water in the node's street tiles. A clip read before those tiles came was an empty path,
# kept for as long as the camera stayed put: no crests at all. It is read again when the map goes idle or the street
# source gets data. While the camera glides there are no crests (each frame re-read every water vertex), and after it
# they fade back in. A lost WebGL context calls the Wall back, for it to mount the map again. The wind and the crests read
# the replayed hour's own slot: a gap in any of their inputs leaves that effect off for that hour (CodeRabbit on #406).
sea = json.loads(subprocess.run(["node", "-e", r"""
const fs = require('fs'), vm = require('vm');
const W = JSON.parse(fs.readFileSync('./tests/fixtures/wall-node1.json', 'utf8'));
let water = [], moving = false, reads = 0;
class FakeMap {
  constructor() { this.ev = {}; FakeMap.last = this; }
  on(e, f) { (this.ev[e] ||= []).push(f); } fire(e, a) { (this.ev[e] || []).forEach(f => f(a)); }
  addSource() {} addLayer() {} getLayer() { return true; } addControl() {} isMoving() { return moving; }
  setLayoutProperty() {} setPaintProperty() {} getSource() { return { setData() {} }; } fitBounds() {}
  getCenter() { return { toArray: () => [0, 0] }; } getZoom() { return 10; }
  querySourceFeatures() { reads++; return water; } project([x, y]) { return { x, y }; } remove() {}
}
class Path2D { constructor() { this.n = 0; } moveTo() { this.n++; } lineTo() { this.n++; } }
const clips = [], strokes = []; let winds = 0, losts = 0;
const g = { setTransform() {}, clearRect() {}, save() {}, restore() {}, clip(p) { clips.push(p.n); }, beginPath() {}, moveTo() {}, lineTo() {},
  stroke() { if (this.lineWidth !== 2) strokes.push(this.globalAlpha); else winds++; }, globalAlpha: 1, lineWidth: 1 };   /* the crests' strokes; the wind's are 2 px */
const subs = new Map();
const CLOCK = { reduced: () => false, on(id, fn) { subs.set(id, fn); return true; }, off(id) { subs.delete(id); } };
const el = { innerHTML: '', firstChild: {}, lastChild: { getContext: () => g }, getBoundingClientRect: () => ({ width: 800, height: 600 }) };
const ctx = { maplibregl: { Map: FakeMap, Marker: class {}, AttributionControl: class {} }, Path2D, CLOCK, view: () => 'wall', performance, devicePixelRatio: 1,
  console, W, el, location: { origin: 'http://n' }, D: { issues: {} }, Math,
  getComputedStyle: () => ({ getPropertyValue: () => '#123456' }), document: { createElement: () => ({}) } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('./app/static/doors-wallmap.js', 'utf8'), ctx);
ctx.story = vm.runInContext('wallStory(W, { issues: {} })', ctx);
ctx.lost = () => losts++;
const M = vm.runInContext('wallMapMount(el, W, story, { vector: true }, lost)', ctx), map = FakeMap.last, out = {};
let t = 0; const frame = (dt = 16) => { t += dt; subs.get('wall-fx')(t); };
map.fire('load'); M.go(2, true); M.hour(3); frame();
out.before = clips.splice(0);                                      // the tiles have not come: an empty sea
water = [{ geometry: { type: 'Polygon', coordinates: [[[0, 0], [10, 0], [10, 10], [0, 0]]] } }];
frame(); out.cached = clips.splice(0);
map.fire('sourcedata', { sourceId: 'sat' }); frame(); out.other = clips.splice(0);
map.fire('sourcedata', { sourceId: 'v' }); frame(); out.came = clips.splice(0);
reads = 0; moving = true; strokes.length = 0; frame(); frame(); out.glide = { clips: clips.splice(0), reads };
moving = false; strokes.length = 0; for (let i = 0; i < 40; i++) frame(); out.fade = strokes.slice(); clips.length = 0;
water = [...water, ...water]; map.fire('idle'); frame(); out.idle = clips.splice(0);
out.lost0 = losts; map.fire('webglcontextlost'); out.lost1 = losts;
/* hour 5 has no wind speed and no swell period, its neighbours have both: nothing of either is drawn at 5 */
W.hours.wind_kmh[5] = null; W.hours.swell_s[5] = null;
const fx = h => { M.hour(h); clips.length = 0; winds = 0; frame(); return { crests: clips.length, wind: winds }; };
out.gap = fx(5); out.whole = fx(4); W.hours.wind_from[4] = null; W.hours.wave_from[6] = null; out.dir = [fx(4), fx(6)];
console.log(JSON.stringify(out));
"""], capture_output=True, text=True, check=True).stdout)
assert sea["before"] == [0] and sea["cached"] == [0], sea
assert sea["other"] == [0], "another source's data leaves the sea as it was"
assert sea["came"] == [4], ("the street tiles came: the sea is read again", sea["came"])
assert sea["glide"] == {"clips": [], "reads": 0}, ("no crests and no water read while the camera glides", sea["glide"])
fade = sea["fade"]
assert fade[0] < fade[5] < fade[-1] and abs(fade[-1] - 0.28) < 1e-9, ("the crests fade back in after a glide", fade[:6], fade[-1])
assert sea["idle"] == [8], ("the map at rest reads the sea again", sea["idle"])
assert sea["lost0"] == 0 and sea["lost1"] == 1, "a lost WebGL context does not call the Wall back"
assert sea["whole"]["crests"] == 1 and sea["whole"]["wind"] > 0, sea["whole"]
assert sea["gap"] == {"crests": 0, "wind": 0}, ("a neighbour's speed or period drawn at an hour that has none", sea["gap"])
assert sea["dir"] == [{"crests": 1, "wind": 0}, {"crests": 0, "wind": sea["dir"][1]["wind"]}] and sea["dir"][1]["wind"] > 0, ("a neighbour's bearing drawn", sea["dir"])
print("  mount: the wind and the crests read their own hour, and are off for it when it lacks one of theirs")
print("  mount: the sea is read again when its tiles come or the map rests, never while it glides; the crests fade back in")
