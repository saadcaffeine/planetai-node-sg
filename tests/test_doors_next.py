"""Next days, a part of Now on the doors (docs/SPEC_next_days.md §5).

nextFrom(forecast, locale) turns GET /forecast?hours=72 (the forecast-v0 answers in tests/data/forecast/, which
packs/forecast/days.py wrote) into what drawNext() draws: a row card per thing in the order of Now's rows (air, heat),
then wind and rain, the sea, then the packs' lines; three day columns; the sources as pills; the sentence that says
these are models. It is lifted out of doors-now.js and run in node, as tests/test_doors_asks.py does, in en, es and id.
Until 4 Nov 2026 a switch at the top of Now ("Now · Next days") showed one or the other; now Next days is drawn with Now,
under What to do, and #now/next scrolls to it.
Run: python3 tests/test_doors_next.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FX = {n: json.loads((ROOT / "tests/data/forecast" / f"{n}.json").read_text()) for n in ("full", "om_off", "none", "community")}
MODELS = "These come from models. The node does not forecast, and nothing here sends a message."
OPTIN = ("Air, the sea and more hours come from Open-Meteo, which is off on this node. "
         "Turn it on in Set up → Packs → forecast.")

prog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), now = fs.readFileSync('./app/static/doors-now.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const fn = (src, n) => src.match(new RegExp('function ' + n + '\\b[\\s\\S]*?\\n}\\n'))[0];
const block = n => now.match(new RegExp('^const ' + n + ' = [\\s\\S]*?\\n};\\n', 'm'))[0];
const one = n => now.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8')), out = {};
for (const [name, f, locale] of cases) {
  const ctx = { D: { tz: 'Asia/Makassar', locale }, doorsLocal: L.doorsLocal, WORDS: L.WORDS };
  vm.createContext(ctx);
  vm.runInContext(['esc', 'WD', 'loc', 'dayOf', 'dLabel', 'fmt', 'said', 'num', 'UNLOCK_AT'].map(pick).join('\n') + '\n' + block('NX') + one('NX_SRC') + '\n'
    + fn(now, 'packWord') + fn(now, 'nxCell') + fn(now, 'nextFrom') + 'var got = nextFrom(F, D.locale);', Object.assign(ctx, { F: f }));
  out[name] = ctx.got;
}
console.log(JSON.stringify(out));
"""

evil = json.loads(json.dumps(FX["full"]))
evil["lines"][0]["title"]["en"] = "<i>Surf</i>"
evil["lines"][0]["days"]["2026-11-04"]["en"] = '<b>x</b><img src=x onerror="alert(1)">'
far = json.loads(json.dumps(FX["om_off"]))
far["far_from_node"] = [{"sensor_id": "forecast-bmkg", "km": 14.2}]
farsea = json.loads(json.dumps(FX["full"]))
next(x for x in farsea["sources"] if x["sensor_id"] == "forecast-marine")["km_from_node"] = 22.0   # far_from_node stays null: the sea is not in it
CASES = [["farsea", farsea, "en"], ["full", FX["full"], "en"], ["om_off", FX["om_off"], "en"], ["none", FX["none"], "en"], ["community", FX["community"], "en"],
         ["evil", evil, "en"], ["far", far, "en"], ["es", FX["full"], "es"], ["id", FX["full"], "id"],
         ["off", {"off": True}, "en"], ["fail", None, "en"], ["old", {"point": {}, "sources": [], "hours": []}, "en"],
         ["locked", {"locked": True}, "en"]]
r = subprocess.run(["node", "-e", prog], input=json.dumps(CASES), capture_output=True, text=True, cwd=ROOT)   # stdin: Linux caps one argument at 128 KB
assert r.returncode == 0, r.stderr[-3000:]
out = json.loads(r.stdout)
text = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()  # noqa: E731

full = out["full"]
assert [x["key"] for x in full["rows"]] == ["air", "heat", "wind_rain", "sea"], [x["key"] for x in full["rows"]]
assert [x["id"] for x in full["lines"]] == ["surf"] and full["empty"] is None, full["lines"]
assert [h["date"] for h in full["heads"]] == ["2026-11-03", "2026-11-04", "2026-11-05"], full["heads"]
assert [h["word"] for h in full["heads"]] == ["Today", "Tomorrow", ""] and full["heads"][2]["label"] == "Thu, 5 Nov", full["heads"]
assert all(len(x["cells"]) == 3 for x in full["rows"] + full["lines"])
print("  the rows in Now's order (air, heat), then wind and rain, the sea, then a pack's line; three days, headed by weekday and date")

cells = [c for o in ("full", "community", "om_off") for x in out[o]["rows"] for c in x["cells"]]
for c in cells:
    bare = re.sub(r"<span data-num=\"[^\"]+\" data-cmp=\"[^\"]+\">[^<]*</span>", "", c)
    bare = re.sub(r"\d\d:\d\d(–\d\d:\d\d)?", "", text(bare)).replace("µg/m³", "").replace("km/h", "")
    assert not re.search(r"\d", bare), (c, bare)
air0 = full["rows"][0]["cells"][0]
assert 'data-num="next.air.2026-11-03"' in air0 and "14" in text(air0) and "3 h over 15" in text(air0) and "peak 30 at 19:00" in text(air0), air0
assert "gusts 42 km/h · 9.0 mm, most 16:00–19:00" in text(full["rows"][2]["cells"][0]), full["rows"][2]["cells"][0]
assert text(full["rows"][2]["cells"][2]) == "gusts 42 km/h · no rain" and text(full["rows"][3]["cells"][1]) == "waves 1.4 m", full["rows"][2]["cells"]
assert text(out["om_off"]["rows"][1]["cells"][0]) == "no rain", "BMKG has no gusts: none is said"
assert "over in 1 of 3 cells" in text(out["community"]["rows"][0]["cells"][0]), out["community"]["rows"][0]["cells"][0]
print("  every number in a cell carries data-num and its comparison; wind and rain, the sea and the cells read as the spec says")

for c in cells:
    for m in re.finditer(r'<span class="([^"]*)">(over|near|under)</span>', c):
        assert m.group(1) == "state", m.group(0)
    assert not re.search(r'class="[^"]*(signal|worse|better|hue|red|act)\b', c), c
assert '<span class="state">near</span>' in air0 and '<span class="state">over</span>' in full["rows"][1]["cells"][0]
print("  the state words (over, near, under) are ink: class state, no hue")

assert [text(n) for n in full["notes"]] == [MODELS], full["notes"]
assert [text(n) for n in out["om_off"]["notes"]] == [MODELS, OPTIN], out["om_off"]["notes"]
assert 'href="#setup/packs"' in out["om_off"]["notes"][1]
assert [x["key"] for x in out["om_off"]["rows"]] == ["heat", "wind_rain"] and out["om_off"]["empty"] is None
print("  the provenance sentence is exact; Open-Meteo off draws BMKG's rows and the exact opt-in copy, linked to Set up → Packs")

srcs = [text(s) for s in full["sources"]]
assert srcs == ["BMKG, issued 08:00", "Open-Meteo, fetched 13:00", "CAMS, fetched 13:00", "Open-Meteo Marine, fetched 13:00"], srcs
assert [text(s) for s in out["community"]["sources"]][1] == "Open-Meteo, fetched 13:00 · 3 cells"
assert [text(s) for s in out["far"]["sources"]] == ["BMKG, issued 08:00 14 km from this node"], out["far"]["sources"]
assert farsea["far_from_node"] is None
assert [text(s) for s in out["farsea"]["sources"]][3] == "Open-Meteo Marine, fetched 13:00 22 km from this node", out["farsea"]["sources"]
assert all('class="pill"' in s for s in full["sources"])
print("  the sources as pills in the node's own time, the cells counted, and a source more than 10 km away says so")

for o in ("none", "off", "fail", "old", "locked"):
    assert out[o]["rows"] == [] and out[o]["lines"] == [] and out[o]["empty"], (o, out[o])
assert text(out["none"]["empty"]) == "No forecast source answers for this place. Turn one on in Set up → Packs → forecast." \
    and 'href="#setup/packs"' in out["none"]["empty"], "an Indonesian node with no BMKG code is not told BMKG covers Indonesia only"
assert text(out["locked"]["empty"]).startswith("This screen can’t answer yet.") and 'href="#setup/screen"' in out["locked"]["empty"], \
    "a 401 or 403 is the doors' locked line and the way to unlock"
assert text(out["off"]["empty"]) == "The forecast pack is off on this node. Turn it on in Set up → Packs → forecast." and 'href="#setup/packs"' in out["off"]["empty"]
assert 'href="#setup/packs"' in out["fail"]["empty"] and text(out["old"]["empty"]) == "No forecast has arrived on this node yet."
print("  no source, the pack off, no answer, a locked screen, an older node: one line saying why, never an empty grid")

ev = out["evil"]["lines"][0]
assert "<i>" not in ev["title"] and "&lt;i&gt;Surf&lt;/i&gt;" in ev["title"], ev["title"]
assert "<b>" not in ev["cells"][1] and "<img" not in ev["cells"][1] and "&lt;b&gt;x&lt;/b&gt;&lt;img" in ev["cells"][1], ev["cells"][1]
assert ev["cells"][0] == "" and text(out["full"]["lines"][0]["cells"][2]) == "nothing looks good"
print("  a pack's line is escaped: <b> comes out as text; it has no today")

es, idn = out["es"], out["id"]
assert text(es["lines"][0]["title"]) == "Olas" and text(es["lines"][0]["cells"][1]) == "Uluwatu 16:00–18:00" and text(idn["lines"][0]["title"]) == "Ombak"
assert [h["word"] for h in es["heads"]][:2] == ["Hoy", "Mañana"] and [h["word"] for h in idn["heads"]][:2] == ["Hari ini", "Besok"]
assert [x["title"] for x in es["rows"]] == ["Aire", "Calor", "Viento y lluvia", "Mar"], [x["title"] for x in es["rows"]]
assert "<span class=\"state\">cerca</span>" in es["rows"][0]["cells"][0] and es["notes"][0] != MODELS and idn["notes"][0] != MODELS
print("  es and id: the doors' words and the pack's own line in the page's locale")

ser = {x["key"]: x["series"] for x in full["rows"]}
assert ser["air"]["metric"] == "fc_pm25" and ser["air"]["line"] == 15 and len(ser["air"]["pts"]) > 24, ser["air"]
assert ser["heat"]["metric"] == "apparent" and ser["heat"]["line"] == 35 and len(ser["heat"]["pts"]) > 24, \
    "heat's 72 h are the feels-like the line is on, which the route computes with the engine's function"
assert ser["wind_rain"]["metric"] == "fc_wind_gusts" and ser["wind_rain"]["line"] is None and ser["sea"]["metric"] == "fc_wave_m"
assert out["om_off"]["rows"][1]["series"]["metric"] == "fc_rain" and out["om_off"]["rows"][0]["series"]["metric"] == "apparent"
assert all(p[0] < q[0] for p, q in zip(ser["air"]["pts"], ser["air"]["pts"][1:])), "the hours in order"
print("  each row carries its 72 hours from its own source, with its line where it has one")


html = (ROOT / "app/static/doors.html").read_text()
nowh = html[html.index('<main class="face view" data-view="now">'):html.index("<!-- PLACE -->")]
assert "nowsw" not in nowh and "data-nv" not in nowh, "the switch is gone: Next days is a part of Now"
lcol = nowh[nowh.index('<div class="lcol">'):nowh.index('<div class="rcol">')]
assert lcol.index('id="decide"') < lcol.index('id="nexth"') < lcol.index('id="next"'), "Next days sits in the left column, under What to do"
nx = re.search(r'<section [^>]*id="next"[^>]*>', nowh).group(0)
assert 'aria-labelledby="nexth"' in nx and "aria-live" not in nx, "a press would read the whole grid again"
src = (ROOT / "app/static/doors-now.js").read_text()
vnow = src.split("VIEWS.now = function")[1].split("\n};")[0]
assert "drawNext()" in vnow and "#now/next" in vnow and "scrollIntoView" in vnow, "Now draws Next days, and #now/next scrolls to it"
assert 'class="linep"' in src and "lineLab(" in src.split("function nxSeries")[1], "the series' line is the doors' .linep with lineLab"
assert '<span class="vh">' in src.split("async function drawNext")[1], "each cell says its day to a screen reader"
assert re.search(r"\.focus\(\)", src.split("async function drawNext")[1].split("\n}\n")[0]), "a pressed row keeps the focus"
assert 'data-learn="now-next"' in nx and 'data-reads="/forecast"' in nx and 'data-kind="readout"' in nx, nx
src = (ROOT / "app/static/doors-now.js").read_text()
assert "planetai_now_view" not in src and "nowView" not in src, "no choice is kept: there is nothing to choose"
load = (ROOT / "app/static/doors-load.js").read_text()
assert "'/forecast?hours=72'" in load and "/forecast" not in load.split("const DOORS_ROUTES")[1].split("};")[0], \
    "/forecast is asked by Now's Next days and kept there, never with the routes every door reads"
core = (ROOT / "app/static/doors-core.js").read_text()
assert ".bar .reg button" in core and "querySelectorAll('.reg button')" not in core, "the theme switch would take the Now switch's buttons"
print("  Next days is a part of Now under What to do, no switch and nothing kept; /forecast is Now's own ask")

# the forecast is kept for 30 minutes, and a failure (no answer, locked, the pack off) never: lifted drawNext, stubbed DOM
prog_cache = r"""
const fs = require('fs'), vm = require('vm'), now = fs.readFileSync('./app/static/doors-now.js', 'utf8');
const fn = (src, n) => src.match(new RegExp('(?:async )?function ' + n + '\\b[\\s\\S]*?\\n}\\n'))[0];
const one = n => now.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const answers = [null, { locked: true }, { off: true }, { days: [] }, { days: [] }], asked = [];
let t = 0;
const el = { innerHTML: '', clientWidth: 600, querySelectorAll: () => [], querySelector: () => null };
const ctx = { $: () => el, view: () => 'now', nextFrom: () => ({ empty: 'x' }), D: {}, Date: { now: () => t },
  loadForecast: async () => { asked.push(t); return answers.shift(); } };
vm.createContext(ctx);
vm.runInContext(one('NX_FRESH') + '\n' + one('NEXT') + '\n' + fn(now, 'drawNext'), ctx);
(async () => {
  for (const at of [0, 1, 2, 3, 4, 5, 60e3 * 29, 60e3 * 31, 60e3 * 32]) { t = at; await vm.runInContext('drawNext()', ctx); }
  console.log(JSON.stringify(asked));
})();
"""
rc = subprocess.run(["node", "-e", prog_cache], capture_output=True, text=True, cwd=ROOT)
assert rc.returncode == 0, rc.stderr[-2000:]
assert json.loads(rc.stdout) == [0, 1, 2, 3, 60e3 * 31], rc.stdout
print("  no answer, locked and the pack off are asked again on the next showing; an answer is kept 30 minutes")
print("doors next: Next days on Now draws the forecast-v0 answer as row cards, three days, sources and the models sentence")
sys.exit(0)
