"""Sections a pack declares, on the doors (the default page since 2026-10-07).

Until 31 Oct 2026 only the classic layout drew them, so every wild pack's band (paddy, bmkg-synop on node #1) was
invisible on a node's default page. Now draws each one beside the part of Now with the same stage: decide and act under
What to do, measure under Did it work, and since 4 Nov observe in Also read here, a row under both columns. The section comes from the engine
(engine._sections), through buildD(), into declaredBands() (doors-load.js, shared with the phone page) and
doors-now.js's drawDeclared(), lifted out and run in node. The phone's own placing is tests/test_mobile_sections.py.
Run: PYTHONPATH=app python3 tests/test_doors_sections.py
"""
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
os.environ.setdefault("PACKS_DIR", str(ROOT / "packs"))
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
from issues import engine   # noqa: E402

STATIC = ROOT / "app/static"
L3 = lambda en, i: {"en": en, "id": i, "es": en}  # noqa: E731


def sec(id, stage, order=None, n=2, pack="p", sid="s"):
    s = {"id": id, "pack": pack, "stage": stage, "title": L3(f"{id} title", f"{id} judul"), "note": L3("Why.", "Mengapa."),
         "readouts": [{"metric": f"m{i}", "sensor_id": sid, "unit": "ha", "dp": 1, "label": L3(f"m{i} label", f"m{i} label id")}
                      for i in range(n)]}
    if order is not None:
        s["order"] = order
    return s


now = datetime(2026, 10, 31, 7, 0, tzinfo=timezone.utc)
obs = [{"sensor_id": "s", "metric": m, "value": v, "kind": "satellite", "ts": "2026-10-31T05:00:00+00:00"} for m, v in (("m0", 639.04), ("m1", 7.6))]
served = engine._sections([sec("rice", "observe", 48, n=3, pack="paddy"), sec("wx", "observe", 47, pack="bmkg-synop"),
                           sec("ask", "decide"), sec("did", "act", 10), sec("worked", "measure"), sec("none", "measure", sid="gone"),
                           sec("wx", "observe"), {**sec("odd", "decide"), "stage": "look"}], obs, now)

prog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), now = fs.readFileSync('./app/static/doors-now.js', 'utf8');
const load = fs.readFileSync('./app/static/doors-load.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0], fn = (src, n) => src.match(new RegExp('function ' + n + '\\b[\\s\\S]*?\\n}\\n'))[0];
const F = JSON.parse(fs.readFileSync('app/issues/fixtures/node1-2026-10-06-figures.json', 'utf8'));
F.issues.sections = JSON.parse(process.argv[1]);
const out = {};
for (const lc of ['en', 'id']) {
  const D = L.buildD({ ...F, days: F.issues_days }, lc), els = {};
  const ctx = { D, $: q => (els[q] ||= { hidden: true, innerHTML: '' }) };
  vm.createContext(ctx);
  vm.runInContext(['esc', 'fmt', 'said', 'sign', 'NODE', 'PROV', 'prov', 'ago', 'num'].map(pick).join('\n') + '\n'
    + load.match(/^const DECL_STAGES = .*$/m)[0] + '\n' + load.match(/^const DECL_AT = .*$/m)[0] + '\n'
    + fn(load, 'declaredBands') + fn(load, 'declaredBand') + fn(now, 'drawDeclared') + 'drawDeclared();', ctx);
  /* two sources in one band: each row says its source only where it changes from the row above */
  if (lc === 'en') out.mixed = vm.runInContext('declaredBand(' + JSON.stringify({ id: 'mx', pack: 'surface-heat', stage: 'observe', readouts: [
    { metric: 'a', value: 1, source: 'Landsat', age_minutes: 120 }, { metric: 'b', value: 2, source: 'Landsat', age_minutes: 120 },
    { metric: 'c', value: 3, source: 'MODIS', age_minutes: 120 }, { metric: 'd', value: 4, source: 'MODIS', age_minutes: 120 }] }) + ')', ctx);
  out[lc] = Object.fromEntries(Object.entries(els).map(([k, v]) => [k, { hidden: v.hidden, html: v.innerHTML }]));
}
console.log(JSON.stringify(out));
"""
r = subprocess.run(["node", "-e", prog, json.dumps(served)], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-2000:]
out = json.loads(r.stdout)
en, idn = out["en"], out["id"]
ob, de, me = en["#ndecl-observe"], en["#ndecl-decide"], en["#ndecl-measure"]
ids = lambda h: re.findall(r'<section class="decl" id="decl-([a-z-]+)"', h)  # noqa: E731

assert ids(ob["html"]) == ["wx", "rice"] and not ob["hidden"], ids(ob["html"])
assert ids(de["html"]) == ["ask", "did"] and ids(me["html"]) == ["worked", "none"], (ids(de["html"]), ids(me["html"]))
assert "decl-odd" not in json.dumps(en) and ob["html"].count('id="decl-wx"') == 1
print("  each band sits beside Now's part of its stage, in its pack's order; act joins decide; a second id or a stage the page does not know is left out")

rice = ob["html"][ob["html"].index('id="decl-rice"'):]
assert 'data-stage="observe"' in rice and 'data-pack="paddy"' in rice and 'data-learn="now-bands"' in rice and 'data-reads="/issues"' in rice, rice[:300]
assert 'rice title</span></h3><p class="fine src">' in rice and "· 2 h old</p>" in rice, rice[:300]
assert rice.count('class="row decl" data-kind="readout"') == 2, rice
assert '<span data-num="rice.s.m0" data-cmp="the paddy pack’s figure, beside nothing of this node’s">639.0</span><small>ha</small>' in rice, rice
assert '<span class="sub">' not in rice, "the source is said once, under the head"
mx = out["mixed"]
assert mx.count('<span class="sub">') == 1 and mx.index('class="fine src">Landsat') < mx.index('<span class="sub">MODIS'), mx
print("  a band is the pack's title, its source and age once under it, one readout row per reading the node holds, each figure with "
      "its comparison; a row says its source again only where it changes")

assert "1 of the 3 readings the paddy pack declares has not arrived on this node yet." in rice, rice
assert "None of the 2 readings the p pack declares has arrived on this node yet." in me["html"], me["html"]
assert '<details class="how"><summary>How this is read</summary><p class="in">Why.</p></details>' in rice, rice
assert "ships no code" not in json.dumps(out), "the developers' sentence left Now (docs/PACKS.md says it)"
print("  the band counts what has not arrived, and its note is folded under How this is read")

assert "rice judul" in idn["#ndecl-observe"]["html"] and "m0 label id" in idn["#ndecl-observe"]["html"] and "Mengapa." in idn["#ndecl-observe"]["html"]
print("  titles, labels and notes are read in the page's locale")

# a node with no declared section: every mount stays hidden and empty
r2 = subprocess.run(["node", "-e", prog, "[]"], capture_output=True, text=True)
assert r2.returncode == 0, r2.stderr[-2000:]
assert not en["#alsoread"]["hidden"], "Also read here stayed hidden with observe bands"
for k, v in json.loads(r2.stdout)["en"].items():
    assert v == {"hidden": True, "html": ""}, (k, v)
print("  a node with no declared section draws nothing on Now")

html = (STATIC / "doors.html").read_text()
nowh = html[html.index('<main class="face view" data-view="now">'):html.index("<!-- PLACE -->")]
assert nowh.index('id="decide"') < nowh.index('id="ndecl-decide"') < nowh.index('id="nremember"') < nowh.index('id="ndecl-measure"') \
    < nowh.index('id="next"') < nowh.index('class="rcol"') < nowh.index('id="rows"') < nowh.index('class="around"') \
    < nowh.index('id="alsoread"') < nowh.index('id="ndecl-observe"'), "a mount moved"
assert "drawDeclared();" in (STATIC / "doors-now.js").read_text().split("VIEWS.now = function")[1].split("};")[0]
assert "sections" not in (STATIC / "doors-wall.js").read_text(), "the Wall door does not take the declared bands; wall: true is the classic wall's"
print("  the three mounts sit where the design put them (observe in Also read here, under both columns), Now draws them on every visit, and the Wall door is unchanged")
print("doors sections: a pack's declared band draws on Now, beside its stage, with Now's own readout rows")
