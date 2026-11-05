"""Sections a pack declares, on the phone page (?layout=mobile, where a phone with no remembered layout lands).

PR #363 drew them on the doors' Now on 31 Oct 2026 and left the phone out, so on a phone a wild pack's band (paddy,
bmkg-synop on node #1) was still invisible. The phone draws the same bands with the same renderer (declaredBands in
doors-load.js, which both pages load), in its one column, beside the part of its Now with the same stage: decide and
act under the Decide card, observe under the other issues, and measure last, since the phone has no Did it work.
The section comes from the engine (engine._sections), through buildD(), into mobile.js's drawNow(), lifted out and
run in node.
Run: PYTHONPATH=app python3 tests/test_mobile_sections.py
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
                           sec("ask", "decide"), sec("did", "act", 10), sec("worked", "measure"), sec("wx", "observe")], obs, now)

prog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const mob = fs.readFileSync('./app/static/mobile.js', 'utf8'), load = fs.readFileSync('./app/static/doors-load.js', 'utf8');
const pick = (src, n) => src.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0], fn = (src, n) => src.match(new RegExp('function ' + n + '\\b[\\s\\S]*?\\n}\\n'))[0];
const F = JSON.parse(fs.readFileSync('app/issues/fixtures/node1-2026-10-06-figures.json', 'utf8'));
F.issues.sections = JSON.parse(process.argv[1]);
const src = ['esc', 'hhmm', 'fmt', 'NODE', 'said', 'sign', 'PROV', 'prov', 'num', 'ago', 'ANSWER_STAGE', 'hasToken', 'CAPTURE_KINDS'].map(n => pick(mob, n)).join('\n') + '\n'
  + pick(load, 'DECL_STAGES') + '\n' + pick(load, 'DECL_AT') + '\n' + fn(load, 'declaredBands') + fn(load, 'declaredBand')
  + fn(mob, 'drawNow') + fn(mob, 'decideHTML') + fn(mob, 'captureHTML');
const out = {};
for (const [lc, tok] of [['en', ''], ['id', ''], ['en', 't']]) {
  const D = L.buildD({ ...F, days: F.issues_days }, lc), els = {};
  const ctx = { D, leadKey: D.lead, doorsLocal: L.doorsLocal, stateWord: L.stateWord, kindWord: L.kindWord, WORDS: L.WORDS,
    DOORS_TOKEN: () => tok, $: q => (els[q] ||= { innerHTML: '' }) };
  vm.createContext(ctx);
  vm.runInContext(src + 'drawNow();', ctx);
  out[lc + (tok ? '_unlocked' : '')] = els['#now-v'].innerHTML;
}
console.log(JSON.stringify(out));
"""
r = subprocess.run(["node", "-e", prog, json.dumps(served)], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-2000:]
out = json.loads(r.stdout)
en, idn, unl = out["en"], out["id"], out["en_unlocked"]
ids = lambda h: re.findall(r'<section class="decl" id="decl-([a-z-]+)"', h)  # noqa: E731

assert ids(en) == ["ask", "did", "wx", "rice", "worked"], ids(en)
at = lambda h, s: h.index(s)  # noqa: E731
assert at(en, 'class="decide"') < at(en, 'id="decl-ask"') < at(en, 'id="decl-did"') < at(en, 'class="rowb"') \
    < at(en, 'id="decl-wx"') < at(en, 'id="decl-rice"') < at(en, 'id="decl-worked"'), "a band left its stage's place"
assert en.count('id="decl-wx"') == 1
print("  decide and act under the Decide card, observe under the other issues, measure closes Now; a second id is left out")

rice = en[at(en, 'id="decl-rice"'):at(en, 'id="decl-worked"')]
assert 'data-stage="observe"' in rice and 'data-pack="paddy"' in rice and rice.count('class="row decl" data-kind="readout"') == 2, rice[:400]
assert '<span data-num="rice.s.m0" data-cmp="the paddy pack’s figure, beside nothing of this node’s">639.0</span><small>ha</small>' in rice
assert "· 2 h old" in rice and "1 of the 3 readings the paddy pack declares has not arrived on this node yet." in rice
assert '<summary>How this is read</summary><p class="in">Why.</p>' in rice and "ships no code" not in rice
print("  the doors' band, character for character: its rows, each figure's comparison and age, what has not arrived, the note")

assert "rice judul" in idn and "m0 label id" in idn and "Mengapa." in idn
assert at(unl, 'id="decl-worked"') < at(unl, 'id="capture"'), "Add an image moved above the bands"
print("  titles, labels and notes in the page's locale; Add an image stays the last thing on Now")

r2 = subprocess.run(["node", "-e", prog, "[]"], capture_output=True, text=True)
assert r2.returncode == 0, r2.stderr[-2000:]
assert all('class="decl"' not in h for h in json.loads(r2.stdout).values())
print("  a node with no declared section draws nothing more on the phone")

mjs, core, html = (STATIC / "mobile.js").read_text(), (STATIC / "doors-core.js").read_text(), (STATIC / "mobile.html").read_text()
ago = lambda t: re.search(r"^const ago = (.*?);", t, re.M).group(1)  # noqa: E731
assert ago(mjs) == ago(core), "mobile.js's copy of ago drifted from doors-core.js's"
assert "function declaredBand" not in mjs and "function declaredBand" not in (STATIC / "doors-now.js").read_text(), "one renderer, in doors-load.js"
assert html.index('src="/static/doors-load.js"') < html.index('src="/static/mobile.js"')
assert re.search(r"\.row\.decl\{[^}]*min-height:44px", html), "a band's row on a phone is a 44 px target"
print("  one renderer for both pages, the phone's ago is the doors' own, and a band row is 44 px")
print("mobile sections: a pack's declared band draws on the phone page, beside its stage, with the doors' renderer")
