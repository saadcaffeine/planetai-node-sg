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
  const F = JSON.parse(fs.readFileSync('%s', 'utf8')), els = {};
  const ctx = { D: L.buildD({ ...F, days: F.issues_days }, 'en'), VIEWS: {}, $: q => (els[q] ||= {}), out: null, doorsLocal: L.doorsLocal };
  vm.createContext(ctx);
  vm.runInContext(['esc', 'fmt', 'plain', 'said', 'num', 'unitOf', 'labelOf', 'loc', 'dayOf'].map(pick).join('\n') + '\n' + fs.readFileSync('./app/static/doors-wall.js', 'utf8')
    + '\nconst now15 = s => ((D.stats15[s.sensor_id] || {}).pm25 || [])[0] ?? null, st = D.sensors.filter(s => s.kind === "sensor");'
    + ' const hv = st.filter(s => s.local).map(now15).filter(v => v != null), house = hv.length ? hv.reduce((a, b) => a + b) / hv.length : null;'
    + ' const say = Array(30).fill("Close the windows facing the street").join(" ") + ".";'
    + ' $("#wnarr").classList = { toggle() {}, add() {}, remove() {} }; const nd = () => { narrDraw(); return { hidden: $("#wnarr").hidden, html: $("#wnarr").innerHTML, note: $("#wnote").textContent }; };'
    + ' const narr = { empty: nd() }; NARR.busy = true; narr.asking = nd(); NARR.err = "The node’s model did not answer: 500"; narr.err = nd();'
    + ' NARR.prev = "The air inside is calm."; narr.kept = nd(); NARR.busy = false; NARR.err = null; NARR.shown = "The air"; NARR.typing = true; narr.typing = nd();'
    + ' out = { ask: D.order.map(k => wallAsk(D.issues[k])).join(" "), cap: wallCaption(house, st.filter(s => !s.local).map(now15), D.issues.air.line),'
    + ' caps: [wallCaption(10, [20, 5], 15), wallCaption(20, [], 15), wallCaption(null, [16], 15, "at 15:00"), wallCaption(5, [], null)], narr,'
    + ' long: wallAsk({ asking: [{ says: say }] }), short: oneLine("Open the windows. Then wait."),'
    + ' fresh: wallStale({ last_poll: new Date().toISOString() }), old: wallStale({ last_poll: "2026-10-06T11:19:50+00:00" }), none: wallStale({}) };'
    /* the walk's four pages, at the day's last hour, with a place learning shaped as GET /learned/place answers it */
    + ' WALK.place = [{ issue: "air", numbers: { by_hour: Object.fromEntries([...Array(24)].map((_, h) => [h, 10 + h %% 5])), days: 28 }, checked_at: "2026-10-06T08:00:00+08:00" }];'
    + ' out.pages = [0, 1, 2, 3].map(i => wallPage(i, 23)); out.when = [wallWhen(new Date().toISOString()), wallWhen("2025-07-01T08:00:00+08:00")];'
    + ' WALK.place = []; out.bare = wallPage(1, 23);', ctx);
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
_names = {x["name"].strip() for x in json.loads(Path(FIX).read_text())["sensors"] if len(x["name"].strip()) > 3}
_wall = json.dumps(t["wall"], ensure_ascii=False)
assert not [n for n in _names if n in _wall], [n for n in _names if n in _wall]
assert "Nothing is asked now." in t["wall"]["ask"], "6 Oct 19:22: a stale alert and an answered event ask nothing now"
assert t["wall"]["old"] and t["wall"]["none"] and not t["wall"]["fresh"], t["wall"]
print("doors: the Wall names no sensor, room or kit, and says stale only when the last poll is old")
# THE WALK (Tomas picked option A, 16 Oct): four scales, the phone's own; every figure says when and one provenance word;
# the land is a hundred squares; floods are said to be not watched, never drawn; the learned usual only when the node has it.
_pg = t["wall"]["pages"]
_wsrc = (STATIC / "doors-wall.js").read_text()
_ws = re.search(r"const WALL_SCALES = (\[.*?\]);", _wsrc).group(1)
# The story rolls when it is longer than its box (Tomas, 21 Oct: the end was cut and the start never came back): after
# typing, and again when a scale gives the box its room back; still under reduced motion.
assert "if (!NARR.typing) narrRoll();" in _wsrc and "!NARR.typing) narrRoll();" in _wsrc.split("function wallFit")[1].split("function wallHour")[0], \
    "the Wall's story does not start rolling after typing, or when its box gets room again"
assert re.search(r"prefers-reduced-motion: reduce\)\{[^}]*\.wnarr \.nw\.roll \.nt\{animation:none", html), "the story rolls under reduced motion"
_ps = re.search(r"const SCALES = (\[.*?\]);", (STATIC / "walk.js").read_text()).group(1)
assert re.findall(r"k: '(\w+)'", _ws) == re.findall(r"k: '(\w+)'", _ps) and re.findall(r"res: (\d+)", _ws) == re.findall(r"res: (\d+)", _ps)[:4], (_ws, _ps)
for _i, _h in enumerate(_pg):
    _figs = re.findall(r'<div class="wfig">(.*?)</div>', _h)
    assert _figs or _i == 3, f"scale {_i} draws no figure"
    for _f in _figs:
        assert re.search(r'class="wpw">(live|partial|model|cached|example)<', _f) and re.search(r"· \d\d:\d\d ", _f), f"a figure with no time or word: {_f}"
    assert not re.findall(r'class="wpw">(?!(?:live|partial|model|cached|example)<)', _h), f"a word that is not one of the five on scale {_i}"
assert "dotted: what this node learned is usual outside" in _pg[1] and "dotted" not in t["wall"]["bare"], "the usual is drawn only when learned"
assert 'stroke-dasharray="1 6"' in _pg[1] and 'stroke-width="3"' in _pg[1] and 'stroke-dasharray="1 6"' not in _pg[0], "the street's day and its usual, dotted"
assert re.search(r'<p class="wat">.* at <b>\d\d:00</b>: ', _pg[1]), "the replayed hour said in words, house, street and ring"
_hund = re.search(r'<div class="whund"[^>]*>(.*?)</div>', _pg[2]).group(1)
assert _hund.count("<i ") == 100 and re.search(r"built <b>\d+%</b>", _pg[2]), _pg[2][:400]
assert "OpenStreetMap" in _pg[2] and "too few to tell homes from shops" in _pg[2], "the places counted, and why there is no homes-and-shops split"
assert "<th>Floods</th><td>not watched on this node yet</td>" in _pg[3]
assert t["wall"]["when"][1] == "Jul 2025" and re.fullmatch(r"\d\d:\d\d", t["wall"]["when"][0]), t["wall"]["when"]
print("doors: the Wall walks the phone's four scales; every figure has its time and word; land as 100 squares; floods not invented")

# 15 Oct, the Wall read from 3 m (Tomas's review of 14 Oct). Each check fails if its fix regresses.
# The map's caption says in words what its red discs mean against the house: a clean headline beside red discs.
_c = t["wall"]["caps"]
assert t["wall"]["cap"].startswith("This house") and "clean-air line now" in t["wall"]["cap"], t["wall"]["cap"]
assert _c[0] == "This house is under the clean-air line now; one station nearby, in red, is over it.", _c[0]
assert _c[1] == "This house is over the clean-air line now; no station nearby is." and "at 15:00" in _c[2] and _c[3] == "", _c
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
print("doors: the Wall's caption, its one line and its narration box say what they should, and nothing when empty")
# THE TYPE FLOOR: every size in the Wall's CSS is --wf or a multiple of it, and --wf is 28 px at 1920x1080. Nothing
# drawn on the Wall carries a class whose size is set outside that block (.k, .fine, <small>); the map's words are --wf.
_wcss = html[html.index("/* ================= WALL:"):html.index("/* ================= FLOW:")]
_wf = re.search(r"--wf:min\(([\d.]+)vw,([\d.]+)vh\)", _wcss)
assert _wf and min(float(_wf.group(1)) * 19.2, float(_wf.group(2)) * 10.8) >= 28, "the floor is 28 px at 1920x1080"
_sizes = re.findall(r"font(?:-size)?:([^;}]*)", re.sub(r"/\*.*?\*/", "", _wcss, flags=re.S))
assert len(_sizes) >= 18, len(_sizes)
for _f in _sizes:
    _m = re.search(r"calc\(var\(--wf\) \* ([\d.]+)\)|var\(--wf\)|(\d[\d.]*)(px|em|rem|vw|vh)\b", _f)
    assert _m and (_m.group(0) == "var(--wf)" or (_m.group(1) and float(_m.group(1)) >= 1)), f"under the Wall's type floor: font:{_f}"
_wjs = (STATIC / "doors-wall.js").read_text().split("/* THE NODE, THINKING ALOUD")[0] + (STATIC / "doors-wallmap.js").read_text()
assert not re.search(r'class="(?:k|fine)\b|<small', _wjs.split("if (o.time) {")[0] + _wjs.split("if (o.time) {")[-1].split("o.time.querySelectorAll('.seg")[-1]), \
    "a class sized outside the Wall's block, drawn on the Wall"
assert re.findall(r"getSize: (\w+)", _wjs) == ["wf", "wf"], "the map's words are at the floor"
# CHROME: a wall is not operated. The back button, the chips and the hour strip are .wchrome, invisible until a pointer
# or the keyboard is in them; the back button is the first thing in keyboard order.
assert "#wallv .wchrome{opacity:0" in _wcss and "#wallv .wchrome:hover,#wallv .wchrome:focus-within{opacity:1}" in _wcss
assert re.search(r'<div class="wtop wchrome"><button class="wback"', _wjs) and 'class="wrail" id="wrail"' in _wjs and "flowtime" not in _wjs, \
    "the rail is how a reader knows the scale: never chrome; the hour strip is gone"
assert "#wallv .wrail button" in _wcss and "#wallv .wback,#wallv .wchips button,#wallv .wrail button{min-height:44px;min-width:44px}" in _wcss
for _gone in ("share level", "#wall", "more</a>", "readings in", "next in", "Read at", "replay with the token"):
    assert _gone not in _wjs.lower().replace("#wallv", ""), f"admin chrome is back on the Wall: {_gone}"
print("doors: nothing on the Wall is under 28 px at 1920x1080, and its chrome shows only under a pointer or the keyboard")
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
    + fn(core, 'evAt') + fn(core, 'answerWords') + now.match(/^const ANSWER_STAGE = .*$/m)[0] + '\n' + fn(now, 'decision')
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
assert _marks == ["now-sentence", "figure", "now-distances", "now-todo", "now-worked", "now-next", "now-rows", "now-around", "now-things"], _marks
assert _nowh.index('id="decide"') < _nowh.index('id="nremember"') < _nowh.index('class="rcol"'), "What to do, then Did it work, then around"
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
_ph = html[html.index("@media (max-width:480px){"):]
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
_wall = (STATIC / "doors-wall.js").read_text() + (STATIC / "doors-wallmap.js").read_text()
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
# SPEC_place_microgis §4 (4 Nov 2026): the cake | the screen | the tools, then the lower band: selected | the place in figures
assert _place.index('id="cake"') < _place.index('class="mapc"') < _place.index('id="facts"') < _place.index('id="pmargin"') \
    < _place.index('id="ptools"') < _place.index('class="plow"') < _place.index('id="ptable"') < _place.index('id="pfigures"'), \
    "the cake, the screen with its status line and the marks around the house, the tools; then the lower band"
assert 'class="pcols"' not in _place and 'id="reach"' not in _place and 'id="layers"' not in _place and 'id="pleads"' not in _place, "the old workbench is gone"
assert "'#pfigures').innerHTML = `<h3 class=\"pmh\">the place in figures</h3>` + yearly()" in (STATIC / "doors-place.js").read_text(), "Land and Coast are the place's figures"
_css = html[html.index("/* ================= PLACE: a small GIS"):html.index("/* ================= NODE")]
assert re.search(r"\.tools button,\.zoom button\{width:44px;height:44px", _css), "the map's tools are 44 px targets"
assert "box-shadow:0 0 0 1px #000,0 0 0 5px #1b1b1b,0 0 0 6px #000" in _css and "border-radius:10px" in _css, "the screen sits in its bezel"
assert re.search(r"\.bench\{display:grid;grid-template-columns:216px minmax\(0,1fr\) 286px", _css) and ".page[data-view=\"place\"]{max-width:1440px}" in _css, \
    "216 px of cake, the screen, 286 px of tools"
_v2 = _css[:_css.index("#pedges{")]   # the v2 rules; the swatches after them predate it
_v2 = _v2.replace(_v2[_v2.index(".mapc{--ink"):_v2.index(".mapw{")], "")   # the screen's own values and its bezel
assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", _v2), "no raw colour outside the screen: the frozen layer's names"
assert re.search(r"@media \(max-width:760px\)\{[^@]*\.bench\{grid-template-columns:minmax\(0,1fr\)", html), "a phone: one column, the screen first"
assert ".phour button{width:44px;height:44px" in _css and "min-height:44px;padding:0 12px" in _css and "#altbar button{background:none;border:1px solid var(--hair);border-radius:999px;color:var(--ink);width:44px;height:44px" in _css, \
    "every target on the screen is 44 px: the hour, the rungs, the satellite's years"
assert re.search(r"@media \(max-width:760px\)\{[^@]*#cake,#ptools\{display:none;position:fixed;left:0;right:0;bottom:0", html), "a phone's cake and tools are a sheet over the lower band"
assert re.search(r"#cake,#ptools\{height:0;min-height:100%;overflow-y:auto", _css), "the cake and the tools scroll inside the bench, which the screen's column sets"
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
out.tools = /\['from', '⌂'/.test(pm) && /class="done" data-t="done"/.test(pm);
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
  vm.runInContext(fs.readFileSync('./app/static/doors-cake.js', 'utf8') + '\n' + pm + '\nwindow.placeMap()', c);
  await new Promise(r => setTimeout(r, 50));
  out.flat = { map: c.$('#map').innerHTML, cake: c.$('#cake').innerHTML, facts: c.$('#facts').innerHTML, margin: c.$('#pmargin').innerHTML };
  console.log(JSON.stringify(out));
})();
""" % replayed(FIX)
pp = json.loads(subprocess.run(["node"], input=pprog, capture_output=True, text=True, check=True).stdout)
assert sorted(pp["on"]) == ["images", "mine", "own", "public", "species", "street"], pp["on"]
print("doors: Place opens with five layers on: the street, the node's cell, its sensors, the public stations, the images (and their species)")
assert pp["house"] and pp["tools"], "the house is named on the map; From the house and Done are tools"
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
const ctx = { D: L.buildD({ ...F, days: F.issues_days }, 'en'), d3, doorsLocal: L.doorsLocal, VIEWS: {}, setTimeout: f => f(), CSS: { escape: x => x },
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
   tok = ''; real.ledgerBlock(); out.locked = $('#ledger').innerHTML;`, ctx);
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
_w = (STATIC / "doors-wall.js").read_text() + (STATIC / "doors-wallmap.js").read_text()
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
assert "const P = () => PAL.dark" in pm, "the screen is black in both registers (SPEC_place_microgis §4)"
assert "outside(D.sensors)" in pm and pm.count("D.sensors") == pm.count("outside(D.sensors)"), "Place draws no indoor sensor"
assert "D.sensors" not in pl, "doors-place.js reads no sensor of its own"
assert all("cake:" in l for l in re.findall(r"\{ id: '[a-z]+'.*?\}", pm.split("const LAYERS = [")[1].split("];")[0])), "every layer names its cake section"
assert "group:" not in pm.split("const LAYERS = [")[1].split("];")[0] and "id: 'index'" not in pm, "no layer groups, and the Index cells are figures"
assert "PVIEWS" not in pl and 'class="pviews"' not in html, "one map: From orbit and What changed are no longer views"
for i in ("cake", "ptools", "ptable", "pfigures", "pask"):
    assert f'id="{i}"' in html, i
assert "Where the readings come from" not in html, "each cake row names its source instead"
assert "Tools run on this node with a token. Unlock this screen in Set up." in pl, "a tokenless screen says why the tools are quiet"
assert "$('#pask').hidden = !!D.askOff" in pl and "D.askOff || view() !== 'place'" in pl, "UI_ASK off: the Place Ask line is not drawn and `/` does nothing"
assert "if (D.askOff) return;" in pl.split("$('#pask').onsubmit")[1].split("};")[0], "a submit on a hidden Ask line reaches nothing"
assert ".pask[hidden]{display:none}" in html, "hidden wins over the flex row"
assert "$('#askbtn').addEventListener('click', closeSheet)" in pl, "Ask opens over a phone's sheet: the sheet closes first"
_names = re.findall(r"id: '[a-z0-9]+'.*? name: '([^']+)'", pm.split("const LAYERS = [")[1].split("];")[0])
assert len(_names) == 25 and max(map(len, _names)) <= 14, ("a cake row's name must fit the 216 px column", sorted(_names, key=len)[-3:])
assert "<h2><span>${esc(s.name)}</span>" in pm and "#cake .ck>h2{" in html and "#cake h2" not in html and "<h3><span>" not in pm, "cake headings are h2 under the page's h1"
print("  place: one map, black screen, the cake on the left, tools on the right")

print("all doors checks passed")
