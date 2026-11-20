"""The Place drawing's pure half (app/static/doors-draw.js): the geodesic math, the state of a drawing in progress, and
the figure the readout shows. Run under node from here; nothing is drawn, so nothing needs a browser."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# one node run: the script is small (argv), the answers come back on stdout
out = subprocess.run(["node", "-e", """
const D = require('./app/static/doors-draw.js');
const sq = [[0,0],[0.001,0],[0.001,0.001],[0,0.001],[0,0]];
let a = D.addPt(D.addPt(D.drawState('area'), [0,0]), [0.001,0]);
const open = { can: D.canFinish(a), feat: D.toFeature(a, {}) };
const a3 = D.addPt(a, [0.001,0.001]);
const ln = D.addPt(D.addPt(D.addPt(D.drawState('line'), [115.167,-8.819]), [115.168,-8.819]), [115.168,-8.818]);
console.log(JSON.stringify({
  len: D.lengthM([[115.167,-8.819],[115.168,-8.819]]), area: D.areaM2(sq), areaOpen: D.areaM2(sq.slice(0, 4)),
  perim: D.perimeterM(sq), perimOpen: D.perimeterM(sq.slice(0, 4)), lenOne: D.lengthM([[1,1]]), areaTwo: D.areaM2([[0,0],[1,1]]),
  f: [D.fmtArea(312), D.fmtArea(24000), D.fmtArea(10000), D.fmtLen(1240), D.fmtLen(58.4), D.fmtLen(999.4), D.fmtLen(0)],
  open, feat: D.toFeature(a3, {label: 'x'}), back: D.backPt(a3).pts, backEmpty: D.backPt(D.drawState('line')).pts,
  immut: a.pts.length, can: [D.canFinish(a3), D.canFinish(D.addPt(D.drawState('line'), [0,0])), D.canFinish(ln), D.canFinish(D.addPt(D.drawState('marker'), [1,2])), D.canFinish(D.drawState('note'))],
  line: D.toFeature(ln, {kind: 'x'}), marker: D.toFeature(D.addPt(D.drawState('marker'), [115.1702,-8.8183]), {}),
  fig: { empty: D.figure(D.drawState('line')), line: D.figure(ln), lineHover: D.figure(D.addPt(D.drawState('line'), [115.167,-8.819]), [115.168,-8.819]),
         area: D.figure(D.addPt(D.addPt(D.addPt(D.drawState('area'), [0,0]), [0.0005,0]), [0.0005,0.0005])), areaBig: D.figure(D.addPt(D.addPt(D.addPt(D.addPt(D.drawState('area'), [0,0]), [0.001,0]), [0.001,0.001]), [0,0.001])), areaTwo: D.figure(a), marker: D.figure(D.addPt(D.drawState('marker'), [115.1702,-8.8183])),
         areaEmpty: D.figure(D.drawState('area')), note: D.figure(D.drawState('note')), markerEmpty: D.figure(D.drawState('marker')) },
  keys: D.KEYS, onWindow: typeof window,
}));
"""], capture_output=True, text=True, check=True)
R = json.loads(out.stdout)

assert abs(R["len"] - 110.0) < 1.0, R["len"]
assert abs(R["area"] - 12364) < 60, R["area"]
assert R["area"] == R["areaOpen"], "a ring closed or left open has the same area"
assert abs(R["perim"] - 4 * 111.19) < 1 and abs(R["perim"] - R["perimOpen"]) < 1e-6, (R["perim"], R["perimOpen"])
assert R["lenOne"] == 0 and R["areaTwo"] == 0, "fewer points than a shape needs measure nothing"
print("  draw: length, area and perimeter on the sphere")

assert R["f"] == ["312 m² · 0.03 ha", "2.4 ha", "1 ha", "1.24 km", "58 m", "999 m", "0 m"], R["f"]
print("  draw: the figures read as the mockup writes them")

assert R["open"]["can"] is False and R["open"]["feat"] is None, "two corners are not an area"
f = R["feat"]
ring = f["geometry"]["coordinates"][0]
assert f["geometry"]["type"] == "Polygon" and ring[0] == ring[-1] and len(ring) == 4, ring
assert f["properties"] == {"kind": "area", "label": "x"}, f["properties"]
assert R["back"] == [[0, 0], [0.001, 0]] and R["backEmpty"] == [] and R["immut"] == 2, "backPt and addPt leave the old state alone"
assert R["can"] == [True, False, True, True, False], R["can"]
assert R["line"]["geometry"]["type"] == "LineString" and R["line"]["properties"]["kind"] == "x", "the caller's props win"
assert R["marker"]["geometry"] == {"type": "Point", "coordinates": [115.1702, -8.8183]}
print("  draw: the state machine adds, takes back, and finishes only when the shape is a shape")

g = R["fig"]
assert g["empty"]["hint"].startswith("Press to add a point") and g["empty"]["value"] == "", g["empty"]
assert g["line"]["unit"].endswith("2 segments") and g["line"]["value"].replace(".", "").isdigit(), g["line"]
assert g["lineHover"]["unit"].endswith("1 segment") and float(g["lineHover"]["value"]) > 100, g["lineHover"]
assert g["area"]["unit"].startswith("m² · 0.15 ha · ") and g["area"]["unit"].endswith(" m round"), g["area"]
assert g["areaBig"]["value"] == "1.2" and g["areaBig"]["unit"].startswith("ha · 445 m round"), g["areaBig"]
assert g["area"]["hint"].startswith("Press to add a corner"), g["area"]
assert g["areaTwo"]["value"] == "" and g["areaEmpty"]["value"] == ""
assert g["marker"]["value"] == "−8.8183, 115.1702" and g["markerEmpty"]["hint"].startswith("Press the map to drop it")
assert g["note"]["hint"].startswith("A note sits on the map")
print("  draw: the readout figure, with and without a hover point")

assert R["keys"] == [["select", "V"], ["marker", "M"], ["line", "L"], ["area", "A"], ["note", "N"], ["image", "I"]]
assert R["onWindow"] == "undefined", "no DOM, no window: the module exports itself under node"

# The keys on the map's left edge say their names and their letters (Tomas, 17 Nov 2026: "make it more understandable
# what are buttons"). keysHTML is lifted from doors-placemap.js with the icons emptied: the words are what is read here.
html = subprocess.run(["node", "-e", """
const fs = require('fs'), pm = fs.readFileSync('./app/static/doors-placemap.js', 'utf8'), { KEYS } = require('./app/static/doors-draw.js');
Object.defineProperty(globalThis, 'navigator', { value: { platform: 'MacIntel' }, configurable: true });
const KEYICON = new Proxy({}, { get: () => '' }), PM = { tool: 'select' };
eval(pm.match(/^const KEYNAME = .*$/m)[0].replace('const KEYNAME', 'globalThis.KEYNAME'));
eval(pm.match(/^const UNDOKEY = .*$/m)[0].replace('const UNDOKEY', 'globalThis.UNDOKEY'));
eval(pm.match(/^const keysHTML = [\\s\\S]*?;\\n\\n/m)[0].replace('const keysHTML', 'globalThis.keysHTML'));
console.log(keysHTML());
"""], capture_output=True, text=True, check=True).stdout
assert html.count('<span class="kn">') == 7, html
for name, key in [("Select", "V"), ("Marker", "M"), ("Line", "L"), ("Area", "A"), ("Note", "N"), ("Image", "I"), ("Undo", "⌘Z")]:
    assert f'<span class="kn">{name}</span><kbd>{key}</kbd>' in html, (name, html)
assert 'aria-label="Line, with distance"' in html and 'title="Undo · ⌘Z or Ctrl+Z"' in html and "<small>" not in html, html
# Undo's letter is the one this machine's keyboard has: ⌘Z on a Mac, Ctrl+Z anywhere else (node #3 is Linux)
linux = subprocess.run(["node", "-e", """
const fs = require('fs'), pm = fs.readFileSync('./app/static/doors-placemap.js', 'utf8'), { KEYS } = require('./app/static/doors-draw.js');
Object.defineProperty(globalThis, 'navigator', { value: { platform: 'Linux x86_64' }, configurable: true });
const KEYICON = new Proxy({}, { get: () => '' }), PM = { tool: 'select' };
eval(pm.match(/^const KEYNAME = .*$/m)[0].replace('const KEYNAME', 'globalThis.KEYNAME'));
eval(pm.match(/^const UNDOKEY = .*$/m)[0].replace('const UNDOKEY', 'globalThis.UNDOKEY'));
eval(pm.match(/^const keysHTML = [\\s\\S]*?;\\n\\n/m)[0].replace('const keysHTML', 'globalThis.keysHTML'));
console.log(keysHTML());
"""], capture_output=True, text=True, check=True).stdout
assert '<span class="kn">Undo</span><kbd>Ctrl+Z</kbd>' in linux and "⌘Z</kbd>" not in linux, linux[-300:]
print("  draw: each key says its name and its letter, and Undo's is Ctrl+Z off a Mac")
print("draw: every check passed")
sys.exit(0)
