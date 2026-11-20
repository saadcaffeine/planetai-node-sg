"""The five doors (/?layout=doors): what they read, and that they read only what a screen is given.

buildD() and flowFrom() run in node on node #1's capture (app/issues/fixtures/node1-2026-10-06-figures.json); the
prototype in planetai-design drew from a hand-built copy of the same capture, and these were checked against it
value for value on 7 Oct 2026. Here the checks are the ones that must keep holding: the shapes the doors read, the
token-only parts left empty without the token, and every file the page names served by its NAME.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("DATABASE_URL", "postgresql://test@127.0.0.1:1/test")
os.environ.setdefault("PACKS_DIR", str(ROOT / "packs"))      # the replays below need the packs the events engine replaced
STATIC = ROOT / "app" / "static"
FIX = "app/issues/fixtures/node1-2026-10-06-figures.json"

# Every file doors.html names is one the node serves by name (the /static/{name} rule: a name, never a path).
import main  # noqa: E402

html = (STATIC / "doors.html").read_text()
named = re.findall(r'(?:src|href)="/static/([^"]+)"', html)
assert named and all(n in main.COMPANIONS for n in named), [n for n in named if n not in main.COMPANIONS]
for f in STATIC.glob("doors-*.js"):
    assert f.name in main.COMPANIONS, f"{f.name} is shipped but the node does not serve it"
    assert f.name in named, f"{f.name} is served but doors.html never loads it"
js = "".join(f.read_text() for f in STATIC.glob("doors-*.js"))
for asset in re.findall(r"'/static/([\w.-]+)'", js):
    assert asset in main.COMPANIONS, f"a door asks for /static/{asset}, which the node does not serve"
assert "/node/" not in js and "data.json" not in js and "flow.json" not in js, "a door still reads the prototype's capture or proxy"
assert "h3-js" not in html and not re.search(r"\bh3\.\w+\(", js), "the node computes the cells; the page draws them"
print("doors: every file the page names is served by name, and no door reads the prototype's capture")

# singapore-node: / serves the classic dashboard (the Singapore wall lives there); /?layout=doors serves the doors.
from fastapi.testclient import TestClient  # noqa: E402
c = TestClient(main.app)
assert c.get("/").text == (STATIC / "index.html").read_text()
assert c.get("/", params={"layout": "doors"}).text == html
assert c.get("/", params={"layout": "classic"}).text == (STATIC / "index.html").read_text()
print("doors: / and ?layout=classic is the classic dashboard, ?layout=doors the doors")
# the frozen theme asks for the mono at fonts/…, and every page requested it: that one path answers (14 Oct 2026)
_mono = c.get("/static/fonts/jetbrains-mono-latin.woff2")
assert _mono.status_code == 200 and _mono.headers["content-type"] == "font/woff2", _mono.status_code
assert "url('fonts/jetbrains-mono-latin.woff2')" in (STATIC / "planetai-theme.css").read_text().replace('"', "'")
print("doors: the theme's fonts/jetbrains-mono-latin.woff2 answers 200")
# the unit /issues names for a metric is the unit the node stores it in, which Home Assistant is told too: pressure
# said hPa over kPa values, and the Data door read 99.8 hPa beside the model's 996 (14 Oct 2026)
from issues import engine as _engine  # noqa: E402
def _ha_units():
    """HA_UNITS from packs/home-assistant, where Home Assistant lives since 22 Oct (not importable as a package)."""
    import importlib.util as _iu
    _spec = _iu.spec_from_file_location("ha_hooks", "packs/home-assistant/hooks.py")
    _m = _iu.module_from_spec(_spec); _spec.loader.exec_module(_m)
    return _m.HA_UNITS


_off = {m: (u, _engine.METRICS[m]["unit"]) for m, (u, _) in _ha_units().items() if u and m in _engine.METRICS and _engine.METRICS[m]["unit"] != u}
assert not _off, _off
print("doors: every metric's unit on the page is the unit the node stores it in")

# the phone page (SPEC_mobile §8.1): the same shell route, every /static name it uses is served, no heavy
# library, and it never writes a setting or stores the admin token
mob = (STATIC / "mobile.html").read_text()
mobjs = (STATIC / "mobile.js").read_text()
assert c.get("/", params={"layout": "mobile"}).text == mob
mnamed = re.findall(r'(?:src|href)="/static/([^"]+)"', mob) + re.findall(r"['\"]/static/([\w.#-]+)['\"]", mobjs)
assert mnamed and all(n.split("#")[0] in main.COMPANIONS for n in mnamed), [n for n in mnamed if n.split("#")[0] not in main.COMPANIONS]
assert not re.search(r'(?:src|href)="/static/(?:maplibre|deck|d3|plot)', mob), "the phone page's shell loads no map or chart library"
assert not re.search(r"deck\.gl|d3\.|plot\.umd", mobjs, re.I), "the phone page fetches MapLibre for its walk, and nothing heavier"
assert "planetai_admin'" not in mobjs.replace("removeItem('planetai_admin')", ""), "the phone page never stores the admin token"
assert not re.search(r"fetch\(\s*['\"]/settings", mobjs), "the phone page reads /settings through loadD (GET) and never calls it"
print("doors: ?layout=mobile is the phone page; it names only served files, loads no map library up front, touches no settings")

# the walk out from the house (SPEC_mobile §11.2): the phone page's middle, one page; mobile.js fetches MapLibre and
# walk.js when it nears the screen. It names no issue: every issue /issues carries is walked, at the scales it has
walkjs = (STATIC / "walk.js").read_text()
assert c.get("/", params={"layout": "walk"}).text == mob, "?layout=walk is the phone page"
assert 'id="walk"' in mob and "/static/walk.js" in mobjs and "/static/maplibre-gl.js" in mobjs
assert not re.search(r"['\"](air|heat|land|coast)['\"]", walkjs), "the walk names no issue; it walks what /issues carries"
print("doors: the walk is the phone page's middle; it loads when reached and names no issue")

# one phone mode (12 Oct 2026): at SHARE_LEVEL=open the walk's map answers without a token, but /geo/cell keeps what
# it says relative to the node for a token, or a phone could find the house asking res 15 cell by cell
assert "/geo/cell" in main._SHARE_OPEN[0] and "/ground/" in main._SHARE_OPEN[1] and "/geo/cell" not in main._SHARE_OFF[0]
from types import SimpleNamespace  # noqa: E402
os.environ.setdefault("NODE_LAT", "-8.819"); os.environ.setdefault("NODE_LON", "115.164")
_rq = lambda t: SimpleNamespace(state=SimpleNamespace(share_trusted=t))  # noqa: E731
_kw = dict(id=None, lat=-8.8, lon=115.17, res=14, children=15, polar=True)
_open, _mine = main.geo.geo_cell(_rq(False), **_kw), main.geo.geo_cell(_rq(True), **_kw)
assert not {"is_node", "cells_from_node", "ring_polar", "children_polar"} & set(_open) and _open["ring"] == _mine["ring"], _open.keys()
assert {"is_node", "cells_from_node", "ring_polar", "children_polar"} <= set(_mine)
print("doors: a phone with no token gets the map and the cells, never where they stand from the house")

# the phone's QR unlock: /settings/phone hands the act token to the admin token only, Set up draws it only unlocked,
# and the phone page keeps #act= and takes it out of the address bar
os.environ["ADMIN_TOKEN"] = "adm"
from fastapi import HTTPException  # noqa: E402
for _a in ("", "Bearer nope"):
    try:
        main.settings_phone(_a); raise AssertionError("/settings/phone answered without the admin token")
    except HTTPException as e:
        assert e.status_code in (401, 403), e.status_code
assert "/settings/phone" not in main._SHARE_OPEN[0] and "qrcode.js" in main.COMPANIONS
_setup = (STATIC / "doors-setup.js").read_text()
assert "(unlocked ? `<div class=\"srow\"><div class=\"sl\"><label>A phone" in _setup and "/static/qrcode.js" in _setup
assert "#act=" in mobjs and "history.replaceState" in mobjs
print("doors: the phone unlocks from a QR code only the admin's Set up can draw")

if not shutil.which("node"):
    print("doors: node is not installed, skipping the loader checks (skipped)")
    sys.exit(0)

prog = """
const fs = require('fs');
const { buildD } = require('./app/static/doors-load.js');
const src = fs.readFileSync('./app/static/doors-flow.js', 'utf8');
const flowFrom = new Function(src.match(/function flowFrom[\\s\\S]*?\\n}\\n/)[0] + '; return flowFrom;')();
const F = JSON.parse(fs.readFileSync('%s', 'utf8'));
const open = { ...F, days: F.issues_days }; delete open.readings_1h; delete open.actions; delete open.alerts;
const full = buildD({ ...F, days: F.issues_days }, 'en'), locked = buildD(open, 'en');
const fl = flowFrom(full), fo = flowFrom(locked);
/* the phone page's subset (SPEC_mobile §8.1): the capture minus the token-only three builds a D whose Now and
   Decide card draw — the engine's words (an old capture falls back to the sentence) and the event's asking+action */
const phone = buildD(open, 'en'), pl = phone.issues[phone.lead] || {};
const pev = phone.events.filter(e => !e.cleared_at).map(e => ({ asking: e.asking, action: e.action, message: 'message' in e, seen: 'last_seen_at' in e }));
/* node #1's live table carries forecast rows up to 48 h ahead (7 Oct): the doors' table must stop at the present */
const ahead = buildD({ ...F, days: F.issues_days, readings_1h: F.readings_1h.concat([{ bucket: '2099-01-01T00:00:00+08:00', sensor_id: 'forecast-om', metric: 'fc_cloud', mean: 1, min: 1, max: 1, n: 1 }]) }, 'en');
console.log(JSON.stringify({
  aheadLast: ahead.raw.buckets[ahead.raw.buckets.length - 1], fullLast: full.raw.buckets[full.raw.buckets.length - 1], aheadN: ahead.raw.n.length, fullN: full.raw.n.length,
  order: full.order, lead: full.lead, n: full.buckets.length, issues: Object.keys(full.issues),
  air: full.issues.air, ev: full.events, raw: full.raw && { b: full.raw.buckets.length, ids: Object.keys(full.raw.series).length },
  lockedRaw: locked.raw, lockedNotes: locked.notes, fullNotes: full.notes, lockedActions: locked.actions.length,
  lockedNote: locked.actions.some(a => 'note' in a), stats: Object.keys(full.stats15).length, point: full.point,
  flow: { b: fl.buckets.length, ids: Object.keys(fl.counts).length, alerts: fl.alerts.length, answers: fl.answers.length, counted: fl.counted },
  flowLocked: { b: fo.buckets.length, ids: Object.keys(fo.counts).length, alerts: fo.alerts.length, answers: fo.answers.length, counted: fo.counted },
  phone: { title: pl.title, tagline: pl.tagline, plain: pl.plain, sentence: pl.sentence, pev },
}));
""" % FIX
r = json.loads(subprocess.run(["node"], input=prog, capture_output=True, text=True, check=True).stdout)

# the walk walks every issue with a reading, in the engine's order, at the scales it has: land and coast are read only
# at the region, so their walk starts there; an issue with no reading anywhere is left off the switch
wprog = """const { walkOf } = require('./app/static/walk.js'); const F = JSON.parse(require('fs').readFileSync('%s', 'utf8'));
const I = F.issues; I.issues.empty = { stack: { room: null, yard: null, ring: null, region: { value: null } } }; I.order = I.order.concat('empty', 'gone');
console.log(JSON.stringify(walkOf(I).map(w => [w.k, w.at.map(Boolean)])));""" % FIX
wk = json.loads(subprocess.run(["node"], input=wprog, capture_output=True, text=True, check=True).stdout)
assert [k for k, _ in wk] == ["air", "heat", "land", "coast"], wk
assert dict(wk)["land"] == [False, False, False, True] and dict(wk)["air"] == [True] * 4, wk
print("doors: the walk takes every issue with a reading, in order, each at the scales it has")

# the issues, as the doors read them (/issues for the words, /issues/days for the seven days)
assert r["order"] == ["air", "heat", "land", "coast"] and r["lead"] == "heat" and r["n"] == 168, r["order"]
air = r["air"]
assert air["name"] == "Air" and air["line"] == 15 and air["unit"] == "µg/m³" and air["hero_distance"] == "room"
assert air["sentence"].startswith("Climbing to 8") and air["pix"] == "pix-air" and len(air["usual"]) == 24
assert len(air["series"]["room"]) == 168 and air["series"]["region"] is None and len(air["per_day"]) == 8
assert set(air["stack"]["room"]) == {"value", "provenance", "source"}, "the stack keeps three words, not the node's whole row"
# an event carries its own answer, its action's words and its rooms
assert [e["id"] for e in r["ev"]] == [1, 2, 3]
assert r["ev"][2]["answer"]["stage"] == "acted" and r["ev"][0]["answer"] is None and len(r["ev"][0]["rooms"]) == 3
assert r["ev"][0]["action"].startswith("Open the side where it started")
print("doors: the issues and the events are the node's own words, renamed and never recomputed")

# token-only parts: the hourly table and the household's notes stay on the node for a screen without the token
assert r["raw"] == {"b": 24, "ids": 21} and r["lockedRaw"] is None
assert r["fullNotes"] is True and r["lockedNotes"] is False and r["lockedActions"] > 0 and not r["lockedNote"], \
    "without the token the ledger comes from /issues' asks: stages and actors, never the notes"
assert r["stats"] == 18 and r["point"] == [115.164, -8.819], "the point is /health's, rounded as it gives it"
print("doors: without the token the hourly table is absent and the ledger carries no notes")

# the flow: counts from the hourly table, alerts and answers in its window (matched flow.json exactly on 7 Oct)
# 7 answers in /actions and 2 left on alert events, which /actions without events=1 does not return (audit, 15 Oct)
assert r["flow"] == {"b": 24, "ids": 21, "alerts": 30, "answers": 9, "counted": True}, r["flow"]
assert r["flowLocked"]["answers"] >= 2, f"a screen with no token counts the events' answers too: {r['flowLocked']}"
assert r["flowLocked"]["counted"] is False and r["flowLocked"]["ids"] == 0 and r["flowLocked"]["b"] == 24
print("doors: the flow counts what the hourly table counted, and says it did not count without it")
assert r["aheadLast"] == r["fullLast"] and r["aheadN"] == r["fullN"], "a forecast hour ahead of /issues entered the replayed table"
print("doors: the hourly table stops at the hour /issues was computed; forecast rows ahead of it stay out")

# the phone page's D (SPEC_mobile §8.1): the engine's words and the open event's asking and action. This capture
# predates title/tagline on the wire, so the check is the page's own fallback: a title, or the sentence it stands on.
ph = r["phone"]
assert ph["plain"] and (ph["title"] or ph["sentence"]), "the phone's Now has none of the engine's words to draw"
assert ph["pev"] and all(e["asking"] is not None and e["action"] for e in ph["pev"]), \
    "the phone's Decide card needs the event's asking and the live action's words"
assert all(e["message"] and e["seen"] for e in ph["pev"]), "the phone's card reads message.sent and last_seen_at"
print("doors: the phone page's subset builds a D with the words, the asking and the action it draws")

# Data (Tomas, 14 Oct): Images and Things are tables; a card, the whole form, opens only in a dialog
_dj = (STATIC / "doors-data.js").read_text()
_body = lambda name: _dj[_dj.index(f"async function {name}()"):_dj.index("\n}\n", _dj.index(f"async function {name}()"))]  # noqa: E731
assert '<table class="tbl things">' in _body("thingsBlock") and "icard" not in _body("thingsBlock").split("const open")[0], \
    "Things is a table; its form opens in a dialog"
assert '<table class="tbl imgs">' in _body("imagesBlock") and "icard" not in _body("imagesBlock").split("const show")[0], \
    "Images is a table; a card opens in a dialog, one image or all of them"
assert '<table class="tbl species">' in _body("imagesBlock") and "file?w=96" in _body("imagesBlock"), "species a table; thumbnails small"
print("doors: Data's images and things are tables, and a card is a dialog someone opens")
# Fixes from the design review of node #1 (14 Oct 2026). Each check fails if its fix regresses.
# 1. Local time: a UTC string and the node's own offset print the same hour (node #1 showed "as of 11:52" beside
#    "at 19:00"); a string with no offset, or a page with no zone yet, keeps its own clock.
# 3. A screen with no token asks no token-only route: doorsFetch answers a stand-in 403 and never reaches the network.
# 7. The Wall names no sensor, room or kit, and says stale only when the last poll is old.
# A capture as ?fixture= serves it (app/issues/api.py): its issues replayed through today's engine, so a field the engine
# added since the capture (title, tagline, asking) reaches the page as it would from a node.
import tempfile  # noqa: E402
from issues import engine as _engine_r, load as _load_r  # noqa: E402
_TMP = Path(tempfile.mkdtemp())


def replayed(path: str) -> str:
    snap = json.loads(Path(path).read_text())
    snap["issues"] = _engine_r.replay(snap, main.settings, _load_r())
    (_TMP / Path(path).name).write_text(json.dumps(snap, default=str))
    return str(_TMP / Path(path).name)


tprog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const tz = 'Asia/Makassar';
const calls = []; globalThis.fetch = p => { calls.push(p); return Promise.resolve(new Response('[]')); };
(async () => {
  const locked = await L.doorsFetch('/things'), cap = await L.doorsFetch('/captures/3/file?w=96'), open = await L.doorsFetch('/stats');
  const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
  const F = JSON.parse(fs.readFileSync('%s', 'utf8')), els = {}, WF = JSON.parse(fs.readFileSync('./tests/fixtures/wall-node1.json', 'utf8'));
  /* /wall on the capture's own last 24 hours, so the issues' series and /wall's meet at every slot */
  const D0 = L.buildD({ ...F, days: F.issues_days }, 'en'); WF.hours.buckets = D0.buckets.slice(-24);
  /* a screen with no MapLibre (the visual rig is one): /wall answers, /ground/meta does not, the clock is still */
  const ctx = { D: D0, VIEWS: {}, $: q => (els[q] ||= {}), out: null, doorsLocal: L.doorsLocal, WF, performance, AbortSignal, clearTimeout,
    doorsFetch: p => Promise.resolve(p === '/wall' ? new Response(JSON.stringify(WF)) : new Response('{}', { status: 404 })),
    CLOCK: { subs: new Map(), reduced: () => true, on() { return false; }, off() {} }, view: () => 'wall',
    matchMedia: () => ({ matches: true, addEventListener() {} }), document: { fonts: { ready: Promise.resolve() } } };
  vm.createContext(ctx);
  vm.runInContext(['esc', 'fmt', 'plain', 'said', 'num', 'unitOf', 'labelOf', 'loc', 'dayOf'].map(pick).join('\n') + '\n' + fs.readFileSync('./app/static/doors-wallmap.js', 'utf8')
    + '\n' + fs.readFileSync('./app/static/doors-wall.js', 'utf8')
    + '\nconst say = Array(30).fill("Close the windows facing the street").join(" ") + ".";'
    + ' $("#wnarr").classList = { toggle() {}, add() {}, remove() {} }; const nd = () => { narrDraw(); return { hidden: $("#wnarr").hidden, html: $("#wnarr").innerHTML, note: $("#wnote").textContent }; };'
    + ' const narr = { empty: nd() }; NARR.busy = true; narr.asking = nd(); NARR.err = "The node’s model did not answer: 500"; narr.err = nd();'
    + ' NARR.prev = "The air inside is calm."; narr.kept = nd(); NARR.busy = false; NARR.err = null; NARR.shown = "The air"; NARR.typing = true; narr.typing = nd();'
    + ' out = { ask: D.order.map(k => wallAsk(D.issues[k])).join(" "), narr,'
    + ' long: wallAsk({ asking: [{ says: say }] }), short: oneLine("Open the windows. Then wait."),'
    + ' fresh: wallStale({ last_poll: new Date().toISOString() }), old: wallStale({ last_poll: "2026-10-06T11:19:50+00:00" }), none: wallStale({}) };'
    /* the strip and the column, every replayed hour of the last 24, at each of the three sizes */
    + ' function getComputedStyle() { return { fontSize: "20px" }; } $("#wallv"); WALL.W = WF; WALL.story = wallStory(WF, D, { vector: true }); WALL.R = wallDay24(WF);'
    + ' out.n = WALL.story.map(S => S.chapters.length); out.titles = WALL.story.map(S => S.chapters.map(c => c.title));'
    + ' const over = () => ({ where: $("#wwhere").innerHTML, cap: $("#wcap").innerHTML, capHidden: $("#wcap").hidden, hex: $("#whex").innerHTML });'
    + ' out.hours = [...Array(24)].map((_, h) => { WALL.s = 0; wallDraw(h); const strip = $("#wstrip").innerHTML, chap = [$("#wscale").innerHTML], ov = [over()];'
    + ' for (const s of [1, 2]) { WALL.s = s; wallDraw(h); chap.push($("#wscale").innerHTML); ov.push(over()); }'
    + ' return { strip, chap, ov, from: [WF.hours.wave_from[h], WF.hours.wind_from[h]] }; });'
    /* ONE TIMELINE: /wall an hour ahead of the issues (the Wall opened after the hour turned); a wind bearing missing at
       one hour; a new node whose /wall holds three hours */
    + ' const cl = o => JSON.parse(JSON.stringify(o)), WA = cl(WF); WA.hours.buckets = WF.hours.buckets.map(b => new Date(Date.parse(b) + 3600e3).toISOString());'
    + ' const RA = wallDay24(WA), dd = D.issues.air.hero_distance || "room", hd = D.issues.heat.hero_distance || "room"; WALL.R = RA; WALL.s = 0; wallDraw(23);'
    + ' out.ahead = { B: RA.B, wallB: WA.hours.buckets, Dbuckets: D.buckets.slice(-25), dust: RA.dust.v, heat: RA.heat.v, sea: RA.sea.v, swell: WA.hours.swell_m,'
    + ' dustS: D.issues.air.series[dd].slice(-25), heatS: D.issues.heat.series[hd].slice(-25), strip: $("#wstrip").innerHTML, clock: hhmm(RA.B[23]) };'
    + ' const WG = cl(WF); WG.hours.wind_from[5] = null; WALL.R = wallDay24(WG); wallDraw(5); out.gap = $("#wstrip").innerHTML;'
    + ' const WS = cl(WF); for (const k of Object.keys(WS.hours)) WS.hours[k] = WS.hours[k].slice(-3); WS.stations.forEach(x => { x.pm25 = x.pm25.slice(-3); });'
    + ' const RS = wallDay24(WS); WALL.R = RS; wallDraw(23);'
    + ' out.sparse = { B: RS.B, last: WS.hours.buckets[2], sea: RS.sea.v, wind: RS.wind.v, hours: RS.W.hours, pm25: RS.W.stations.map(x => x.pm25), raw: WS.stations.map(x => x.pm25),'
    + ' strip: $("#wstrip").innerHTML, clock: hhmm(WS.hours.buckets[2]) }; WALL.R = wallDay24(WF);'
    + ' WALL.story = [{ ...WALL.story[0], chapters: [] }]; WALL.s = 0; wallDraw(5); out.bare = $("#wscale").innerHTML;'
    + ' const bare = D.buckets, rawb = D.raw.buckets; D.buckets = []; out.nodays = { B: wallDay24().B, raw: rawb.slice(-24) };'
    + ' D.raw.buckets = []; out.nohours = wallDay24().B; out.asof = D.as_of; D.raw.buckets = rawb.slice(-5); out.short5 = wallDay24().B; D.raw.buckets = rawb; D.buckets = bare;'
    /* and the whole view, drawn on that screen */
    + ' D.askOff = true; WALL.h = null; out.view = VIEWS.wall().then(() => ({ wallv: $("#wallv").innerHTML, map: $("#wmbox").innerHTML, strip: $("#wstrip").innerHTML,'
    + ' scale: $("#wscale").innerHTML, h: WALL.h, s: WALL.s, sub: [...CLOCK.subs.keys()] }));', ctx);
  ctx.out.view = await ctx.out.view;
  const pm = fs.readFileSync('./app/static/doors-placemap.js', 'utf8').match(/function packRows[\s\S]*?\n}\n/)[0];
  vm.runInContext('const LAYERS = [{ id: "earth" }];' + pm + 'packRows(); out.pack = LAYERS.map(l => l.none);', ctx);
  console.log(JSON.stringify({
    utc: L.doorsLocal('2026-10-14T11:52:07.1+00:00', tz), z: L.doorsLocal('2026-10-14T11:52:00Z', tz), own: L.doorsLocal('2026-10-14T19:00:00+08:00', tz),
    midnight: L.doorsLocal('2026-10-14T17:30:00+00:00', tz), bare: L.doorsLocal('2026-10-14T11:52:00', tz), notz: L.doorsLocal('2026-10-14T11:52:00+00:00', null),
    locked: locked.status, cap: cap.status, open: open.status, calls, wall: ctx.out }));
})();
""" % replayed(FIX)
t = json.loads(subprocess.run(["node"], input=tprog, capture_output=True, text=True, check=True).stdout)
assert t["utc"] == t["z"] == "2026-10-14T19:52" and t["own"] == "2026-10-14T19:00", t
assert t["midnight"] == "2026-10-15T01:30", "a UTC evening is the node's next morning, day and all"
assert t["bare"] == t["notz"] == "2026-10-14T11:52", "no offset, or no zone: the string's own clock"
print("doors: every time is the node's local time, from a UTC string and from its own offset alike")
assert t["locked"] == t["cap"] == 403 and t["open"] == 200 and t["calls"] == ["/stats"], t
_locked = re.search(r"DOORS_LOCKED = /\^\\/\?\((.+?)\)\\b/", (STATIC / "doors-load.js").read_text()).group(1)
_paths = ["/" + x.replace("\\/", "/") for x in re.split(r"\|(?![^(]*\))", _locked)]
for _p in _paths:
    for _q in ([_p.split("(")[0] + y for y in _p.split("(")[1].rstrip(")").split("|")] if "(" in _p else [_p]):
        _opened = _q in main._SHARE_OPEN[0] or _q.startswith(main._SHARE_OPEN[1])
        assert not _opened or _q == "/alerts", f"{_q} answers a screen without a token at SHARE_LEVEL=open; doorsFetch must ask it"
_lk = json.loads(subprocess.run(["node", "-e", "const L = require('./app/static/doors-load.js'); console.log(JSON.stringify(['/learned', '/learned/search?q=x', '/learned/place'].map(p => L.DOORS_LOCKED.test(p))))"],
                                capture_output=True, text=True, check=True).stdout)
assert _lk == [True, True, False], f"the house's learnings ask the token, the place's do not: {_lk}"
print("doors: a screen with no token asks no token-only route; with one it asks as before")
# a facility is a public place the Wall may name (the lab, 18 Nov spec: "the only names are a public station's place, a
# lab, a power plant and a basin"); a sensor's name is a room, a kit or an address and never shows
_names = {x["name"].strip() for x in json.loads(Path(FIX).read_text())["sensors"] if len(x["name"].strip()) > 3 and x.get("kind") != "facility"}
_wall = json.dumps(t["wall"], ensure_ascii=False)
assert not [n for n in _names if n in _wall], [n for n in _names if n in _wall]
assert "Nothing is asked now." in t["wall"]["ask"], "6 Oct 19:22: a stale alert and an answered event ask nothing now"
assert t["wall"]["old"] and t["wall"]["none"] and not t["wall"]["fresh"], t["wall"]
print("doors: the Wall names no sensor, room or kit, and says stale only when the last poll is old")
# THE WALK (Tomas, 18 Nov: "more prominence to a satellite map showing the data of the node changing in three scales"):
# the map walks base → community → city, a column beside it says the moment and the size's chapters, and a strip of
# four small gauges and the clock sits under both. Every figure in the strip says its hour and one of the five words at
# every hour, and the swell's and the wind's needles point where they go: the hour's "from" bearing turned half a circle.
_wsrc = (STATIC / "doors-wall.js").read_text()
_hs = t["wall"]["hours"]
_FIVE = r"(?:live|partial|model|cached|example)"
assert len(_hs) == 24
for _i, _x in enumerate(_hs):
    _figs = re.findall(r'<div class="wrv">(.*?)</div>', _x["strip"])
    assert len(_figs) == 4 and _x["strip"].count('class="wg"') == 4 and 'class="wclock"' in _x["strip"], f"the strip is not four gauges and the clock at hour {_i}"
    for _v in _figs:
        assert re.search(r"<span>(\d\d:\d\d <span class=\"wpw\">" + _FIVE + r"</span>|not read (at \d\d:\d\d|here))</span>", _v), f"a figure with no time or word at hour {_i}: {_v}"
    assert not re.findall(r'class="wpw">(?!' + _FIVE + '<)', _x["strip"] + "".join(_x["chap"])), f"a word that is not one of the five at hour {_i}"
    _rot = [float(r) for r in re.findall(r'rotate\(([\d.-]+)\)', _x["strip"])]
    assert len(_rot) == 2 and all(abs(r - (f + 180) % 360) < 0.05 for r, f in zip(_rot, _x["from"])), f"the needles do not point where the swell and the wind go at hour {_i}: {_rot} {_x['from']}"
    # the column: the size's chapters, one row each, the chapter of the hour on, its word and its words with it
    for _s, _c in enumerate(_x["chap"]):
        _n = t["wall"]["n"][_s]
        assert _c.count("<li") == _n and _c.count('class="on"') == 1, f"size {_s} at hour {_i}: {_c.count('<li')} rows, {_c.count('class=\"on\"')} on"
        _on = re.search(r'<li class="on"[^>]*>.*?<span class="t">(.*?)</span>', _c).group(1)
        assert _on == t["wall"]["titles"][_s][min(_n - 1, _i * _n // 24)], f"size {_s} at hour {_i} has {_on} on"
# ONE TIMELINE (CodeRabbit on #406): /issues and /wall are two reads, and the hour can turn between them. The replay's
# slots are /wall's hours; every series is joined to them by instant, so with /wall an hour ahead each gauge shows the
# value of its slot's own instant, or that it was not read, and the clock says that slot's time.
from datetime import datetime  # noqa: E402
_ms = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
_ah = t["wall"]["ahead"]
assert [_ms(b) for b in _ah["B"]] == [_ms(b) for b in _ah["wallB"]], "the replay's slots are not /wall's hours"
_hit = 0
for _h, _b in enumerate(_ah["B"]):
    _j = next((j for j, d in enumerate(_ah["Dbuckets"]) if _ms(d) == _ms(_b)), None)
    for _k, _ser in (("dust", "dustS"), ("heat", "heatS")):
        _want = None if _j is None else _ah[_ser][_j]
        assert _ah[_k][_h] == _want, f"{_k} at slot {_h} ({_b}) reads {_ah[_k][_h]}, its instant holds {_want}"
    _hit += _j is not None
assert _hit == 23 and _ah["dust"][23] is None, ("/wall one hour ahead: 23 slots meet the issues, the last is not read yet", _hit)
assert _ah["sea"] == _ah["swell"], "the swell is /wall's own slot"
_f23 = re.findall(r'<div class="wrv">(.*?)</div>', _ah["strip"])
assert f"not read at {_ah['clock']}" in _f23[0] and f'<div class="wclock"><b>{_ah["clock"]}</b>' in _ah["strip"], (_f23[0], _ah["clock"])
# a bearing is its own hour's: with none at hour 5 the wind has no needle and no "from", beside its own speed
assert "<span>wind</span>" in t["wall"]["gap"] and len(re.findall(r"rotate\(", t["wall"]["gap"])) == 1, t["wall"]["gap"]
# a new node whose /wall holds three hours: the last real hour is slot 23, for the gauges, the clock and the map's W
_sp = t["wall"]["sparse"]
assert len(_sp["B"]) == 24 and _ms(_sp["B"][23]) == _ms(_sp["last"]) and all(_ms(b) - _ms(a) == 3600 for a, b in zip(_sp["B"], _sp["B"][1:])), _sp["B"][-3:]
assert _sp["sea"][:21] == [None] * 21 and None not in _sp["sea"][21:] and _sp["wind"][23] is not None, _sp["sea"]
assert all(len(v) == 24 for v in _sp["hours"].values()) and all(p[21:] == r for p, r in zip(_sp["pm25"], _sp["raw"])), "the map's /wall is not on the 24 slots"
_fs = re.findall(r'<div class="wrv">(.*?)</div>', _sp["strip"])
assert 'class="wnum"' in _fs[2] and 'class="wnum"' in _fs[3] and f'<div class="wclock"><b>{_sp["clock"]}</b>' in _sp["strip"], _sp["strip"][-400:]
print("doors: the Wall replays one timeline: every series at its slot's own instant, a bearing at its own hour, hour 23 the last real one")
# A /wall that fails or is slow (18 Nov review, I5): the column and the strip are painted before /wall answers; with no
# /wall the Wall asks again in 30 s, 60 s, doubling to 5 min, and mounts the map when it comes; a redraw whose /wall
# fails keeps the last good one; and a map whose WebGL context was lost is mounted again after 2 s, doubling to a
# minute (a GPU that keeps resetting), on a still screen too, while it is still the page's map. CodeRabbit on #406: /wall never waits on /ground/meta, which mounts the map
# again when its layers come (and is read once more when /wall came without it); a hung /wall reaches the retry path;
# a retry belongs to the visit that set it; the first /wall starts the replay over at the base size.
rprog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const F = JSON.parse(fs.readFileSync('%s', 'utf8')), els = {}, WF = fs.readFileSync('./tests/fixtures/wall-node1.json', 'utf8');
let wallAns = [], metaAns = [], waits = [], timers = [], mounts = 0, reduced = true, honour = false;
class FakeMap { constructor() { mounts++; this.ev = {}; FakeMap.last = this; } on(e, f) { (this.ev[e] ||= []).push(f); } fire(e) { (this.ev[e] || []).forEach(f => f()); }
  addSource() {} addLayer() {} getLayer() { return true; } addControl() {} isMoving() { return false; } setLayoutProperty() {} setPaintProperty() {}
  getSource() { return { setData() {} }; } fitBounds() {} getCenter() { return { toArray: () => [0, 0] }; } getZoom() { return 10; }
  querySourceFeatures() { return []; } project() { return { x: 0, y: 0 }; } remove() {} }
const ctx = { D: L.buildD({ ...F, days: F.issues_days }, 'en'), VIEWS: {}, $: q => (els[q] ||= { querySelectorAll: () => [] }), doorsLocal: L.doorsLocal, performance, console, JSON, Math, Promise, AbortSignal, AbortController, WF,
  /* /wall and /ground/meta answer when the test says; with `honour` a /wall gives up when its signal does */
  doorsFetch: (p, init) => p === '/wall' ? new Promise((res, rej) => { wallAns.push(res); if (honour) init.signal.addEventListener('abort', () => rej(init.signal.reason)); })
    : p === '/ground/meta' ? new Promise(res => metaAns.push(res)) : Promise.resolve(new Response('{}', { status: 404 })),
  setTimeout: (f, ms) => { waits.push(ms); timers.push(f); return timers.length; }, clearTimeout() {},
  maplibregl: { Map: FakeMap, Marker: class {}, AttributionControl: class {} }, devicePixelRatio: 1, location: { origin: 'http://n' },
  getComputedStyle: () => ({ getPropertyValue: () => '', fontSize: '20px' }),
  CLOCK: { subs: new Map(), reduced: () => reduced, on() { return false; }, off() {} }, view: () => 'wall',
  matchMedia: () => ({ matches: true, addEventListener() {} }), document: { fonts: { ready: Promise.resolve() }, createElement: () => ({}) } };
els['#wmbox'] = { innerHTML: '', firstChild: {}, lastChild: { getContext: () => null }, getBoundingClientRect: () => ({ width: 800, height: 600 }) };
vm.createContext(ctx);
vm.runInContext(['esc', 'fmt', 'plain', 'said', 'num', 'unitOf', 'labelOf', 'loc', 'dayOf'].map(pick).join('\n') + '\n' + fs.readFileSync('./app/static/doors-wallmap.js', 'utf8')
  + '\n' + fs.readFileSync('./app/static/doors-wall.js', 'utf8') + '\nD.askOff = true; $("#wnarr").classList = { toggle() {}, add() {}, remove() {} };', ctx);
const WALL = () => vm.runInContext('WALL', ctx);
const tick = () => new Promise(r => setImmediate(r)), settle = async () => { for (let i = 0; i < 6; i++) await tick(); };
const answer = ok => { wallAns.shift()(ok ? new Response(WF) : new Response('{}', { status: 503 })); };
const meta = on => { metaAns.shift()(on ? new Response(JSON.stringify({ on_disk: on })) : new Response('{}', { status: 404 })); };
const drain = async () => { for (let i = 0; i < 3; i++) { while (wallAns.length) answer(false); while (metaAns.length) meta(null); await settle(); } };
const fresh = () => vm.runInContext('if (WALL.map) WALL.map.destroy(); WALL.map = null; WALL.W = null; WALL.G = null; WALL.retry = 0; WALL.tries = 0;', ctx);
const titles = () => WALL().story[0].chapters.map(c => c.title);
const fire = async () => { const f = timers.shift(); f(); await tick(); };
(async () => {
  const out = {};
  const first = ctx.VIEWS.wall(); await tick();
  out.painted = { strip: els['#wstrip'].innerHTML.includes('class="wg"'), asked: wallAns.length, mounts };
  answer(false); await first; await tick();
  out.none = { map: els['#wmbox'].innerHTML, W: WALL().W, waits: waits.slice() };
  for (let i = 0; i < 5; i++) { await fire(); answer(false); await tick(); await tick(); }
  out.backoff = waits.slice();
  await fire(); answer(true); await tick(); await tick();
  out.came = { mounts, chapters: WALL().story.map(S => S.chapters.length), W: !!WALL().W, timers: timers.length };
  const again = ctx.VIEWS.wall(); await tick(); answer(false); await again; await tick();
  out.kept = { W: !!WALL().W, chapters: WALL().story.map(S => S.chapters.length), timers: timers.length, map: !!WALL().map };
  timers.length = 0; waits.length = 0;
  const m0 = mounts, A = FakeMap.last, h0 = WALL().map; A.fire('webglcontextlost'); A.fire('webglcontextlost');   /* a still screen: no draw follows */
  const held = { mounts: mounts - m0, timers: timers.length }; await fire();
  const m1 = mounts, B = FakeMap.last, newMap = WALL().map !== h0; A.fire('webglcontextlost');                 /* the map it replaced, again: nothing */
  const staleAsk = timers.length; B.fire('webglcontextlost'); const tB = timers.shift();
  ctx.VIEWS.wall(); const m2 = mounts; tB(); const replaced = mounts - m2;          /* a new visit let B go before its pause ran out */
  const C = FakeMap.last; C.fire('webglcontextlost'); vm.runInContext('WALL.map.destroy(); WALL.map = null;', ctx); await fire();   /* another door let C go */
  out.lost = { held, now: m1 - m0, fresh: newMap, staleAsk, replaced, gone: mounts - m2, waits: waits.slice() };
  await drain();
  /* /wall comes while /ground/meta hangs: the map mounts without it, and again when its layers come */
  fresh(); timers.length = 0; let v = ctx.VIEWS.wall(); await tick(); const m4 = mounts; answer(true); await v; await tick();
  out.noMeta = { mounts: mounts - m4, G: WALL().G, titles: titles() }; meta({ vector: true }); await settle();
  out.meta = { mounts: mounts - m4, vector: !!(WALL().G || {}).on_disk.vector, titles: titles(), asked: metaAns.length };
  /* /ground/meta fails, then /wall comes: it is read once more, and the map mounts again with its layers */
  fresh(); v = ctx.VIEWS.wall(); await tick(); meta(null); await tick(); answer(true); await v; await settle();
  const m5 = mounts; out.reread = metaAns.length; meta({ imagery: true }); await settle();
  out.reread = { asked: out.reread, mounts: mounts - m5, G: WALL().G.on_disk };
  /* a retry is the visit's that set it: a later visit clears it and gets its own, and the old one asks nothing */
  fresh(); timers.length = 0; waits.length = 0; v = ctx.VIEWS.wall(); await tick(); answer(false); await v; await tick();
  const stale = timers.shift(); v = ctx.VIEWS.wall(); await tick(); answer(false); await v; await tick();
  const asked = wallAns.length; stale(); await tick();
  out.visit = { own: timers.length, staleAsked: wallAns.length - asked };
  /* ... and one started in an earlier visit that answers in a later one takes nothing */
  fresh(); timers.length = 0; v = ctx.VIEWS.wall(); await tick(); answer(false); await v; await tick();
  timers.shift()(); await tick(); const late = ctx.VIEWS.wall(); await tick(); const m6 = mounts;
  answer(true); await tick(); await tick(); out.late = { W: !!WALL().W, mounts: mounts - m6 }; answer(false); await late; await tick();
  await drain();
  /* the first /wall starts the replay over at the base size's first hour; later ones keep it; reduced motion: hour 23 */
  reduced = false; fresh(); vm.runInContext('WALL.h = 16; WALL.s = 2; WALL.t0 = 0; wallTake(JSON.parse(WF), WALL.gen)', ctx);
  out.first = [WALL().h, WALL().s, WALL().t0 > 0]; vm.runInContext('WALL.h = 16; WALL.s = 2; wallTake(JSON.parse(WF), WALL.gen)', ctx); out.later = [WALL().h, WALL().s];
  reduced = true; fresh(); vm.runInContext('WALL.h = 4; wallTake(JSON.parse(WF), WALL.gen)', ctx); out.still = [WALL().h, WALL().s];
  await drain();
  /* a /wall that never answers gives up after WAIT and reaches the retry path */
  fresh(); honour = true; timers.length = 0; waits.length = 0; vm.runInContext('WALL_TIME.WAIT = 40', ctx);
  const hold = setTimeout(() => {}, 5000);   /* AbortSignal.timeout's timer holds no process open */
  v = ctx.VIEWS.wall(); await v; clearTimeout(hold); wallAns.length = 0; out.hung = { waits: waits.slice(), map: els['#wmbox'].innerHTML };
  while (metaAns.length) meta(null);
  /* an older TV's browser: no AbortSignal.timeout, a controller on a timer instead; with neither, the map still comes */
  ctx.AbortSignal = {}; fresh(); timers.length = 0; waits.length = 0; v = ctx.VIEWS.wall(); await tick(); while (timers.length) timers.shift()(); await v; await settle();
  out.oldTv = { waits: waits.slice(), map: els['#wmbox'].innerHTML }; wallAns.length = 0; while (metaAns.length) meta(null);
  ctx.AbortSignal = undefined; ctx.AbortController = undefined; honour = false; fresh(); v = ctx.VIEWS.wall(); await tick(); answer(true); await v; await settle();
  out.oldest = { W: !!WALL().W, map: !!WALL().map }; while (metaAns.length) meta(null);
  /* ... and with neither, a /wall that never answers still gives up after WAIT and reaches the retry path */
  fresh(); timers.length = 0; waits.length = 0; v = ctx.VIEWS.wall(); await tick(); while (timers.length) timers.shift()(); await v; await settle();
  out.oldestHung = { waits: waits.slice(), map: els['#wmbox'].innerHTML }; wallAns.length = 0; while (metaAns.length) meta(null);
  console.log(JSON.stringify(out));
})();
""" % replayed(FIX)
_rr = subprocess.run(["node"], input=rprog, capture_output=True, text=True)
assert _rr.returncode == 0, _rr.stderr[-2000:]
rt = json.loads(_rr.stdout)
assert rt["painted"] == {"strip": True, "asked": 1, "mounts": 0}, ("the strip is painted before /wall answers", rt["painted"])
assert rt["none"]["map"] == '<p class="wnomap">The node sent no map.</p>' and rt["none"]["W"] is None and rt["none"]["waits"] == [30000], rt["none"]
assert rt["backoff"] == [30000, 60000, 120000, 240000, 300000, 300000], ("30 s, then 60 s, doubling, at most 5 min", rt["backoff"])
# no /ground/meta here, so no street tiles: the base size has no Buildings or Sun to light (CodeRabbit on #406)
assert rt["came"]["mounts"] == 1 and rt["came"]["W"] and rt["came"]["chapters"] == [1, 4, 3] and rt["came"]["timers"] == 0, rt["came"]
assert rt["kept"]["W"] and rt["kept"]["chapters"] == rt["came"]["chapters"] and rt["kept"]["timers"] == 0 and rt["kept"]["map"], \
    ("a redraw whose /wall failed keeps the last good one, and asks no retry", rt["kept"])
assert rt["lost"] == {"held": {"mounts": 0, "timers": 1}, "now": 1, "fresh": True, "staleAsk": 0, "replaced": 0, "gone": 0, "waits": [2000, 4000, 2000]}, \
    ("a lost WebGL context: a new map after a pause that doubles, a visit starts it at 2 s again, only the page's own", rt["lost"])
assert rt["noMeta"]["mounts"] == 1 and rt["noMeta"]["G"] is None and "Sun today" not in rt["noMeta"]["titles"], ("/wall waited on /ground/meta", rt["noMeta"])
assert rt["meta"]["mounts"] == 2 and rt["meta"]["vector"] and "Sun today" in rt["meta"]["titles"] and rt["meta"]["asked"] == 0, ("the layers came and the map stayed bare", rt["meta"])
assert rt["reread"] == {"asked": 1, "mounts": 1, "G": {"imagery": True}}, ("/wall came without /ground/meta and it was never read again", rt["reread"])
assert rt["visit"] == {"own": 1, "staleAsked": 0}, ("a retry from an earlier visit", rt["visit"])
assert rt["late"] == {"W": False, "mounts": 0}, ("an earlier visit's retry answered in a later one and took the page", rt["late"])
assert rt["first"] == [0, 0, True] and rt["later"] == [16, 2] and rt["still"] == [23, 0], ("the first /wall starts the replay over", rt["first"], rt["later"], rt["still"])
assert rt["hung"]["waits"] == [30000] and "The node sent no map." in rt["hung"]["map"], ("a hung /wall never reached the retry path", rt["hung"])
assert rt["oldTv"]["waits"][-1] == 30000 and 40 in rt["oldTv"]["waits"] and "The node sent no map." in rt["oldTv"]["map"], ("no AbortSignal.timeout: a hung /wall never gave up", rt["oldTv"])
assert rt["oldest"] == {"W": True, "map": True}, ("no AbortSignal.timeout and no AbortController: the map never came", rt["oldest"])
assert rt["oldestHung"]["waits"][-1] == 30000 and "The node sent no map." in rt["oldestHung"]["map"], \
    ("no AbortSignal.timeout and no AbortController: a hung /wall never gave up", rt["oldestHung"])
print("doors: the Wall paints before /wall answers, asks again 30 s to 5 min while it has none, keeps the last good one, and remounts a lost map")
print("doors: /wall never waits on /ground/meta, a hung read gives up, a retry is its visit's, the first /wall starts the day over")
# Over the map, as the approved mockup has them (Tomas, 18 Nov): the size, its cells, resolution and area at the top
# left; the chapter's words with where they are from and one of the five words at the bottom left; the three sizes as
# hexagons at the bottom right, only the size on the map lit.
_scales = json.loads(Path("tests/fixtures/wall-node1.json").read_text())["scales"]
for _i, _x in enumerate(_hs):
    for _s, _o in enumerate(_x["ov"]):
        _S = _scales[_s]
        assert f"{len(_S['cells'])} cells · res {_S['res']} · {_S['km2']:.1f} km²" in _o["where"] and ("Base", "Community", "City")[_s] in _o["where"], f"size {_s} at hour {_i}: {_o['where']}"
        assert not _o["capHidden"] and re.search(r'<span class="wcs">.+ · ' + _FIVE + r'</span>$', _o["cap"]), f"size {_s} at hour {_i}: the caption has no word: {_o['cap']}"
        _lit = re.findall(r'class="s on">.*?</svg>(\w+)</div>', _o["hex"])
        assert _o["hex"].count('class="s') == 3 and _lit == [_S["k"]], f"size {_s} at hour {_i}: the legend lights {_lit}"
assert "pointer-events:none" in html[html.index(".wover{"):].split("}")[0], "a map overlay can be pressed"
assert min(t["wall"]["n"]) >= 2, f"a size with under two chapters: the rows above switched nothing ({t['wall']['n']})"
assert len({_x["strip"] for _x in _hs}) > 12, "the strip does not change with the hour"
# A size with nothing to show keeps its cells and says so in one line; it never asks for chapter -1.
assert "The node holds nothing at this size yet." in t["wall"]["bare"] and "<li" not in t["wall"]["bare"], t["wall"]["bare"]
# The strip read real figures: dust and heat each show a figure at some hour, so the checks above asserted something.
for _g, _what in ((0, "fine dust"), (1, "apparent heat")):
    assert any('class="wnum"' in re.findall(r'<div class="wrv">(.*?)</div>', _x["strip"])[_g] for _x in _hs), f"the capture drew no {_what}: the checks above asserted nothing"
# Without /issues/days the replay takes /aggregates' hours; without either, 24 hours ending at the as-of time's hour;
# five hours of /aggregates fill the last five of the 24.
from datetime import datetime
_ms = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
_nd = t["wall"]["nodays"]
assert len(_nd["B"]) == 24 and [_ms(b) for b in _nd["B"]] == [_ms(b) for b in _nd["raw"]], "without /issues/days the replay does not take /aggregates' hours"
assert len(t["wall"]["short5"]) == 24 and _ms(t["wall"]["short5"][-1]) == _ms(_nd["raw"][-1]) and \
    all(_ms(b) - _ms(a) == 3600 for a, b in zip(t["wall"]["short5"], t["wall"]["short5"][1:])), t["wall"]["short5"][-2:]
assert len(t["wall"]["nohours"]) == 24 and _ms(t["wall"]["nohours"][-1]) == _ms(t["wall"]["asof"]) // 3600 * 3600 and \
    all(_ms(b) - _ms(a) == 3600 for a, b in zip(t["wall"]["nohours"], t["wall"]["nohours"][1:])), t["wall"]["nohours"][-2:]
# A screen that cannot draw the map (no MapLibre, no WebGL; the visual rig is one) still draws the column and the strip,
# and says so in one line where the map would be.
_vw = t["wall"]["view"]
assert _vw["map"] == '<p class="wnomap">This screen cannot draw the map.</p>', _vw["map"]
assert _vw["strip"].count('class="wg"') == 4 and "Base node" in _vw["scale"] and 'class="wsent"' in _vw["wallv"], _vw
assert "WALL.h == null || WALL.still !== still" in _wsrc and "if (view() !== 'wall') { WALL.still = null; return; }" in _wsrc, \
    "motion turned on or off off the Wall resumes the old replay's hour"
# Under reduced motion the Wall is one still frame at the last hour of the base size: no replay clock, the story still.
assert _vw["h"] == 23 and _vw["s"] == 0 and not _vw["sub"], _vw
assert "{ WALL.h = still ? 23 : 0;" in _wsrc and "if (!still) CLOCK.on('wall-replay', wallTick);" in _wsrc, "the replay runs under reduced motion"
assert re.search(r"prefers-reduced-motion: reduce\)\{[^}]*\.wnarr \.nw\.roll \.nt\{animation:none", html), "the story rolls under reduced motion"
assert "#wallv *{transition:none}" in html.replace(" !important", ""), "a step on the Wall is tweened (the camera's glide is MapLibre's own)"
# The wind and the crests run on their own clock key, stopped off the Wall like the replay.
_wmjs = (STATIC / "doors-wallmap.js").read_text()
assert "CLOCK.on('wall-fx'" in _wmjs and "CLOCK.off('wall-fx')" in _wmjs and "view() !== 'wall'" in _wmjs, "the motion canvas runs off the Wall"
# Reduced motion turned on while the Wall shows stops the canvas too (CLOCK.on refuses then, but keeps a key already on),
# and leaving the Wall lets its map go, so no WebGL context runs on another door. tests/test_doors_wallmap.py runs both.
assert _wsrc.count("CLOCK.off('wall-replay'); CLOCK.off('wall-fx');") == 2, "a reduced-motion path leaves the wind running"
assert "if (v !== 'wall' && typeof WALL !== 'undefined' && WALL.map) { WALL.map.destroy(); WALL.map = null; }" in (STATIC / "doors-core.js").read_text(), \
    "leaving the Wall keeps its map"
# The story rolls when it is longer than its box (Tomas, 21 Oct: the end was cut and the start never came back), a line a step.
assert "if (!NARR.typing) narrRoll();" in _wsrc and "--roll-n" in _wsrc, "the Wall's story does not start rolling after typing"
# The marks, in reading order: the map, the words, the node's own words, the strip.
_marks = re.findall(r'data-learn="([a-z-]+)"', _wsrc.split("VIEWS.wall = ")[1].split("/* THE NODE, THINKING ALOUD")[0])
assert _marks == ["wall-map", "wall-sentence", "wall-narration", "wall-strip"], _marks
assert not re.search(r"figDust|figHeat|figSea|figWind|wallStage|wallBalance|wallCaption|\bWG\b", _wsrc), "the instruments are back"
print("doors: the Wall walks the three sizes; every strip figure has its time and word; the needles point where the sea and the wind go")

# 15 Oct, the Wall read from 3 m (Tomas's review of 14 Oct). Each check fails if its fix regresses.
# What the node suggests is one line ending on a word ("If somethin…"), and still never a button that answers.
_long = re.search(r'class="wsay said">(.*?)</span>', t["wall"]["long"]).group(1)
_say = " ".join(["Close the windows facing the street"] * 30) + "."
assert len(_long) <= 91 and _long.endswith("…") and _say.startswith(_long[:-1]) and _say[len(_long) - 1] == " ", _long   # ends on a word
assert t["wall"]["short"] == "Open the windows.", t["wall"]["short"]
assert "Answer on Telegram, not here." in t["wall"]["long"] and "<button" not in t["wall"]["long"]
# The narration box is collapsed until there is text; it keeps the last text while the next is written, and says whose.
_n = t["wall"]["narr"]
assert _n["empty"]["hidden"] and _n["asking"]["hidden"] and _n["err"]["hidden"] and not _n["empty"]["html"], _n
assert "did not answer" in _n["err"]["note"], "a failure is chrome (#wnote), never the box"
assert not _n["kept"]["hidden"] and "The air inside is calm." in _n["kept"]["html"] and "a model’s words" in _n["kept"]["html"], _n["kept"]
assert "The air<" in _n["typing"]["html"] and "calm" not in _n["typing"]["html"], _n["typing"]
print("doors: the Wall's one line and its narration box say what they should, and nothing when empty")
# THE TYPE FLOOR: every size in the Wall's CSS is --wf or a multiple of it, and --wf is 20 px at 1920x1080 (Tomas, 18 Nov:
# the text and the size legend were "too big"; it was 28). Nothing drawn on the Wall carries a class sized outside that block.
_wcss = html[html.index("/* ================= WALL:"):html.index("/* ================= FLOW:")]
assert "#wallv{--wf:min(1.0417vw,1.8519vh)" in _wcss, "the Wall's floor is not the mockup's 20 px"
_wf = re.search(r"--wf:min\(([\d.]+)vw,([\d.]+)vh\)", _wcss)
assert _wf and min(float(_wf.group(1)) * 19.2, float(_wf.group(2)) * 10.8) >= 20, "the floor is 20 px at 1920x1080"
# The one exception is the size legend over the map, at .8 of the floor: the mockup Tomas approved set it so after he
# asked for the legend smaller (18 Nov), and the controller's ruling of 18 Nov keeps it. Nothing else may go under.
_hexrule = re.search(r"\n\.whex\{[^}]*\}", _wcss).group(0)
assert "font-size:calc(var(--wf) * .8)" in _hexrule, _hexrule
_sizes = re.findall(r"font(?:-size)?:([^;}]*)", re.sub(r"/\*.*?\*/", "", _wcss.replace(_hexrule, ""), flags=re.S))
assert len(_sizes) >= 18, len(_sizes)
for _f in _sizes:
    _m = re.search(r"calc\(var\(--wf\) \* ([\d.]+)\)|var\(--wf\)|(\d[\d.]*)(px|em|rem|vw|vh)\b", _f)
    assert _m and (_m.group(0) == "var(--wf)" or (_m.group(1) and float(_m.group(1)) >= 1)), f"under the Wall's type floor: font:{_f}"
_wjs = (STATIC / "doors-wall.js").read_text().split("/* THE NODE, THINKING ALOUD")[0]
assert not re.search(r'class="(?:k|fine)\b|<small', _wjs + _wmjs), "a class sized outside the Wall's block, drawn on the Wall"
# CHROME: a wall is not operated. The back button, the chips and the hour strip are .wchrome, invisible until a pointer
# or the keyboard is in them; the back button is the first thing in keyboard order.
assert "#wallv .wchrome{opacity:0" in _wcss and "#wallv .wchrome:hover,#wallv .wchrome:focus-within{opacity:1}" in _wcss
assert re.search(r'<div class="wtop wchrome"><button class="wback"', _wjs) and "flowtime" not in _wjs, "the back button is first, the hour strip is gone"
assert "#wallv .wback{min-height:44px;min-width:44px}" in _wcss
assert "@media (any-pointer:coarse){#wallv .wchrome{opacity:1}#wallv .wback{min-height:44px;min-width:44px}}" in _wcss and "(pointer:coarse)" not in _wcss, \
    "a touch laptop whose primary pointer is a mouse cannot see or press the back button"
for _gone in ("share level", "#wall", "more</a>", "readings in", "next in", "Read at", "replay with the token"):
    assert _gone not in _wjs.lower().replace("#wallv", ""), f"admin chrome is back on the Wall: {_gone}"
print("doors: nothing on the Wall is under 20 px at 1920x1080, and its chrome shows only under a pointer or the keyboard")
# 2. One answer to "is something asked now" (14 Oct): Now's Decide said "No event was open for air" from the events while
#    the Wall showed an open ask from open_asks. Both now read /issues `asking`; run on three captures, they agree.
aprog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), now = fs.readFileSync('./app/static/doors-now.js', 'utf8'), place = fs.readFileSync('./app/static/doors-place.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0], fn = (src, n) => src.match(new RegExp('function ' + n + '[\\s\\S]*?\\n}\\n'))[0];
const out = {};
for (const [name, path] of Object.entries(JSON.parse(process.argv[1]))) {
  const F = JSON.parse(fs.readFileSync(path, 'utf8')), els = {}, D = L.buildD({ ...F, days: F.issues_days }, 'en');
  D.now = D.buckets.length - 1;
  const ctx = { D, S: { issue: null, i: D.now }, doorsLocal: L.doorsLocal, WORDS: L.WORDS, stateWord: L.stateWord, kindWord: L.kindWord, VIEWS: {}, $: q => (els[q] ||= {}), document: { querySelectorAll: () => [] } };
  vm.createContext(ctx);
  vm.runInContext(['esc', 'loc', 'dayOf', 'fmt', 'said', 'num', 'unitOf', 'labelOf', 'NODE', 'sign', 'PROV', 'prov', 'ISSUES_DRAWN'].map(pick).join('\n') + '\n'
    + 'let NOWL = null;\n' + (now.includes('function usualLine') ? fn(now, 'usualLine') : '') + fn(now, 'rows')
    + (place.includes('function yearly') ? fn(place, 'yearly') : 'function yearly() { return ""; }\n')
    + fn(core, 'evAt') + fn(core, 'answerWords') + now.match(/^const ANSWER_STAGE = .*$/m)[0] + '\n' + fn(now, 'decision') + 'function stripFold() {}\n'
    + fs.readFileSync('./app/static/doors-wall.js', 'utf8').match(/const oneLine[\s\S]*?\n};\n/)[0]
    + fs.readFileSync('./app/static/doors-wall.js', 'utf8').match(/function wallAsk[\s\S]*?\n}\n/)[0], ctx);
  /* the phone's Decide card, its own copy of the helpers (mobile.js says why) */
  const mob = fs.readFileSync('./app/static/mobile.js', 'utf8'), mpick = n => mob.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
  const pctx = { D, leadKey: null, doorsLocal: L.doorsLocal, kindWord: L.kindWord, DOORS_TOKEN: () => '' };
  vm.createContext(pctx);
  vm.runInContext(['esc', 'hhmm', 'fmt', 'said', 'ANSWER_STAGE'].map(mpick).join('\n') + '\n' + fn(mob, 'decideHTML'), pctx);
  out[name] = Object.fromEntries(D.order.map(k => {
    ctx.S.issue = k; vm.runInContext('decision()', ctx); pctx.leadKey = k;
    return [k, { wall: vm.runInContext('wallAsk(D.issues[S.issue])', ctx), now: els['#decide'].innerHTML, asking: D.issues[k].asking.length,
                 phone: vm.runInContext('decideHTML(D.issues[leadKey])', pctx) }];
  }));
  vm.runInContext('rows()', ctx);
  out[name]._rows = els['#rows'].innerHTML; out[name]._yearly = vm.runInContext('yearly()', ctx);
}
console.log(JSON.stringify(out));
"""
_caps = {n: replayed(f"app/issues/fixtures/node1-{n}.json") for n in ("2026-10-06-figures", "2026-10-06-events", "2026-09-21d")}
_ar = subprocess.run(["node", "-e", aprog, json.dumps(_caps)], capture_output=True, text=True)
assert _ar.returncode == 0, _ar.stderr[-2000:]
a = json.loads(_ar.stdout)
_fg, _ev, _ru = a["2026-10-06-figures"], a["2026-10-06-events"], a["2026-09-21d"]
# 19:22, events: air's only open alert is a stale nearby one, heat's event was answered Done. Nothing is asked, on both.
assert "Nothing is asked now." in _fg["air"]["wall"] and "Nothing is asked now." in _fg["air"]["now"], _fg["air"]
# one sentence on every screen for "nothing is asked" (Tomas, 15 Oct: "Nothing is asked now"): Now, the Wall, the phone
_said = [(STATIC / f).read_text() for f in ("doors-now.js", "doors-wall.js", "mobile.js")]
assert all("Nothing is asked now." in t for t in _said) and not any("Nothing to do now" in t for t in _said), "one sentence, three screens"
assert "No event was open" not in _fg["air"]["now"], "at the live hour Now speaks for the node's asking, not the events alone"
assert "Nothing is asked now." in _fg["heat"]["wall"] and "answered: Done" in _fg["heat"]["now"] and 'class="ans"' not in _fg["heat"]["now"]
# 09:00, events: the danger event asks, and the Wall counts it with the two nearby alerts still true. This capture has
# no /issues/days, so no event row: Now says the node's own words for it rather than "nothing is asked".
assert "3 things are asked of this house." in _ev["air"]["wall"] and "an event open since 07:18 (danger)" in _ev["air"]["now"], _ev["air"]
# 21 Sep, rules: heat's alert is still true and no event stands for it; Now draws the alert, the Wall counts it
assert "One thing is asked of this house." in _ru["heat"]["wall"] and "and still true" in _ru["heat"]["now"] and "Reply /act" in _ru["heat"]["now"], _ru["heat"]
# the card says when it was asked once, in the node's own words (4 Nov: "asked since 07:14 · still open" sat over "asked at 07:14, and still true")
_t = re.search(r"asked at (\d\d:\d\d), and still true", _ru["heat"]["now"]).group(1)
assert re.sub(r"<[^>]+>", "", _ru["heat"]["now"]).count(_t) == 1 and "still open" not in _ru["heat"]["now"], _ru["heat"]["now"]
_rows = {n: (c.pop("_rows"), c.pop("_yearly")) for n, c in a.items()}
for _cap in a.values():
    for _k, _v in _cap.items():
        assert ("Nothing is asked now." in _v["wall"]) == (_v["asking"] == 0), (_k, _v)
        # the phone says the same: an ask is drawn (the event's card or the node's words), or nothing is asked
        assert ("still open" in _v["phone"] or "data-ev" in _v["phone"]) == (_v["asking"] > 0), (_k, _v["phone"])
assert "Reply /act" in _ru["heat"]["phone"] and "Nothing is asked now." in _fg["air"]["phone"], (_ru["heat"]["phone"], _fg["air"]["phone"])
print("doors: Now's Decide card, the Wall and the phone read one answer to what is asked now, on three captures")
# NOW'S READING ORDER (Tomas, 15 Oct 2026: "I am not happy with what is showing"). Ten blocks of equal weight became
# one order: the sentence and its day, the distances in a line, What to do, Did it work and Yesterday, Around the house.
_nowh = html[html.index('<main class="face view" data-view="now">'):html.index("<!-- PLACE -->")]
_nowjs = (STATIC / "doors-now.js").read_text()
# the res 2–12 rail is Place's: Now draws none, and keeps one link to the cell on Place
assert 'id="rail"' not in _nowh and "function rail(" not in _nowjs and 'id="cellink" title="This node\'s cell, on Place"' in _nowh, \
    "the grain rail is back on Now"
# the parts in reading order, each keeping its learn mark: lead, figure, distances, buttons, then the house's states
_marks = re.findall(r'data-learn="([a-z-]+)"', _nowh)
assert _marks == ["now-sentence", "figure", "now-distances", "now-rows", "now-things", "now-around", "now-city", "now-todo", "now-worked", "now-next"], _marks
# Tomas, 9 Nov: Around the house heads the right column, the map under it, then the Index as the city's local
# production capacity; Did it work leaves the column for a row under What to do
assert _nowh.index('class="rcol"') < _nowh.index('id="rows"') < _nowh.index('class="around"') < _nowh.index('id="ncity"') < _nowh.index('class="nstrip"') < _nowh.index('id="decide"') < _nowh.index('id="nremember"') < _nowh.index('class="lcol2"') < _nowh.index('id="next"'), "Around the house, the map, the Index; then What to do as a strip, Did it work under it; then Next days across the page"
_css = (STATIC / "doors.html").read_text()
assert '"kick kick" "l r" "td td" "rm rm" "l2 l2"' in _css and '"kick" "l" "r" "td" "rm" "l2"' in _css and 'rcol2' not in _css and '.nstrip{grid-area:td' in _css and '.nrem{grid-area:rm' in _css, "What to do and Did it work span both columns, under the top row"
# What to do is one line until its button opens it (Tomas, 9 Nov: "just one line collapsed")
assert '.nstrip:not(.open) :is(#decide .dm,#decide .ans,#decide .nk,#asks,#ndecl-decide){display:none!important}' in _css, "the folded strip hides the answers and the asks"
assert "function decision() { decideLine(); stripFold(); }" in _nowjs and "stripFold();\n}" in _nowjs and "`Options to act · ${n} ↓`" in _nowjs and "NFOLD_OPEN = !NFOLD_OPEN; stripFold();" in _nowjs, "the strip folds after every redraw of What to do and the asks"
assert '.nstrip .decide{display:contents}' in _css and 'new ResizeObserver(() => map.resize())' in _nowjs, "the strip is one band; the map takes the frame's height"
# heads name the reader's question, in sentence case; no engine stage shouted on Now
assert "Around the house</h2>" in _nowh and "`Right now · " in _nowjs and '<h2 class="nh">What to do</h2>' in _nowjs
assert not re.search(r"observe · |decide · |the node’s own sentence", _nowh + _nowjs), "a capitalised engine stage is back as a head"
# Land and Coast change yearly: off Now's rows, on Place beside the ground
for _n, (_rw, _yr) in _rows.items():
    assert 'data-k="land"' not in _rw and 'data-k="coast"' not in _rw, (_n, _rw)   # a capture with no days draws no rows at all
    assert 'data-k="land"' in _yr and 'data-k="coast"' in _yr, (_n, _yr[:300])
assert 'data-k="air"' in _rows["2026-10-06-figures"][0] and 'data-k="heat"' in _rows["2026-10-06-figures"][0], _rows["2026-10-06-figures"][0]
# What to do is framed, with its buttons, only while something is asked; otherwise it is one plain line
for _n, _cap in a.items():
    for _k, _v in _cap.items():
        assert ('class="decide"' in _v["now"]) == (_v["asking"] > 0), (_n, _k, _v["now"][:300])
        assert ("Nothing is asked now." in _v["now"]) == (_v["asking"] == 0), (_n, _k, _v["now"][:300])
        assert '<h2 class="nh">What to do</h2>' in _v["now"]
# a phone: the bar's targets, and the week, are 44 px
_ph = html[html.index("@media (max-width:480px){\n"):]  # the bar's block; one-line phone rules sit before it
_ph = _ph[:_ph.index("\n}\n")]
for _sel in (".iconbtn{width:44px;height:44px", ".doors a{flex:1;display:flex;align-items:center;justify-content:center;min-height:44px", ".reg button{min-height:44px"):
    assert _sel in _ph, f"the phone bar lost a 44 px target: {_sel}"
assert ".week button{" in html and "min-height:44px" in html[html.index(".week button{"):][:400] and "week: !phone" in _nowjs
print("doors: Now reads in order: the sentence and its day, the distances, What to do (framed only when asked), Did it work, around the house; land and coast on Place")
# 6. Place's land-change row says what the node holds (node #1: nine years compared) and where it is, not "nothing"
assert re.match(r"\d+ comparisons · a count, not a shape: Land, in the figures below$", t["wall"]["pack"][0]), t["wall"]["pack"]
print("doors: Place's land-change row says what the node holds and where it is drawn")
# 11. A locked part points to where a screen is unlocked, Set up › This screen, never "under Node".
assert "under Node" not in js and "UNLOCK_AT" in _dj, "unlocking lives in Set up › This screen (#setup/screen)"
# 13. Without the token the ledger draws stages and times only (/issues gives no names; test_events_wire holds that).
# (a locked ledger naming nobody is checked by rendering it, with the Data tabs below)
# 9, 10. The household form is not the head's 20 px bold .who; a cell after a number has its gap on the left.
assert 'class="who"' not in _dj and ".who{" in html, "the household form took the page's .who rule"
assert ".tbl th.n+th:not(.n),.tbl td.n+td:not(.n){padding-left:" in html
# 12. The phone reads either token, as the doors do.
assert "const hasToken = () => !!DOORS_TOKEN();" in mobjs
print("doors: locked parts link to Set up › This screen; a locked ledger names nobody; the phone reads both tokens")
# The diary split (Tomas, 14 Oct 2026): Now says Yesterday and Did it work for the issue on screen, Node keeps the record
# in "What it remembers" as tables with the long text in a dialog, Data keeps a line pointing there. All of it needs the
# admin token: a screen without one asks nothing and is shown nothing but where to unlock; the Wall never reads it.
LEARNED = {"digests": {"day": 9, "week": 1}, "checked": "2026-10-06T00:05:00+00:00", "learnings": [
    {"kind": "worked", "key": "air-quality/events", "issue": "air-quality", "status": "holding", "n": 6, "for_whom": [],
     "statement": "Acted on 6 times: PM2.5 inside changed -4.1 µg/m³ in the 1–2 h after, while on the street it changed +0.3 µg/m³. Left unanswered 3 times: PM2.5 inside changed -0.5 µg/m³.",
     "numbers": {"acted": {"n": 6, "change": -4.1, "street": 0.3}, "unanswered": {"n": 3, "change": -0.5, "street": 0.2}, "after_hours": [1, 2],
                 "unit": "µg/m³", "verdict": "helps", "cases": {
                     "acted": [{"at": "2026-10-06T07:00:00+08:00", "before": 40.2, "after": 12.3, "change": -27.9, "street": 0.4, "note": "closed the windows, purifier on"}],
                     "unanswered": [{"at": "2026-10-05T16:00:00+08:00", "before": 30.0, "after": 28.0, "change": -2.0, "street": 1.0}]}}},
    {"kind": "worked", "key": "heat/events", "issue": "heat", "status": "too_early", "n": 2, "statement": "Acted on 2 times so far: too early to say.",
     "numbers": {"acted": {"n": 2, "change": -0.4, "street": 0.1}, "unanswered": {"n": 0, "change": None, "street": None}, "after_hours": [3, 6], "unit": "°C",
                 "verdict": "too_early", "cases": {"acted": [], "unanswered": []}}},
    {"kind": "usual", "key": "indoor-pm25", "issue": "air", "metric": "pm25", "status": "holding", "scope": "house", "statement": "Usually highest around 07:00.",
     "numbers": {"high_hour": 7, "high": 12.1, "unit": "µg/m³", "by_hour": {}}}]}
DAY = {"q": "", "results": [{"source": "digest", "scale": "day", "period_start": "2026-10-05", "label": "Sunday 5 October 2026",
        "text": "Sunday 5 October 2026. PM2.5 inside averaged 9.1 µg/m³, highest 187.3 µg/m³ (17:00); PM2.5 outside averaged 14.2 µg/m³. 2 alerts (danger 2), 1 acted on. What was done: “closed the windows”.",
        "numbers": {"indoor-pm25": {"mean": 9.1, "max": 187.3, "max_at": "2026-10-05T17:00:00+08:00", "hours": 24},
                    "outdoor-pm25": {"mean": 14.2, "max": 30.0, "max_at": "2026-10-05T18:00:00+08:00", "hours": 24},
                    "alerts": {"danger": {"raised": 2, "acted": 1}}, "notes": 1}}]}
HOUSE = {"people": {}, "choices": {"older": "someone over 65", "under5": "a child under five"}}
rprog = r"""
const fs = require('fs'), vm = require('vm');
const [path, learned, day, house] = JSON.parse(process.argv[1]);
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), now = fs.readFileSync('./app/static/doors-now.js', 'utf8'), node = fs.readFileSync('./app/static/doors-node.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0], fn = (src, n) => src.match(new RegExp('function ' + n + '[\\s\\S]*?\\n}\\n'))[0];
const calls = [];
globalThis.fetch = (p) => { calls.push(p); const b = p.startsWith('/learned/search') ? day : p === '/learned' ? learned : p === '/household' ? house : {};
  return Promise.resolve(new Response(JSON.stringify(b))); };
const L = require('./app/static/doors-load.js'), F = JSON.parse(fs.readFileSync(path, 'utf8')), D = L.buildD({ ...F, days: F.issues_days }, 'en');
D.now = D.buckets.length - 1;
const mk = () => ({ innerHTML: '', hidden: false, cls: new Set(), classList: { toggle(c, v) { this._.cls[v ? 'add' : 'delete'](c); } }, querySelectorAll: () => [], querySelector: () => ({}), scrollIntoView() {} });
const run = async (token, issue, hash) => {
  globalThis.localStorage = token ? { getItem: () => 'tok' } : undefined; calls.length = 0;
  const els = {}, dlg = [], $ = q => { if (!els[q]) { els[q] = mk(); els[q].classList._ = els[q]; } return els[q]; };
  const ctx = { D, S: { issue, i: D.now }, doorsLocal: L.doorsLocal, doorsFetch: L.doorsFetch, $, location: { hash }, setTimeout,
    document: { getElementById: () => mk() }, dayStrip: () => '', cardDialog: (t, h) => dlg.push([t, h]), DOORS_AUTH: () => ({}) };
  vm.createContext(ctx);
  vm.runInContext(['esc', 'WD', 'loc', 'dayOf', 'dLabel', 'wdhm', 'fmt', 'said', 'num', 'UNLOCK_AT'].map(pick).join('\n') + '\n' + fn(core, 'answerWords')
    + now.slice(now.indexOf('let NOWL = null;'), now.indexOf('// The things this home keeps'))
    + node.slice(node.indexOf('const LSTATUS'), node.indexOf('/* What comes in, what goes out')), ctx);
  await vm.runInContext('rememberLoad()', ctx);
  const nr = $('#nremember'), out = { hidden: nr.hidden, html: nr.innerHTML, frame: nr.cls.has('decide') };
  for (const k of ['heat', 'land']) { ctx.S.issue = k; vm.runInContext('nowRemember()', ctx); out[k] = $('#nremember').innerHTML; }
  out.usual = typeof ctx.usualLine === 'function' ? vm.runInContext("usualLine('air')", ctx) : '';
  await vm.runInContext('remember()', ctx);
  return { usual: out.usual, now: out, node: $('#remember').innerHTML, diary: $('#rdiary').innerHTML, worked: $('#rworked').innerHTML, who: $('#rwho').innerHTML, dlg, calls: calls.slice() };
};
(async () => console.log(JSON.stringify({ on: await run(true, 'air', '#node/remember/day/2026-10-05'), off: await run(false, 'air', '#node') })))();
"""
_rr = subprocess.run(["node", "-e", rprog, json.dumps([replayed(FIX), LEARNED, DAY, HOUSE])], capture_output=True, text=True)
assert _rr.returncode == 0, _rr.stderr[-2000:]
rm = json.loads(_rr.stdout)
on, off = rm["on"], rm["off"]
_n = on["now"]["html"]
assert not on["now"]["hidden"] and "<h3>Yesterday</h3>" in _n and "<h3>Did it work</h3>" in _n, _n
assert re.search(r"Yesterday the air inside averaged <span[^>]*>9\.1</span> µg/m³", _n) and "over the WHO line for" in _n and ", worse." in _n, \
    "yesterday's entry in plain words, from its own numbers and the house's hours over the line"
assert "over the WHO line for 1 hour;" in re.sub(r"<[^>]+>", "", _n), "one hour, not one hours"
assert "2 alert" in re.sub(r"<[^>]+>", "", _n) and "#node/remember/day/2026-10-05" in _n, "its alerts, and a link to the whole entry on Node"
_t = re.sub(r"<[^>]+>", "", _n)
assert "The node last asked Tue, 6 Oct at 07:18" in _t and "see What to do, above" in on["now"]["heat"] and "Done Tue, 6 Oct at 07:00: “closed the windows, purifier on”" in _t, _t
assert "Inside went from 40.2 to 12.3 µg/m³ in the 1–2 h after; the street +0.4." in _t, "what happened after: the case's own numbers"
assert "It helps here. Acted on 6 times:" in _t and "Left unanswered" not in _t, "the node's verdict, and its statement kept short"
assert "usually worst" not in _t and "who lives here?" in _t and "#node/remember/who" in _n, "the usual hour is said in What to do now"
assert "It is usually worst around 07:00 inside (12.1 µg/m³)." in re.sub(r"<[^>]+>", "", on["usual"]), on["usual"]
assert _t.index("Did it work") < _t.index("Yesterday"), "Did it work comes first, then Yesterday"
assert "The node is asking now" not in on["now"]["heat"], "heat's event was answered Done: nothing is asked, so Did it work says so too"
assert "Too early to say." in on["now"]["heat"] and "Did it work" not in on["now"]["land"], "heat is too early; land never asks"
assert not on["now"]["frame"], "no frame while nothing is asked"
assert "<h3>Yesterday" not in off["now"]["html"] and off["now"]["hidden"] and not [c for c in off["calls"] if "learned" in c or "household" in c], \
    "a screen without the token asks nothing of the house's own and shows nothing on Now"
print("doors: Now says Yesterday and Did it work for the issue on screen, from the node's numbers; nothing without the token")
assert "diary entries kept (9 days, 1 week)" in on["node"] and "never leaves" in on["node"], on["node"][:400]
assert '<table class="tbl diary">' in on["diary"] and "Sunday 5 October 2026" in on["diary"] and "187.3" in on["diary"] and "14.2" in on["diary"]
assert "closed the windows" in on["diary"] and "Against the" not in on["diary"], "what was done, from the entry"
assert on["dlg"] and on["dlg"][0][0] == "Sunday 5 October 2026" and "What was done" in on["dlg"][0][1], "#node/remember/day/<date> opens that entry"
assert '<table class="tbl worked">' in on["worked"] and "every ask about the air" in on["worked"] and "6 · -4.1" in on["worked"] and ">helps<" in on["worked"]
assert "Acted on 6 times" not in on["worked"] and "data-w=" in on["worked"], "the statement and its cases open in a dialog, not in the table"
assert 'data-f="who"' in on["who"] and "a child under five" in on["who"], "the household form lives on Node now"
assert "admin token" in off["node"] and "#setup/screen" in off["node"] and "<table" not in off["node"] and "Sunday" not in off["node"]
print("doors: Node › What it remembers holds the diary and what worked as tables, the text in a dialog; locked, it only says where to unlock")
_dh = html[html.index('data-view="data"'):html.index("<!-- WALL -->")]
assert not re.search(r'id="d-(learned|usual|diary)"', _dh) and "learnedBlock" not in _dj and 'href="#node/remember"' in _dh, \
    "Data no longer holds the diary, what is usual or what worked; it points to Node"
_wall = (STATIC / "doors-wall.js").read_text()
assert "/learned" not in _wall.replace("/learned/place", "") and "/household" not in _wall, "the Wall never reads the house's learnings"
print("doors: Data points to Node for the diary; the Wall reads none of it")

# The WHO line (Tomas, 14 Oct 2026: "put the WHO line in graphics as reference"): every drawing of PM2.5 draws the
# air's own line, red and dashed (.linep, or the same three attributes on the phone), labelled "WHO 15". Each
# drawing is rendered here on node #1's capture: Now's day (d3, on a twenty-line stand-in for the DOM), Data's
# every source, seven days and usual day, and the phone's walk. Heat keeps its own "line 35.0" and gains no line.
gprog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js'), d3 = require('./app/static/d3.min.js');
const F = JSON.parse(fs.readFileSync('%s', 'utf8'));
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), pick = n => core.match(new RegExp('^(?:const|function) ' + n + '\\b.*$', 'm'))[0];
const SVG = 'http://www.w3.org/2000/svg', doc = { createElementNS: (ns, t) => new El(t), documentElement: { namespaceURI: SVG }, body: {} };
class El {
  constructor(t) { Object.assign(this, { tagName: t, namespaceURI: SVG, ownerDocument: doc, a: {}, kids: [], textContent: '', parentNode: null,
    style: { setProperty() {}, removeProperty() {}, getPropertyValue: () => '' } }); }
  setAttribute(k, v) { this.a[k] = String(v); } removeAttribute(k) { delete this.a[k]; } getAttribute(k) { return this.a[k]; }
  appendChild(c) { c.parentNode = this; this.kids.push(c); return c; } insertBefore(c) { return this.appendChild(c); }
  removeChild(c) { this.kids = this.kids.filter(x => x !== c); return c; } addEventListener() {}
  querySelectorAll() { const o = [], w = e => e.kids.forEach(c => { o.push(c); w(c); }); w(this); return o; }
  get outerHTML() { return `<${this.tagName}${Object.entries(this.a).map(([k, v]) => ` ${k}="${v}"`).join('')}>${this.textContent}${this.kids.map(c => c.outerHTML).join('')}</${this.tagName}>`; }
}
const els = {}, ctx = { D: L.buildD({ ...F, days: F.issues_days }, 'en'), d3, document: doc, getComputedStyle: () => ({ color: '#000' }),
  doorsLocal: L.doorsLocal, VIEWS: {}, $: q => (els[q] ||= {}), out: {} };
vm.createContext(ctx);
vm.runInContext(['esc', 'WD', 'loc', 'dayOf', 'dLabel', 'fmt', 'lineLab', 'plain', 'NODE', 'sign', 'PROV', 'prov', 'said', 'num', 'unitOf', 'labelOf',
  'ISSUES_DRAWN', 'val'].map(pick).join('\n') + '\n' + fs.readFileSync('./app/static/doors-fig.js', 'utf8') + '\n' + fs.readFileSync('./app/static/doors-data.js', 'utf8')
  + `\nD.dates = [...new Set(D.buckets.map(dayOf))]; D.at = {}; D.buckets.forEach((b, i) => { D.at[dayOf(b) + '|' + hourOf(b)] = i; });
   D.now = D.buckets.length - 1; D.sens = Object.fromEntries(D.sensors.map(s => [s.sensor_id, s]));   /* doors-core.js's boot, line for line */
   const S = { i: D.now, issue: 'air' }, day = (k, w) => { const el = document.createElementNS(0, 'svg'); el.id = 'f' + w; el.parentNode = { clientWidth: w };
     dayWeek({ el, issue: k }); return el.outerHTML; };
   const H = Object.fromEntries([...Array(24).keys()].map(h => [h, 4 + h]));
   /* What is usual lives on Node now (doors-node.js usualBlock), which draws each day with this dayStrip, so: */
   sensorsBlock(); issuesBlock();
   out = { day: day('air', 900), narrow: day('air', 400), heat: day('heat', 900), usual: [dayStrip(H, D.issues.air), dayStrip(H, false)],
     sensors: $('#sensors').innerHTML, issues7: $('#issues7').innerHTML.split('<figure').slice(1) };`, ctx);
/* the walk, the phone's: its whole script on a stand-in page, for the air and for the heat */
const walk = hash => new Promise(done => {
  const E = {}, el = q => (E[q] ||= { innerHTML: '', querySelectorAll: () => [], insertAdjacentHTML() {}, remove() {} });
  const json = { '/issues': F.issues, '/issues/days?days=1': F.issues_days, '/health': F.health };
  const map = { on: (e, f) => e === 'load' && f(), getSource: () => ({ setData() {} }), getLayer: () => null, setProjection() {}, setPaintProperty() {},
    setLayoutProperty() {}, flyTo() {}, fitBounds() {} };
  const w = { doorsFetch: p => Promise.resolve(json[p] ? { ok: true, json: () => json[p] } : { ok: false }), DOORS_AUTH: () => ({}), innerHeight: 800,
    location: { hash, origin: 'http://node' }, maplibregl: { Map: function () { return map; } }, IntersectionObserver: function () { this.observe = () => {}; },
    document: { querySelector: el, querySelectorAll: () => [], addEventListener() {} } };
  w.window = w; vm.createContext(w); vm.runInContext(fs.readFileSync('./app/static/walk.js', 'utf8'), w);
  setTimeout(() => done({ ready: w.WALK_READY, chs: el('#chs').innerHTML }), 50);
});
Promise.all([walk('#air'), walk('#heat')]).then(([air, heat]) => console.log(JSON.stringify({ ...ctx.out, walk: air, walkHeat: heat })));
""" % FIX
w = json.loads(subprocess.run(["node"], input=gprog, capture_output=True, text=True, check=True).stdout)
LINEP = 'stroke="var(--signal-worse)" stroke-width="1.5" stroke-dasharray="6 4"'
for name in ("day", "narrow"):
    assert w[name].count('class="linep"') == 1 and ">WHO 15<" in w[name], f"Now's day ({name}) draws no labelled WHO line"
assert ">line 35.0<" in w["heat"] and "WHO" not in w["heat"], "heat's line keeps its own name: it is this place's, not the WHO's"
assert w["sensors"].count('class="linep"') == w["sensors"].count('class="srow"') == w["sensors"].count(">WHO 15<") > 3, \
    "Data's every source, last 24 hours: a labelled WHO line in every row"
air7 = [f for f in w["issues7"] if f.startswith(' class="sm"><figcaption><b><span class="said">Air')]
assert len(air7) == 3 and all('class="linep"' in f and ">WHO 15<" in f for f in air7), "Data's seven days: each air drawing labels its line"
assert 'class="linep"' in w["usual"][0] and ">WHO 15<" in w["usual"][0], "What is usual: the PM2.5 day draws the WHO line"
assert "linep" not in w["usual"][1], "What is usual: the heat day draws no air line"
assert w["walk"]["ready"] and w["walk"]["chs"].count(LINEP) == w["walk"]["chs"].count(">WHO 15<") == 5, \
    "the walk: the house, the street, the stations, the ring and the region each draw the labelled WHO line"
assert w["walkHeat"]["chs"].count(LINEP) == 2 and "WHO" not in w["walkHeat"]["chs"], "the walk's heat keeps its two lines, named its own"
print("doors: every PM2.5 drawing draws the air's own line, red and dashed, labelled WHO 15; heat keeps its own")
# every verdict learn.py can give has words on Now and on Node (the voice pass added `worse`, 14 Oct)
import importlib, sys as _sys                                       # noqa: E402,E401
_sys.path.insert(0, "app"); _learn = importlib.import_module("learn")
_nowjs, _nodejs = (STATIC / "doors-now.js").read_text(), (STATIC / "doors-node.js").read_text()
for _v in set(_learn.VERDICT_WORDS) - {"gone"}:
    assert re.search(rf"const VERDICT = {{[^}}]*\b{_v}:", _nowjs), f"Now has no words for the verdict {_v}"
for _v in _learn.VERDICT_WORDS:
    assert re.search(rf"const VERDICT_W = {{[^}}]*\b{_v}:", _nodejs), f"Node has no words for the verdict {_v}"
# PHASE 4a, Place and Node (Tomas, 14–15 Oct 2026). Each check fails if its fix regresses.
_place = html[html.index('<section class="page view" data-view="place"'):html.index("<!-- DATA -->")]
# SPEC_place_microgis §4, as Tomas changed it on 5 Nov 2026: the tools a menu on the top line; the cake | the screen;
# the years end to end; then the lower band, the place in figures across the page (Tomas, 9 Nov: the open map's
# table went)
assert _place.index('id="pask"') < _place.index('id="ptoolsb"') < _place.index('id="ptools"') < _place.index('id="cake"') < _place.index('class="mapc"') \
    < _place.index('id="facts"') < _place.index('id="pmargin"') < _place.index('class="pyears"') < _place.index('id="pchange"') \
    < _place.index('class="plow"') < _place.index('id="pfigures"'), \
    "Ask and Tools on the top line; the cake, the screen with its status line and the marks around the house; the years; then the lower band"
assert 'id="paddimg"' not in _place and 'class="addimg"' not in html and "addimg" not in (STATIC / "doors-place.js").read_text(), "+ Add an image left the top line: the Image key does it"
assert 'data-fold="rc"' not in _place and _place.count('class="pfold"') == 1 and 'data-s="tools"' not in _place, "one side menu, the left: no right column, no right fold, no tools sheet"
assert '<button type="button" id="ptoolsb" class="ptoolsb" aria-expanded="false" aria-controls="ptools">Tools</button><div id="ptools" class="ptmenu" role="group" aria-label="Tools" hidden>' in _place, \
    "the tools are one button with a menu it discloses"
assert 'class="pcols"' not in _place and 'id="reach"' not in _place and 'id="layers"' not in _place and 'id="pleads"' not in _place, "the old workbench is gone"
assert "const h = `<h3 class=\"pmh\">the place in figures</h3>` + yearly()" in (STATIC / "doors-place.js").read_text() and "$('#pfigures').innerHTML = h;" in (STATIC / "doors-place.js").read_text(), \
    "Land and Coast are the place's figures"
# the hydro pack in the figures (8 Nov): a Rivers row from GET /hydro, and a link that turns both map rows on and flies out
_pjs = (STATIC / "doors-place.js").read_text()
assert '<div id="phydro"></div>' in _pjs and "doorsFetch('/hydro')" in _pjs and "planetai run hydro fetch" in _pjs, "Rivers is a row of the figures"
assert "window.placeRivers = () => { setLayer('rivers', true); setLayer('basin', true); if (PM.map) fly(6); };" in (STATIC / "doors-placemap.js").read_text(), "on the map turns both rows on and goes to District"
assert "river_m: 'the nearest river, away'" in (STATIC / "doors-data.js").read_text(), "Data names the hydro figures"
_css = html[html.index("/* ================= PLACE: a small GIS"):html.index("/* ================= NODE")]
assert re.search(r"\.tools button,\.zoom button\{width:var\(--k\);height:var\(--k\)", _css), "the map's tools are --k square"
assert "--k:36px;container:place / inline-size;" in _css and "@media (pointer:coarse){.mapc{--k:44px}}" in _css, \
    "the keys inside the screen are 36 px with a pointer and 44 px under a finger (Tomas, 5 Nov 2026)"
assert not re.search(r"(width|height):44px", _css.split("@media (pointer:coarse){.mapc{--k:44px}}")[1].split("/* under the screen")[0]), "no 44 px target left inside the screen: --k sizes it"
assert ".pmpop .maplibregl-popup-close-button{font:400 18px/1 var(--mono);color:var(--ink);width:var(--k);height:var(--k)" in html, "the popup's close button follows --k too"
assert "@container place (max-width:759px){#mapbar .scales b{display:none}" in _css and "@media (min-width:761px){@container place (max-width:559px){" in _css \
    and ".mapc .nonode{right:calc(var(--k) + 24px);bottom:56px;pointer-events:none}" in _css and "width:min(300px,calc(100% - 2 * var(--k) - 302px))" in _css, \
    "the screen's controls lay out by its own width: the rungs by number under 760 px, the base and the hour move under 560 px (tests/visual/measure.mjs placescreen proves the boxes)"
assert "box-shadow:0 0 0 1px #000,0 0 0 5px #1b1b1b,0 0 0 6px #000" in _css and "border-radius:10px" in _css, "the screen sits in its bezel"
assert re.search(r"\.bench\{display:grid;grid-template-columns:224px minmax\(0,1fr\);", _css) and ".page[data-view=\"place\"]{max-width:1440px}" in _css, \
    "224 px of cake (216 until the rows' marks became switches, 17 Nov 2026: 'Water samples' was cut), and the screen takes the rest"
_v2 = _css[:_css.index("#pedges{")]   # the v2 rules; the swatches after them predate it
_v2 = _v2.replace(_v2[_v2.index(".mapc{--ink"):_v2.index(".mapw{")], "")   # the screen's own values and its bezel
if ".scr{--ink" in _v2:   # the doors' .scr screens carry the same screen values and bezel
    _i = _v2.index(".scr{--ink"); _v2 = _v2[:_i] + _v2[_v2.index("}", _i) + 1:]
assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", _v2), "no raw colour outside the screen: the frozen layer's names"
assert re.search(r"@media \(max-width:760px\)\{[^@]*\.bench\{grid-template-columns:minmax\(0,1fr\)", html), "a phone: one column, the screen first"
assert ".phour button{width:var(--k);height:var(--k)" in _css and ".pbase button{min-height:var(--k);padding:0 12px" in _css and "min-height:var(--k);padding:0 12px;border:0;border-radius:999px;background:none;color:var(--mute);cursor:pointer;font:400 11px" in _css \
    and "#altbar button{background:none;border:1px solid var(--hair);border-radius:999px;color:var(--ink);width:44px;height:44px" in _css, \
    "the hour, the base switch and the rungs follow --k; the satellite's years, on the page, keep 44 px"
assert re.search(r"@media \(max-width:760px\)\{[^@]*#cake\{display:none;position:fixed;left:0;right:0;bottom:0", html), "a phone's cake is a sheet over the lower band"
assert re.search(r"#cake\{height:0;min-height:100%;overflow-y:auto", _css), "the cake scrolls inside the bench, which the screen's column sets"
assert "#ptools{" not in _css.replace("#ptools{display", ""), "no right column is styled"
assert not re.search(r"(^|[},])\.ph[ ,{]", _css, re.M), "Place's headings are .pmh: .ph is Set up's pack card"
assert "overflow-x:auto" not in html[html.index("/* ================= NODE"):].split("\n")[1], "the flow never scrolls sideways"
pprog = r"""
const fs = require('fs'), vm = require('vm'), d3 = require('./app/static/d3.min.js');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const pm = fs.readFileSync('./app/static/doors-placemap.js', 'utf8'), place = fs.readFileSync('./app/static/doors-place.js', 'utf8'), node = fs.readFileSync('./app/static/doors-node.js', 'utf8');
const fn = (src, n) => src.match(new RegExp('(?:async )?function ' + n + '\\(' + '[\\s\\S]*?\\n}\\n'))[0];
const F = JSON.parse(fs.readFileSync('%s', 'utf8')), D = L.buildD({ ...F, days: F.issues_days }, 'en');
const out = {};
/* five on by default; the rest off */
out.on = eval(pm.match(/const LAYERS = \[[\s\S]*?\n\];/)[0] + '; LAYERS').filter(l => l.on).map(l => l.id);
out.house = !/id: '(house|species)-l'/.test(pm) && /name: 'This house', ll: D\.point/.test(pm);
out.tools = /\['From the house', 'geo\.measure', null, 'from'\]/.test(place) && !/\['inspect'/.test(pm);
const mk = () => { const els = {}; return q => (els[q] ||= { innerHTML: '', textContent: '', clientWidth: 600, clientHeight: 600, style: {}, appendChild() {}, setAttribute() {}, onclick: null }); };
const page = tok => ({ D, d3, $: mk(), console, Response, DOORS_TOKEN: () => (tok ? 't' : ''), sign: id => `<svg data-s="${id}"></svg>`, UNLOCK_AT: '<a href="#setup/screen">Set up › This screen</a>',
  doorsFetch: p => Promise.resolve(!tok ? new Response('{}', { status: 403 }) : new Response(JSON.stringify(
    p.startsWith('/species') ? { species: [{ key: 3152559, name: 'Hibiscus rosa-sinensis L.', rank: 'SPECIES', count: 2, images: 1, others: 14 }] }
    : p.startsWith('/captures') ? [{ id: 2, outside: false, analysis: { confirmed_by: 'T', findings: [{ taxon: { key: 3152559 } }] } }] : {}), { status: 200 })) });
(async () => {
  /* the species table: a table with the token, one line pointing at the unlock without it */
  for (const tok of [true, false]) {
    const c = page(tok); vm.createContext(c);
    vm.runInContext(['esc', 'num'].map(pick).join('\n') + '\n' + fn(place, 'speciesBlock') + 'speciesBlock()', c);
    await new Promise(r => setTimeout(r, 20)); out[tok ? 'sp' : 'spLocked'] = c.$('#pspecies').innerHTML;
  }
  /* the verdict, on the capture, stale, and with a failing loop */
  const v = new vm.Script(['loc', 'dayOf', 'ago'].map(pick).join('\n') + '\n' + fn(node, 'verdict') + 'verdict');
  const vc = { D, doorsLocal: L.doorsLocal }; vm.createContext(vc); const verdict = v.runInContext(vc);
  out.v = verdict(D); out.vStale = verdict({ ...D, health: { ...D.health, last_poll: '2026-10-06T08:00:00+00:00' } });
  out.vErr = verdict({ ...D, health: { ...D.health, errors: { forecast: 'boom' } } });
  out.vSrc = verdict(D, { missing: 1, sources: [{ name: 'Alerts on Telegram', ok: false, state: 'missing' }, { name: 'Weather', ok: true, state: 'ok' }, { name: 'Backup', ok: null, state: 'elsewhere' }] });
  /* the flow on a phone */
  const lay = new Function(fn(node, 'flowLayout') + 'return flowLayout;')()(358, 6, 7);
  out.flow = { W: 358, H: lay.H, right: lay.cx + lay.R, tx: lay.tx, rails: [0, 1, 2, 3, 4, 5].map(lay.inX).concat([0, 1, 2, 3, 4, 5, 6].map(lay.outX)),
    lastIn: lay.inY(5) + 15, top: lay.cy - lay.R, bottom: lay.cy + lay.R, firstOut: lay.outY(0) - 12 };
  /* no WebGL: the still map, the list and the facts all draw */
  const c = page(false), noop = () => {};
  Object.assign(c, { esc: s => String(s ?? ''), fmt: (v, d) => v == null ? '—' : (+v).toFixed(d), prov: w => w, lastRaw: () => null, plain: s => s, hhmm: s => s, when: s => s,
    CLOCK: { reduced: () => true, on: noop, off: noop }, view: () => 'place', DOORS_AUTH: () => ({}), location: { origin: 'http://node' }, devicePixelRatio: 1,
    document: { documentElement: { dataset: {} }, querySelector: () => null, querySelectorAll: () => [], createElement: () => ({ style: {}, setAttribute: noop }), addEventListener: noop },
    maplibregl: { Map: function () { throw new Error('Failed to initialize WebGL'); } }, deck: {} });
  c.window = c; c.D = { ...D, ngeo: null, ngeoErr: 'GET /geo/cell answered 403' }; vm.createContext(c);
  vm.runInContext(fs.readFileSync('./app/static/doors-cake.js', 'utf8') + '\n' + fs.readFileSync('./app/static/doors-draw.js', 'utf8') + '\n' + pm + '\nwindow.placeMap()', c);
  await new Promise(r => setTimeout(r, 50));
  out.flat ={ map: c.$('#map').innerHTML, cake: c.$('#cake').innerHTML, facts: c.$('#facts').innerHTML, margin: c.$('#pmargin').innerHTML };
  console.log(JSON.stringify(out));
})();
""" % replayed(FIX)
pp = json.loads(subprocess.run(["node"], input=pprog, capture_output=True, text=True, check=True).stdout)
assert sorted(pp["on"]) == ["images", "mine", "own", "public", "species", "street"], pp["on"]
print("doors: Place opens with five layers on: the street, the node's cell, its sensors, the public stations, the images (and their species)")
assert pp["house"] and pp["tools"], "the house is named on the map; From the house is a tool in the right column, Inspect is gone"
assert '<table class="tbl species">' in pp["sp"] and "gbif.org/species/3152559" in pp["sp"] and "in the seven cells" in pp["sp"] \
    and "14 in the seven cells" in pp["sp"], pp["sp"]
assert "<table" not in pp["spLocked"] and "#setup/screen" in pp["spLocked"], pp["spLocked"]
print("doors: the species confirmed here are a table below the map; without the token one line says where to unlock")
_f = pp["flat"]
assert "<svg" in _f["map"] and 'class="house"' in _f["map"] and "This house" not in _f["map"] and "no WebGL" in _f["map"], _f["map"][:300]
# the cake: every section in McHarg's order turned over, a row per layer, the not-yet rows dotted and disabled
_ck = _f["cake"]
assert [m for m in re.findall(r'data-cake="([a-z]+)"', _ck)] == ["results", "microclimate", "flows", "built", "animals", "plants", "soil", "water", "ground", "frame"], _ck[:300]
assert re.search(r'data-l="terrain"><button class="ly soon" aria-pressed="false" aria-disabled="true" title="Terrain · GLO-30 · not yet">', _ck), "a row the node cannot fill stays, dotted, with its source"
# one line a row (the v2 drawing): the dot, the name and one word for the source; the sentence is the title, and the status line on a press
assert "<small>GLO-30</small></button>" in _ck and "<small>" not in _ck.replace("</span><small>", "") , "a row is one line: its source word inside the row"
assert re.search(r'data-l="images"><button class="ly off held" aria-pressed="false" aria-disabled="true" title="Images · withheld · unlock this screen in Set up › This screen">.*?token-only</small>', _ck), "withheld stays visible, in a word"
assert re.search(r'data-l="public"><button class="ly on" aria-pressed="true" title="Stations · hollow · display only, never alert">', _ck), "a layer that is on says so to a screen reader"
assert "live map only" in _ck and 'data-l="index"' not in _ck and "lystrip" not in _ck, "no strip; the Index is a figure"
# the list says what it is and what a press does (Tomas, 17 Nov 2026: "make it more understandable what are buttons"):
# a head over the rows, a count that says what it counts, and the slider under a row that is on says "opacity"
assert _ck.startswith('<header class="ckh"><h2>Layers</h2><p>Press a row to draw it on the map or take it off.</p></header>'), _ck[:200]
assert re.search(r'<b>\d+ of \d+ on</b>', _ck) and not re.search(r'<b>\d+ of \d+</b>', _ck), "a section's count says what it counts"
# this capture has no WebGL, so no row carries a slider: the template is read, and the visual gate sees it drawn
assert '<label class="opw"><span class="opl">opacity</span><input class="op" type="range"' in open("app/static/doors-placemap.js").read(), "the slider says what it is"
print("doors: the layer list has a head that says what a press does, and its counts say what they count")
# locked, the images cannot draw, so four of the five are on; the status line says so
assert "In view" in _f["facts"] and "res 8 in view" in _f["facts"] and re.search(r"4 of \d+ layers on", _f["facts"]), _f["facts"][:400]
# the margin names the house, never the map; without the token the house's own rows say withheld and keep their place
assert "This house" in _f["margin"] and _f["margin"].count("<b>withheld</b>") == 2 and "This house’s stations" in _f["margin"], _f["margin"][:600]
assert _f["margin"].index("withheld") < _f["margin"].index("This house</span>"), "withheld rows stand where the house is, first" 
print("doors: Place: the cake in its sections, the house named in the list under the screen (withheld rows first without the token), the status line; without WebGL the map draws still")
assert pp["v"]["ok"] and pp["v"]["head"] == "Working" and re.match(r"Last reading 19:19; 6 of 6 sensors, \d+ of 20 stations heard in the last hour\.$", pp["v"]["text"]), pp["v"]
assert not pp["vStale"]["ok"] and pp["vStale"]["head"] == "Needs a look" and "the last reading was at" in pp["vStale"]["text"].lower(), pp["vStale"]
assert not pp["vErr"]["ok"] and "forecast loop failed" in pp["vErr"]["text"], pp["vErr"]
assert not pp["vSrc"]["ok"] and pp["vSrc"]["text"] == "Alerts on Telegram is not set up.", pp["vSrc"]   # /health/sources, with the token
print("doors: Node leads with its verdict: Working, or Needs a look and why")
_fl = pp["flow"]
assert _fl["right"] <= _fl["W"] and max(_fl["rails"]) < _fl["tx"] and _fl["lastIn"] < _fl["top"] and _fl["firstOut"] > _fl["bottom"], _fl
print("doors: under 700 px the flow is vertical, in above the hexagon and out below, inside the screen's width")
# Data as tabs (phase 4b, 15 Oct 2026): #data/<tab> draws one tab's sections and hides the rest; every anchor Data had
# still lands (its tab and element, or Node for what moved); the ledger collapses repeats, says who in words and keeps a
# stage filter, and without a token draws the time and the stage only. Rendered here in node on node #1's capture.
dprog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js'), d3 = require('./app/static/d3.min.js');
const F = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), pick = n => core.match(new RegExp('^(?:const|function) ' + n + '\\b.*$', 'm'))[0];
const els = {}, mk = id => ({ id, innerHTML: '', hidden: false, classList: { add() {}, remove() {}, toggle() {} }, querySelectorAll: () => [], querySelector: () => null, scrollIntoView() {} });
const ctx = { D: L.buildD({ ...F, days: F.issues_days }, 'en'), buildD: L.buildD, F, d3, doorsLocal: L.doorsLocal, VIEWS: {}, setTimeout: f => f(), CSS: { escape: x => x },
  $: q => (els[q.slice(1)] ||= mk(q.slice(1))), document: { getElementById: id => (els[id] ||= mk(id)), querySelector: () => null, querySelectorAll: () => [] },
  location: { hash: '', replace(h) { this.replaced = h; } }, tok: '', out: {} };
ctx.DOORS_TOKEN = () => ctx.tok;
vm.createContext(ctx);
vm.runInContext(['esc', 'WD', 'loc', 'dayOf', 'dLabel', 'wdhm', 'fmt', 'lineLab', 'plain', 'NODE', 'sign', 'PROV', 'prov', 'said', 'num', 'unitOf', 'labelOf',
  'UNLOCK_AT', 'ISSUES_DRAWN'].map(pick).join('\n') + '\n' + fs.readFileSync('./app/static/doors-data.js', 'utf8')
  + `\nD.dates = [...new Set(D.buckets.map(dayOf))]; D.now = D.buckets.length - 1; D.sens = Object.fromEntries(D.sensors.map(s => [s.sensor_id, s]));
   const calls = [], spy = n => { globalThis[n] = () => calls.push(n); };
   const real = { ledgerBlock, modelsBlock };
   ['metricTiles', 'sensorsBlock', 'issuesBlock', 'perdayBlock', 'modelsBlock', 'imagesBlock', 'thingsBlock', 'ledgerBlock', 'apiBlock', 'workbenchBlock'].forEach(spy);
   const draw = h => { calls.length = 0; location.hash = h; location.replaced = null; VIEWS.data();
     return { calls: calls.slice(), shown: Object.values(DTABS).flatMap(t => t[1]).filter(id => !document.getElementById(id).hidden),
       on: (document.getElementById('dnav').innerHTML.match(/href="(#data\\/\\w+)"[^>]*class="on"/) || [])[1] || null, node: location.replaced }; };
   out.tabs = Object.fromEntries(Object.keys(DTABS).map(t => [t, draw('#data/' + t)]));
   const sid = D.sensors.find(s => s.local && s.kind === 'sensor').sensor_id, mid = D.sensors.find(s => s.kind === 'model').sensor_id;
   out.old = Object.fromEntries(['#data', '#data/d-images', '#data/d-things', '#data/perday', '#data/issues7', '#data/cells', '#data/d-learned', '#data/' + sid, '#data/' + mid]
     .map(h => [h, draw(h)]));
   out.route = { sid: dataRoute('#data/' + sid), old: dataRoute('#data/d-things') };
   real.modelsBlock(); out.models = $('#models').innerHTML;
   tok = 'x'; real.ledgerBlock(); out.ledger = $('#ledger').innerHTML;
   LSTAGE = 'decided'; real.ledgerBlock(); out.decided = $('#ledger').innerHTML; LSTAGE = '';
   tok = ''; real.ledgerBlock(); out.locked = $('#ledger').innerHTML;
   /* the place rows come from their own route (GET /actions?stage=place), never through D.actions, which the flow counts as answers */
   const n = D.actions.length;
   D = buildD({ ...F, days: F.issues_days, place_actions: [
     { ts: '2026-10-06T09:00:00+08:00', stage: 'place', actor: 'Tomas', choice: 'drew', note: 'Rain garden on Garden plan (mark 12)', alert_id: null },
     { ts: '2026-10-06T09:01:00+08:00', stage: 'place', actor: 'Tomas', choice: 'drew', note: 'Hose run on Garden plan (mark 13)', alert_id: null }] }, 'en');
   out.flowActions = { before: n, after: D.actions.length, place: D.actions.filter(a => a.stage === 'place').length };
   tok = 'x'; real.ledgerBlock(); out.place = $('#ledger').innerHTML;
   LSTAGE = 'place'; real.ledgerBlock(); out.placeOnly = $('#ledger').innerHTML; LSTAGE = '';`, ctx);
console.log(JSON.stringify(ctx.out));
"""
_d = json.loads(subprocess.run(["node", "-e", dprog, FIX], capture_output=True, text=True, check=True).stdout)
_want = {"readings": (["metricTiles", "sensorsBlock", "issuesBlock", "perdayBlock"], ["d-readings", "issues7", "perday"]),
         "models": (["modelsBlock"], ["models"]), "home": (["imagesBlock", "thingsBlock"], ["d-images", "d-things"]),
         "ledger": (["ledgerBlock"], ["ledger", "dnote"]), "api": (["apiBlock"], ["api"]),
         "workbench": (["workbenchBlock"], ["d-workbench"])}
for _t, (_calls, _shown) in _want.items():
    _g = _d["tabs"][_t]
    assert _g["calls"] == _calls and _g["shown"] == _shown and _g["on"] == f"#data/{_t}", (_t, _g)
print("doors: each Data tab draws only its own sections, and the tab bar marks it")
_o = _d["old"]
for _h, _t in (("#data", "readings"), ("#data/d-images", "home"), ("#data/d-things", "home"), ("#data/perday", "readings"), ("#data/issues7", "readings")):
    assert _o[_h]["on"] == f"#data/{_t}" and not _o[_h]["node"], (_h, _o[_h])
assert _o["#data/cells"]["node"] == "#node/cells" and _o["#data/d-learned"]["node"] == "#node/remember", "what moved lands on Node"
_sid = [k for k in _o if k not in ("#data", "#data/d-images", "#data/d-things", "#data/perday", "#data/issues7", "#data/cells", "#data/d-learned")]
assert _o[_sid[0]]["on"] == "#data/readings" and _o[_sid[1]]["on"] == "#data/models", "a station's dot opens its readings; a model's the models"
assert _d["route"]["old"] == {"tab": "home", "el": "d-things"} and "sensor" in _d["route"]["sid"], _d["route"]
assert 'id="cells"' in html[html.index("<!-- NODE -->"):] and 'id="cells"' not in _dh and "function cellsBlock" in (STATIC / "doors-node.js").read_text()
print("doors: every anchor Data had lands on its tab and element; the Index cells and the diary land on Node")
_m = _d["models"]
assert _m.count("<table") == 1 and ">yearly" in _m and ">hourly" in _m and "P1Y" not in _m and "PT1H" not in _m, "one table, cadence in words"
# every source links to where it publishes, in a new tab (Tomas, 15 Oct)
assert 'href="https://open-meteo.com/' in _m and 'target="_blank" rel="noopener">source ↗' in _m, "a model's source links out, in a new tab"
_dj = (STATIC / "doors-data.js").read_text()
assert "smartcitizen.me/kits/" in _dj and "srcLink({ ...r.s" in _dj, "every sensor row links to its source"
assert "years" not in _m.lower().replace("yearly", "") and "fc_" not in _m and "lead" not in _m, "the node's own counters are not drawn"
assert ">hPa<" in _m and ">%<" in _m and _m.count('class="grp"') >= 5, "a unit column, a row per source"
print("doors: the models are one table, a row per source, a unit, hourly not PT1H, no internal counters")
_l, _k, _x = _d["ledger"], _d["locked"], _d["decided"]
assert "×" in _l and re.search(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2} (Sep|Oct) \d\d:\d\d", _l), "repeats collapse; a day and a time on one line"
assert ">gui<" not in _l and "local-model/" not in re.sub(r'title="[^"]*"', "", _l) and "a screen of this node" in _l and "its own model, via Telegram" in _l
assert 'data-st="decided"' in _l and "acted</td>" not in _x and "decided" in _x, "the stage filter keeps one stage"
assert "<th>who</th>" not in _k and "Tomas" not in _k and "The air" not in _k and "UNLOCK" not in _k and "Set up › This screen" in _k, "a locked ledger names nobody"
print("doors: the ledger collapses repeats, says who in words, filters by stage; locked, the time and the stage only")
_pl, _po = _d["place"], _d["placeOnly"]
assert _d["flowActions"]["before"] == _d["flowActions"]["after"] and _d["flowActions"]["place"] == 0, \
    ("the flow's answers are D.actions; place rows stay out of them", _d["flowActions"])
_ld = (STATIC / "doors-load.js").read_text()
assert "place_actions: 'actions?stage=place&limit=500'" in _ld, "the ledger's place rows have their own route"
assert "for (const k of ['readings_1h', 'actions', 'place_actions', 'alerts']) delete A[k]" in _ld, "a replayed capture drops them without the token"
assert json.loads(subprocess.run(["node", "-e", "console.log(require('./app/static/doors-load.js').DOORS_LOCKED.test('/actions?stage=place&limit=500'))"],
                                 capture_output=True, text=True, check=True).stdout), "a tokenless screen never asks for them"
assert 'data-st="place"' in _pl and "Rain garden on Garden plan" in _po and "Hose run on Garden plan" in _po, _po[-600:]
assert "(mark 12)" not in _po and "×2" not in _po and "decided" not in re.sub(r'<div class="lfilt".*?</div>', "", _po), \
    "a drawing is its own row, in words, under the place filter; the node's key stays out"
print("doors: the ledger's place stage: a filter, and a row per drawing, saying what was drawn on which map")

# Set up's consequences step: a change that leaves the machine or runs code asks first, in the setting's own words;
# a plain change, or turning one off, does not. Read from the node's own describe() and pack list.
import settings as _settings  # noqa: E402
import packs as _packs  # noqa: E402
assert "PACKS_ALLOW_CODE" in _settings.RUNS_CODE and "MAP_TILES" in _settings.OUTWARD
_desc = _settings.describe(unlocked=True)
assert all("runs_code" in r for r in _desc["runtime"]), "describe() says which settings run code"
_pk = [{"id": "a", "kind": "data", "name": "A"}, {"id": "b", "kind": "code", "name": "B", "description": "reads a meter"}]
cprog = r"""
const fs = require('fs'), vm = require('vm'), [desc, packs] = JSON.parse(process.argv[1]);
const src = fs.readFileSync('./app/static/doors-setup.js', 'utf8');
const ctx = { out: null, VIEWS: {}, document: { addEventListener() {} } }; vm.createContext(ctx);
vm.runInContext(src.slice(src.indexOf('const sOff'), src.indexOf('function sConfirm')) + `
  const c = b => sConsequences(b, ${JSON.stringify(desc)}, ${JSON.stringify(packs)}, 'a');
  out = { share: c({ SHARE_LEVEL: 'open' }), off: c({ SHARE_LEVEL: 'off', MAP_TILES: 'off', PACKS_ALLOW_CODE: '0' }), code: c({ PACKS_ALLOW_CODE: '1' }),
    plain: c({ COAST_MAX_KM: '5', NODE_ISSUES: 'air' }), tiles: c({ MAP_TILES: 'on' }), pack: c({ PACKS_ENABLED: 'a,b' }), pack2: c({ PACKS_ENABLED: '' }),
    key: c({ AGENT_ONLINE_KEY: 'sk-x' }) };`, ctx);
console.log(JSON.stringify(ctx.out));
"""
_c = json.loads(subprocess.run(["node", "-e", cprog, json.dumps([_desc, _pk])], capture_output=True, text=True, check=True).stdout)
_help = {r["key"]: r["help"] for r in _desc["runtime"]}
assert len(_c["share"]) == 1 and _c["share"][0]["leaves"] and _c["share"][0]["help"] == _help["SHARE_LEVEL"], _c["share"]
assert _c["tiles"][0]["leaves"] and _c["code"][0]["code"] and not _c["code"][0]["leaves"] and "privileges" in _c["code"][0]["help"]
assert _c["off"] == [] and _c["plain"] == [], "turning one off, or a plain setting, asks nothing"
assert [x["label"] for x in _c["pack"]] == ["B"] == [x["label"] for x in _c["pack2"]] and _c["pack"][0]["code"], "switching on a code pack asks"
assert _c["key"][0]["to"] == "a new value" and "sk-x" not in json.dumps(_c["key"]), "a secret is never repeated back"
_setup = (STATIC / "doors-setup.js").read_text()
assert "confirm(" not in _setup[_setup.index("async function sSave"):] and "sConfirm(c)" in _setup and "Save anyway" in _setup and 'data-a="back"' in _setup
# counted as the .env instruction, not every `planetai restart`: a wild pack's card says how to remove it (27 Oct)
assert "Read at start" in _setup and _setup.count("<code>.env</code> on the node, then run <code>planetai restart</code>") == 1 \
    and "edit .env" not in _setup, "what is read at start is one table, its instruction said once"
# Set up in categories (24 Oct 2026): every section in the menu has its explainer, a group no category names still
# reaches the menu (in the last one), and what leaves the machine is said on the closed row, never only inside the fold
_cats = sorted(set(re.findall(r"'([a-z]+)'", _setup[_setup.index("const SETUP_CATS"):_setup.index("const SETUP_TIPS")])))
_tips = sorted(re.findall(r"^  ([a-z]+): '", _setup[_setup.index("const SETUP_TIPS"):_setup.index("const SETUP_BOOLS")], re.M))
assert _cats == _tips, f"a section in the menu has no explainer, or an explainer no section: {_cats} vs {_tips}"
assert "cats[cats.length - 1][1].push(...[...have].filter(x => !named.has(x)))" in _setup, "an unnamed group must still reach the menu"
_grp = _setup[_setup.index("function sGroup"):_setup.index("function sGrafana")]
assert 'class="pbody"' in _grp and "mine.map(r => sRow(r, unlocked))" in _grp[_grp.index('class="pbody"'):], "a pack's settings are inside its fold"
assert _grp.index('data-pack="${esc(p.id)}"') < _grp.index('class="pbody"'), "a pack's on/off switch stays on the closed card"
assert 'class="more"' not in _setup and "class=\"sx\"" not in _setup, "rows are not folded one by one: the pack is (Tomas, 24 Oct 2026)"
assert 'role="tooltip"' in _setup and 'aria-describedby="tip-${s}"' in _setup, "the explainer is tied to its section for a screen reader"
print("doors: Set up's menu in categories, every section explained, each pack folded with its switch outside")
_gf = _setup[_setup.index("function sGrafana"):_setup.index("function sUpdates")]
assert "sGrafana(d.bootstrap" in _setup and "g === 'system' ? sGrafana" in _setup, "Set up › System draws the Grafana block"
assert "!/^GRAFANA_/.test(b.key)" in _setup, "Grafana's keys are its block, not three more rows in the start-time table"
assert "planetai grafana" in _gf and "ssh -L" in _gf and "grafana/" in _gf, "the block says how to turn it on, how to reach it, and links its page"
assert "GRAFANA_ADMIN_PASSWORD') ?" in _gf and "esc(v('GRAFANA_ADMIN_PASSWORD'))" not in _gf, "the password is only ever set or not"
print("doors: Set up asks before a change that leaves the machine or runs code, in the setting's own words, and never otherwise")

# 44 px targets: the tab bars (Data's and Set up's), Set up's switches and buttons, the ledger's filter; the tab bar
# holds on a phone and wraps rather than clipping; the gear says when Set up is open.
for _sel in (".snav a{display:flex;justify-content:space-between;align-items:center;gap:8px;min-height:44px;min-width:44px",
             "#setupv2 .sw{display:inline-flex;align-items:center;justify-content:center;min-width:64px;height:44px",
             ".sbtn{background:none;border:1px solid var(--ink);color:var(--ink);padding:0 20px;min-width:44px;height:44px", ".lfilt button{min-height:44px",
             ".dgrid .snav{position:sticky;top:0;z-index:5;background:var(--ground);flex-wrap:wrap", ".iconbtn[aria-current=\"page\"]{"):
    assert _sel in html, f"lost: {_sel}"
assert "gear.setAttribute('aria-current', 'page')" in (STATIC / "doors-core.js").read_text()
print("doors: every tab, switch and button in Data and Set up is a 44 px target; the gear shows Set up is open")
# the Wall shows no alert answers (Tomas, 16 Oct): no row of answered alerts, no rings around the house
_w = (STATIC / "doors-wall.js").read_text()
assert not re.search(r"rhoRow|RHO_ROW|wrho|F\.answers|F\.alerts|answers back", _w), "the Wall shows answers to alerts again"
assert ".wrho" not in html
print("doors: the Wall counts no answers to alerts, in words or rings")

# a newer release is one small line in the bar, hidden until /health says so, and it opens Set up › Updates
assert re.search(r'<header class="bar"[^>]*>.*id="relnote" href="#setup/updates"[^>]*hidden.*</header>', html, re.S)
assert "$('#relnote').hidden = !rel.newer" in js
print("doors: a newer release shows in the bar, and only then")
# the Place cake (SPEC_place_microgis §5): the layers in McHarg's order turned over, sky first, and no indoor sensor outside
cake = subprocess.run(["node", "-e", """
const K = require('./app/static/doors-cake.js');
const L = [{id:'own', cake:'microclimate', name:'Outdoor kit'}, {id:'soil1', cake:'soil', name:'SoilGrids', soon:true},
           {id:'street', cake:'frame', name:'Street map'}];
console.log(JSON.stringify({ids: K.CAKE.map(s => s.id), secs: K.cakeSections(L, {own:true, street:false}),
  out: K.outside([{sensor_id:'a', indoor:true}, {sensor_id:'b', indoor:false}, {sensor_id:'c'}]).map(s => s.sensor_id)}));
"""], capture_output=True, text=True, check=True)
C = json.loads(cake.stdout)
assert C["ids"] == ["results", "microclimate", "flows", "built", "animals", "plants", "soil", "water", "ground", "frame"], C["ids"]
sec = {s["id"]: s for s in C["secs"]}
assert [r["state"] for r in sec["microclimate"]["rows"]] == ["on"]
assert [r["state"] for r in sec["soil"]["rows"]] == ["soon"]
assert [r["state"] for r in sec["frame"]["rows"]] == ["off"]
assert sec["water"]["rows"] == [] and sec["water"]["classes"] == ["water"] and sec["water"]["ceiling"] == "freshwater"
assert C["out"] == ["b", "c"], C["out"]
print("  place: the cake in McHarg's order, sky first; nothing indoor")

# the Place door redrawn (SPEC_place_microgis §4): the cake left, a black screen, the tools right, a lower band
pm = (STATIC / "doors-placemap.js").read_text(); pl = (STATIC / "doors-place.js").read_text()
assert "const P = () => (PM.sheet && PM.sheet.paper ? PAL.light : PAL.dark);" in pm, "the screen is black in both registers (SPEC_place_microgis §4); only the sheet's Paper picture is light (SPEC_place_report §3)"
assert "outside(D.sensors)" in pm and pm.count("D.sensors") == pm.count("outside(D.sensors)"), "Place draws no indoor sensor"
assert "D.sensors" not in pl, "doors-place.js reads no sensor of its own"
assert all("cake:" in l for l in re.findall(r"\{ id: '[a-z]+'.*?\}", pm.split("const LAYERS = [")[1].split("];")[0])), "every layer names its cake section"
assert "group:" not in pm.split("const LAYERS = [")[1].split("];")[0] and "id: 'index'" not in pm, "no layer groups, and the Index cells are figures"
assert "PVIEWS" not in pl and 'class="pviews"' not in html, "one map: From orbit and What changed are no longer views"
assert 'id="ptable"' not in html and "function mapTable" not in pm, "the open map's table is gone from Place"
for i in ("cake", "ptools", "pfigures", "pask"):
    assert f'id="{i}"' in html, i
assert "Where the readings come from" not in html, "each cake row names its source instead"
assert "Tools run on this node with a token. Unlock this screen in Set up." in pl, "a tokenless screen says why the tools are quiet"
assert "$('#pask').hidden = !!D.askOff" in pl and "if (k !== '/' || D.askOff) return;" in pl, "UI_ASK off: the Place Ask line is not drawn and `/` does nothing"
assert "if (D.askOff) return;" in pl.split("$('#pask').onsubmit")[1].split("};")[0], "a submit on a hidden Ask line reaches nothing"
assert ".pask[hidden]{display:none}" in html, "hidden wins over the flex row"
assert "$('#askbtn').addEventListener('click', closeSheet)" in pl, "Ask opens over a phone's sheet: the sheet closes first"
_names = re.findall(r"id: '[a-z0-9]+'.*? name: '([^']+)'", pm.split("const LAYERS = [")[1].split("];")[0])
assert len(_names) == 28 and max(map(len, _names)) <= 14, ("a cake row's name must fit the 224 px column", sorted(_names, key=len)[-3:])
assert "<h2><span>${esc(s.name)}</span>" in pm and "#cake .ck>h2{" in html and "#cake h2" not in html and "<h3><span>" not in pm, "cake headings are h2 under the page's h1"
print("  place: one map, black screen, the cake on the left, tools on the right")

# The Fab City Index row on Place (GET /index/place): the place, its label and its figure, or its range and never a 0 score,
# or where to choose one. Run on the files index.fab.city served on 6 Nov 2026, as the route reshapes them.
_idx = json.loads((ROOT / "tests/data/index_place_barcelona_2026-11-06.json").read_text())
_acc = json.loads((ROOT / "tests/data/index_place_accra_2026-11-06.json").read_text())
def _route(b, tried="2026-11-06T08:00:00+00:00", ok=True, error=None):
    return {"chosen": b["place"]["slug"], "place": b["place"], "read": {"at": b["generated"], "ok": ok, "error": error, "tried": tried},
            "score": b["score"], "indicators": [{"label": i["label"], "unit": i["unit"], "source": i["source"], "latest": i["series"][-1]} for i in b["indicators"]],
            "links": {"page": b["links"]["page"], "report": b["links"]["report"]}, "registry": {"sha": "8099744", "at": None, "from": "live", "filed_here": 35}}
iprog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), place = fs.readFileSync('./app/static/doors-place.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0], fn = n => place.match(new RegExp('function ' + n + '\\([\\s\\S]*?\\n}\\n'))[0];
const F = JSON.parse(fs.readFileSync('%s', 'utf8')), out = {};
for (const [k, ip] of Object.entries(JSON.parse(process.argv[1]))) {
  const D = L.buildD({ ...F, days: F.issues_days, index_place: ip }, 'en'), els = {};
  const c = { D, $: q => (els[q] ||= {}), sign: id => `<svg data-s="${id}"></svg>`, doorsLocal: L.doorsLocal };
  vm.createContext(c);
  try { vm.runInContext(['esc', 'loc', 'num', 'PROV', 'prov'].map(pick).join('\n') + '\nfunction yearly() { return ""; }\nfunction rivers() {}\nfunction who() {}\n' + fn('indexRow') + fn('figures') + 'figures()', c); out[k] = els['#pfigures'].innerHTML; } catch (e) { out[k] = 'THROWS ' + e.message; }
}
console.log(JSON.stringify(out));
""" % FIX
_ip = json.loads(subprocess.run(["node", "-e", iprog, json.dumps({
    "bcn": _route(_idx), "acc": dict(_route(_acc), registry={"sha": "8099744", "at": None, "from": "live", "filed_here": 0}), "none": None, "stale": _route(_idx, "2026-11-08T08:00:00+00:00", False, "HTTP 503"),
    "unread": dict(_route(_idx), read={"at": None, "ok": False, "error": "x", "tried": None}, score=None, indicators=[], links=None),
    # the route's real shapes: the pack answers 200 with nothing chosen (its routes follow PACKS_ENABLED, not its switch),
    # an unknown slug has no place, and the Index may send a null where it has no figure
    "empty": {"chosen": "", "place": None, "read": {"at": None, "ok": False, "error": None, "tried": None}, "score": None, "indicators": [], "links": None,
              "registry": {"sha": "x", "at": None, "from": "pinned", "filed_here": 0}},
    "typo": {"chosen": "barcelone", "place": None, "read": {"at": None, "ok": False, "error": "not an Index place: barcelone", "tried": "2026-11-06T08:00:00+00:00"},
             "score": None, "indicators": [], "links": None, "registry": {"sha": "x", "at": None, "from": "pinned", "filed_here": 0}},
    "nullval": dict(_route(_idx), indicators=[{"label": "A", "unit": "u", "source": "s", "latest": {"year": 2022, "value": None}},
                                              {"label": "B", "unit": "u", "source": "s", "latest": {"year": 2023, "value": 5}}, None, {"label": "C", "latest": None}]),
    "nullrange": dict(_route(_acc), score=dict(_acc["score"], fci=None, fci_range=None)),
    "nullbounds": dict(_route(_acc), score=dict(_acc["score"], fci=None, fci_range=[None, 0.5])),
    "nofci": dict(_route(_idx), score=dict(_idx["score"], fci=None, fci_range=None)),
    "nolabel": dict(_route(_idx), score={"status": "partial", "fci": 0.4})})],
    capture_output=True, text=True, check=True).stdout)
_b = _ip["bcn"]
assert "Barcelona · Partial" in _b and ">0.454<" in _b and "read 2026-11-05" in _b and "35 sources filed for Barcelona in the registry" in _b, _b
assert 'class="pill' in _b and "https://index.fab.city/city?locality=barcelona" in _b and _b.index("Fab City Index ·") < _b.index("Index cells"), "the row sits above Index cells"
assert _b.count('data-num="place.index.') == 3 and "2022 · index, 0-100" in _b and ">91.3<" in _b, "the first three indicators, each with its year and unit"
assert _b.index('data-num="place.fci"') < _b.index('data-num="place.index.'), "the figure, then the indicators under it"
_a = _ip["acc"]
assert "Accra · Simulated" in _a and ">0 – 0<" in _a and "FCI 0" not in _a and 'data-num="place.fci"' not in _a and "0 sources filed for Accra" in _a, _a
assert "Choose this node's Index place" in _ip["none"] and "<code>planetai place</code>" in _ip["none"] and "Index cells" in _ip["none"], _ip["none"]
assert "last read 2026-11-05 · tried 2026-11-08" in _ip["stale"] and ">0.454<" in _ip["stale"], "a failed read keeps the last values and dates them by the file"
assert "not read yet" in _ip["unread"] and "not read</span>" in _ip["unread"] and "data-num=\"place.fci\"" not in _ip["unread"], _ip["unread"]
_row = lambda h: h.split("Index cells<small>")[0]
assert "sign-prov-partial" in _row(_b) and "sign-prov-live" not in _row(_b), "the Index's numbers are a portal's: partial, never live"
assert "sign-prov-cached" in _row(_ip["stale"]) and "sign-prov-partial" not in _row(_ip["stale"]), "a failed read is cached"
assert "sign-prov-partial" in _row(_a) and "sign-prov-live" not in _row(_a)
assert "sign-prov" not in _row(_ip["unread"]), "nothing read, nothing to say the provenance of"
assert "THROWS" not in "".join(_ip.values()), {k: v for k, v in _ip.items() if "THROWS" in v}
# nothing chosen, from the route as it answers with INDEX_PLACE empty: not chosen, no nameless row
_e = _ip["empty"]
assert "Choose this node's Index place" in _e and "<code>planetai place</code>" in _e and "not chosen" in _e and "not read yet" not in _e and "sources filed" not in _e, _e
assert 'href="https://index.fab.city/method"' in _e and "Index cells" in _e, "where to read how the Index counts a place, and the figures below still draw"
# a slug the Index does not know: said with the slug, not as "not read yet"
_t = _ip["typo"]
assert "barcelone" in _t and "not an Index place" in _t and "<code>planetai place</code>" in _t and "not read yet" not in _t and "sources filed" not in _t, _t
# the Index sent nulls: the row draws what it has and does not throw, so the map below it still draws
_n = _ip["nullval"]
assert "THROWS" not in _n and _n.count('data-num="place.index.') == 1 and ">5<" in _n and "<span>B<small>" in _n and "<span>A<small>" not in _n and "<span>C<small>" not in _n and "Index cells" in _n and "place.index.0" in _n, _n
assert "THROWS" not in _ip["nullrange"] and "not read</span>" in _ip["nullrange"] and 'data-num="place.fci' not in _ip["nullrange"] and "Accra" in _ip["nullrange"], _ip["nullrange"]
assert ">– – 0.5<" in _ip["nullbounds"] or ">– – 0.5" in _ip["nullbounds"], _ip["nullbounds"]
assert "not read</span>" in _ip["nofci"] and 'data-num="place.fci' not in _ip["nofci"] and "sign-prov" not in _row(_ip["nofci"]), "neither a figure nor a range: not read"
assert "Barcelona<small>" in _ip["nolabel"] and "Barcelona · <" not in _ip["nolabel"] and ">0.4<" in _ip["nolabel"], _ip["nolabel"]
# each indicator says its source, cut before any link, and is keyed by its place in the row (two labels can be the same)
assert "2022 · index, 0-100 · Idescat, based on INE&#39;s" in _b or "2022 · index, 0-100 · Idescat, based on INE's" in _b, _b
assert ": http" not in _b and "idescat.cat" not in _b and "Generalitat de Catalunya 69zu-w48s" in _b, "the source line stops before its link"
assert all(f'data-num="place.index.{k}"' in _b for k in range(3)) and "place.index.Residual" not in _b
# the read dates are the node's own zone, not a slice of the UTC string
assert "esc(loc(x).slice(0, 10))" in (STATIC / "doors-place.js").read_text() and "String(x || '').slice(0, 10)" not in (STATIC / "doors-place.js").read_text()
assert "index_place: 'index/place'" in (STATIC / "doors-load.js").read_text() and "index_place: A.index_place || null" in (STATIC / "doors-load.js").read_text()
print("doors: Place's Fab City Index row says the city's label and figure, a range as a range, and where to choose a place")
# Now's In the city and the head's line on Place (Tomas, 7 Nov: "it should be also in the now section"; mocked on node #1
# and approved): the brief row has the place, label, figure and date and a way to Place's figures, never the indicators or
# the registry count; the head's line is one line, or nothing when no figure has been read.
bprog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), place = fs.readFileSync('./app/static/doors-place.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0], fn = n => place.match(new RegExp('function ' + n + '\\([\\s\\S]*?\\n}\\n'))[0];
const c = { D: { tz: 'Asia/Makassar' }, sign: id => `<svg data-s="${id}"></svg>`, doorsLocal: L.doorsLocal }, out = {};
vm.createContext(c);
vm.runInContext(['esc', 'loc', 'num', 'PROV', 'prov'].map(pick).join('\n') + '\n' + fn('indexRow') + fn('indexLine') + fn('indexScreen'), c);
for (const [k, ip] of Object.entries(JSON.parse(process.argv[1]))) {
  c.P = ip; out[k] = { brief: vm.runInContext('indexRow(P, true)', c), line: vm.runInContext('indexLine(P)', c), scr: vm.runInContext('indexScreen(P)', c) };
}
console.log(JSON.stringify(out));
"""
_bp = json.loads(subprocess.run(["node", "-e", bprog, json.dumps({"bcn": _route(_idx), "acc": _route(_acc), "empty": {"chosen": "", "place": None}, "none": None, "notindex": {"chosen": "Ungasan", "place": None},
    "unread": dict(_route(_idx), score=None), "nullrange": dict(_route(_acc), score=dict(_acc["score"], fci=None, fci_range=None))})],
    capture_output=True, text=True, check=True).stdout)
_bb = _bp["bcn"]["brief"]
assert "Barcelona · Partial" in _bb and ">0.454<" in _bb and "read 2026-11-05" in _bb and 'href="#place/figures"' in _bb and "sign-prov-partial" in _bb, _bb
assert "sources filed" not in _bb and "place.index." not in _bb and "index.fab.city/city" not in _bb, "Now's row leaves the indicators, the count and the outside link to Place"
assert _bp["bcn"]["line"].startswith('<p class="lede mono">Barcelona on the Fab City Index · Partial <b>0.454</b>') and 'id="pidxgo"' in _bp["bcn"]["line"], _bp["bcn"]["line"]
assert "<b>0 – 0</b>" in _bp["acc"]["line"] and "Simulated" in _bp["acc"]["line"], "a range stays a range in the head too"
assert all(_bp[k]["line"] == "" for k in ("empty", "unread", "nullrange")), "no place or no figure: the head says nothing, the figures band says why"
_html, _nowjs, _pl = (STATIC / "doors.html").read_text(), (STATIC / "doors-now.js").read_text(), (STATIC / "doors-place.js").read_text()
assert 'id="ncity" data-learn="now-city" data-reads="/index/place"' in _html and 'data-pack="index"' in _html and '<h2 class="nh" id="ncityh">Local production capacity in the city</h2>' in _html
assert _html.index('<div class="rcol">') < _html.index('id="rows"') < _html.index('id="rose"') < _html.index('id="ncity"') < _html.index('id="ncityrow"') < _html.index('id="decide"'), "the right column: Around the house, the map, then the Index (Tomas, 9 Nov)"
assert "$('#ncityrow').innerHTML = indexScreen(D.index_place)" in _nowjs and "#ncity').hidden" not in _nowjs, "Now always draws the city screen; without an Index it says how to get one"
# the city screen (Tomas, 7 Nov): the figure large and linked to the city on the Index, 20 cells with the measured lit, the
# label once (not beside the same provenance word), the read; no city or no Index says how to get one
_sc = _bp["bcn"]["scr"]
assert '>0.454<' in _sc and 'href="https://index.fab.city/city?locality=barcelona"' in _sc and "[Barcelona]" in _sc and "1 of 20 cells measured" in _sc and "read 2026-11-05" in _sc, _sc
assert _sc.count("<i") == 20 and _sc.count('<i class="on">') == 1 and "sign-prov-partial" in _sc and "Partial ·" not in _sc and 'href="#place/figures"' in _sc, _sc
assert "0 – 0" in _bp["acc"]["scr"] and "Simulated ·" in _bp["acc"]["scr"], "a range stays a range on the screen, with its label"
assert all("planetai place" in _bp[k]["scr"] and 'href="https://index.fab.city/"' in _bp[k]["scr"] for k in ("empty", "none")), _bp["empty"]["scr"]
assert "Ungasan has no Fab City Index yet" in _bp["notindex"]["scr"] and "index.fab.city/method" in _bp["notindex"]["scr"], _bp["notindex"]["scr"]
assert '<p class="ixv">–</p>' in _bp["unread"]["scr"] and "cells measured" not in _bp["unread"]["scr"] and "sign-prov" not in _bp["unread"]["scr"], "no score read: a dash, no provenance word"
assert "location.hash === '#place/figures'" in _pl and "e.preventDefault(); go();" in _pl, "#place/figures scrolls to the figures; on Place the line scrolls without a new address"
print("doors: Now says the city in one row under Around the house, and Place's head says it in one line over the map")
# Drawing on the screen, and your maps (SPEC_place_microgis §4, §10). Booted in node with a map that does nothing and a
# deck that records its layers: the keys and the readout on the screen with a token and none without, your maps above
# the cake's results, the open map's table in the lower band, and every name and label from the node escaped.
_lk2 = json.loads(subprocess.run(["node", "-e", "const L = require('./app/static/doors-load.js'); console.log(JSON.stringify(['/place/maps', '/place/marks/3', '/place/maps/3/marks', '/place/geojson', '/place/cells', '/place/cells/8895a4c843fffff/claim', '/area'].map(p => L.DOORS_LOCKED.test(p))))"],
                                 capture_output=True, text=True, check=True).stdout)
assert _lk2 == [True] * 7, f"a tokenless screen never asks for the household's maps, cells or an area pull: {_lk2}"
# the seven as GET /place/cells answers them for node #1's cell: home, one held, one claimed, four open (app/cells.py)
import cells  # noqa: E402
_h8 = "8895a4c843fffff"; _r8 = cells.ring(_h8); _rows8 = cells.states(_h8, {_r8[1], _r8[2]}, {_r8[1]})
_SEVEN = {"home": _h8, "res": 8, "cells": _rows8, "held": cells.held_count(_rows8), "of": 7, "community_ready": False}
mprog = r"""
const fs = require('fs'), vm = require('vm'), d3 = require('./app/static/d3.min.js');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const src = ['doors-cake.js', 'doors-draw.js', 'doors-placemap.js'].map(f => fs.readFileSync('./app/static/' + f, 'utf8')).join('\n');
const place = fs.readFileSync('./app/static/doors-place.js', 'utf8'), fn = (s, n) => s.match(new RegExp('function ' + n + '\\(' + '[\\s\\S]*?\\n}\\n'))[0];
const F = JSON.parse(fs.readFileSync('%s', 'utf8')), D = L.buildD({ ...F, days: F.issues_days }, 'en');
const BAD = '<img src=x onerror=1>';
const MAPS = { maps: [{ id: 3, name: BAD, owner: 'Tomas', agent: null, shared: false, held: false, share_error: null, from_node: null, marks: 2, updated_at: '2026-11-04T10:00:00Z' },
  { id: 4, name: 'Rain on the street', owner: null, agent: null, shared: false, held: false, share_error: null, from_node: null, marks: 0, updated_at: '2026-11-03T10:00:00Z' }],
  palette: { 1: '#FFFFFF', 2: '#FFE600', 3: '#9BFF2E', 4: '#00E5FF', 5: '#FF3DCB', 6: '#FF3B30' } };
const MARKS = { marks: [
  { id: 11, map_id: 3, kind: 'area', colour: 3, label: BAD, note: 'catch the roof’s water', capture_id: null, length_m: null, area_m2: 312.4, alert_id: null, event_id: null,
    geometry: { type: 'Polygon', coordinates: [[[115.167, -8.819], [115.168, -8.819], [115.168, -8.818], [115.167, -8.819]]] } },
  { id: 12, map_id: 3, kind: 'line', colour: 2, label: 'Hose run', note: null, capture_id: 7, length_m: 102.4, area_m2: null, alert_id: null, event_id: null,
    geometry: { type: 'LineString', coordinates: [[115.167, -8.819], [115.168, -8.819]] } }] };
const noop = () => {};
const SAVED = [];   /* every file the page hands the browser to save, by its name */
const el = () => ({ innerHTML: '', textContent: '', hidden: false, style: {}, dataset: {}, kids: [], className: '', attrs: {},
  setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k]; }, appendChild(x) { this.kids.push(x); }, append(...x) { this.kids.push(...x); },
  querySelector: () => null, querySelectorAll: () => [], addEventListener: noop, remove: noop, focus: noop, closest: () => null, contains: () => false,
  click() { if (this.download) SAVED.push(this.download); },
  getContext: () => ({ setTransform: noop, clearRect: noop }), clientWidth: 900, clientHeight: 560 });
async function boot(tok, o = {}) {
  const els = {}, map = el(), asked = [], drawn = {}, patched = [], posted = [], keys = [], ons = {}, onced = [], eased = [], renders = [];
  const chip = { classList: { contains: () => true }, focus() { c.document.activeElement = chip; } };
  els['#dread'] = Object.assign(el(), { querySelector: q => (q === '.dchip' ? chip : null), contains: x => x === chip });
  const ask = (p, init = {}) => { asked.push(p); if (!tok && L.DOORS_LOCKED.test(p)) return Promise.resolve(new Response('{}', { status: 403 }));
    const own = o.route && o.route(p, init); if (own) return Promise.resolve(own);
    if (p.startsWith('/place/cells') && o.cells) return Promise.resolve(o.cells(p, init));
    if (init.method === 'PATCH') { const b = JSON.parse(init.body); patched.push(b);
      return Promise.resolve(new Response(JSON.stringify({ mark: { ...MARKS.marks.find(k => p.endsWith('/' + k.id)), ...b } }), { status: 200 })); }
    if (init.method === 'POST' && /^\/place\/maps\/\d+\/marks/.test(p)) { const b = JSON.parse(init.body); posted.push(b);
      return Promise.resolve(new Response(JSON.stringify({ mark: { id: 99, map_id: 3, kind: b.properties.kind, colour: 1, label: null, note: null, capture_id: null, geometry: b.geometry } }), { status: 200 })); }
    const f = p.match(/^\/place\/maps\/(\d+)\.(geojson|kml|dxf)\?/);
    if (f) return Promise.resolve(new Response('x', { status: 200, headers: { 'content-disposition': `attachment; filename="n-${f[1]}.${f[2]}"` } }));
    const b = p.startsWith('/ground/meta') && o.meta ? o.meta : p.startsWith('/nearby') && o.nearby ? o.nearby
      : p.startsWith('/place/maps/3/marks') ? MARKS : p.startsWith('/place/maps/4/marks') ? { marks: [] } : p.startsWith('/place/maps') ? MAPS
      : p.startsWith('/captures') ? [] : p.startsWith('/species') ? { species: [] } : {};
    return Promise.resolve(new Response(JSON.stringify(b), { status: 200 })); };
  const layer = function (props) { return { id: props && props.id, props }; };
  const c = { D: o.D || D, d3, console, Response, URL, doorsLocal: L.doorsLocal, setTimeout, clearTimeout, $: q => (els[q] ||= el()), DOORS_TOKEN: () => (tok ? 't' : ''), DOORS_AUTH: () => ({}), doorsFetch: ask,
    UNLOCK_AT: '<a href="#setup/screen">Set up › This screen</a>', sign: id => `<svg data-s="${id}"></svg>`, prov: w => w, lastRaw: () => null, plain: s => s,
    hhmm: s => s, when: s => s, dLabel: s => s, dayOf: s => s, CLOCK: { reduced: () => true, on: noop, off: noop }, view: () => 'place', location: { origin: 'http://node' },
    devicePixelRatio: 1, localStorage: { getItem: () => null, setItem: noop }, requestAnimationFrame: f => setTimeout(f, 0),
    document: { documentElement: { dataset: {} }, querySelector: () => null, querySelectorAll: () => [], createElement: () => el(), getElementById: () => null, activeElement: null,
      fullscreenEnabled: o.fs !== false, fullscreenElement: null,
      addEventListener: (t, f) => { if (t === 'keydown') keys.push(f); } },
    maplibregl: { ScaleControl: function () {}, Map: function (opts) { map.opts = opts; return Object.assign(map, { on: (t, f) => (ons[t] ||= []).push(f), once: (t, f) => { onced.push(t); renders.push(f); }, addControl: noop,
      getContainer: () => map, triggerRepaint: noop, getLayer: () => null,
      getCanvas: () => (map.cv ||= { style: {}, width: 1800, height: 1120, clientWidth: 900, focus: () => { map.focused = (map.focused || 0) + 1; } }), touchZoomRotate: { disableRotation: noop }, doubleClickZoom: { enable: noop, disable: noop }, getZoom: () => o.zoom || 13.6, resize: noop,
      project: ([x, y]) => ({ x: x * 1e4, y: -y * 1e4 }), unproject: ([x, y]) => ({ lng: x / 1e4, lat: -y / 1e4 }), easeTo: a => eased.push(a), panBy: a => (map.panned ||= []).push(a),
      getCenter: () => ({ lng: 115.167, lat: -8.819 }) }); } },
    deck: new Proxy({}, { get: (t, k) => k === 'MapboxOverlay' ? function () { return { _deck: { device: { canvasContext: { _framebuffer: 'old' } } }, setProps: x => { (x.layers || []).forEach(l => { drawn[l.id] = l.props; }); },
      pickObject: () => (o.hit ? o.hit(drawn) : null) }; } : layer }) };
  c.window = c; vm.createContext(c);
  vm.runInContext(['esc', 'fmt', 'ago'].map(pick).join('\n') + '\n' + src + '\nwindow.placeMap()', c);
  await new Promise(r => setTimeout(r, 80));
  /* a drawing pressed on the map puts it in hand (the lower band's table that did it went on 9 Nov) */
  const press = id => { const m = MARKS.marks.find(x => x.id === id), h = o.hit; o.hit = () => ({ layer: { id: 'draw-' + m.kind }, object: m });
    (ons.click || []).forEach(f => f({ lngLat: { lng: 115.1675, lat: -8.8187 }, point: { x: 1, y: 1 } })); o.hit = h; };
  const kk = map.kids.find(x => x.className === 'dkeys'), pan = map.kids.find(x => x.className === 'dpanel');
  const out = { keys: kk ? kk.innerHTML : null, panel: pan ? pan.innerHTML : null, read: c.$('#dread').innerHTML, cake: c.$('#cake').innerHTML,
    asked };
  /* without a mouse: the area in hand, an arrow moves its first point, the full stop steps, the next arrow moves the second */
  if (tok) {
    const key = k => keys.forEach(f => f({ key: k, target: { closest: () => null }, preventDefault: noop, stopPropagation: noop, shiftKey: false, metaKey: false, ctrlKey: false, altKey: false }));
    press(11); out.held = c.$('#dread').innerHTML;
    key('ArrowRight'); await new Promise(r => setTimeout(r, 650));
    key('.'); out.stepped = c.$('#dread').innerHTML;
    key('ArrowUp'); await new Promise(r => setTimeout(r, 650));
    out.patched = patched;
  }
  if (o.then) Object.assign(out, await o.then({ c, map, ons, drawn, asked, onced, eased, renders, keys, posted, press }));
  return { ...out, drawn: Object.fromEntries(Object.entries(drawn).filter(([k]) => k.startsWith('draw-')).map(([k, v]) => [k, (v.data || []).length])) };
}
(async () => {
  const out = { tok: await boot(true), locked: await boot(false) };
  /* the screen's right column, the download menu, the base and the drone pins: a node holding imagery and two drone
     flights, seen from zoom 12, below the drone layer's 13 */
  const fl = [{ provider: 'Bayu', title: 'a', gsd_m: 0.04, date: '2024-03-15', bbox: [115.15, -8.83, 115.17, -8.81] },
    { provider: 'Made', title: 'b', gsd_m: 0.031, date: '2025-11-02', bbox: [115.10, -8.80, 115.12, -8.78] }];
  const META = { on_disk: { imagery: true, drone: true }, layers: { imagery: { passes: 3, from: '2025-01', to: '2025-12', bytes: 1, attribution: 'Contains modified Copernicus Sentinel data' }, drone: { bytes: 1, mosaics: fl } } };
  const btn = d => ({ closest: () => ({ dataset: d }) });
  out.gis = await boot(true, { zoom: 12, meta: META, hit: dr => (dr['drone-pins'] ? { layer: { id: 'drone-pins' }, object: dr['drone-pins'].data[0] } : null),
    then: async ({ c, map, ons, drawn, asked, onced, eased, renders, keys }) => {
      const col = map.kids.find(x => x.className === 'tools'), menu = map.kids.find(x => x.className === 'dlmenu'), base = map.kids.find(x => x.className === 'pbase');
      const r = { col: col && col.innerHTML, imagery: c.__PM.on.imagery, base: base && base.innerHTML,
        pins: (drawn['drone-pins'] || {}).data, pinText: (drawn['drone-pins-l'] || {}).data };
      col.onclick({ target: btn({ t: 'dl' }) }); r.menu = menu && menu.innerHTML; r.menuShown = menu && !menu.hidden;
      /* everything on the screen, with the second map hidden: the PNG and the open map's three files */
      c.__PM.mapOff.add(4); SAVED.length = 0;
      menu.onclick({ target: btn({ dl: 'all' }) }); await new Promise(x => setTimeout(x, 60));
      r.files = asked.filter(p => /^\/place\/maps\/\d+\.[a-z]+\?/.test(p)); r.saved = [...SAVED]; r.png = onced.includes('render');
      /* the PNG is composed: the map's canvas, then the scale and the credit drawn on a copy, which is what is saved */
      const calls = [], cv = { width: 0, height: 0, toDataURL: () => 'data:composed', getContext: () => new Proxy({}, {
        get: (t, k) => k === 'measureText' ? s => ({ width: String(s).length * 5 }) : k in t ? t[k] : (...a) => calls.push([k, ...a]), set: (t, k, v) => { t[k] = v; return true; } }) };
      const mk = c.document.createElement; c.document.createElement = t => (t === 'canvas' ? cv : mk(t));
      renders.forEach(f => f()); c.document.createElement = mk;
      /* Map only and Full screen are wired: each press goes to the folding (doors-place.js) */
      c.placeWide = () => { r.wide = (r.wide || 0) + 1; }; c.placeFull = () => { r.full = (r.full || 0) + 1; };
      col.onclick({ target: btn({ t: 'wide' }) }); col.onclick({ target: btn({ t: 'full' }) });
      r.ops = calls.map(x => x[0]); r.texts = calls.filter(x => x[0] === 'fillText').map(x => x[1]); r.pngSaved = SAVED.filter(n => n.endsWith('.png'));
      r.credit = c.$('#mapcredit').textContent;
      /* a press that closes the menu does nothing else, even with the marker key pressed */
      c.__PM.setTool('marker'); col.onclick({ target: btn({ t: 'dl' }) }); const before = asked.length;
      (ons.click || []).forEach(f => f({ lngLat: { lng: 115.16, lat: -8.82 }, point: { x: 1, y: 1 } })); await new Promise(x => setTimeout(x, 30));
      r.closeOnly = { hidden: menu.hidden, asked: asked.slice(before), state: c.__PM.draw.state };
      c.__PM.setTool('select');
      /* Esc in the menu closes it and leaves the drawing in hand */
      c.__PM.draw.sel = 11; col.onclick({ target: btn({ t: 'dl' }) });
      const esc = { key: 'Escape', target: { closest: q => (q.includes('.dlmenu') ? {} : null) }, preventDefault: noop, stopPropagation: noop, shiftKey: false, metaKey: false, ctrlKey: false, altKey: false };
      keys.forEach(f => f(esc)); menu.onkeydown(esc); r.escKept = c.__PM.draw.sel; r.escClosed = menu.hidden;
      /* a pin pressed flies to its flight */
      (ons.click || []).forEach(f => f({ lngLat: { lng: 115.16, lat: -8.82 }, point: { x: 1, y: 1 } })); r.eased = eased;
      return r; } });
  /* a browser without element full screen (Safari on iPhone) gets no Full screen key */
  out.nofs = await boot(true, { fs: false, then: async ({ map }) => ({ col: map.kids.find(x => x.className === 'tools').innerHTML }) });
  /* past Block the satellite (10 m, tiles to zoom 15) hands the base to the street map, and a drone flight comes on
     above it; the credit line says whose picture is drawn at this zoom */
  const SATM = { on_disk: { imagery: true, drone: true, vector: true }, layers: { imagery: { attribution: 'Contains modified Copernicus Sentinel data' }, drone: { mosaics: [{ provider: 'Bayu', bbox: [115.15, -8.83, 115.17, -8.81] }] } } };
  const credit = async zoom => boot(true, { zoom, meta: SATM, then: async ({ c, map, ons }) => ({ credit: (map.kids.find(x => x.className === 'pbase').onclick({ target: { closest: () => ({ dataset: { b: 'satellite' } }) } }), c.$('#mapcredit').textContent),
    layers: map.opts.style.layers.filter(l => ['imagery', 'drone', 'drone-close'].includes(l.id)).map(l => [l.id, l.minzoom ?? null, l.maxzoom ?? null]) }) });
  out.satFar = await credit(13.6); out.satClose = await credit(16.5);
  /* a node without imagery keeps the streets as its base */
  out.plain = await boot(true, { then: async ({ c }) => ({ imagery: c.__PM.on.imagery }) });
  /* the L key pressed with the focus on the page, not the screen: once a line is started the arrows pan the map
     (Enter adds at its centre); on the canvas MapLibre pans, so the page does not pan twice */
  out.drawPan = await boot(true, { then: async ({ c, map, keys, ons }) => {
    const press = (k, inCanvas) => keys.forEach(f => f({ key: k, target: { closest: q => (inCanvas && q.includes('maplibregl-canvas-container') ? {} : null) },
      preventDefault: noop, stopPropagation: noop, shiftKey: false, metaKey: false, ctrlKey: false, altKey: false }));
    c.__PM.setTool('line'); press('ArrowRight'); const idle = (map.panned || []).length;
    press('Enter'); press('ArrowRight'); const drawing = (map.panned || []).length;
    press('ArrowRight', true); const r = { idle, drawing, canvas: (map.panned || []).length, pts: c.__PM.draw.state && c.__PM.draw.state.pts.length };
    /* a drawing key by letter hands the focus to the map; Select keeps it where it was */
    const f0 = map.focused || 0; press('v'); r.focusV = (map.focused || 0) - f0; press('a'); r.focusA = (map.focused || 0) - f0;
    /* after a frame, a framebuffer not the canvas's size (Full screen, a fold) goes, so deck draws at the new height */
    const cc = c.__PM.overlay._deck.device.canvasContext, mine = (ons.render || []).filter(f => String(f).includes('_framebuffer'));
    cc._framebuffer = { width: 1800, height: 1120 }; mine.forEach(f => f()); r.fbSame = !!cc._framebuffer;
    cc._framebuffer = { width: 1108, height: 560 }; mine.forEach(f => f()); r.fb = cc._framebuffer; return r; } });
  /* the map moving (node #1, 5 Nov): the pins on the screen's edge follow the map on `move`, one frame at a time, not
     only once it settles; the list under the screen waits for `moveend` */
  const pubs = D.sensors.filter(s => !s.local && s.indoor !== true && s.kind === 'sensor' && s.lat != null);
  out.move = await boot(true, { nearby: { ring: pubs.map(s => ({ sensor_id: s.sensor_id, km: 3 })) }, then: async ({ c, map, ons }) => {
    const before = c.$('#pedges').innerHTML, list = c.$('#pmargin').innerHTML;
    map.project = ([x, y]) => ({ x: x * 1e4 + 400, y: -y * 1e4 - 300 });
    (ons.move || []).forEach(f => f()); (ons.move || []).forEach(f => f());   /* two moves in one frame draw once */
    await new Promise(r => setTimeout(r, 20));
    return { before, after: c.$('#pedges').innerHTML, listKept: c.$('#pmargin').innerHTML === list, moves: (ons.move || []).length }; } });
  /* the Image key, now that the top line's + Add an image is gone: with nothing in hand it offers a photo on its own, and
     Enter pins a marker at the map's centre and opens the picker, whose first button is a new photo */
  /* the readout is a chip: folded at first, opened by a press, folded by a second; open by itself while a drawing of
     this house's is in hand, folded when it is let go; Esc from inside it folds it and keeps the focus on the chip */
  out.chip = await boot(true, { then: async ({ c, keys, press }) => {
    const r = {}, read = () => c.$('#dread').innerHTML, chip = c.$('#dread').querySelector('.dchip');
    const esc = inPanel => keys.forEach(f => f({ key: 'Escape', target: { closest: q => (inPanel && q === '.dpanel' ? {} : null) }, preventDefault: noop, stopPropagation: noop, shiftKey: false, metaKey: false, ctrlKey: false, altKey: false }));
    c.__PM.draw.sel = null; c.__PM.draw.open = false; c.__PM.draw.auto = false; c.__PM.readout = null;
    c.__PM.setTool('select'); r.start = read();
    chip.onclick(); r.opened = read(); chip.onclick(); r.folded = read();
    chip.onclick(); c.document.activeElement = chip; esc(true); r.escInside = { html: read(), focus: c.document.activeElement === chip };
    press(11); r.held = read();
    esc(false); r.letGo = { html: read(), sel: c.__PM.draw.sel };
    return r; } });
  out.image = await boot(true, { then: async ({ c, keys, posted }) => {
    c.__PM.draw.sel = null; c.__PM.setTool('image'); const form = c.$('#dform').innerHTML;
    keys.forEach(f => f({ key: 'Enter', target: { closest: () => null }, preventDefault: noop, stopPropagation: noop, shiftKey: false, metaKey: false, ctrlKey: false, altKey: false }));
    await new Promise(r => setTimeout(r, 40));
    return { form, posted: posted.map(b => [b.properties.kind, b.geometry.coordinates]), picker: c.$('#dform').innerHTML }; } });
  /* fix round: while a line is drawn and the map zooms without the mouse moving, the leg to the pointer keeps its end
     under the pointer (move, in the same frame as the edge pins); Esc on the Tools button leaves the screen alone; a
     press that closes Tools does nothing on the map; the Image key with no map says make one first */
  out.fix = await boot(true, { then: async ({ c, map, ons, keys, posted }) => {
    const r = {}, ev = (k, closest) => keys.forEach(f => f({ key: k, target: { closest }, preventDefault: noop, stopPropagation: noop, shiftKey: false, metaKey: false, ctrlKey: false, altKey: false }));
    c.__PM.setTool('line');
    (ons.click || []).forEach(f => f({ lngLat: { lng: 115.167, lat: -8.819 }, point: { x: 100, y: 100 } }));
    (ons.mousemove || []).forEach(f => f({ lngLat: { lng: 115.168, lat: -8.8185 }, point: { x: 300, y: 200 } }));
    r.before = c.__PM.draw.hover;
    map.unproject = ([x, y]) => ({ lng: x / 2e4 + 115, lat: -y / 2e4 - 8 });   /* the map zoomed: the same pixel is another place */
    (ons.move || []).forEach(f => f()); await new Promise(x => setTimeout(x, 20));
    r.after = c.__PM.draw.hover; c.__PM.setTool('select');
    c.__PM.draw.sel = 11; ev('Escape', q => (q.includes('.ptools') ? {} : null)); r.escTools = c.__PM.draw.sel;
    /* a tool chosen from the menu leaves the focus on the Tools button, the menu shut: the screen's keys work from there */
    c.$('#ptools').hidden = true; c.__PM.draw.sel = null; c.__PM.setTool('from');
    ev('Escape', q => (q.includes('.ptools') ? {} : null)); r.escFrom = c.__PM.tool;
    ev('m', q => (q.includes('.ptools') ? {} : null)); r.mFrom = c.__PM.tool; c.$('#ptools').hidden = false; c.__PM.setTool('select');
    /* a shape started from the keyboard has no leg to the pointer, and a zoom does not give it one */
    c.__PM.setTool('line'); ev('Enter', () => null); const kb = c.__PM.draw.hover;
    (ons.move || []).forEach(f => f()); await new Promise(x => setTimeout(x, 20)); r.kbLeg = [kb, c.__PM.draw.hover]; c.__PM.setTool('select');
    c.__PM.draw.sel = null; c.__PM.setTool('marker'); const n = posted.length;
    c.document.getElementById = id => (id === 'ptoolsb' ? { getAttribute: () => 'true' } : null);
    (ons.click || []).forEach(f => f({ lngLat: { lng: 115.16, lat: -8.82 }, point: { x: 1, y: 1 } })); await new Promise(x => setTimeout(x, 30));
    r.toolsClick = { posted: posted.length - n, state: c.__PM.draw.state };
    c.document.getElementById = () => null; c.__PM.setTool('select');
    c.__PM.draw.map = null; c.__PM.setTool('image'); r.noMap = { read: c.$('#dread').innerHTML, form: c.$('#dform').innerHTML };
    return r; } });
  /* the seven at Cell scale (seven cells, Task 5): GET /place/cells drawn by state under the 'mine' row, the line
     under the map, and a neighbour's Claim or Release, each a call to the node and the node's answer drawn again */
  const SEVEN = %s, calls = [], tick = ms => new Promise(r => setTimeout(r, ms));
  let SV = SEVEN, HIT = null;
  const cellsRoute = (p, init = {}) => { calls.push([init.method || 'GET', p]);
    if (init.method === 'POST' && p.includes(SEVEN.cells[4].cell)) return new Response(JSON.stringify({ detail: 'That cell is already the node’s.' }), { status: 409 });
    if (init.method) { const id = p.split('/')[3]; SV = { ...SV, cells: SV.cells.map(x => (x.cell === id ? { ...x, state: init.method === 'POST' ? 'claimed' : 'open' } : x)) }; }
    return new Response(JSON.stringify(SV), { status: 200 }); };
  out.seven = await boot(true, { cells: cellsRoute, hit: () => HIT, then: async ({ c, ons, drawn }) => {
    c.placeLayer('mine', true); await tick(40);   /* a redraw and the status line; the mock map cannot load a grid */
    const P = c.__PM, d = drawn.seven, r = { line: c.$('#facts').innerHTML };
    r.n = d ? d.data.length : 0;
    r.poly = d && d.getPolygon(d.data[1]);
    r.style = d && d.data.map(x => [x.state, d.getDashArray(x), d.getLineColor(x).slice(0, 3), d.getFillColor(x)[3]]);
    r.pickable = d && d.pickable;
    delete drawn.seven; P.res = 9; c.placeLayer('mine', true); r.at9 = !!drawn.seven; P.res = 8; c.placeLayer('mine', true);
    delete drawn.seven; c.placeLayer('mine', false); r.off = !!drawn.seven; c.placeLayer('mine', true);
    let BTN = null; const fx = c.$('#facts');
    fx.querySelector = q => { const m = q === '[data-claim]' && fx.innerHTML.match(/data-claim="([^"]+)" data-verb="(\w+)"/); return m ? (BTN = { dataset: { claim: m[1], verb: m[2] } }) : null; };
    const pressCell = async i => { BTN = null; HIT = { layer: { id: 'seven' }, object: SV.cells[i] };
      (ons.click || []).forEach(f => f({ lngLat: { lng: 115.167, lat: -8.819 }, point: { x: 1, y: 1 } })); await tick(30); return fx.innerHTML; };
    r.home = await pressCell(0); r.homeBtn = !!BTN;
    r.open = await pressCell(3); const n = calls.length; BTN.onclick(); await tick(40);
    r.claim = { call: calls.slice(n), after: fx.innerHTML, state: P.cells.cells[3].state, drawn: drawn.seven.data[3].state };
    r.claimed = await pressCell(2); const m = calls.length; BTN.onclick(); await tick(40);
    r.release = { call: calls.slice(m), after: fx.innerHTML, state: P.cells.cells[2].state };
    await pressCell(4); BTN.onclick(); await tick(40);
    r.refused = { after: fx.innerHTML, state: P.cells.cells[4].state };
    return r; } });
  out.sevenLocked = await boot(false, { cells: cellsRoute, then: async ({ c }) => { c.placeLayer('mine', true); await tick(40); return { line: c.$('#facts').innerHTML }; } });
  /* the Pull tool (Task 8): tap cells or choose a drawn area, then Pull; POST /area's three blocks in the inspector, each
     with its source and age, an empty one saying why, a number the node did not send a dash */
  const iso = m => new Date(Date.now() - m * 6e4).toISOString();
  const ANS = { cells: 1, res: 8,
    own: { cells: [SEVEN.cells[1].cell], sensors: 1, metrics: { pm25: { latest: 12.34, latest_at: iso(10), mean_24h: null, n: 0 } }, unplaced: 2, children_unplaced: 0 },
    peers: { sensors: 0, metrics: {}, unplaced: 1, why: 'No neighbouring node has a reading in these cells in the last 24 hours.' },
    open: [{ pack: 'hydro', source: BAD, licence: 'CC-BY 4.0', rows: [1, 2, 3], as_of: iso(125), note: 'Only the part within 3 km of the node: hydro keeps nothing further out.' },
      { pack: 'eyes', off: true, why: 'The eyes pack is off on this node: set SPECIES_MATCH=on to ask it.' },
      { pack: 'forecast', off: false, why: 'The forecast pack has nothing for this area.' },
      { pack: 'surf', error: 'The surf pack failed on this area; the node’s log says why.' }] };
  const pulls = []; let GEO = 0, REFUSE = false;
  const pullRoute = (p, init = {}) => {
    if (p.startsWith('/geo/cell?lat=')) { const x = SEVEN.cells[1 + (GEO++ %% 2)]; return new Response(JSON.stringify({ id: x.cell, res: 8, ring: x.ring }), { status: 200 }); }
    if (p === '/area') { pulls.push(JSON.parse(init.body));
      return REFUSE ? new Response(JSON.stringify({ detail: 'That selection covers more than 500 cells at resolution 8. Choose a smaller area.' }), { status: 400 })
        : new Response(JSON.stringify(ANS), { status: 200 }); }
    return null; };
  /* the mock deck keeps a layer's last props: a test deletes them first to see whether the next redraw draws it */
  out.pull = await boot(true, { route: pullRoute, cells: cellsRoute, hit: () => HIT, then: async ({ c, ons, drawn }) => {
    const P = c.__PM, fx = c.$('#facts'); let BTNS = [];
    fx.querySelectorAll = q => (q === '[data-pull]' ? (BTNS = [...fx.innerHTML.matchAll(/data-pull="([^"]+)"/g)].map(m => ({ dataset: { pull: m[1] } }))) : []);
    const btn = k => BTNS.find(b => b.dataset.pull === k);
    const tap = async () => { HIT = null; (ons.click || []).forEach(f => f({ lngLat: { lng: 115.167, lat: -8.819 }, point: { x: 1, y: 1 } })); await tick(30); };
    P.setTool('pull'); await tick(20);
    const r = { start: fx.innerHTML, read: c.$('#dread').innerHTML };
    await tap(); await tap(); r.two = { n: drawn.pull ? drawn.pull.data.length : 0, html: fx.innerHTML, poly: drawn.pull && drawn.pull.getPolygon(drawn.pull.data[0]) };
    await tap(); r.one = { n: drawn.pull ? drawn.pull.data.length : 0, ids: P.pull.cells.map(x => x.id) };
    btn('go').onclick(); await tick(40);
    r.asked = pulls.slice(); r.ans = fx.innerHTML;
    delete drawn.pull; btn('m11').onclick(); await tick(20); r.marked = { html: fx.innerHTML, n: drawn.pull ? drawn.pull.data.length : 0 };
    btn('go').onclick(); await tick(40); r.markAsked = pulls[pulls.length - 1];
    REFUSE = true; btn('go').onclick(); await tick(40); r.refused = fx.innerHTML; REFUSE = false;
    btn('clear').onclick(); await tick(20); r.cleared = { html: fx.innerHTML, mark: P.pull.mark, n: P.pull.cells.length };
    HIT = { layer: { id: 'draw-area' }, object: MARKS.marks[0] }; (ons.click || []).forEach(f => f({ lngLat: { lng: 115.1675, lat: -8.8187 }, point: { x: 1, y: 1 } })); await tick(20);
    r.pressedMark = P.pull.mark;
    delete drawn.pull; P.setTool('select'); await tick(20); r.left = { pull: P.pull, drawn: drawn.pull ? drawn.pull.data.length : 0 };
    return r; } });
  /* From the house, in the Tools menu: a tool row that runs with the token */
  const els = {}, c = { $: q => (els[q] ||= el()), DOORS_TOKEN: () => 't', document: { activeElement: null, querySelectorAll: () => [], querySelector: () => null }, window: { __PM: { on: {}, tool: 'select' } } };
  vm.createContext(c); vm.runInContext(place.match(/const TOOLS = [\s\S]*?\n\];\n/)[0] + fn(place, 'placeTools') + 'placeTools()', c);
  out.ptools = c.$('#ptools').innerHTML;
  console.log(JSON.stringify(out));
})();
""" % (replayed(FIX), json.dumps(_SEVEN))
_r = subprocess.run(["node"], input=mprog, capture_output=True, text=True)
assert _r.returncode == 0, _r.stderr[-3000:]
M = json.loads(_r.stdout)
# the seven at Cell scale (seven cells, Task 5)
_sv, _svl = M["seven"], M["sevenLocked"]
assert "2 of 7 cells held" in _sv["line"], ("the line under the map says how many of the seven are held", _sv["line"][:500])
assert _sv["n"] == 7 and _sv["pickable"], ("the seven are one pickable layer at Cell scale", _sv["n"])
assert len(_sv["poly"]) == 7 and _sv["poly"][0] == _sv["poly"][-1] and _sv["poly"][0] == [_rows8[1]["ring"][2], _rows8[1]["ring"][1]], \
    ("a cell's outline is the node's ring, reordered to [lng, lat] and closed, never computed", _sv["poly"])
_CELLS, _MUTE = [127, 165, 232], [163, 161, 159]
_st = {s[0]: s[1:] for s in _sv["style"]}
assert set(_st) == {"home", "held", "claimed", "open"}, _st
assert all(v[1] in (_CELLS, _MUTE) for v in _st.values()), ("the seven take the screen's own colours, no new one", _st)
assert _st["home"][1] == _st["held"][1] == _st["claimed"][1] == _CELLS and _st["open"][1] == _MUTE, _st
assert len({json.dumps(v) for v in _st.values()}) == 4 and _st["claimed"][0] != _st["held"][0] and _st["open"][2] == 0, \
    ("each state draws apart: held solid, claimed dashed, open grey, unfilled", _st)
assert not _sv["at9"] and not _sv["off"], "the seven draw at Cell scale only, and with the node's cell row"
assert "home" in _sv["home"] and not _sv["homeBtn"], ("home is never claimed or released", _sv["home"][:400])
assert 'data-verb="claim"' in _sv["open"] and "Claim this cell" in _sv["open"], _sv["open"][:500]
assert _sv["claim"]["call"] == [["POST", f"/place/cells/{_r8[3]}/claim?actor="]], _sv["claim"]["call"]
assert _sv["claim"]["state"] == "claimed" and _sv["claim"]["drawn"] == "claimed" and 'data-verb="release"' in _sv["claim"]["after"], \
    ("the node's answer is drawn again: the cell is claimed, and offers Release", _sv["claim"])
assert _sv["release"]["call"] == [["DELETE", f"/place/cells/{_r8[2]}/claim?actor="]] and _sv["release"]["state"] == "open", _sv["release"]
assert "That cell is already the node’s." in _sv["refused"]["after"] and _sv["refused"]["state"] == "open", ("a refusal says the node's sentence", _sv["refused"])
assert "cells held" not in _svl["line"] and "/place/cells" not in _svl["line"], ("without the token the line says nothing of the seven", _svl["line"][:400])
print("  place: at Cell scale the seven are drawn by state; the line under the map says how many are held; a neighbour claims or releases")
_pu = M["pull"]
assert "data-pull" in _pu["start"] and 'data-pull="m11"' in _pu["start"] and 'data-pull="go"' not in _pu["start"], \
    ("Pull starts with what to do and the household's drawn areas to choose, and nothing to send yet", _pu["start"][:600])
assert "&lt;img" in _pu["start"] and "<img src=x" not in _pu["start"], "a drawing's label is escaped"
assert "pull" in _pu["read"], ("the readout names the tool", _pu["read"][:300])
assert _pu["two"]["n"] == 2 and 'data-pull="go"' in _pu["two"]["html"] and "2 cells" in _pu["two"]["html"], ("two taps, two cells on the map, and Pull", _pu["two"]["html"][:400])
assert _pu["two"]["poly"] and _pu["two"]["poly"][0] == _pu["two"]["poly"][-1], "a tapped cell is drawn by the node's own outline, closed"
assert _pu["one"]["n"] == 1 and _pu["one"]["ids"] == [_rows8[2]["cell"]], ("a second tap on a cell lets it go", _pu["one"])
assert _pu["asked"] == [{"cells": [_rows8[2]["cell"]]}], ("Pull sends the cells tapped", _pu["asked"])
_a = _pu["ans"]
for said in ("12.3", "10 min old", "2 h old", "No neighbouring node has a reading in these cells in the last 24 hours.", "set SPECIES_MATCH=on to ask it",
             "The forecast pack has nothing for this area.", "failed on this area", "Only the part within 3 km", "CC-BY 4.0"):
    assert said in _a, (f"the answer says {said!r}", _a[:1500])
assert "&lt;img" in _a and "<img src=x" not in _a, "a source's words are escaped"
assert "0.0" not in _a and "—" in _a, ("a 24 h mean the node did not send is a dash, never 0", _a[:1500])
assert re.search(r"\b2\b[^<]*no place", _a) and re.search(r"\b1\b[^<]*(distance|no place)", _a), ("own and peers say how many they could not place", _a[:1500])
assert _a.count('class="pb"') == 6, ("three blocks: own, peers, and one per open source", _a.count('class="pb"'))
assert _pu["marked"]["n"] == 0 and 'aria-pressed="true"' in _pu["marked"]["html"] and _pu["markAsked"] == {"mark_id": 11}, \
    ("a drawn area chosen replaces the cells and is sent by its number", _pu["marked"]["n"], _pu["markAsked"])
assert "That selection covers more than 500 cells" in _pu["refused"], ("a refusal says the node's sentence", _pu["refused"][:400])
assert _pu["cleared"]["mark"] is None and _pu["cleared"]["n"] == 0 and 'data-pull="go"' not in _pu["cleared"]["html"], _pu["cleared"]
assert _pu["pressedMark"] == 11, "a press on one of the household's drawn areas chooses it"
assert _pu["left"]["pull"] is None and _pu["left"]["drawn"] == 0, ("leaving the tool lets the selection go", _pu["left"])
print("  place: Pull takes tapped cells or a drawn area, asks POST /area, and draws own, peers and open sources with source and age, each empty one saying why")
_t, _x = M["tok"], M["locked"]
_keys = re.findall(r'<button[^>]*aria-label="([^"]+)"[^>]*aria-pressed="(true|false)"', _t["keys"] or "")
assert [k for k, _ in _keys] == ["Select", "Marker", "Line, with distance", "Area, with surface", "Note", "Image"] and [p for _, p in _keys].count("true") == 1, _keys
assert re.search(r'<button[^>]*aria-label="Undo"', _t["keys"]) and _keys[0][1] == "true", "an Undo key, and Select pressed to start"
assert all(f"<kbd>{k}</kbd>" in _t["keys"] for k in "VMLANI") and _t["keys"].startswith('<b class="dkh" aria-hidden="true">Draw</b>'), \
    "a head over the keys, and each key's letter beside its name"
assert 'id="dsaid" class="vh" aria-live="polite"' in _t["panel"] and 'id="dread" class="dread">' in _t["panel"], \
    "only the finished figure is live; the readout that follows the pointer is not"
assert "&lt;img src=x onerror=1&gt;" in _t["read"], "the readout names the open map, escaped"
print("  place: six drawing keys and Undo on the screen, Select pressed; the kept figure is aria-live; the readout names the open map")
_ring = [[115.167, -8.819], [115.168, -8.819], [115.168, -8.818]]
_p1, _p2 = [x["geometry"]["coordinates"][0] for x in _t["patched"]]
assert "Arrows move point 1 of 3. Press . for the next point." in _t["held"] and "point 2 of 3" in _t["stepped"], (_t["held"], _t["stepped"])
assert _p1[0] != _ring[0] and _p1[1:3] == _ring[1:3] and _p1[0] == _p1[-1], ("the first arrow moves the first point, the ring stays closed", _p1)
assert _p2[0] == _p1[0] and _p2[1] != _ring[1] and _p2[1][1] > _ring[1][1] and _p2[2] == _ring[2], ("after the full stop the arrow moves the second point, up", _p2)
print("  place: without a mouse, a drawing in hand moves point by point: the arrows move one, the full stop steps to the next")
_ck = _t["cake"]
assert _ck.index('id="ymaps"') < _ck.index('data-cake="results"'), "your maps sit above the results"
assert _ck.index('class="ly map') < _ck.index('class="ly new"') and ">New map<" in _ck, "a square-dot row per map, then New map"
assert _ck.count('class="ly map') == 2 and "2 drawn" in _ck and "0 drawn" in _ck, _ck[:800]
assert "<img src=x" not in _ck and "&lt;img src=x onerror=1&gt;" in _ck, "a map's name is the household's text, escaped"
assert _t["drawn"].get("draw-area") == 1 and _t["drawn"].get("draw-line") == 1, ("the drawings are deck.gl layers, so the PNG holds them", _t["drawn"])
assert "/place/maps" in _t["asked"] and "/place/maps/3/marks" in _t["asked"], _t["asked"]
print("  place: your maps above the cake, then New map; names escaped")
assert _x["keys"] is None and _x["panel"] is None, "without the token no key is drawn"
_ys = re.sub(r"<[^>]+>", "", _x["cake"][_x["cake"].index('id="ymaps"'):_x["cake"].index('data-cake="results"')])
assert "Your maps are kept on this node. Unlock this screen in Set up to draw." in _ys and 'class="ly new"' not in _x["cake"], _ys
assert not [p for p in _x["asked"] if p.startswith(("/place/maps", "/place/marks"))], "a tokenless screen does not ask for maps"
print("  place: without the token, your maps say where they are and how to unlock; no key, no New map")
assert 'data-tool="from"' in M["ptools"] and "From the house" in M["ptools"], M["ptools"][:400]
assert 'data-tool="pull"' in M["ptools"] and "<span>Pull</span><code>area.pull</code>" in M["ptools"], ("Pull is a Tools row with its command id", M["ptools"][:600])
assert 'data-go="#place/report"' in M["ptools"] and "<code>place.report</code>" in M["ptools"], "the Place report is a tool row with its id (SPEC_place_report §9)"
_css = html[html.index("/* ================= PLACE: a small GIS"):html.index("/* ================= NODE")]
assert ".dkeys button{width:100%;height:var(--k)" in _css and ".dkeys button{width:var(--k);grid-template-columns:var(--k);padding:0}" in _css and ".dread .dsw button{flex:none;width:var(--k);height:var(--k)" in _css and re.search(r"\.dkeys button:focus-visible,\.dchip:focus-visible,\.dpanel button:focus-visible,\.dpanel input:focus-visible,"
                                                                    r"\.dpanel textarea:focus-visible,\.dpanel select:focus-visible\{outline:2px solid var\(--cells\)", _css), \
    "--k keys (a row with its name when the screen is wide, a --k square when it folds) and swatches; focus on the black screen is the cells' blue, as the hour pill's"
assert "p.cells" in pm[pm.index("function drawLayers"):pm.index("function drawLayers") + 4000], "a drawing in focus is outlined in the cells' blue"
assert ".ly,.ly.new,.tl,.spd summary{min-height:44px}" in html, "New map is a 44 px target on a phone, like the rows (its own 28 px outranked the phone rule; final review, 17 Nov)"
assert ".ly[aria-disabled=\"true\"] i{" in _css and ".ly.held[aria-disabled=\"true\"] i{border-style:dashed}" in _css, \
    "a row that cannot switch, for any reason, has the small mark and never a dead switch; a locked one's is dashed"
assert ".ly.map i{border-radius:3px}" in _css and ".ly i{position:relative;width:22px;height:12px;border-radius:999px" in _css, "a map's switch is square, a layer's round"
assert "'The image stays on this node. The map only names which one it is, and the file never leaves.'" in pm and "never the file’s" not in pm, \
    "the image hint says only what is true: a photo's own GPS still wins on the node"
print("  place: From the house in the Tools menu; --k keys; focus is the cells' blue on the screen")

# Share's second press sends the map exactly, so only the node's own warning (409, code share_warning) may arm it.
# A 500, or "no node upstream", shows its words and the next press asks for the warning again (final review I3).
sprog = r"""
const fs = require('fs'), vm = require('vm'), pm = fs.readFileSync('./app/static/doors-placemap.js', 'utf8');
const lift = n => pm.match(new RegExp('^(?:async )?function ' + n + '\\([\\s\\S]*?\\n}\\n', 'm'))[0];
const WARN = { code: 'share_warning', text: 'Sharing sends every drawing in this map…' };
const answers = [], sent = [];
const c = { PM: { draw: { asked: null } }, panel() {}, mapTable() {}, actor: () => 'Tomas',
  send: async (m, p, body) => { sent.push(body); return answers.shift(); } };
vm.createContext(c);
vm.runInContext(pm.match(/^const refused = .*$/m)[0] + '\n' + lift('mapPatch') + lift('share'), c);
const m = { id: 3, shared: false, held: false }, out = {};
const press = async a => { answers.push(a); await c.share(m); return { body: sent[sent.length - 1], shown: c.PM.draw.asked && c.PM.draw.asked.text }; };
(async () => {
  out.e500 = await press({ ok: false, status: 500, detail: 'Internal Server Error' });
  out.after500 = await press({ ok: false, status: 409, detail: 'There is no node upstream to share with. Set PARENT in Set up first.' });
  out.afterParent = await press({ ok: false, status: 409, detail: WARN });
  out.confirm = await press({ ok: true, status: 200, map: { shared: true } });
  console.log(JSON.stringify(out));
})();
"""
_s = json.loads(subprocess.run(["node", "-e", sprog], capture_output=True, text=True, check=True).stdout)
assert _s["e500"]["body"] == {"shared": True, "actor": "Tomas"} and _s["e500"]["shown"] == "Internal Server Error", _s["e500"]
assert _s["after500"]["body"] == {"shared": True, "actor": "Tomas"}, ("a 500 armed the second press", _s["after500"])
assert _s["afterParent"]["body"] == {"shared": True, "actor": "Tomas"}, ("no node upstream armed the second press", _s["afterParent"])
assert _s["afterParent"]["shown"] == "Sharing sends every drawing in this map…", "the warning is shown in its own words"
assert _s["confirm"]["body"] == {"shared": True, "confirm": "exact", "actor": "Tomas"}, ("the warning arms the second press", _s["confirm"])
print("  place: only the node's warning arms Share's second press; a 500 or no node upstream does not")

# Downloads in four formats, the satellite first, the years below the map, drone pins (SPEC_place_microgis §4, Task 8)
_g = M["gis"]
_col = re.findall(r'<button[^>]*aria-label="([^"]+)"', _g["col"] or "")
assert _col == ["Map only", "Full screen", "Back to this node’s cell", "Download"], _col
_dl = re.findall(r'<button[^>]*aria-label="([^"]+)"', _g["menu"] or "")
assert _dl == ["Image of the screen · PNG", "For upstream and QGIS · GeoJSON", "For Google Earth, phones · KML", "For CAD, in metres · DXF",
               "Everything on the screen", "Report, to print or save as PDF"], _dl
assert _g["menuShown"], "Download opens its menu"
assert "save(screenImage().toDataURL('image/png'), name)" in pm and "x.drawImage(src, 0, 0)" in pm, "the PNG is the canvas, drawings and all, composed"
assert _g["png"] and sorted(_g["saved"]) == ["n-3.dxf", "n-3.geojson", "n-3.kml"] and len(_g["files"]) == 3, \
    ("everything on the screen: the PNG, then each visible map's three files, one download each", _g["files"], _g["saved"])
assert _g["ops"][:2] == ["drawImage", "scale"], ("the map canvas first, then the page pixels", _g["ops"][:4])
_tx = " · ".join(_g["texts"])
assert all(x in _tx for x in _g["credit"].split(" · ")) and "Copernicus" in _tx and "Natural Earth" in _tx, ("the PNG carries the credit #mapcredit shows", _g["texts"], _g["credit"])
assert any(re.fullmatch(r"\d+ (m|km)", t) for t in _g["texts"]), ("the PNG carries a scale in metres", _g["texts"])
assert "stroke" in _g["ops"] and _g["pngSaved"], "a scale bar is drawn, and the composed image is what is saved"
print("  place: the PNG carries the credit line and a scale bar, drawn on a copy of the map's canvas")
assert _g["closeOnly"]["hidden"] and not [p for p in _g["closeOnly"]["asked"] if "/marks" in p] and not _g["closeOnly"]["state"], \
    ("a press that closes the menu drops no marker", _g["closeOnly"])
assert _g["escClosed"] and _g["escKept"] == 11, "Esc in the menu closes it and keeps the drawing in hand"
print("  place: closing the menu, by a press or Esc, does nothing else on the screen")
print("  place: the right column reads Map only, Full screen, Back to this node’s cell, Download; the menu offers four formats and everything on the screen")
assert _g["imagery"] is True and M["plain"]["imagery"] is False, "the satellite is the base where the node holds imagery, the streets elsewhere"
_sf, _sc = M["satFar"], M["satClose"]
assert ["imagery", None, 15] in _sf["layers"] and ["drone-close", 15, None] in _sf["layers"], ("the satellite stops at zoom 15 and a drone flight takes over past it", _sf["layers"])
assert "Copernicus" in _sf["credit"] and "OpenStreetMap" in _sf["credit"], ("at Cell scale the satellite's credit is on the line", _sf["credit"])
assert "Copernicus" not in _sc["credit"] and "OpenStreetMap" in _sc["credit"] and "OpenAerialMap" in _sc["credit"], \
    ("at Street scale the street map and the drone flight are credited, not the satellite", _sc["credit"])
print("  place: past Block the satellite gives the base to the street map and any drone flight, and the credit line follows")
_dp = {k: M["drawPan"][k] for k in ("idle", "drawing", "canvas", "pts")}
assert M["drawPan"]["fbSame"] and M["drawPan"]["fb"] is None, ("a framebuffer of the canvas's size stays; one of another size is made again", M["drawPan"]["fbSame"], M["drawPan"]["fb"])
assert (M["drawPan"]["focusV"], M["drawPan"]["focusA"]) == (0, 1), ("a drawing key hands the focus to the map, Select does not", M["drawPan"]["focusV"], M["drawPan"]["focusA"])
assert _dp == {"idle": 0, "drawing": 1, "canvas": 1, "pts": 1}, ("a started line pans the map from anywhere, the page's arrows are left alone before, and the canvas pans by itself", _dp)
_ch = M["chip"]
_open = lambda h: 'class="dchip" aria-expanded="true"' in h and '<div id="dfull" class="dfull">' in h
_shut = lambda h: 'class="dchip" aria-expanded="false"' in h and '<div id="dfull" class="dfull" hidden>' in h
assert _shut(_ch["start"]) and 'class="dot"' in _ch["start"] and 'data-c="1"' in _ch["start"], ("the readout opens folded, a chip with a dot in the colour", _ch["start"][:400])
assert _open(_ch["opened"]) and _shut(_ch["folded"]), "a press on the chip opens the colours and the hint, a second folds them"
assert _shut(_ch["escInside"]["html"]) and _ch["escInside"]["focus"], "Esc from inside the readout folds it and keeps the focus on the chip"
assert _open(_ch["held"]) and "Arrows move point 1 of 3" in _ch["held"] and '<span class="v" aria-hidden="true">' in _ch["held"], ("a drawing of the house's in hand opens the colours by itself", _ch["held"][:500])
assert _shut(_ch["letGo"]["html"]) and _ch["letGo"]["sel"] is None, ("Esc lets the drawing go, and the readout it opened folds again", _ch["letGo"])
assert 'id="dsaid" class="vh" aria-live="polite"' in _t["panel"], "the finished-figure live region stays as it was"
print("  place: the readout is a chip with the tool, the map, the live figure and a dot; a press opens the colours; a drawing in hand opens it; Esc folds it")
_fx = M["fix"]
assert _fx["before"] == [115.168, -8.8185] and _fx["after"] == [115 + 300 / 2e4, -8 - 200 / 2e4], ("on move the leg's end follows the pointer's pixel", _fx["before"], _fx["after"])
assert _fx["escTools"] == 11, "Esc on the Tools button while its menu is open is the menu's: the drawing in hand stays"
assert _fx["escFrom"] == "select" and _fx["mFrom"] == "marker", ("with the menu shut and the focus on Tools, Esc ends From the house and M takes the marker key", _fx["escFrom"], _fx["mFrom"])
assert _fx["kbLeg"] == [None, None], ("a shape from the keyboard gains no leg to an old mouse pixel when the map moves", _fx["kbLeg"])
assert _fx["toolsClick"] == {"posted": 0, "state": None}, ("a press that closes Tools drops no marker", _fx["toolsClick"])
assert "Make a map first with New map" in _fx["noMap"]["read"] and "Add a photo on its own." in _fx["noMap"]["form"] and "Press the map" not in _fx["noMap"]["form"], \
    ("the Image key with no map says make one first, and still offers a photo on its own", _fx["noMap"])
assert "@container place (max-width:899px){.dchip .v small.more{display:none}}" in html and ".dchip .m{flex:0 1000 auto;" in html and "text-overflow:ellipsis}.dchip .v:empty" in html, \
    "the chip gives way name first, then the tool; the figure ends in an ellipsis and keeps its unit when narrow"
assert "@media (min-width:761px){#pchange .pair figure{aspect-ratio:auto;height:min(420px,calc(50vw - 40px))}#pchange .pair img{object-fit:contain;object-position:center}" in html \
    and "#pchange .photo{height:min(420px,calc(100vw - 80px));object-fit:contain;object-position:center}" in html and "#pchange .pair figure,#pchange .photo{background:var(--screen)}" in html \
    and "object-fit:cover;object-position:center" not in html, "at a desk then and now are at most 420 px tall and show the whole square, the single year too, on the screen's ground"
assert "max-height:calc(100% - 3 * var(--k) - 44px)" in html, "under 560 px of screen the readout and its form stop above the hour"
print("  place: the leg follows the pointer through a zoom; Esc and a press that close Tools touch nothing else; the Image key with no map says so")
_im = M["image"]
assert 'data-a="newphoto"' in _im["form"] and "A new photo" in _im["form"], ("the Image key with nothing in hand offers a photo on its own", _im["form"])
assert _im["posted"] == [["marker", [115.167, -8.819]]] and 'data-a="newimg"' in _im["picker"], ("Enter with the Image key pins a marker at the centre and opens the picker", _im)
assert 'data-learn="place-image"' in pm and "on('newphoto', () => window.placeAddImage && window.placeAddImage());" in pm, "the Image key carries the image's learn mark; its photo opens #imgdlg"
print("  place: the Image key adds a photo on its own or pinned at the map's centre by Enter, through the same dialog")
_mv = M["move"]
assert "<circle" in _mv["before"] and _mv["moves"] >= 1, ("the off-screen stations have edge pins, and the map listens to move", _mv["moves"], _mv["before"][:200])
assert _mv["after"] != _mv["before"] and _mv["listKept"], ("on move the edge pins follow the map; the list waits for moveend", _mv)
print("  place: while the map moves, the edge pins follow it frame by frame; the list under the screen waits for it to settle")
_bs = re.findall(r'<button[^>]*aria-pressed="(true|false)"[^>]*>([a-z]+)<', _g["base"] or "")
assert [b for _, b in _bs] == ["satellite", "streets", "drone"] and [p for p, _ in _bs] == ["true", "false", "false"], _bs
print("  place: satellite on at load where the node holds it; the base switch reads satellite · streets · drone")
assert len(_g["pins"] or []) == 2 and [round(v, 6) for v in _g["pins"][0]["q"]] == [115.16, -8.82], _g["pins"]
assert [x["t"] for x in _g["pinText"]] == ["drone, 4 cm, Mar 2024", "drone, 3 cm, Nov 2025"], _g["pinText"]
assert any(e.get("zoom") == 16 and [round(v, 6) for v in e.get("center")] == [115.16, -8.82] for e in _g["eased"]), ("a pin pressed flies to its flight at zoom 16", _g["eased"])
print("  place: below zoom 13 each drone flight is a pin, named by its resolution and month; pressed, it flies there at 16")
_pl = html[html.index('<section class="page view" data-view="place"'):html.index("<!-- DATA -->")]
assert "altc" not in html and "mapalt" not in html, "the then-and-now pair is off the screen"
assert _pl.index('class="pyears"') < _pl.index('id="pchange"') < _pl.index('class="plow"') < _pl.index('id="pfigures"'), \
    "what changed is a band of its own under the screen, end to end, above the place in figures"
assert re.search(r"\.pyears\{[^}]*\}", _css) and ".years{display:grid;gap:4px;align-items:end;height:98px" in _css and "#pchange .pair{grid-template-columns:minmax(0,1fr)}" in html, \
    "the years are bigger: the bars twice as tall; then and now side by side, stacked on a phone"
_dr = (STATIC / "doors-load.js").read_text()
assert "place_yearly: 'history?sensor_id=place-point&metric=sat_buildings_yearly'" in _dr, "the yearly count is the node's own series, GET /history"
yprog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0];
const place = fs.readFileSync('./app/static/doors-place.js', 'utf8'), fn = (s, n) => s.match(new RegExp('function ' + n + '\\(' + '[\\s\\S]*?\\n}\\n'))[0];
const F = JSON.parse(fs.readFileSync('%s', 'utf8'));
const Y = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023].map((y, i) => ({ ts: `${y}-07-01T08:00:00+08:00`, value: 98.4 + i * 4.2 }));
const D = L.buildD({ ...F, days: F.issues_days, place_yearly: Y }, 'en');
const els = {}, c = { D, sign: () => '', $: q => (els[q] ||= { innerHTML: '' }), window: {} }; vm.createContext(c);
vm.runInContext(['esc', 'num', 'PROV', 'prov', 'SAT'].map(pick).join('\n') + '\nlet YEAR = 2025, COMPARE = true, PAST = null;\n' + fn(place, 'layer') + 'layer()', c);
const none = L.buildD({ ...F, days: F.issues_days }, 'en');
console.log(JSON.stringify({ yearly: D.place_yearly, none: none.place_yearly, html: c.$('#pchange').innerHTML }));
""" % replayed(FIX)
_y = json.loads(subprocess.run(["node"], input=yprog, capture_output=True, text=True, check=True).stdout)
assert _y["none"] == [] and [r["year"] for r in _y["yearly"]] == list(range(2016, 2024)), _y["yearly"]
_ch = _y["html"]
assert "what changed, year on year" in _ch and 'class="pair"' in _ch and "then · 2016" in _ch and "now · 2025" in _ch, _ch[:600]
assert 'aria-label="Earlier"' in _ch and 'aria-label="Later"' in _ch, "the year arrows came along"
assert re.search(r"ha changed.*model", _ch, re.S), "the AlphaEarth hectares, with their model word"
_bars = _ch[_ch.index('class="years"'):]
assert _bars.count("<i ") == 8 and "2016" in _bars and "2023" in _bars, _bars[:400]
print("  place: what changed, year on year, under the map: the then-and-now pair, its arrows, the hectares (model) and a bar a year")

# Folding sides, map only, full screen, the phone (SPEC_place_microgis §4, §10, Task 9)
_g = M["gis"]
assert "aria-disabled" not in _g["col"] and "not yet" not in _g["col"], "Map only and Full screen are keys now, not placeholders"
assert re.search(r'data-t="wide"[^>]*aria-label="Map only" title="Map only · \\" aria-pressed="false"', _g["col"]) \
    and re.search(r'data-t="full"[^>]*aria-label="Full screen" title="Full screen · F" aria-pressed="false"', _g["col"]), _g["col"]
assert _g.get("wide") == 1 and _g.get("full") == 1, ("a press on each goes to the folding", _g.get("wide"), _g.get("full"))
assert re.findall(r'aria-label="([^"]+)"', M["nofs"]["col"]) == ["Map only", "Back to this node’s cell", "Download"], M["nofs"]["col"]
print("  place: Map only and Full screen are wired; where the browser has no element full screen its key is not drawn")
_pl = html[html.index('<section class="page view" data-view="place"'):html.index("<!-- DATA -->")]
_fb = re.findall(r'<button type="button" class="pfold" data-fold="(lc|rc)" aria-controls="(cake|ptools)" aria-expanded="true" aria-label="(Hide the layers|Hide the tools)" title="[^"]+ · ([\[\]])">', _pl)
assert _fb == [("lc", "cake", "Hide the layers", "[")], ("one side folds, the left", _fb)
_css = html[html.index("/* ================= PLACE: a small GIS"):html.index("/* ================= NODE")]
assert re.search(r"@media \(min-width:761px\)\{[^@]*\.bench\.lc\{grid-template-columns:36px minmax\(0,1fr\)\}", _css), "the layers fold to a 36 px strip and the screen takes the rest"
assert ".bench.rc" not in _css and "lc.rc" not in _css and "1081px" not in _css, "no right side to fold"
assert re.search(r"\.bench\.lc \.pfold\[data-fold=\"lc\"\]\{left:0;top:0;bottom:0;width:36px", _css) and "writing-mode:vertical-rl" in _css, \
    "a folded side is a 36 px strip with its name written down it, and the strip is the button that opens it"
assert '.pfold[data-fold="lc"]{grid-row:1/2;grid-column:1/2;' in _css, "the strip is held by the screen's row and stops at its foot"
assert ".bench.lc.mo .mapc #map{height:max(560px,calc(100vh - 80px))}" in _css, "map only: the screen takes the window's height, less the header"
assert re.search(r"\.mapc:fullscreen\{[^}]*\}\.mapc:fullscreen \.mapw\{[^}]*height:100%\}\.mapc:fullscreen #map\{flex:1", _css), "full screen: the screen fills it"
_ph9 = re.search(r"@media \(max-width:760px\)\{\n  \.phead[^@]*", html).group(0)
assert ".bench{position:relative}.pfold{display:none}" in _css and re.search(r"@media \(min-width:761px\)\{\n  \.pfold\{position:absolute", _css) \
    and '.tools [data-t="wide"]{display:none}' in _ph9, "a phone has no side to fold: the sheet holds it"
for _n in ("doors-place.js", "doors-placemap.js"):
    _bare = [ln for ln in (STATIC / _n).read_text().splitlines() if "localStorage." in ln and not re.search(r"try \{[^}]*localStorage\.", ln)]
    assert not _bare, (f"{_n}: storage read or written outside try", _bare)
fprog = r"""
const fs = require('fs'), vm = require('vm');
const place = fs.readFileSync('./app/static/doors-place.js', 'utf8'), noop = () => {};
function load({ store = {}, fsOk = true, broken = false, tok = true } = {}) {
  const cls = new Set(), keys = [], clicks = [], seen = { resized: 0, full: 0, scrolled: 0, layers: [], tools: [] };
  const btn = f => ({ dataset: { fold: f }, attrs: {}, title: '', setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k]; }, focus() { doc.activeElement = this; } });
  const folds = [btn('lc')], wide = btn('wide');
  const bench = { dataset: {}, classList: { contains: x => cls.has(x), add: x => cls.add(x), toggle: (x, on) => ((on === undefined ? !cls.has(x) : on) ? cls.add(x) : cls.delete(x)) } };
  const screen = { requestFullscreen: () => { seen.full++; return Promise.reject(new Error('refused')); }, scrollIntoView: () => { seen.scrolled++; } };
  /* a cake row with focus, inside #cake */
  const row = { name: 'row' }, cake = { contains: x => x === row };
  /* the Tools button and its menu: rows are made from the menu's html, as the browser would */
  const tb = { name: 'toolsb', attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, focus() { doc.activeElement = this; } };
  const menu = { hidden: true, html: '', rows: [],
    set innerHTML(h) { this.html = h; this.rows = [...h.matchAll(/<button([^>]*)>/g)].map(([, at]) => { const d = at.match(/data-(layer|tool)="([a-z]+)"/) || [];
      return { name: d[2], kind: d[1], disabled: / disabled/.test(at), dataset: d[1] ? { [d[1]]: d[2] } : {}, focus() { doc.activeElement = this; } }; }); },
    get innerHTML() { return this.html; },
    querySelector: q => (q === 'button:not(:disabled)' ? menu.rows.find(r => !r.disabled) || null : null) };
  const ls = broken ? { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } } : { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
  const doc = { fullscreenEnabled: fsOk, fullscreenElement: null, activeElement: null,
      addEventListener: (t, f) => { if (t === 'keydown') keys.push(f); if (t === 'click') clicks.push(f); },
      querySelector: q => (q === '.bench' ? bench : q === '.mapc' ? screen : q === '.tools [data-t="wide"]' ? wide : q === '#cake' ? cake
        : q === '.pfold[data-fold="lc"]' ? folds[0] : q === '.ptools' ? wrap : null),
      querySelectorAll: q => (q === '.pfold' ? folds : q === '#ptools button[data-layer]' ? menu.rows.filter(r => r.kind === 'layer') : q === '#ptools button[data-tool]' ? menu.rows.filter(r => r.kind === 'tool') : []) };
  const els = { '#ptools': menu, '#ptoolsb': tb }, wrap = { on: {}, addEventListener(t, f) { this.on[t] = f; }, contains: x => x === tb || menu.rows.includes(x) };
  const c = { VIEWS: {}, D: {}, console, view: () => 'place', localStorage: ls, $: q => els[q] || { addEventListener: noop }, document: doc, DOORS_TOKEN: () => (tok ? 't' : '') };
  c.window = c; c.__PM = { map: { resize: () => { seen.resized++; } }, on: {}, tool: 'select', setTool: t => seen.tools.push(t) };
  c.placeLayer = (l, on) => seen.layers.push(`${l}:${on}`);
  vm.createContext(c); vm.runInContext(place, c);
  const typing = sel => /input/.test(sel) ? {} : null;
  const key = (k, o = {}) => keys.forEach(f => f({ key: k, target: { closest: o.typing ? typing : o.menu ? (s => /ptmenu/.test(s) ? {} : null) : () => null }, preventDefault: noop, metaKey: !!o.meta, ctrlKey: !!o.ctrl, altKey: !!o.alt }));
  const state = () => ({ cls: [...cls].sort().join(' '), labels: folds.map(b => `${b.attrs['aria-label']}:${b.attrs['aria-expanded']}`), title: folds[0].title,
    wide: wide.attrs['aria-pressed'], store: store.planetai_place_folds, ...seen });
  return { folds, key, state, store, doc, row, tb, menu, c, wrap, click: inside => clicks.forEach(f => f({ target: { closest: s => (inside && s === '.ptools' ? {} : null) } })) };
}
const out = {}, a = load();
out.start = a.state();
a.folds[0].onclick(); out.left = a.state();
a.key(']'); out.bracket = a.state();
a.key('[', { typing: true }); a.key('[', { ctrl: true }); out.typing = a.state();
a.key('['); out.open = a.state();
a.key('\\'); out.wideOn = a.state();
a.key('\\'); out.wideOff = a.state();
a.key('F'); out.full = a.state();
a.key('\\'); out.reload = load({ store: { planetai_place_folds: a.store.planetai_place_folds } }).state();
out.oldRight = load({ store: { planetai_place_folds: 'lc rc' } }).state();
out.oldRightOnly = load({ store: { planetai_place_folds: 'rc' } }).state();
const n = load({ fsOk: false }); n.key('f'); out.noFs = n.state();
const b = load({ broken: true }); b.key('['); out.broken = b.state();
/* focus on a cake row: `[` hides it, and focus goes to the layers' strip, not to the page */
const fo = load(); fo.doc.activeElement = fo.row; fo.key('['); out.focus = fo.doc.activeElement === fo.folds[0] ? 'strip' : fo.doc.activeElement ? fo.doc.activeElement.name : 'body';
/* Option on a Spanish or German Mac, AltGr (Ctrl+Alt) on Windows: `[` still folds; with ⌘ it does not */
const al = load(); al.key('[', { alt: true }); out.alt = al.state();
const me = load(); me.key('[', { meta: true }); me.key('\\', { meta: true }); out.meta = me.state();
/* the Tools menu: the button opens it on its first runnable row; Esc closes it and gives the focus back; a press outside
   closes it; a tool chosen runs and closes it */
const t = load(); t.c.placeTools(); const order = [...t.menu.html.matchAll(/<span>([^<]+)<\/span><code>([^<]+)<\/code>/g)].map(m => `${m[1]}|${m[2]}`);
t.tb.onclick(); out.menu = { order, open: !t.menu.hidden, exp: t.tb.attrs['aria-expanded'], focus: t.doc.activeElement && t.doc.activeElement.name };
t.key('Escape', { menu: true }); out.menu.esc = { hidden: t.menu.hidden, exp: t.tb.attrs['aria-expanded'], focus: t.doc.activeElement && t.doc.activeElement.name };
t.tb.onclick(); t.click(true); out.menu.inside = t.menu.hidden; t.click(false); out.menu.outside = t.menu.hidden;
t.tb.onclick(); t.menu.rows.find(r => r.name === 'from').onclick(); out.menu.from = { tools: t.state().tools, hidden: t.menu.hidden, focus: t.doc.activeElement && t.doc.activeElement.name };
t.tb.onclick(); t.menu.rows.find(r => r.name === 'rings').onclick(); out.menu.rings = t.state().layers;
t.tb.onclick(); t.wrap.on.focusout({ relatedTarget: t.menu.rows[1] }); out.menu.focusIn = t.menu.hidden;
t.wrap.on.focusout({ relatedTarget: null }); out.menu.focusNull = t.menu.hidden;
t.wrap.on.focusout({ relatedTarget: { name: 'canvas', closest: q => (q === '.maplibregl-canvas-container' ? {} : null) } }); out.menu.focusMap = t.menu.hidden;
t.wrap.on.focusout({ relatedTarget: { name: 'elsewhere' } }); out.menu.focusOut = t.menu.hidden;
const lk = load({ tok: false }); lk.c.placeTools(); out.locked = { html: lk.menu.html, any: lk.menu.rows.filter(r => r.kind && !r.disabled).length };
console.log(JSON.stringify(out));
"""
_r = subprocess.run(["node"], input=fprog, capture_output=True, text=True)
assert _r.returncode == 0, _r.stderr[-3000:]
F9 = json.loads(_r.stdout)
assert F9["start"]["cls"] == "" and F9["start"]["labels"] == ["Hide the layers:true"], F9["start"]
assert F9["left"]["cls"] == "lc" and F9["left"]["labels"][0] == "Show the layers:false" and F9["left"]["title"] == "Show the layers · [" \
    and F9["left"]["store"] == "lc" and F9["left"]["resized"] >= 1 and F9["left"]["wide"] == "false", ("the arrow folds the layers, says so, remembers it and resizes the map", F9["left"])
assert F9["bracket"]["cls"] == "lc" and F9["bracket"]["store"] == "lc", ("] does nothing now: there is no right side", F9["bracket"])
assert F9["typing"]["cls"] == "lc", "never while somebody types, never with Ctrl"
assert F9["open"]["cls"] == "" and F9["open"]["store"] == "", ("[ opens the left again", F9["open"])
assert F9["wideOn"]["cls"] == "lc mo" and F9["wideOn"]["wide"] == "true" and F9["wideOn"]["store"] == "lc mo" and F9["wideOn"]["scrolled"] == 1, \
    ("\\ folds the left, grows the screen and brings it into the window", F9["wideOn"])
assert F9["wideOff"]["cls"] == "" and F9["wideOff"]["wide"] == "false", ("\\ again opens the left", F9["wideOff"])
assert F9["full"]["full"] == 1 and F9["noFs"]["full"] == 0, "F asks for full screen on the screen, only where the browser has it"
assert F9["reload"]["cls"] == "lc mo" and F9["reload"]["labels"] == ["Show the layers:false"], ("a reload keeps map only", F9["reload"])
assert F9["oldRight"]["cls"] == "lc" and F9["oldRightOnly"]["cls"] == "", ("a stored rc from an older visit is ignored", F9["oldRight"], F9["oldRightOnly"])
assert F9["broken"]["cls"] == "lc", ("without storage the page is still right: it folds, it just forgets", F9["broken"])
assert F9["focus"] == "strip", ("a side folded from the keyboard hands focus to its strip", F9["focus"])
assert F9["alt"]["cls"] == "lc" and F9["meta"]["cls"] == "", ("Option and AltGr fold; ⌘ does not", F9["alt"], F9["meta"])
assert "(document.fullscreenElement ? document.exitFullscreen() : sc.requestFullscreen()).catch(() => {})" in (STATIC / "doors-place.js").read_text(), \
    "a refused full screen is caught, never an unhandled rejection"
print("  place: the left folds by its arrow and by [, \\ is map only, F full screen; a stored right fold is ignored; never while typing; remembered in try/catch")
_mn = F9["menu"]
assert _mn["order"][:4] == ["Rings and distance|geo.rings", "From the house|geo.measure", "Pull|area.pull", "Place report|place.report"] and all(x.endswith("|not yet") for x in _mn["order"][4:]) and len(_mn["order"]) == 16, _mn["order"]
assert _mn["open"] and _mn["exp"] == "true" and _mn["focus"] == "rings", ("Tools opens its menu on the first runnable row", _mn)
assert _mn["esc"] == {"hidden": True, "exp": "false", "focus": "toolsb"}, ("Esc closes the menu and gives the focus back to Tools", _mn["esc"])
assert _mn["inside"] is False and _mn["outside"] is True, "a press outside the menu closes it, one inside does not"
assert _mn["from"] == {"tools": ["from"], "hidden": True, "focus": "toolsb"} and _mn["rings"] == ["rings:true"], ("a tool chosen runs and closes the menu", _mn)
assert _mn["focusMap"] is False, "focus going to the map's canvas (a press on the map) leaves the menu to the click, which swallows that press"
assert _mn["focusIn"] is False and _mn["focusNull"] is False and _mn["focusOut"] is True, ("focus leaving the menu closes it; moving within it, or a press, does not", _mn)
assert F9["locked"]["any"] == 0 and "Tools run on this node with a token. Unlock this screen in Set up." in F9["locked"]["html"], "without the token the rows are quiet and say why"
print("  place: Tools is one button on the top line; its menu lists the three that run, then the ones not yet; Esc or a press outside closes it")

print("all doors checks passed")
