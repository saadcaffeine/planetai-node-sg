"""The ring's outlier fence, run out of the node that owns it.  PYTHONPATH=app python3 tests/test_dashboard.py

On 8 September node #1's card read "5 to 152 µg/m³": one neighbour was reading 152 while the rest read 5 to 12,
and the axis stretched to fit it until the box was a smear at the left edge. The fence decides which stations are
the neighbourhood and which are their own event.

Tukey's 1.5 x IQR is the usual answer and it fails here — with three stations reading 5, 10 and 152, the 152 IS
the upper quartile. A ring is often three or four stations, so this uses median absolute deviation instead. The
case that matters most is the last one: a real regional event, where every station reads high AND agrees, must
never be pinned away as an outlier.

The fence used to be JavaScript in app/static/index.html, where it trimmed a chart axis and nothing else, and
this suite lifted it out of the page with a regular expression and ran it in node. In Release 1 it moved to the
node as `issues.engine.fenced_median`, where every issue's ring column reads it, so this runs the real function
instead of a copy of the page's copy. The page no longer has a fence and must not grow one back.
"""
import json
import re
import os
import shutil
import subprocess
import sys
from pathlib import Path

def _node(prog):
    """Run a JS program through node, with the program on STDIN and never in argv.

    Linux caps a single argument at 128 KiB (MAX_ARG_STRLEN) and macOS does not, so a program
    that outgrew that limit passed on every dev machine and failed only in CI, with `OSError:
    [Errno 7] Argument list too long: 'node'` and no hint that the size was the reason. It
    failed that way from v0.68. The program is a lifted function plus a JSON blob of settings,
    and the blob grows every time a setting is added, so argv was always going to be outgrown.
    tools/check_ui.py already reads its input this way."""
    r = subprocess.run(["node"], input=prog, capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "app"))

from issues.engine import fenced_median   # noqa: E402

CASES = {
    # node #1's own card, 8 September: one station at 152, the rest ordinary
    "node1": [152, 5, 10, 6, 9, 11, 8, 12],
    # the small ring Tukey cannot handle: with n=3 the wild value is itself the upper quartile
    "three_one_wild": [5, 10, 152],
    "calm": [5, 7, 9, 10, 11, 12],
    "identical": [8, 8, 8, 8],
    # every station high AND agreeing. This is smoke over the whole area — `everywhere`, not an outlier.
    "regional_event": [40, 44, 38, 47, 41, 39],
}
out = {k: dict(zip(("median", "pinned"), fenced_median(v))) for k, v in CASES.items()}

assert out["node1"]["pinned"] == [152], f"node #1's 152 must be pinned off the ring: {out['node1']}"
# What "the axis ends near the other eight" became once the fence stopped drawing an axis: the number the ring
# column reports is the other seven's, not one dragged upward by the station having its own event. The plain
# mean of these eight is 26.6 and the plain median 9.5; the fenced median is 9, which is the street.
assert out["node1"]["median"] == 9, f"and the street must read as the other seven read: {out['node1']}"
assert out["three_one_wild"]["pinned"] == [152], \
    f"three stations is a normal ring here; the fence must still hold: {out['three_one_wild']}"
assert out["calm"]["pinned"] == [], f"an ordinary ring pins nothing: {out['calm']}"
# The MAD of a ring that agrees exactly is 0, and without the floor the fence would sit on the median itself and
# call every station its own outlier. 8 in, 8 out, nothing pinned.
assert out["identical"]["pinned"] == [] and out["identical"]["median"] == 8, \
    f"a ring that agrees exactly must not fence itself down to nothing: {out['identical']}"
assert out["regional_event"]["pinned"] == [], \
    ("smoke over the whole area must never be pinned away as an outlier — that is the one reading the household "
     f"most needs to see: {out['regional_event']}")

# And the page must not grow the fence back. It draws the ring's shape from what /nearby already answered; a
# median, a MAD or a fence appearing in dashboard.js is the computation walking back into the renderer.
_js = (ROOT / "app/static/dashboard.js").read_text()
_js = re.sub(r"/\*.*?\*/", " ", _js, flags=re.S)
_js = re.sub(r"(?m)^\s*//.*$", " ", _js)
for _word in ("mad", "fence"):
    assert not re.search(rf"\b{_word}\s*=", _js), f"dashboard.js computes a {_word} again — it belongs in the engine"

# A hole in a series must be a hole in the line. Plot breaks a line at a null by itself (its lineY treats null as
# undefined), so the page keeps the nulls: what this holds is that a nulled hour reaches the day figure's readout as
# "nothing recorded", never as a value. See A NODE THAT CHANGES CLOCK below.

# --- the modular page: three files, one contract, ten sections -------------------------------------------------
#
# Rewritten 15 September 2026 with the page. Everything below used to assert the structure of the
# single-renderer page — its #hero, its Figures table, its Arrange mounts — and that page is gone.
# Each finding it was written from is re-made against the page that draws today; nothing was dropped
# because it was inconvenient to re-express.
_h = (ROOT / "app/static/index.html").read_text()
_css = (ROOT / "app/static/dashboard.css").read_text()

for _must in ('src="static/dashboard.js"', 'href="static/dashboard.css"', 'id="page"'):
    assert _must in _h, f"index.html lacks {_must}"
assert "<style" not in _h and "<script>" not in _h, \
    "index.html carries an inline style or script again — the page is three files, not one"

assert "window.PAI = { STAGES, register, render, wall, sections, problems, has }" in _js, \
    "dashboard.js no longer carries the page contract (kit-page.js) verbatim"
for _sec in ("'ground'", "'sensors'", "'satellite'", "'reticulum'", "'meshtastic'", "'hardware'",
             "'claims'", "'grain'", "'asks'", "'measure'"):
    assert f"id: {_sec}" in _js, f"dashboard.js no longer registers the section {_sec}"
assert "async function boot()" in _js and "/issues/fixtures/" in _js, \
    "dashboard.js boots from /issues and can replay a fixture with ?fixture="
# A style written from JavaScript cannot be read without running the page, and two sections used to.
assert "<style" not in _js and "createElement('style')" not in _js, \
    "no JS-injected styles in production: every module's CSS is in dashboard.css"
# Live tiles tell a tile server which square of the planet is being looked at. They are off unless a
# keeper turns them on, and the setting that turns them on is the only thing that may.
assert "tile.openstreetmap.org" not in _js or "MAP_TILES" in _js, \
    "live tiles are no longer gated on the MAP_TILES setting"

# ...and the page must be able to READ that setting. The line above is a string-proximity check: it
# passed for the whole of the branch while `window.SETTINGS.MAP_TILES` was undefined on every load,
# because GET /settings is describe() — {unlocked, runtime: [{key, value, …}], bootstrap: [...]} —
# and never a flat map. So the predicate was permanently false: no tile was ever requested at any
# setting, the two live bases were never offered, and the page printed "live tiles are off on this
# node" to a keeper who had just turned them on. This runs the page's own two functions against the
# real body of that endpoint, which is the only thing that could have caught it.
if shutil.which("node"):
    import settings as _settings          # the same module app/main.py serves GET /settings from

    def _lift(pattern, what):
        m = re.search(pattern, _js, re.S)
        assert m, f"dashboard.js no longer defines {what}"
        return m.group(0)

    _tiles_js = "\n".join((
        _lift(r"const PLAN_FROM = \d+;", "PLAN_FROM"),
        _lift(r"const tilesAllowed = \(res, settings\) =>.*?;", "tilesAllowed()"),
        _lift(r"const MASKED = '[^']*';", "MASKED"),
        _lift(r"function flatSettings\(d\) \{.*?\n\}", "flatSettings()"),
    ))
    _os_backup = {k: os.environ.get(k) for k in ("MAP_TILES", "TELEGRAM_BOT_TOKEN")}
    _bodies = {}
    for _tiles, _unlocked in (("on", False), ("on", True), ("off", False), (None, False)):
        if _tiles is None:
            os.environ.pop("MAP_TILES", None)
        else:
            os.environ["MAP_TILES"] = _tiles
        os.environ["TELEGRAM_BOT_TOKEN"] = "never-printed"   # a secret must stay masked either way
        _settings._cache["at"] = 0.0
        _bodies[f"{_tiles}-{'unlocked' if _unlocked else 'anonymous'}"] = \
            _settings.describe(unlocked=_unlocked, public=_settings.PUBLIC)
    for _k, _v in _os_backup.items():
        os.environ.pop(_k, None) if _v is None else os.environ.__setitem__(_k, _v)
    _settings._cache["at"] = 0.0

    _prog = (_tiles_js + "\nconst B = " + json.dumps(_bodies) + ";\n"
             + "const out = {};\nfor (const [k, body] of Object.entries(B)) {\n"
             + "  const flat = flatSettings(body);\n"
             + "  out[k] = { at8: tilesAllowed(8, flat), at9: tilesAllowed(9, flat),\n"
             + "             value: flat.MAP_TILES === undefined ? null : flat.MAP_TILES,\n"
             + "             secretLeaked: 'TELEGRAM_BOT_TOKEN' in flat,\n"
             + "             rowsKept: Array.isArray(flat.runtime) };\n}\n"
             + "console.log(JSON.stringify(out))")
    _t = _node(_prog)

    assert _t["on-anonymous"]["value"] == "on", \
        f"MAP_TILES=on must reach window.SETTINGS unmasked for a reader with no token: {_t['on-anonymous']}"
    assert _t["on-anonymous"]["at8"] is True, \
        f"with MAP_TILES=on the page must offer and fetch tiles at resolution 8: {_t['on-anonymous']}"
    assert _t["on-anonymous"]["at9"] is False, \
        f"from resolution 9 inward the node's own plan fills the frame and sends nothing: {_t['on-anonymous']}"
    assert _t["on-unlocked"]["at8"] is True, "the same must hold with the admin token presented"
    assert _t["off-anonymous"]["at8"] is False and _t["None-anonymous"]["at8"] is False, \
        f"off, and unset, must both refuse a tile at every resolution: {_t}"
    # A masked value is not a value. Reading "•••• set" as a setting is how a secret becomes a switch.
    assert not any(v["secretLeaked"] for v in _t.values()), \
        f"a masked or secret key must not be flattened onto window.SETTINGS: {_t}"
    assert all(v["rowsKept"] for v in _t.values()), \
        "the runtime rows themselves must survive: the Set up pane and readLayout() read them"

    # STATIONS_SHOWN, read the same way and for the same reason. The list draws this node's own
    # hardware plus the nearest N of everybody else's, so the keeper's number has to survive the
    # same trip MAP_TILES did not: GET /settings is describe(), never a flat map, and this runs the
    # page's own capOf() against that endpoint's real body rather than against a map written here.
    #
    # The two that are not about plumbing: a blank value is the default, not "no cap" (a node that
    # has never touched the setting must not get a fourteen-row list), and an unreadable one is the
    # default, not zero and not an empty neighbourhood (a typo in a settings box may not blank the
    # section). 0 alone means every station.
    _cap_js = "\n".join((
        _lift(r"const STATIONS_DEFAULT = \d+;", "STATIONS_DEFAULT"),
        _lift(r"const capOf = \(settings\) =>.*?\n\};", "capOf()"),
        _lift(r"const MASKED = '[^']*';", "MASKED"),
        _lift(r"function flatSettings\(d\) \{.*?\n\}", "flatSettings()"),
    ))
    _sb = os.environ.get("STATIONS_SHOWN")
    _caps = {}
    for _v in ("3", "7", "0", "", "nine"):
        if _v == "":
            os.environ.pop("STATIONS_SHOWN", None)
        else:
            os.environ["STATIONS_SHOWN"] = _v
        _settings._cache["at"] = 0.0
        _caps[_v or "unset"] = _settings.describe(unlocked=False, public=_settings.PUBLIC)
    os.environ.pop("STATIONS_SHOWN", None) if _sb is None else os.environ.__setitem__("STATIONS_SHOWN", _sb)
    _settings._cache["at"] = 0.0

    _c = _node(_cap_js + "\nconst B = " + json.dumps(_caps) + ";\n"
                + "const out = {};\nfor (const [k, body] of Object.entries(B)) "
                + "out[k] = capOf(flatSettings(body));\nconsole.log(JSON.stringify(out))")

    assert _c["3"] == 3 and _c["7"] == 7, f"the keeper's number must reach the page: {_c}"
    assert _c["0"] is None, f"0 lists every station: {_c}"
    assert _c["unset"] == 3, f"a node that never set it lists three, not all fourteen: {_c}"
    assert _c["nine"] == 3, f"an unreadable value is the default, never an empty neighbourhood: {_c}"

# The grain section's flat run is READ OFF the table, never written down.
#
# It shipped as `filter(g => g.occupied === 9)` -- node #1's own flat run as a literal -- and on the
# live node proved on 16 September 2026 (no stations, every row zero) `flat[0].res` threw and the
# whole decide stage printed "grain did not render". A literal that happens to be true of one node
# is the thing this assertion exists to keep out.
assert "g.occupied === 9" not in _js, \
    "the grain section is back on node #1's own occupied count as a literal; it must read the table"
assert "function flatRun(H)" in _js, "the grain section no longer derives its flat run"
if shutil.which("node"):
    _run = _lift(r"function flatRun\(H\) \{.*?\n\}", "flatRun()")
    _tables = {
        # node #1, 6 September: nine cells from resolution 9 inward and never again
        "node1": [{"res": r, "occupied": 1 if r < 4 else 9 if r >= 9 else r} for r in range(2, 13)],
        # a node with no station that carries a coordinate: every row zero, and no finding to make
        "empty": [{"res": r, "occupied": 0} for r in range(2, 13)],
        # a node still splitting cells at the finest stop: no flat run either, for the other reason
        "busy": [{"res": r, "occupied": r} for r in range(2, 13)],
    }
    _f = _node(_run + "\nconst T = " + json.dumps(_tables) + ";\nconst out = {};\n"
                + "for (const [k, grain_table] of Object.entries(T)) "
                + "out[k] = flatRun({ grain_table }).map(r => r.res);\nconsole.log(JSON.stringify(out))")
    assert _f["node1"] == [9, 10, 11, 12], f"the flat run must be the tail that stops changing: {_f}"
    assert _f["empty"] == [], f"every row zero is an empty node, not a finding about grain: {_f}"
    assert _f["busy"] == [], f"a count still changing at the finest stop has no flat run: {_f}"

# NOTHING READS THE URL AT MODULE SCOPE, EXCEPT THE FIXTURE.
#
# `const Q = new URLSearchParams(location.search)` at the top level of the nav module was correct for
# as long as every press reloaded the document: the module ran again and the capture was the new URL.
# When v0.55 made a press a re-render, that line became a snapshot of the query the page was FIRST
# opened with, and where() kept answering with the opening cell and resolution — so the dial and every
# cell link changed the URL and nothing else. Zero requests, five milliseconds, and the same page.
#
# No static check saw it and neither did the visual gate, which measures one render. tests/visual/
# measure.mjs gained a `press` command for the behaviour; this is the rule, which needs no browser.
_load_reads = re.findall(r'^(?:const|let|var)\s+(\w+)\s*=\s*new URLSearchParams\(location\.search\)', _js, re.M)
assert set(_load_reads) <= {"FIXTURE"}, (
    f"{sorted(set(_load_reads) - {'FIXTURE'})} capture(s) location.search at module scope. A press is a "
    "re-render now, so a load-time capture is frozen at whatever the page was opened with and the "
    "control it feeds goes dead. Read it at call time — see query() in dashboard.js.")
assert "const query = () => new URLSearchParams(location.search)" in _js, \
    "query() is gone — where() is reading the URL from somewhere that may be stale"

# SET UP OFFERS WHAT `planetai config` OFFERS — every group, every key, the node's own words.
#
# Both read settings.describe(); the CLI walks its groups and prints every key in each. The pane
# filters the same rows by group — except the packs branch, which rendered a list of pack switches
# and returned, so PACKS_ENABLED and PACKS_ALLOW_CODE existed in the CLI and nowhere in the
# dashboard. A keeper who read one and went looking in the other did not find them.
#
# The group tab is also the node's own word for the group, because that is the word `planetai config`
# prints and a keeper moves between the two surfaces.
import settings as _s                                     # the module both surfaces read
_groups = []
for _r in _s.describe(unlocked=False, public=_s.PUBLIC)["runtime"]:
    if _r["group"] not in _groups:
        _groups.append(_r["group"])
_gm = re.search(r"const GROUPS = \{(.*?)\n\};", _js, re.S)
assert _gm, "the Set up pane no longer declares GROUPS"
_titled = dict(re.findall(r"^\s*(\w+):\s*\['([^']*)'", _gm.group(1), re.M))
for _g in _groups:
    assert _g in _titled, f"the node declares the settings group {_g!r} and the Set up pane has no tab for it"
    assert _titled[_g].lower() == _g.lower(), (
        f"the {_g!r} tab is labelled {_titled[_g]!r}; `planetai config` prints {_g!r}, and the two "
        "menus are meant to read alike")
# No group may render instead of its keys. One early return is allowed and is bootstrap, which is
# read-only by nature; everything else falls through to the row loop.
assert "let body = rows.filter(r => !r.pack).map(field).join('');" in _js and "body += boot;" in _js, \
    "a group's own keys (PACKS_ENABLED and PACKS_ALLOW_CODE among them) are no longer rendered in every group"
assert "packCard(p, rows.filter(r => r.pack === p.id).map(field)" in _js and "pane.innerHTML = PACKS.map" not in _js, \
    "the packs group no longer draws each pack's own settings in its card"

# AN UNKNOWN HASH IS AN ANCHOR ON THIS PAGE, NOT A VIEW.
#
# readView() took the hash as the view whatever it said. The lead's own ask line links to
# `#stage-act` — it is what a reader presses when the page says "94 asks open · in 3 Act" — so the
# page routed to a view called `stage-act`, found none, fell through to the branch that draws Set up,
# and rendered a band titled STAGE-ACT with nothing in it. A blank page, reached from the page's own
# link, on a household's node. Every in-page anchor did it: the notes band links back to the section
# each note explains, and so does this one.
#
# Reported by Tomas from node #1 at v0.71, which is the release this fixes.
assert "const VIEW_NAMES = new Set(" in _js, \
    "readView no longer has a list of what a view IS, so any hash is one again"
assert re.search(r"VIEW = VIEW_NAMES\.has\(h\) \? h : \(q\.get\('view'\) \|\| \(h && VIEW \? VIEW : 'now'\)\)", _js), \
    ("an unknown hash is being taken as a view again — `#stage-act` empties the page, and so does "
     "every link in the notes band")
# Every hash the page itself writes must either name a view or name an element it draws.
_names = set(re.findall(r"'(now|historical|network|wall|arrange|setup)'",
                        re.search(r"const VIEW_NAMES = new Set\(\[(.*?)\]\)", _js, re.S).group(1)))
assert _names == {"now", "historical", "network", "wall", "arrange", "setup"}, \
    f"VIEW_NAMES and the six views have drifted apart: {sorted(_names)}"
# The one literal anchor the page writes is the lead's, and the element it points at is built from
# a template — `id="stage-${key}"` — so there is no literal to grep for. Assert the pair instead:
# the link, and the template that makes its target. The rig checks the live page lands on it.
# (v0.78: it counts events and points at Decide, where the cards are, not at Act.)
assert 'href="#stage-decide"' in _js, "the lead no longer links to the Decide stage"
assert 'id="stage-${key}"' in _js, \
    "the stages no longer carry an id, so the lead's link to #stage-decide lands nowhere"
# And an anchor must not throw the page away: same view, so scroll rather than re-render.
assert "if (VIEW === before)" in _js and "scrollIntoView({ block: 'start' })" in _js, \
    ("a hashchange that does not change the view re-renders the whole page, which loses the scroll "
     "position, the open folds and the learn panel for a link to somewhere already on screen")

# AN IN-PAGE LINK KEEPS THE VIEW IT WAS CLICKED ON. The header's nav writes `#network`; a click on
# `#grain` then replaced it, `grain` is no view and there is no ?view=, so readView() answered `now`
# and the hashchange handler routed the reader back to Now. Every in-page link on Network and
# Historical did it. This lifts readView and VIEW_NAMES and runs the sequence a reader makes.
if shutil.which("node"):
    _src = (ROOT / "app/static/dashboard.js").read_text()
    _rv = _node("\n".join((
        "globalThis.window = globalThis; let VIEW = 'now', STATE;",
        re.search(r"const VIEW_NAMES = new Set\(.*?\);\n", _src).group(0),
        re.search(r"function readView\(\) \{.*?\n\}\n", _src, re.S).group(0),
        """const at = (search, hash) => { globalThis.location = { search, hash }; readView(); return VIEW; };
const out = {};
out.first_anchor = at('', '#grain');                     /* first load on an anchor, VIEW still 'now' */
out.network = at('', '#network');
out.keeps_network = at('', '#grain');                    /* the in-page link: no view, no query */
out.keeps_again = at('', '#claims');
out.hist_query = at('?view=historical', '#trust');
out.keeps_hist = at('', '#grain');
out.now = at('', '#now');
out.now_no_hash = (at('', '#network'), at('', ''));      /* the Now button clears the hash */
console.log(JSON.stringify(out));""")))
    assert _rv == {"first_anchor": "now", "network": "network", "keeps_network": "network",
                   "keeps_again": "network", "hist_query": "historical", "keeps_hist": "historical",
                   "now": "now", "now_no_hash": "now"}, \
        f"readView: an in-page anchor must keep the view the reader is on: {_rv}"

# THE PAGE KEEPS UP WITH THE NODE, AND SAYS SO WHEN IT CANNOT.
#
# v0.53 ended its boot with `setInterval(refresh, 20000)`. The Phase 2 rewrite did not carry it, and
# for four releases the only repeating timer in this file was the wall stepping its own dial: boot()
# fetched once and the page then showed a `live` pill over figures that had stopped moving when the
# tab opened. Nothing caught it — every check here measures one render, and one render of a frozen
# page looks exactly like one render of a fresh one. These are the assertions that would have.
assert "function refresh()" in _js and "setInterval(refresh, refreshEvery())" in _js, \
    "the page no longer re-fetches on a timer — it will show the readings it booted with, forever"
_bootline = _js[_js.index("boot().then("):]
_bootline = _bootline[:_bootline.index("\n")]
assert "startRefresh()" in _bootline, "boot no longer starts the refresh loop"
assert "route()" in _bootline and "init()" in _bootline, "boot no longer draws the page"

# THE LOADING STATE PLAYS ON THREE THINGS AND A POLL IS NOT ONE OF THEM.
#
# `asking` covers the page. A poll fires every POLL_SECONDS on a page somebody is reading, so an
# overlay on every poll would make a node that is working perfectly look like one that is stuck —
# and it would do it every five minutes, on a wall, unattended. The rule is in prompt 6 and it is one
# line of code away from being broken by accident, so it is asserted here rather than remembered.
assert "ASKING.close()" in _bootline, "the loading state is never taken down after the first paint"
_ask = _js[_js.index("async function refresh()"):_js.index("function redraw(opts)")]
assert "ASKING.open" in _ask, "refresh() never plays the loading state, so a reconnect is silent"
for _line in _ask.splitlines():
    _code = _line.split("//")[0]
    if "ASKING.open" in _code:
        assert "mine" in _code or "STALE" in _code, \
            ("refresh() plays the loading state unconditionally, so it plays on every poll: "
             + _code.strip())
assert "const wasStale = !!window.STALE" in _ask and "mine = wasStale" in _ask, \
    "refresh() no longer decides between a reconnect and a poll before playing the loading state"
# And the header's control is a different function on purpose: if ↻ were refresh() with the overlay
# bolted on, the timer would inherit it the next time somebody edited either one.
assert "async function askAgain()" in _js and "ASKING.open('Asking the node again'" in _js, \
    "the header's re-ask no longer has a function of its own"
# THE FLOOR, AND THE TWO MOMENTS THAT ASK FOR IT.
#
# What the loading state says is the page's account of what it asked of the world — the endpoints and
# the milliseconds each took — and on a fixture the node answers in under a tenth of a second, so
# without a floor nobody ever read it. A reload and the header's ↻ are the two moments a PERSON
# asked to see it; a reconnect is not, because there the page coming back is the thing wanted and a
# delay is only a delay. So exactly those two pass `true`.
assert "ASKING.open('Asking the node', true)" in _js, "a reload no longer holds the loading state"
assert "ASKING.open('Asking the node again', true)" in _js, "the ↻ no longer holds it"
assert re.search(r"ASKING\.open\('The node stopped answering[^)]*\)(?!\s*,\s*true)", _js), \
    "a reconnect now holds the page for the floor, which delays the answer a reader is waiting for"
assert "window.K.msToken('--motion-asking-hold')" in _js, \
    "the floor is no longer read from the layer's own token"
# What it may and may not ask for again. /settings, /earth, /sensors, /cells and the plan do not move
# on the node's poll; re-fetching them every cycle is traffic for no change.
_ref = _js[_js.index("async function refresh()"):_js.index("function redraw(opts)")]
for _route in ("'/issues'", "'/health'"):
    assert _route in _ref, f"refresh() no longer re-reads {_route}"
for _route in ("'/settings'", "'/earth'", "'/sensors'", "'/cells'", "'/place/geojson'"):
    assert _route not in _ref, \
        f"refresh() re-reads {_route} on every poll; it does not change on the node's cadence"
# A fixture is a committed snapshot and cannot change. The measuring rig replays one, so a refresh
# here would also re-fetch underneath a running measurement.
assert "if (FIXTURE || STATE !== 'populated') return;" in _ref, \
    "refresh() no longer refuses to poll a replayed fixture or a synthetic state"
# The cadence is the node's own, not a number typed into the page.
assert "POLL_SECONDS" in _js, "the refresh cadence is no longer read from the node's own poll interval"
# And the one that matters: a failed poll must reach the stamp. Saying `live` over figures nothing is
# refreshing is the fault this whole block exists for.
assert "window.STALE" in _js and "pill('stale'" in _js, \
    "a failed poll no longer reaches the page — the live pill would sit over stale figures again"
assert "the node has not answered for" in _js, \
    "the as-of stamp no longer says how long the node has been silent"

# A POLL DOES NOT ASK A TILE SERVER ANYTHING.
#
# Assigning innerHTML queues an <img> load the instant the markup exists, so a redraw goes to the
# network even for a tile the browser has cached. Measured over CDP while building the refresh loop:
# twelve requests to tiles.maps.eox.at per redraw, none from cache, though the tiles carry max-age of
# a week. At one poll per 300 s that is ~3,500 a day from every open page, each telling that server
# which square of the planet this house is looking at. The rule since Phase 2 is that a press may
# only ever REDUCE what leaves the house; a poll multiplying it by three hundred breaks it from the
# other side. After the gate: 12 on first load, 0 on every poll after.
assert "if (window.KEEP_GROUND) return '';" in _js, \
    "the tile figure no longer refuses to redraw for a data poll — every poll will re-ask the tile server"
assert "if (ground) window.KEEP_GROUND = true;" in _js and "finally { window.KEEP_GROUND = false; }" in _js, \
    "redraw() no longer raises the keep-ground flag across route(), or no longer lowers it after"
# Only a data poll may set it. A press changes the cell or the resolution and MUST draw a new map.
_rd = _js[_js.index("function redraw(opts)"):]
_rd = _rd[:_rd.index("\n}") + 2]
assert "opts && opts.keepGround" in _rd, "redraw() keeps the ground unconditionally — a press would not redraw the map"

# THE RAIL IS NOW'S CONTROL. It was the dial, drawn under every view's header until 18 September,
# where on Network, Historical and Set up nothing on the page answered to it. Arrange keeps it: it
# draws Now's own sections through want(NOW), so taking it away there left seven of them — the
# ground, the station groups, the claims, the grain and the grain line — pointing at a control that
# was not on the page. Renamed to the rail on 21 September when it became the top instrument (design
# log R14); the wall keeps its own dial, which is a different control on a different surface.
assert "VIEW === 'now' || VIEW === 'arrange'" in _js and 'class="railwrap"' in _js, \
    "the rail is no longer drawn for Now and Arrange, or is drawn for every view again"
# (v0.78: the grain line moved to Network with its section, so the rail points at the ground figure.)
assert re.search(r"const ref = 'ground-figure';", _js), \
    "the rail's link out is back to being chosen per view; only Now draws it now"
# The zones are texture, not hue (design log R14). The cells blue has one meaning — a cell — and a
# 12% wash of it for "may leave this machine" spent it on a second, vanished for a reader who cannot
# separate blue from grey, and went white on a printed plate.
assert not re.search(r"\.rail a\.leaves\s*\{[^}]*--cells", _css), \
    "the rail's may-leave zone is back to a wash of the cells blue; it is a dot screen"
assert re.search(r"\.rail a\.leaves\s*\{[^}]*radial-gradient", _css), \
    "the rail's may-leave zone has lost its texture, so the three zones are two"
assert 'data-component="rail"' in _js and 'data-kind="row"' in _js, \
    "the rail no longer declares itself a component of a card kind the page is held to"
assert 'data-ref="dial"' not in _js, \
    "something still points at a component called dial; on Now it is the rail, and T5 counts orphans"

# axe found nothing on any view or state, and these are the findings that had to hold for that.
#
# The page had no h1 at all (a <b> carried the node's name, so page-has-heading-one fired on every
# view in every state, and the wall has no header so it needed its own); a table that scrolls inside
# its own box could not be reached by keyboard; and --dim, at about 4:1 on paper, carried the small
# text that says where a number came from.
assert re.search(r'<h1 class="brand">', _js), "the node's name is not the page's h1 again"
assert re.search(r'<h1 class="vh">', _js), "the wall has no heading of its own; its header is display:none"
assert 'class="tblwrap" tabindex="0"' in _js, "the grain table cannot be scrolled from a keyboard again"
for _sel in (".readrow .who .m {", ".cellhead .n {", "[data-kind=\"readout\"] .src {"):
    _rule = _css[_css.index(_sel):_css.index("}", _css.index(_sel))]
    assert "--dim" not in _rule, f"{_sel.strip(' {')} is back on --dim, which is about 4:1 on paper"

# Arrange must actually arrange, and the view must be in the URL.
#
# Two of these shipped together on the page this replaces and each was invisible until somebody tried
# the mode: the ✕ silently did nothing on five of the nine bands, because render() skipped a hidden
# id and left the mount holding its last content; and the restore menu was markup only — `#arr-restore`
# appeared once in index.html and was never referenced, so a hidden band could only come back via
# Default, which discards every other choice. Both assertions point at the ported code.
#
# `want()` is where a hidden section goes: the view's own list is filtered before anything is drawn,
# so a hidden section is never emitted at all and cannot be left holding anything. Red if the filter
# goes, or if the view stops going through it.
assert "view.filter(id => !(LAYOUT.hidden || []).includes(id))" in _js, \
    "a section hidden in Arrange is no longer filtered out before the page is drawn — ✕ does nothing"
for _v in ("NOW", "NETWORK", "HISTORICAL"):
    assert f"want([...{_v}" in _js or f"want({_v})" in _js, \
        f"the {_v} view no longer goes through want(), so hiding a section has no effect on it"

# A SECTION THE PAGE HAS NEVER HEARD OF HAS TO GO SOMEWHERE.
#
# One registry serves three views through three hardcoded arrays of ids. A pack's section is an id
# this file has never seen — that is the whole point of the contract, and the docstring at the top of
# dashboard.js promises it in as many words. From the Now/Network split until 22 September a
# registered section not typed into one of those arrays was filtered out of all three and drawn
# nowhere: it registered, Set up listed it as `drawing`, and it was on no page. Now is the default
# home for anything the two named lists do not claim, and this is the line that says so.
# Since 2 October 2026 a section can also arrive as data, declared in a pack.yaml and served in /issues; it is placed
# on no view either, so the same line homes both.
assert "const homeless = PAI.sections.concat(PAI.declared(ctx)).map(s => s.id).filter(id => !placed.has(id))" in _js, \
    ("a registered section that no view names is filtered out of every view again, so a pack can "
     "register a section and have it drawn nowhere — which is the contract this page publishes")
assert "want([...NOW, ...homeless])" in _js, \
    "Now is no longer the default home for a section no view names"
# and the restore menu must be read, not just drawn. Red if fillRestore stops filling it or the
# change handler stops putting the section back.
assert "arr-restore" in _js, "the restore menu is markup nobody reads again; a hidden section cannot come back"
assert "function fillRestore()" in _js and "LAYOUT.hidden = (LAYOUT.hidden || []).filter(x => x !== id)" in _js, \
    "the restore menu no longer puts a hidden section back"

# The view must be in the URL, and it must get there without scrolling the page to an element.
assert "history.pushState" in _js, "the view is not in the URL: refresh, back and a shared link all land on Now"
assert not re.search(r"location\.hash\s*=", _js), \
    "assigning location.hash jumps to that element, which eats the scroll restore — use pushState"

# Every entry point into the token path must be listened for. They were drawn and dead once: the
# three cases below lived in the old page's global click listener, and the pane came across without
# them — so unlock() and saveSettings() were defined and unreachable, the gate never opened, and
# PAI_SETTINGS.set() could only ever throw for want of a token nothing could store.
for _case in ("ev.target.id === 'btn-unlock'", "ev.target.id === 'btn-save'",
              "ev.target.closest('[data-reveal]')"):
    assert _case in _js, f"the Set up pane has no handler for {_case} — the button is drawn and dead"

# And the page must read the household's language rather than pinning itself to English.
assert "(S.health || {}).locale" in _js, \
    "initKit no longer reads the locale off /health — the page is back to English on every node"

# And a refused page must say so on whichever surface is being drawn.
#
# At SHARE_LEVEL=off — the default, and what every beta tester has — the page gets 403 on /issues and
# nothing else. /health still answers, so the node's name and the nav are still there and the
# household's own sentence about why is drawn on the view they are standing on, the WALL included: a
# black shelf screen is read as a dead node, and "a blank page would be the node lying about being
# broken" is the renderer's own rule.
_refused = _js[_js.index("function drawRefused()"):]
_refused = _refused[:_refused.index("\n}") + 2]
for _mount in ("wallbox", "wrap"):
    assert f'"{_mount}' in _refused or f"class=\"{_mount}" in _refused, \
        f"the refused branch does not draw into .{_mount} — that view renders blank at SHARE_LEVEL=off"
assert "chrome(" in _refused, "a refused reader cannot reach the other views: the nav is not drawn"
# and the page must not claim a reading it does not have: the provenance word follows the fixture,
# and a refused page never reaches the lead at all.
assert re.search(r"S\.fixture \? pill\('cached'", _js), \
    "the lead's provenance pill no longer follows whether this is a fixture; it said `live` over a snapshot"

# --- the mode, read the way MAP_TILES was not ------------------------------------------------------------------
#
# UI_MODE decides whether the page draws every section or four sentences, so a page that cannot read
# it opens in the wrong one for every household that set it. That is exactly the MAP_TILES bug forty
# lines up: GET /settings is describe() — {unlocked, runtime: [{key, value, ...}], bootstrap: [...]}
# — never a flat map, and a proximity check would pass while `window.SETTINGS.UI_MODE` was forever
# undefined. So this runs the page's own mode() against that endpoint's real body.
#
# The precedence is the other half: `?mode=` for the rig and for a link one person sends another,
# then this browser's own choice, then what the household set the node to. A reader switching must
# not rewrite the node, and the node must not overrule a reader who has switched.
if shutil.which("node"):
    _mode_js = "\n".join((
        _lift(r"const MODE_KEY = '[^']*';", "MODE_KEY"),
        _lift(r"const MODES = \[.*?\];", "MODES"),
        _lift(r"const isMode = .*?;", "isMode()"),
        _lift(r"const SHORT_VIEW = new Set\(\[.*?\]\);", "SHORT_VIEW"),
        _lift(r"function mode\(view\) \{.*?\n\}", "mode()"),
        _lift(r"function modeRaw\(\) \{.*?\n\}", "modeRaw()"),
    ))
    _mode_bodies = {}
    _mb = os.environ.get("UI_MODE")
    for _v in ("simple", "learn", "", "sideways"):
        os.environ["UI_MODE"] = _v
        _settings._cache["at"] = 0.0
        _mode_bodies[_v or "unset"] = _settings.describe(unlocked=False, public=_settings.PUBLIC)
    os.environ.pop("UI_MODE", None) if _mb is None else os.environ.__setitem__("UI_MODE", _mb)
    _settings._cache["at"] = 0.0

    _cases = {
        # name                 node setting   this browser   the URL
        "node_simple":        ("simple",      None,          ""),
        "node_learn":         ("learn",       None,          ""),
        "node_unset":         ("unset",       None,          ""),
        "node_garbage":       ("sideways",    None,          ""),
        "browser_overrides":  ("simple",      "learn",       ""),
        "url_overrides_both": ("simple",      "learn",       "?mode=advanced"),
        "url_garbage":        ("simple",      None,          "?mode=sideways"),
        "storage_blocked":    ("learn",       "THROW",       ""),
    }
    _prog = (_mode_js + "\nconst B = " + json.dumps(_mode_bodies)
             + ";\nconst C = " + json.dumps(_cases) + ";\nconst out = {};\n"
             + "for (const [name, [setting, mine, search]] of Object.entries(C)) {\n"
             + "  globalThis.window = { SETTINGS: B[setting] };\n"
             + "  globalThis.location = { search };\n"
             + "  globalThis.localStorage = mine === 'THROW'\n"
             + "    ? { getItem() { throw new Error('site data blocked'); } }\n"
             + "    : { getItem: k => (k === MODE_KEY && mine !== null ? mine : null) };\n"
             + "  try { out[name] = mode(); } catch (e) { out[name] = 'THREW: ' + e.message; }\n"
             + "}\nconsole.log(JSON.stringify(out))")
    _m = _node(_prog)                   # on stdin: the settings blob outgrew Linux's 128 KiB argv cap at v0.80

    assert _m["node_simple"] == "simple", \
        f"UI_MODE must reach the page through describe()'s runtime rows, not a flat map: {_m}"
    assert _m["node_learn"] == "learn", f"every value the setting allows must arrive: {_m}"
    # A VIEW WITH NO SHORT ANSWER DRAWS THE FULL ONE, whatever this browser last chose.
    #
    # Simple is the short version of what a view reports, and three views do not report: Set up is a
    # form, Arrange is a mode for moving sections about, and the Wall is already one screen at three
    # metres with no header to put a control in. Before this, a reader who chose Simple on Now and
    # then opened Arrange got the digest, no sections at all, and a bar offering to reorder them.
    # The stored choice is not rewritten — going back to Now restores it — so both halves are here.
    _vprog = (_mode_js + ";\nglobalThis.window = { SETTINGS: { runtime: [] } };\n"
              + "globalThis.location = { search: '' };\n"
              + "globalThis.localStorage = { getItem: k => (k === MODE_KEY ? 'simple' : null) };\n"
              + "const out = {}; for (const v of ['now','historical','network','setup','arrange','wall',undefined])\n"
              + "  out[String(v)] = mode(v);\nconsole.log(JSON.stringify(out))")
    _v = _node(_vprog)
    for _view in ("now", "historical", "network"):
        assert _v[_view] == "simple", \
            f"{_view} reports something, so it must honour a reader's Simple: {_v}"
    for _view in ("setup", "arrange", "wall"):
        assert _v[_view] == "advanced", \
            (f"{_view} has no short answer to give, so Simple must not follow a reader onto it — "
             f"on Arrange it took every section away and left the bar with nothing to arrange: {_v}")
    assert _v["undefined"] == "simple", \
        f"asked without a view, mode() must still answer what this browser chose: {_v}"

    assert _m["node_unset"] == "advanced", \
        f"a node that never set it opens on the whole page, not on four sentences: {_m}"
    assert _m["node_garbage"] == "advanced", \
        f"an unreadable setting is the default, never a blank page: {_m}"
    assert _m["browser_overrides"] == "learn", \
        f"a reader who switched keeps their choice over the node's: {_m}"
    assert _m["url_overrides_both"] == "advanced", \
        f"?mode= is what the rig and a shared link use, and it wins: {_m}"
    assert _m["url_garbage"] == "simple", \
        f"a nonsense ?mode= falls through to the node rather than to the default: {_m}"
    assert _m["storage_blocked"] == "learn", \
        f"a browser with site data blocked still renders; it just cannot remember: {_m}"

# The digest is drawn in simple mode and the node writes it. Both halves matter: a page that
# composed its own four sentences would be the renderer making a claim about the household's data.
assert "function digest(ctx)" in _js, "dashboard.js no longer draws the digest"
assert re.search(r"const d = \(ctx\.S\.issues \|\| \{\}\)\.digest", _js), \
    "the digest is no longer READ from /issues — if the page is composing those sentences, stop"
assert re.search(r"simple && onNow \? digest\(ctx\) : ''", _js), \
    "simple mode no longer draws the digest in place of the sections it hides"
# AND ONLY ON NOW. The digest is four sentences about this hour. It was drawn on every view in
# simple mode, so Historical and Network each answered "what is the air doing right now" under a
# heading about the years and about the network, with no sections under them because none of theirs
# opted into simple: 652 characters, not one about the view the reader had asked for. A short answer
# to the wrong question is worse than a long answer to the right one.
assert re.search(r"const onNow = !opts\.only \|\| opts\.only\.includes\('matrix'\)", _js), \
    "the digest is no longer confined to Now, so the other views answer a question nobody asked"
# Each of the other two names its own short answer instead, which is the section the pack says leads
# that view: the satellite loop on Historical, the network map on Network.
for _sec in ("satellite", "netmap"):
    _blk = _js[_js.index(f"id: '{_sec}'"):]
    assert "level: 'simple'" in _blk[:400], \
        f"{_sec} no longer opts into simple, so its view has no short answer to give"
assert "level: 'advanced'" in _js, \
    "the section contract lost its default level, so every section would vanish in simple mode"

# --- what a node publishes, usable from its own page ------------------------------------------------
# Every band names the routes its data came from, and the shell prints them beside the kicker as
# links. check_ui.py checks each route exists; this checks every section carries some and that the
# shell draws them in their own case rather than inside the shouted kicker text.
_js_raw = (ROOT / "app/static/dashboard.js").read_text()
_heads = re.findall(r"^window\.PAI\.register\(\{(.*?)\n  (?:render|lead|controls|wall|notes)\b", _js_raw,
                    re.S | re.M)
assert len(_heads) == len(re.findall(r"^window\.PAI\.register\(\{", _js_raw, re.M)) >= 24, \
    "a registration the test cannot read the fields of, or fewer than the 24 sections this page draws"
for _h in _heads:
    _sid = re.search(r"\bid:\s*'([^']+)'", _h).group(1)
    _r = re.search(r"\breads:\s*\[([^\]]*)\]", _h)
    assert _r and re.findall(r"'(/[^']*)'", _r.group(1)), f"section '{_sid}' does not say which routes it reads"
assert re.search(r'<span class="routes">\$\{s\.reads\.map\(r => `<a href="\$\{esc\(r\)\}">GET \$\{esc\(r\)\}</a>`\)', _js_raw), \
    "the shell no longer prints a band's routes as links beside its kicker"
assert re.search(r"\.band > \.k \.routes \{[^}]*text-transform: none", (ROOT / "app/static/dashboard.css").read_text()), \
    "a band's routes inherit the kicker's uppercase, and a route uppercased cannot be typed back"

# The ledger's note that said the node had no `decided` stage. It has had one since the Decide card.
assert "ledger-no-decision" not in _js_raw and "No stage for a decision" not in _js_raw, \
    "the ledger's note saying there is no decided stage is back, and it is false"

# The registry band sends a reader to the documentation's "Adding a source". The anchor is what
# tools/build_docs.py makes of that heading; a renamed heading is a link to the top of a page.
_anchor = re.search(r"const ADD_A_SOURCE = 'https://planetai\.fab\.city/docs/sources/#([a-z0-9-]+)';", _js_raw)
assert _anchor, "the registry band no longer links to the documentation's steps for adding a source"
_slug = lambda t: re.sub(r"[\s_-]+", "-", re.sub(r"[^\w\s-]", "", t.lower()).strip())   # build_docs.slugify_for("")
_heads_md = [_slug(h) for h in re.findall(r"^#{2,3} (.+)$", (ROOT / "docs/site/sources.md").read_text(), re.M)]
assert _anchor.group(1) in _heads_md, f"#{_anchor.group(1)} is not a heading of docs/site/sources.md: {_heads_md}"

# A provenance word signs.svg has no symbol for is printed as the word, never as an empty square.
_svg = (ROOT / "app/static/signs.svg").read_text()
_signs = re.search(r"const PROV_SIGNS = new Set\(\[([^\]]*)\]\);", _js_raw)
assert _signs, "pill() no longer says which provenance words the sprite draws"
for _w in re.findall(r"'([a-z]+)'", _signs.group(1)):
    assert f'id="sign-prov-{_w}"' in _svg, f"PROV_SIGNS names {_w}, which signs.svg does not draw"

if shutil.which("node"):
    _pill = _node("\n".join((
        re.search(r"const esc = s => .*?\);\n", _js_raw, re.S).group(0),
        _signs.group(0),
        re.search(r"const pill = \(word, note = ''\) => \{.*?\n\};", _js_raw, re.S).group(0),
        "console.log(JSON.stringify({ stale: pill('stale', 'x'), live: pill('live') }))")))
    assert "<use" not in _pill["stale"] and "stale" in _pill["stale"], \
        f"pill('stale') must print the word with no sign, since signs.svg has none: {_pill['stale']}"
    assert "sign-prov-live" in _pill["live"], f"pill('live') lost its sign: {_pill['live']}"

    # THE EVENT CARD (SPEC_dashboard_events §4.2). The helpers are lifted whole; S, ISS and LOC are the
    # kit's own `let` bindings, so the program declares them the way initKit() would.
    _ev = "\n".join((
        re.search(r"const esc = s => .*?\);\n", _js_raw, re.S).group(0),
        re.search(r"const fmt = .*?\n", _js_raw).group(0),
        re.search(r"const sign = \(id, cls = ''\) =>\n.*?;\n", _js_raw).group(0),
        re.search(r"const TOKEN_FINE = .*?</p>`;", _js_raw, re.S).group(0),
        re.search(r"function evState\(\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"const evOpen = .*?\n", _js_raw).group(0),
        re.search(r"function evClock\(iso\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evButtons\(e\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evWord\(stage\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evAnswered\(e\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"const age = m => .*?days ago`;", _js_raw, re.S).group(0),
        re.search(r"function evLive\(e\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evCard\(e, tail = ''\) \{.*?\n\}", _js_raw, re.S).group(0),
    ))
    _evr = _node(_ev + r"""
let LOC = 'en';
let HID = [], DAY_UNMET = true;
const window = { PAI: { sections: [], has: p => p !== 'H3.missing', isHidden: id => HID.includes(id) } };
const secs = (...ids) => { window.PAI.sections = ids.map(id => ({ id, needs: id === 'day' && DAY_UNMET ? ['H3.missing'] : [] })); };
const ISS = { heat: { name: { en: 'Heat' }, unit: '°C', dp: 1, metric: 'temp', hero: { sign: 'sign-heat' } } };
const BTN = { done: 'Done', not_now: 'Not now', doesnt_fit: 'Doesn’t fit' };
const ev0 = { id: 7, issue: 'heat', kind: 'sustained', level: 'warn', opened_at: '2026-10-05T09:30:00Z',
  peak: 36.2, line: 35, rooms: ['loft'], context: { usual: 33.4, outside: 29.1, outside_metric: 'temp',
  outside_from: 'outside' }, action: { id: 'a', text: 'Close the shutters <now>' },
  message: { text: 'It is hot <b>', ts: '2026-10-05T09:31:00Z', sent: true }, alerts: [1, 2], answer: null };
const run = (events, over) => { S = { issues: { events }, health: { tz: 'UTC' } }; return evCard({ ...ev0, ...over }); };
let S;
const E = (engine, extra) => ({ engine, buttons: BTN, open: [], ...extra });
const n = (s, re) => (s.match(re) || []).length;
const out = {
  old: (S = { issues: {} }, evState()), nul: (S = { issues: { events: null } }, evState()),
  err: (S = { issues: { events: { error: 'x' } } }, evState()), shadow: (S = { issues: { events: E('shadow') } }, evState()),
  rules: (S = { issues: { events: E('rules') } }, evState()), evs: (S = { issues: { events: E('events') } }, evState()),
  open: (S = { issues: { events: E('events', { open: [1] }) } }, evOpen()), none: (S = { issues: {} }, evOpen()),
  clock: (S = { issues: {}, health: { tz: 'Asia/Makassar' } }, evClock('2026-10-05T09:30:00Z')),
  utc: (S = { issues: {} }, evClock('2026-10-05T09:30:00Z')), bad: (S = { issues: {} }, evClock('nope')),
  open_card: run(E('events'), {}), shadow_card: run(E('shadow'), {}),
  held_msg: run(E('events'), { message: { text: 'x', ts: '2026-10-05T09:31:00Z', sent: false } }),
  acted: run(E('events'), { answer: { stage: 'acted', actor: 'tomas', ts: '2026-10-05T10:00:00Z' } }),
  held: run(E('events'), { answer: { stage: 'acknowledged', actor: 'tomas', ts: '2026-10-05T10:00:00Z',
    held_until: '2026-10-05T12:00:00Z' } }),
  noted: run(E('events'), { answer: { stage: 'dismissed', actor: 'tomas', ts: '2026-10-05T10:00:00Z',
    note: 'I opened the window <b>' } }),
  under: run(E('events'), { peak: 34 }),
  live: run(E('events'), { last_seen_at: new Date(Date.now() - 3 * 6e4).toISOString() }),
  noact: run(E('events'), { action: null, context: {}, line: null }),
  l_all: (secs('matrix', 'sensors'), run(E('events'), {})),
  l_unmet: (secs('matrix', 'day', 'sensors'), run(E('events'), {})),
  l_none: (secs(), run(E('events'), { alerts: [] })),
  l_hidden: (DAY_UNMET = false, secs('matrix', 'day', 'sensors'), HID = ['day'], run(E('events'), {})),
  l_shown: (HID = [], run(E('events'), {})),
  tail: (S = { issues: { events: E('events') } }, evCard(ev0, '<details id="evrows-7">T</details>')),
};
console.log(JSON.stringify(out));""")
    assert [_evr[k] for k in ("old", "nul", "err", "shadow", "rules", "evs")] == \
        ["old", "old", "error", "shadow", "rules", "events"], f"evState: {_evr}"
    assert _evr["open"] == [1] and _evr["none"] == [], "evOpen reads S.issues.events.open, or []"
    assert _evr["clock"] == "17:30" and _evr["utc"].endswith("UTC") and _evr["bad"] == "", \
        f"evClock: {_evr['clock']!r} {_evr['utc']!r} {_evr['bad']!r}"
    _c = _evr["open_card"]
    assert 'data-num="ev.7.peak"' in _c, "the peak numeral is a data-num, so the number gate reads it"
    # The card is a readout (spec §4.2), and it points at Decide's band: a num-<issue> id exists only for the
    # lead's issue, so an event about any other issue pointed at nothing.
    _head = _c[:_c.index(">")]
    assert 'data-kind="readout"' in _head and 'data-ref="decide"' in _head and "num-" not in _head, _head
    _cmp = re.search(r'data-cmp="([^"]*)"', _c).group(1)
    assert "usual at this hour 33.4" in _cmp and "outside 29.1" in _cmp and "from outside" in _cmp \
        and "the line 35.0" in _cmp, f"data-cmp must name usual, outside and the line: {_cmp}"
    assert "Close the shutters &lt;now&gt;" in _c and "<now>" not in _c, "the action text is the node's, escaped"
    assert "It is hot &lt;b&gt;" in _c and "<b>It" not in _c, "the message is escaped"
    assert len(re.findall(r'<button type="button" class="evb', _c)) == 3, "three buttons"
    for _t in ("Done", "Not now", "Doesn’t fit"):
        assert f">{_t}</button>" in _c, f"button {_t!r} missing"
    assert "sent 09:31" in _c and "would have sent" not in _c, "an events node says sent"
    assert "would have sent 09:31" in _evr["shadow_card"], "a shadow node says would have sent"
    assert "held 09:31" in _evr["held_msg"], "an unsent message says held"
    assert 'class="evnum worse"' in _c and 'class="evnum"' in _evr["under"], "worse only when peak > line"
    # The live stamp (docs/decisions/2026-10-10): an open event says the engine is still watching, from the
    # wire's last_seen_at — and says nothing when the wire carries none.
    assert "watching — last seen" in _evr["live"] and "min ago" in _evr["live"], \
        f"an open event carries its live stamp: {_evr['live'][:200]}"
    assert "watching" not in _c, "no last_seen_at, no stamp — the card never invents one"
    assert 'class="evb' not in _evr["acted"] and "evdone" in _evr["acted"] and "tomas" in _evr["acted"], \
        "an acted event has no buttons and says who"
    assert "evheld" in _evr["held"] and "held until 12:00" in _evr["held"] and 'class="evb' in _evr["held"], \
        "a held event keeps its buttons and says until when"
    assert '“I opened the window &lt;b&gt;”' in _evr["noted"] and "<b>" not in _evr["noted"].split("evnote")[1], \
        "a Doesn't fit with a note carries the household's own words, escaped"
    assert "evnote" not in _evr["acted"], "an answer without a note invents none"
    assert "A name first, so the record says who." in _js_raw, \
        "the card's form refuses an anonymous answer — the five nameless rows of 10 Oct are the why"
    # An evidence link goes only to a section the page is drawing: `sensors` is the air-quality pack's (absent in l_all), and
    # `day` here is registered but its needs are not met. A link to neither would point at nothing.
    assert 'href="#matrix"' in _evr["l_all"] and 'href="#sensors"' in _evr["l_all"] \
        and 'href="#day"' not in _evr["l_all"] and 'href="#evrows-7"' in _evr["l_all"], \
        f"links: matrix and sensors drawn, day absent: {_evr['l_all']}"
    assert 'href="#sensors"' in _evr["l_unmet"] and 'href="#day"' not in _evr["l_unmet"]
    assert 'href="#matrix"' not in _evr["noact"] and 'href="#sensors"' not in _evr["noact"], \
        "no section registered, no link to one"
    assert 'href="#day"' not in _evr["l_hidden"] and 'href="#matrix"' in _evr["l_hidden"], \
        f"a section hidden in Arrange gets no link: {_evr['l_hidden']}"
    assert 'href="#day"' in _evr["l_shown"], "the same section, not hidden and with its needs met, is linked"
    assert _evr["tail"].endswith('<details id="evrows-7">T</details></section>') and "<details" not in _c, \
        "evCard's second argument is drawn inside the card, last"
    assert "evlinks" not in _evr["l_none"], "no link at all draws no evidence line"
    assert "chose no action" in _evr["noact"] and "no usual for this hour yet" in _evr["noact"] \
        and "no outside reading" in _evr["noact"] and "no line" in _evr["noact"], "absence is said four ways"

    # DECIDE DRAWS EVENTS (SPEC_dashboard_events §4.2, §5). These are source checks; the booted run further down
    # renders the section itself. Its render calls evCard and reads uncovered_asks. "Decide about this" is drawn
    # only by card(), which render reaches in the rules/old/error branch AND, on events and shadow nodes, for each
    # issue whose open alerts no event covers.
    _dec = _js_raw[_js_raw.index("id: 'decide', pack"):]
    _dec = _dec[:_dec.index("notes() {")]
    _card = _js_raw[_js_raw.index("function card(ctx, key, d, a, did)"):_js_raw.index("window.PAI.register({\n  id: 'decide'")]
    assert "evCard(e, rowsOf(ctx, e))" in _dec and "uncovered_asks" in _dec, \
        "Decide's render must draw evCard and the alerts no event covers"
    assert "card(" in _dec.split("if (st === 'events' || st === 'shadow') {")[1].split("\n    }\n")[0], \
        "the alerts no event covers are drawn with card()"
    assert _dec.count("Decide about this") == 0 and "Decide about this" in _card, \
        "'Decide about this' belongs to card(), the fallback, and not to the event branch"
    assert 'id="decide-none"' in _dec and 'id="decide-engine"' in _dec and "data-ref=\"stage-decide\"" in _dec
    assert "window.K.didButton(a.id)" in _card, "an alert answered on Decide has the I did this button"
    # The click handler matches `.ask .go` and `.ask form.did .cancel`, finds the form as the button's sibling, and
    # the styles are scoped under `.ask`; so the button must sit in an element with class ask, beside its form.
    assert "closest('.ask .go')" in _js_raw and "closest('.ask form.did .cancel')" in _js_raw \
        and "go.parentElement.querySelector('form.did')" in _js_raw, "the I did this handlers moved: update this check"
    assert re.search(r'<div class="ask">\$\{window\.K\.didButton\(a\.id\)\}</div>', _card), \
        "card() must wrap didButton in an element with class ask, or the button opens nothing and is unstyled"
    assert re.search(r'const didButton = id =>\s*`<button type="button" class="go" .*?<form class="did"', _js_raw, re.S), \
        "didButton is a .go button with a form.did, the pair the handler reads"
    assert 'id="evrows-' in _js_raw and "older than the 200 alerts this page reads" in _js_raw, \
        "evCard links to #evrows-<id>, so rowsOf must draw it"

    # "I did this" and "Record the decision" print what the node said when it refused, word for
    # word. It printed "The node refused it (409)" over a node that had written, in full, what to
    # do first (DECISION_REQUIRED) — the one sentence the person at the screen needed.
    _did = "\n".join((
        re.search(r"async function nodeSaid\(r\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"async function didThis\(form\) \{.*?\n\}", _js_raw, re.S).group(0),
    ))
    _409 = ("this node is set to DECISION_REQUIRED, so an act needs a decision recorded against the same "
            "alert first. Decide on the dashboard, then record what you did.")
    _cases = {
        "409": [409, {"detail": _409}],
        "400": [400, {"detail": "stage must be acknowledged, acted or decided"}],
        "401": [401, {"detail": "closing a loop from off this machine needs Authorization: Bearer <ACT_TOKEN>"}],
        "403": [403, {"error": "this node is not sharing"}],
        "500": [500, None],
        "422": [422, {"detail": [{"msg": "field required"}]}],
    }
    _t = _node(_did + "\nconst C = " + json.dumps(_cases) + r""";
const auth_ = () => ({}); let said = null; const say = (m, bad) => { said = [m, !!bad]; };
const refresh = async () => {};
const form = { querySelector: () => ({ disabled: false }), getAttribute: () => '7',
  classList: { contains: () => false }, elements: { note: { value: 'shut it' }, actor: { value: 'a' } },
  hidden: false, reset() {} };
(async () => {
  const out = {};
  for (const [k, [status, body]] of Object.entries(C)) {
    globalThis.fetch = async () => ({ status, ok: status < 300,
      json: async () => { if (body === null) throw new Error('no body'); return body; } });
    said = null; await didThis(form); out[k] = said;
  }
  console.log(JSON.stringify(out));
})();""")
    assert _t["409"] == [_409, True], f"a 409 must print the node's own sentence and nothing else: {_t['409']}"
    assert _t["400"] == ["stage must be acknowledged, acted or decided", True], f"so must a 400: {_t['400']}"
    assert _t["401"][0].startswith("closing a loop from off this machine") and "planetai ui" in _t["401"][0], \
        f"a 401 carries its sentence in `detail`, and the page adds where the token comes from: {_t['401']}"
    assert _t["403"][0].startswith("this node is not sharing"), f"the middleware's 403 is `error`: {_t['403']}"
    assert _t["500"] == ["The node refused it (500).", True], f"no body, no invented sentence: {_t['500']}"
    assert _t["422"][0] == "field required (422)", f"a schema refusal's messages, joined: {_t['422']}"

    # Pressing Done, Not now or Doesn't fit on an alert event posts the EVENT id (a number), the stage,
    # the name and the note; a post the node takes stores the name, and a refusal prints the node's own
    # sentence. The click and submit handlers are browser-only; Task 11's live proof presses them.
    _ans_m = re.search(r"async function answerEvent\(id, stage, actor, note\) \{.*?\n\}", _js_raw, re.S)
    assert _ans_m, "the page no longer defines answerEvent(id, stage, actor, note) at column 0"
    _ans = "\n".join((re.search(r"async function nodeSaid\(r\) \{.*?\n\}", _js_raw, re.S).group(0), _ans_m.group(0)))
    _ans_cases = {
        "200": [200, None], "404": [404, {"detail": "no such event"}],
        "401": [401, {"detail": "closing a loop from off this machine needs Authorization: Bearer <ACT_TOKEN>"}],
        "400": [400, {"detail": "stage must be acknowledged, acted or dismissed"}],
    }
    _a = _node(_ans + "\nconst C = " + json.dumps(_ans_cases) + r""";
const auth_ = () => ({}); let said = null, refreshed = 0, stored = null, posted = null;
const say = (m, bad) => { said = [m, !!bad]; };
const refresh = async () => { refreshed++; };
const localStorage = { getItem: () => null, setItem: (k, v) => { stored = [k, v]; } };
(async () => {
  const out = {};
  for (const [k, [status, body]] of Object.entries(C)) {
    globalThis.fetch = async (url, opts) => { posted = [url, JSON.parse(opts.body)];
      return { status, ok: status < 300, json: async () => { if (body === null) throw new Error('no body'); return body; } }; };
    said = null; stored = null; refreshed = 0;
    const ok = await answerEvent('7', 'acknowledged', 'ana', undefined);
    out[k] = { ok, said, stored, refreshed, posted };
  }
  for (const [stage, key] of [['acted', 'acted'], ['dismissed', 'dismissed']]) {
    globalThis.fetch = async () => ({ status: 200, ok: true, json: async () => ({}) });
    said = null; await answerEvent(7, stage, 'ana', 'did it by hand'); out[key] = said;
  }
  console.log(JSON.stringify(out));
})();""")
    assert _a["200"]["posted"] == ["/actions", {"event_id": 7, "stage": "acknowledged", "actor": "ana", "note": ""}], \
        f"the body is the event id as a number, not a string: {_a['200']['posted']}"
    assert _a["200"]["ok"] is True and _a["200"]["stored"] == ["planetai_actor", "ana"] \
        and _a["200"]["refreshed"] == 1, f"a 200 stores the name and refreshes: {_a['200']}"
    assert _a["200"]["said"] == ["Not now. The node holds this for three hours, unless it reaches danger.", False]
    assert _a["acted"] == ["Recorded.", False] and _a["dismissed"] == ["Noted: it doesn’t fit.", False]
    assert _a["404"]["said"] == ["This node has no such event any more. Reload and look again.", True] \
        and _a["404"]["stored"] is None and _a["404"]["ok"] is False, f"a 404: {_a['404']}"
    assert _a["401"]["said"][0].startswith("closing a loop from off this machine") \
        and "planetai ui" in _a["401"]["said"][0] and _a["401"]["refreshed"] == 0, f"a 401: {_a['401']}"
    assert _a["400"]["said"] == ["stage must be acknowledged, acted or dismissed", True] \
        and _a["400"]["stored"] is None, f"a 400 prints the node's sentence: {_a['400']}"

# Set up writes only what somebody changed, and never over a key that moved while it was open.
#
# Node #1, 26 September 2026: AGENT_PREFER was set to `private` over PUT /settings at 18:07. Two saves of
# the agent group from a form drawn before that, made to change AGENT_REMOTE_URL, wrote every field in
# the group back, AGENT_PREFER's stale `strongest` with them, and the ask pane sent a question online.
# This runs the page's own saveSettings() against that morning, with the node's describe() shape.
_setup_fns = [re.search(p, _js_raw, re.S) for p in (
    r"function formValues\(\) \{.*?\n\}", r"function movedSince\(before, after, keys\) \{.*?\n\}",
    r"async function saveSettings\(\) \{.*?\n\}", r"async function loadSetup\(\) \{.*?\n\}")]
assert all(_setup_fns), "Set up no longer defines formValues(), movedSince(), saveSettings() or loadSetup()"
assert "LOADED = formValues();" in _setup_fns[3].group(0), \
    "loadSetup() no longer records what the form was drawn with, so a save cannot tell an edit from a stale value"
if shutil.which("node"):
    _rows = lambda prefer, url="": {"unlocked": True, "runtime": [
        {"key": "AGENT_PREFER", "value": prefer, "set": True, "secret": False},
        {"key": "AGENT_REMOTE_URL", "value": url, "set": bool(url), "secret": False},
        {"key": "AGENT_ONLINE_KEY", "value": "•••• set", "set": True, "secret": True},
        {"key": "QUIET_HOURS", "value": "0", "set": False, "secret": False}]}
    _st = _node("\n".join(g.group(0) for g in _setup_fns[:3]) + "\nconst DRAWN = " + json.dumps(_rows("strongest"))
                + "\nconst NOW = " + json.dumps(_rows("private")) + r""";
const window = { K: { age: m => Math.round(m) + ' min ago' } };
const localStorage = { getItem: () => 'tok' };
let GROUP = 'agent', DESC = DRAWN, LOADED = {}, DIRTY = false, puts = [], said = [], boxes = {};
const f = (key, value, extra = {}) => ({ dataset: { key }, type: 'text', value, classList: { contains: () => false }, ...extra });
let F = [];
const qa = sel => sel === '[data-key]' ? F : [];
const q = sel => sel.startsWith('#err-') ? (boxes[sel.slice(5)] = boxes[sel.slice(5)] || { hidden: true }) : null;
const toast = (m, bad) => said.push([m, !!bad]);
const lock = () => {}, route = () => {};
const loadSetup = () => {};
globalThis.fetch = async (url, o = {}) => {
  if (o.method === 'PUT') { puts.push(JSON.parse(o.body)); return { ok: true, status: 200, json: async () => ({}) }; }
  if (url.startsWith('/actions')) return { ok: true, json: async () => [
    { ts: new Date(Date.now() - 24 * 60000).toISOString(), stage: 'settings', actor: 'mcp', note: 'AGENT_PREFER' }] };
  return { ok: true, json: async () => NOW };
};
const draw = () => {
  F = [f('AGENT_PREFER', 'strongest'), f('AGENT_REMOTE_URL', ''), f('AGENT_ONLINE_KEY', '', { type: 'password' }),
       f('QUIET_HOURS', '', { dataset: { key: 'QUIET_HOURS', bool: '1' } })];
  DESC = DRAWN; LOADED = formValues(); puts = []; said = []; boxes = {};
};
const field = k => F.find(x => x.dataset.key === k);
(async () => {
  const out = {};
  draw(); field('AGENT_REMOTE_URL').value = 'http://laptop.local:11434/v1';
  await saveSettings(); out.incident = puts;
  draw(); await saveSettings(); out.untouched = { puts, said };
  draw(); field('AGENT_ONLINE_KEY').value = 'sk-new';
  await saveSettings(); out.secret = puts;
  draw(); field('AGENT_PREFER').value = 'fallback';
  await saveSettings(); out.clash = { puts: [...puts], box: boxes.AGENT_PREFER, said };
  await saveSettings(); out.again = puts;
  console.log(JSON.stringify(out));
})();""")
    assert _st["incident"] == [{"AGENT_REMOTE_URL": "http://laptop.local:11434/v1"}], \
        f"a save must send the one field that was edited, not the group's stale AGENT_PREFER with it: {_st['incident']}"
    assert _st["untouched"]["puts"] == [] and "Nothing to save" in _st["untouched"]["said"][0][0], \
        f"a save with nothing edited must write nothing, and say so: {_st['untouched']}"
    assert _st["secret"] == [{"AGENT_ONLINE_KEY": "sk-new"}], f"a typed secret is sent, and only it: {_st['secret']}"
    _box = _st["clash"].get("box") or {}
    assert _st["clash"]["puts"] == [] and not _box.get("hidden", True), \
        f"an edited key that moved on the node since the form was drawn must not be written over unseen: {_st['clash']}"
    assert '"private"' in _box["textContent"] and "mcp, 24 min ago" in _box["textContent"], \
        f"the page must say what the node holds now and who changed it, from the ledger: {_box}"
    assert _st["again"] == [{"AGENT_PREFER": "fallback"}], \
        f"a second press, once the keeper has been shown, writes the keeper's value and only it: {_st['again']}"

# The packs group sends its own fields, not only the switches.
#
# formValues() used to return PACKS_ENABLED from the pack switches and stop, so PACKS_ALLOW_CODE and every
# key a pack declares were drawn in the packs group and never sent: "Saved." with nothing written, then
# "Nothing to save" once saves diffed. PACKS_ENABLED has two controls there; the switches win only when
# somebody moved one, so a text field naming a pack that is not installed survives an unrelated save.
_pack_fn = re.search(r"function packSwitches\(\) \{.*?\n\}", _js_raw, re.S)
assert _pack_fn, "Set up no longer defines packSwitches()"
assert "DRAWN_PACKS = packSwitches();\n  LOADED = formValues();" in _setup_fns[3].group(0), \
    "loadSetup() must record what the pack switches read before it records the form, or a switch can never be told from the field"
if shutil.which("node"):
    _pk = _node(_pack_fn.group(0) + "\n" + "\n".join(g.group(0) for g in _setup_fns[:3]) + "\nconst DRAWN = "
                + json.dumps({"unlocked": True, "runtime": [
                    {"key": "PACKS_ENABLED", "value": "make,local", "set": True, "secret": False},
                    {"key": "PACKS_ALLOW_CODE", "value": "0", "set": False, "secret": False},
                    {"key": "MAKE_RADIUS_KM", "value": "10", "set": False, "secret": False, "pack": "make"}]}) + r""";
const window = { K: { age: m => Math.round(m) + ' min ago' } };
const localStorage = { getItem: () => 'tok' };
let GROUP = 'packs', DESC = DRAWN, LOADED = {}, DRAWN_PACKS = '', DIRTY = false, puts = [], said = [];
const cls = on => ({ on, contains(c) { return c === 'on' && this.on; } });
let F = [], S = [];
const qa = sel => sel === '[data-key]' ? F : sel === '[data-pack]' ? S : [];
const q = () => null;
const toast = (m, bad) => said.push([m, !!bad]);
const lock = () => {}, route = () => {};
const loadSetup = () => {};
globalThis.fetch = async (url, o = {}) => {
  if (o.method === 'PUT') { puts.push(JSON.parse(o.body)); return { ok: true, status: 200, json: async () => ({}) }; }
  if (url.startsWith('/actions')) return { ok: true, json: async () => [] };
  return { ok: true, json: async () => DRAWN };
};
// The node's two installed packs are make and earth; `local` is named in the field and not installed.
const draw = () => {
  S = [{ dataset: { pack: 'make' }, classList: cls(true) }, { dataset: { pack: 'earth' }, classList: cls(false) }];
  F = [{ dataset: { key: 'PACKS_ENABLED' }, type: 'text', value: 'make,local', classList: cls(false) },
       { dataset: { key: 'PACKS_ALLOW_CODE', bool: '1' }, classList: cls(false) },
       { dataset: { key: 'MAKE_RADIUS_KM' }, type: 'text', value: '10', classList: cls(false) }];
  DRAWN_PACKS = packSwitches(); LOADED = formValues(); puts = []; said = [];
};
const field = k => F.find(x => x.dataset.key === k);
(async () => {
  const out = {};
  draw(); field('PACKS_ALLOW_CODE').classList.on = true; await saveSettings(); out.code = puts;
  draw(); field('MAKE_RADIUS_KM').value = '25'; await saveSettings(); out.packkey = puts;
  draw(); field('PACKS_ENABLED').value = 'make'; await saveSettings(); out.text = puts;
  draw(); S[1].classList.on = true; await saveSettings(); out.switch = puts;
  draw(); await saveSettings(); out.untouched = { puts, said };
  console.log(JSON.stringify(out));
})();""")
    assert _pk["code"] == [{"PACKS_ALLOW_CODE": "1"}], \
        f"allowing code packs must write PACKS_ALLOW_CODE and nothing else, not the switches' PACKS_ENABLED: {_pk['code']}"
    assert _pk["packkey"] == [{"MAKE_RADIUS_KM": "25"}], f"a pack's own key must be sent when it is edited: {_pk['packkey']}"
    assert _pk["text"] == [{"PACKS_ENABLED": "make"}], \
        f"with the switches untouched, the PACKS_ENABLED field is what is sent: {_pk['text']}"
    assert _pk["switch"] == [{"PACKS_ENABLED": ""}], \
        f"a moved switch wins over the field, and every pack on is blank: {_pk['switch']}"
    assert _pk["untouched"]["puts"] == [] and "Nothing to save" in _pk["untouched"]["said"][0][0], \
        f"a packs save with nothing edited must write nothing: {_pk['untouched']}"

# Two bugs node #1 showed on 28 September 2026 at v0.75.7, both in how the page read the node's own lists.
#
# Act printed "asks did not render: Cannot read properties of undefined (reading 'replace')". Its ledger keeps
# four alerts from before packs named their rules (`indoor_pm25_high`, `inside_worse_ventilate`), and the section
# split every rule id as `pack/rule`, so the rule came out undefined and the whole stage went blank. Every split
# now goes through rulePack(), which returns '' for an id with no pack.
assert "const [pack, name] = rule.split('/')" not in _js, "Act is splitting rule ids as pack/rule again"
assert "String(r.rule_id).split('/')[0]" not in _js, "the effect rows name an old rule id as its own pack again"
assert "rulePack(rule)" in _js and "rulePack(r.rule_id)" in _js, "a rule id no longer goes through rulePack()"
# Each section is its own PAI_LOAD closure, so a helper defined in one is not defined in another: the first fix put
# rulePack beside name() and Act died of "rulePack is not defined". It lives on window.K, which every section reads.
assert "interp, rulePack, meterBar" in _js, "rulePack is not on window.K, where every section can reach it"
if shutil.which("node"):
    _rp = _node(re.search(r"const rulePack = id => \{.*?\};", _js).group(0)
                + "\nconsole.log(JSON.stringify(['heat/heat_stress_now', 'indoor_pm25_high', '_test/hello', '']"
                + ".map(rulePack)))")
    assert _rp == ["heat", "", "_test", ""], f"rulePack must return the pack, or '' when there is none: {_rp}"
#
# Network's "Index cells 10 of 20" counted /cells rows. A cell can carry several values (three packs feed
# Environmental|Bioregion on node #1), so 10 rows were 6 cells. "N of 20" is a count of cells.
assert "cellCount: new Set(cells.map(c => c.cell)).size" in _js, "facts() no longer counts distinct cells"
assert "interp(w.cellsN, { n: d.cellCount })" in _js and "{ n: d.cells.length }" not in _js, \
    "Network's N of 20 is counting /cells rows again"

# ACT IS THE RECORD OF WHAT WAS ASKED AND ANSWERED (SPEC_dashboard_events §4.3). The sections are closures, so the
# wiring is a source check and the pure helpers are lifted.
_asks = _js_raw[_js_raw.index("id: 'asks', pack"):]
_asks_render = _asks[:_asks.index("  wall(ctx) {")]
_asks_render = _asks_render[_asks_render.index("render(ctx) {"):]
assert re.search(r"[^\w.]ask\(", _asks_render) is None, "Act's render still draws the kit's alert strip"
assert "title: 'What was asked, and what was answered'" in _asks, "Act's title is the spec's, and its id stays `asks`"
assert "'This node sends alerts, not events.'" in _asks_render and "st === 'error' ? esc(E.error)" in _asks_render, \
    "a rules node keeps its per-rule rows under one line saying it sends alerts, not events; an error node says the node's own words"
_evrow = _asks_render[_asks_render.index("id: `ask-ev-${key}`"):_asks_render.index("}).join('');\n    };")]
assert "asks.ev${key}.action" not in _evrow and _evrow.count("num:") == 1 and "evAnswerText(e)" in _evrow, \
    "an event row's qty holds only the answer: qty does not wrap, and the action is a sentence"
assert "e.action.text" in _evrow.split("qty:")[0], "the action rides the row's wrapping `line`"
assert "whereToGo()" in _asks_render and "capacity()" in _asks_render, "whereToGo and capacity stay in Act"
assert "function ask(key, d, ref)" in _js_raw, "the kit's ask() stays: it is exported"
assert "api('/actions?events=1')" in _js_raw and "api('/actions')" not in _js_raw, \
    "boot() must read /actions?events=1, so the event answers' notes arrive"
assert "`ev${x.event_id}:${x.stage}`" in _js_raw, "ACT_NOTES gains a key for an event's answer"
_led = _js_raw[_js_raw.index("id: 'ledger', pack"):]
_led = _led[:_led.index("  notes() {")]
assert "evAnswers(" in _led, "the ledger lists the answers to events"
assert "events || {}).buttons" in _js_raw[_js_raw.index("function evWord"):][:300], \
    "the ledger's button words are the node's, from events.buttons"
if shutil.which("node"):
    _act = _node("\n".join((
        "const S = { issues: { events: { buttons: { done: 'Done', not_now: 'Not now', doesnt_fit: 'Doesn’t fit' } } } };",
        re.search(r"function evWord\(stage\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evLog\(E\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evAnswerText\(e\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evAnswers\(E\) \{.*?\n\}", _js_raw, re.S).group(0),
        r"""
const A = (stage, actor, ts) => ({ stage, actor, ts, held_until: null });
const e1 = { id: 1, opened_at: '2026-10-03T10:00:00Z', answer: A('acted', 'tomas', '2026-10-03T11:00:00Z'), cleared_after_min: 40.4 };
const e2 = { id: 2, opened_at: '2026-10-04T10:00:00Z', answer: A('acknowledged', 'ana', '2026-10-04T10:30:00Z') };
const e3 = { id: 3, opened_at: '2026-10-05T10:00:00Z', answer: null };
const e4 = { id: 4, opened_at: '2026-10-01T10:00:00Z', answer: A('dismissed', '', '2026-10-01T12:00:00Z') };
const E = { open: [e3, e2], recent: [e2, e1, e4] };
console.log(JSON.stringify({
  log: evLog(E).map(e => e.id),
  text: [e1, e2, e3, e4, { ...e1, cleared_after_min: undefined }].map(evAnswerText),
  answers: evAnswers(E).map(x => x.event.id),
  none: [evLog({}), evAnswers({})],
}));""")))
    assert _act["log"] == [3, 2, 1, 4], f"evLog: newest opened first, an id in both lists once: {_act['log']}"
    assert _act["text"] == ["Done · tomas · cleared 40 min after", "Not now", "no answer",
                            "Doesn’t fit", "Done · tomas"], \
        f"evAnswerText: the button's word; 'cleared N min after' only on a Done the node followed with a clear: {_act['text']}"
    assert _act["answers"] == [2, 1, 4], f"evAnswers: answered events only, newest answer first: {_act['answers']}"
    assert _act["none"] == [[], []], "no events block is an empty record, not a throw"

# SIMPLE MODE'S OPEN ROW (SPEC_dashboard_events §4.4). lead() is a closure, so the markup is a source check; the
# pick is lifted and run. The row's data-ref must be the id monument() draws for the lead's issue.
_lead = _js_raw[_js_raw.index("  function lead() {"):]
_lead = _lead[:_lead.index("\n  }\n")]
assert "evButtons(" in _lead and 'evrow' in _lead and "evPick(evs, hk)" in _lead, \
    "lead() must draw the open event's row with its buttons"
assert "asEv ? evRow(" in _lead and "askRow(askAt" in _lead, "rules/old/error and nothing-open keep askRow"
assert 'id="num-${esc(key)}"' in _js_raw[_js_raw.index("function monument("):_js_raw.index("function heroPix(")], \
    "evrow's data-ref=num-<hk> must exist: monument() ids the numeral num-<key>"
if shutil.which("node"):
    _an = _node("\n".join((
        "const esc = s => String(s), sign = (id, l) => `<svg class=\"sg\"/>`;",
        "let S = { issues: {}, health: { tz: 'Asia/Makassar' } };",
        re.search(r"function evClock\(iso\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evWord\(stage\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"function evAnswered\(e\) \{.*?\n\}", _js_raw, re.S).group(0),
        """const A = (stage, extra) => ({ answer: { stage, actor: 'tomas', ts: '2026-10-05T10:00:00Z', ...extra } });
const own = () => { S.issues = { events: { buttons: { done: 'Fet', not_now: 'Ara no', doesnt_fit: 'No encaixa' } } };
  return [A('acted'), A('acknowledged'), A('dismissed')].map(evAnswered); };
console.log(JSON.stringify({ none: evAnswered({ answer: null }), acted: evAnswered(A('acted')),
  held: evAnswered(A('acknowledged', { held_until: '2026-10-05T12:00:00Z' })), no: evAnswered(A('dismissed')),
  own: own() }));""")))
    assert _an["none"] == "" and "evdone" in _an["acted"] and "Done · tomas" in _an["acted"], _an
    assert "evheld" in _an["held"] and "Not now · tomas" in _an["held"] and "held until 20:00" in _an["held"], _an
    assert "Doesn’t fit · tomas" in _an["no"], _an
    # An answer reads as the button that wrote it, in the node's own words (events.buttons), as the buttons do.
    assert ["Fet · tomas" in _an["own"][0], "Ara no · tomas" in _an["own"][1], "No encaixa · tomas" in _an["own"][2]] \
        == [True] * 3, f"evAnswered must print the node's button labels: {_an['own']}"
assert "evAnswered(e) + (e.answer && e.answer.stage === 'acted' ? '' : evButtons(e))" in _lead, \
    "an acted event's row has no buttons; a held one keeps them beside its answer"
assert "shadow \\u2014 nothing was sent" in _lead, "a shadow node's row says so"
if shutil.which("node"):
    _pk = _node("\n".join((
        re.search(r"const evPick = .*?;\n", _js_raw).group(0),
        """const a = { id: 1, issue: 'air' }, b = { id: 2, issue: 'heat' };
console.log(JSON.stringify({ own: evPick([a, b], 'heat').id, first: evPick([a, b], 'noise').id,
  none: evPick([], 'air') === undefined }));""")))
    assert _pk == {"own": 2, "first": 1, "none": True}, f"evPick: the shown issue's event, else the first: {_pk}"

# THE PAGE LOADS. On 5 Oct the shell set `window.PAI.isHidden` at its top level, which runs before any PAI_LOAD
# function has made window.PAI, so every load threw and the page sat on "Asking the node…" for good. Every check
# above lifts pieces and passed. This loads the whole file the way a browser does (one script, a bare DOM), so a
# top-level statement that throws fails here whatever it is. The handlers it registers are then driven, and the
# Decide closure rendered, against that same load.
if shutil.which("node"):
    # The program is one function: node runs STDIN as a global script, where a `const` of its own would collide
    # with the kit's top-level `let`s the moment dashboard.js declares them.
    _boot = _node(r"""(() => {
const fs = require('fs'), vm = require('vm');
const L = {}, store = {}, posted = [];
globalThis.window = globalThis;
globalThis.localStorage = globalThis.sessionStorage = { getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } };
globalThis.location = { search: '', hash: '', pathname: '/', href: 'http://node/' };
globalThis.document = { addEventListener: (t, f) => (L[t] = L[t] || []).push(f),
  getElementById: () => null, querySelector: () => null, querySelectorAll: () => [] };
globalThis.addEventListener = () => {};
/* POSTs are recorded and never answered, so nothing after the post runs. */
globalThis.fetch = (u, o) => { if (o && o.body) posted.push(JSON.parse(o.body)); return new Promise(() => {}); };
const out = { boot: 'loaded' };
try { vm.runInThisContext(fs.readFileSync('app/static/dashboard.js', 'utf8'), { filename: 'dashboard.js' }); }
catch (e) { out.boot = String((e && e.message) || e); console.log(JSON.stringify(out)); process.exit(0); }

/* An event card's three buttons and its form, as the page draws them. */
const el = (props = {}) => ({ value: '', focused: false, focus() { focusedOn = this.name; }, ...props });
let focusedOn = null;
const f = { stage: el({ name: 'stage' }), actor: el({ name: 'actor' }), note: el({ name: 'note' }) };
const inst = { hidden: true };
const form = { hidden: true, elements: f, dataset: { ev: '11' }, classList: { contains: c => c === 'evform' },
  querySelector: q => (q === '.instead' ? inst : null) };
const card = { querySelector: q => (q === 'form.evform' ? form : null) };
const btn = stage => ({ id: '', getAttribute: a => (a === 'data-stage' ? stage : a === 'data-ev' ? '11' : null),
  closest: q => (q === '.evb' ? btn(stage) : q === '.ev, .evrow' ? card : null) });
const fire = (type, target) => { for (const h of L[type] || []) { try { h({ target, preventDefault() {} }); } catch {} } };
const press = stage => { const b = btn(stage); b.closest = q => (q === '.evb' ? b : q === '.ev, .evrow' ? card : null); fire('click', b); };
const submit = () => fire('submit', { closest: q => (q.includes('form.evform') ? form : null) });

press('dismissed');                         /* Doesn't fit, no name kept: the form opens on the name */
out.dismissFocus = focusedOn; out.dismissInst = inst.hidden;
f.actor.value = 'tomas'; f.note.value = 'opened the door';
form.hidden = true;                         /* Cancel */
press('acted');                             /* then Done */
out.doneFocus = focusedOn; out.doneInst = inst.hidden; out.doneNote = f.note.value;
f.note.value = 'left over'; submit();       /* a stale note in the field must not be sent with Done */
f.stage.value = 'dismissed'; f.note.value = 'opened the door'; submit();
out.posted = posted;

/* Decide, rendered. One card per issue for the alerts no event covers, and none for a covered one. */
vm.runInThisContext("LOC = 'en';");
window.KH = { H: {} };
const reg = [];
window.PAI = { register: s => reg.push(s), sections: [], has: () => true };
/* Some PAI_LOAD closures push others when they run (Act's holds Decide's), so this runs whichever holds Decide's
   registration until it has registered: the list grows as it is walked, the way init() walks it. */
const LOAD = vm.runInThisContext('PAI_LOAD');
for (let i = 0; i < LOAD.length && !reg.some(s => s.id === 'decide'); i++)
  if (LOAD[i].toString().includes("register({\n  id: 'decide', pack")) LOAD[i]();
const decide = reg.find(s => s.id === 'decide');
const ask = (id, text) => ({ id, text, says: { en: text }, age_minutes: 5, current: true });
const ISS = { heat: { name: { en: 'Heat' }, open_asks: [ask(361, 'hot'), ask(356, 'hotter')] },
  air: { name: { en: 'Air' }, open_asks: [ask(400, 'dusty')] } };
const render = events => { vm.runInThisContext(`S = ${JSON.stringify({ issues: { events }, health: {} })};`);
  return decide.render({ ISS, ORDER: ['heat', 'air'], S: { issues: { events }, health: {} }, LOC: 'en' }); };
out.unc = render({ engine: 'events', open: [], uncovered_asks: [361, 356] });
out.none = render({ engine: 'events', open: [], uncovered_asks: [] });
console.log(JSON.stringify(out));
process.exit(0);
})();""")
    assert _boot["boot"] == "loaded", f"dashboard.js throws while it loads, so the page never boots: {_boot['boot']}"
    assert _boot["dismissFocus"] == "actor" and _boot["dismissInst"] is False, _boot
    assert _boot["doneFocus"] == "actor" and _boot["doneInst"] is True and _boot["doneNote"] == "", \
        f"Done opens the form on the name, with Doesn't fit's note hidden and emptied: {_boot}"
    assert [(p["stage"], p["note"]) for p in _boot["posted"]] == [("acted", ""), ("dismissed", "opened the door")], \
        f"only Doesn't fit sends a note: {_boot['posted']}"
    assert _boot["unc"].count('id="decide-heat"') == 1 and 'id="decide-air"' not in _boot["unc"], \
        f"one Decide card per issue with an uncovered alert, none for a covered one: {_boot['unc']}"
    assert 'id="decide-none"' in _boot["none"] and "decide-heat" not in _boot["none"], _boot["none"]

# THE LEAD AND DECIDE AGREE. On events or shadow the lead counts and picks only the alerts no event covers, which
# is what Decide draws: counting all of open_asks said "2 alerts open · in Decide" over a Decide reading
# "Nothing open". lead() is a closure, so its lines are lifted and run.
if shutil.which("node"):
    _ld = _js_raw[_js_raw.index("  function lead() {"):]
    _lc = _ld[_ld.index("    const st = evState(), evs = evOpen()"):]
    _lc = _lc[:_lc.index("e0 = evs[0] || {};") + len("e0 = evs[0] || {};")]
    _la = re.search(r"    const askAt = .*?;\n", _ld).group(0)
    _lr = _node("\n".join((
        re.search(r"function evState\(\) \{.*?\n\}", _js_raw, re.S).group(0),
        re.search(r"const evOpen = .*?\n", _js_raw).group(0),
        "let S; const ORDER = ['heat', 'air'];",
        "const ISS = { heat: { open_asks: [{ id: 361 }] }, air: { open_asks: [{ id: 356 }, { id: 357 }] } };",
        "function lead(events, hk) { S = { issues: { events } }; const d = ISS[hk];",
        _lc, _la,
        "return { nAsk, asEv, askAt: askAt || null, picks: askAt ? asksOf(askAt)[0].id : null }; }",
        """console.log(JSON.stringify({
  covered: lead({ engine: 'events', open: [], uncovered_asks: [] }, 'heat'),
  oneLeft: lead({ engine: 'shadow', open: [], uncovered_asks: [357] }, 'heat'),
  rules: lead({ engine: 'rules' }, 'heat'),
  old: lead(undefined, 'heat'),
}));""")))
    assert _lr["covered"] == {"nAsk": 0, "asEv": False, "askAt": None, "picks": None}, \
        f"every alert covered and no event open: the lead says nothing open, as Decide does: {_lr['covered']}"
    assert _lr["oneLeft"] == {"nAsk": 1, "asEv": False, "askAt": "air", "picks": 357}, \
        f"the lead counts and picks only the uncovered alert: {_lr['oneLeft']}"
    assert _lr["rules"]["nAsk"] == 3 and _lr["rules"]["askAt"] == "heat" and _lr["old"]["nAsk"] == 3, \
        f"a rules or older node counts every open alert: {_lr}"

# THE FIGURES KIT (docs/SPEC_dashboard_figures.md §4). The drawing needs Plot and a DOM; the arithmetic of where a
# drawing starts, which hour a bucket is, and which hour a pointer is nearest does not, so it is run here.
if shutil.which("node"):
    _kit = [re.search(p, _js, re.S) for p in (
        r"const boxOf = \(vals, line, pad = 0\.12\) => \{.*?\n\};",
        r"const offsetOf = iso => \{.*?\n\};",
        r"const localOf = \(iso, ms = Date\.parse\(iso\)\) => \{.*?\n\};",
        r"function nearestIndex\(ts, t\) \{.*?\n\}")]
    assert all(_kit), "dashboard.js lost a figures-kit helper: " + str([bool(k) for k in _kit])
    _k = _node("\n".join(k.group(0) for k in _kit) + r"""
const t = Date.parse('2026-10-06T07:00:00+08:00');
console.log(JSON.stringify({
  air: boxOf([4, 5, 193, null, 6], 15), heat: boxOf([28.4, 35.6, null], 35), cold: boxOf([-2, 3], null),
  flat: boxOf([5, 5, 5], null), none: boxOf([null], null),
  off8: offsetOf('2026-10-06T07:00:00+08:00'), offZ: offsetOf('2026-10-06T07:00:00Z'), offN: offsetOf('2026-10-06T07:00:00-05:30'),
  hhmm: localOf('2026-10-06T07:00:00+08:00').hhmm, hour: localOf('2026-10-06T07:00:00+08:00').hour,
  day: localOf('2026-10-05T23:00:00+08:00').day, dayUtc: localOf('2026-10-05T23:00:00+08:00', t - 8 * 3600e3 + 3600e3).day,
  frac: localOf('2026-10-06T07:05:00.203633+08:00').hhmm, utc: localOf('2026-10-05T23:00:00+00:00').hhmm,
  bad: [localOf(null), localOf('not a time'), localOf(undefined)],
  near: nearestIndex([0, 10, 20, 30], 14), last: nearestIndex([0, 10, 20, 30], 99) }));""")
    assert _k["air"]["lo"] == 0 and _k["air"]["hi"] > 193, f"a concentration never draws a floor below zero: {_k['air']}"
    assert 27 < _k["heat"]["lo"] < 28.4 and _k["heat"]["hi"] > 35.6, f"heat keeps its own floor, not zero: {_k['heat']}"
    assert _k["cold"]["lo"] < -2, f"a quantity that goes negative may: {_k['cold']}"
    assert _k["flat"]["hi"] > _k["flat"]["lo"], f"a flat day still has a box: {_k['flat']}"
    assert _k["none"] is None
    assert (_k["off8"], _k["offZ"], _k["offN"]) == (480, 0, -330), _k
    assert (_k["hhmm"], _k["hour"]) == ("07:00", 7), "the node's hour, never the reader's"
    assert (_k["day"], _k["dayUtc"]) == ("2026-10-05", "2026-10-06"), _k
    assert (_k["frac"], _k["utc"]) == ("07:05", "23:00"), f"a time is read in its own offset, microseconds and all: {_k}"
    assert all(b == {"day": "—", "hour": None, "hhmm": "—"} for b in _k["bad"]), \
        f"a time that does not parse is a dash, never a throw: {_k['bad']}"
    assert (_k["near"], _k["last"]) == (1, 3), _k

# THE DAY FIGURE AND THE STRIPS, as cards (docs/SPEC_dashboard_figures.md §4.2, §4.3). Built for node #1's 6 October
# capture, with /issues/days computed by the engine from the same capture, in the page loaded the way the browser
# loads it. The draw functions need Plot and a DOM and are not run; everything a reader can read without them is.
if shutil.which("node"):
    import datetime as _dt
    from issues import engine as _engine, load as _load

    class _Set:
        def get(self, k, d=""):
            return d

        def num(self, k, d):
            return d

    class _Cur:
        def __init__(self, snap):
            self.snap, self.rows = snap, []

        def execute(self, sql, args=()):
            if "current_setting('TimeZone')" in sql:
                self.rows = [{"tz": "Asia/Makassar"}]
            elif "FROM readings_1h" in sql:
                self.rows = [dict(r, bucket=_dt.datetime.fromisoformat(r["bucket"])) for r in self.snap["readings_1h"]
                             if _dt.datetime.fromisoformat(r["bucket"]) >= args[0]]
            elif "FROM alert_events" in sql:
                self.rows = []
            else:
                raise LookupError(sql[:60])

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

    _snap = json.loads((ROOT / "app/issues/fixtures/node1-2026-10-06-events.json").read_text())
    _rep = _engine.replay(json.loads(json.dumps(_snap)), _Set(), _load())
    _days = _engine.days(_Cur(_snap), _Set(), _load(), 1, now=_dt.datetime.fromisoformat(_snap["as_of"]))
    _days3 = _engine.days(_Cur(_snap), _Set(), _load(), 3, now=_dt.datetime.fromisoformat(_snap["as_of"]))
    _over = sum(p["over"] for p in _days["issues"]["air"]["per_day"])
    _cards = _node(r"""(() => {
const fs = require('fs'), vm = require('vm');
globalThis.window = globalThis;
globalThis.localStorage = globalThis.sessionStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
globalThis.location = { search: '', hash: '', pathname: '/', href: 'http://node/' };
globalThis.document = { addEventListener: () => {}, getElementById: () => null, querySelector: () => null,
  querySelectorAll: () => [] };
globalThis.addEventListener = () => {};
globalThis.fetch = () => new Promise(() => {});
vm.runInThisContext(fs.readFileSync('app/static/dashboard.js', 'utf8'), { filename: 'dashboard.js' });
const I = """ + json.dumps(_rep, default=str) + r""", D = """ + json.dumps(_days, default=str) + r""", D3 = """ + json.dumps(_days3, default=str) + r""";
globalThis.__I = I;
vm.runInThisContext("S = { issues: __I }; ISS = S.issues.issues; DIST = S.issues.distances; LAB = S.issues.labels.en; LOC = 'en';");
const K = window.K;
const air = K.dayFigure('air', I.issues.air), heat = K.dayFigure('heat', I.issues.heat);
const st = K.strips('air', D), st3 = K.strips('air', D3), none = K.strips('air', null), coast = K.strips('coast', D);
console.log(JSON.stringify({
  airFloor: /floor 0<\/span>/.test(air), airNeg: /floor -/.test(air), heatNotZero: /, not zero<\/span>/.test(heat),
  airDay: air.includes('data-num="air.day"'), events: (air.match(/(One event|\d+ events) in these hours/) || [''])[0],
  region: air.includes('region — no model'), usual: (air.match(/no usual band — [^<]*/) || [''])[0],
  keys: air.includes('tabindex="0"'), over: (st.match(/>(\d+) hours over the line</) || [])[1],
  stripsNum: st.includes('data-num="air.days.over"'), none, coast,
  trimHead: (st3.match(/<p class="f-head"><span>([^<]*)<\/span>/) || [])[1] }));
})()""")
    assert _cards["airFloor"] and not _cards["airNeg"], "air draws from 0 and never below"
    assert _cards["heatNotZero"], "heat says its floor is not zero"
    assert _cards["airDay"] and _cards["keys"], "the day figure keeps air.day's comparison and can be read by keyboard"
    assert _cards["events"] == "2 events in these hours", _cards["events"]
    assert _cards["region"], "a distance with no source is named with its reason"
    assert _cards["usual"] == "no usual band — the usual could not be read", _cards["usual"]
    assert _cards["stripsNum"] and int(_cards["over"]) == _over, (_cards["over"], _over)
    assert "does not send its days yet" in _cards["none"], _cards["none"]
    assert "No hourly record of" in _cards["coast"], _cards["coast"]
    assert _cards["trimHead"] == "Air · house · 2 days, from Mon, 05 Oct, the first this node recorded", _cards["trimHead"]

# THE FOLD OF STOPPED STATIONS survives a row it cannot date. toISOString() throws a RangeError on an invalid date;
# one station with no last_heard took down the whole stations section. localOf now answers '—' for it, and the fold
# prints last_heard in its own offset, not the first issue's last bucket's (final review I1, M9).
if shutil.which("node"):
    _sf = _node("\n".join((
        re.search(r"const esc = s => .*?\[c\]\)\);", _js, re.S).group(0),
        re.search(r"const offsetOf = iso => \{.*?\n\};", _js, re.S).group(0),
        re.search(r"const localOf = \(iso, ms = Date\.parse\(iso\)\) => \{.*?\n\};", _js, re.S).group(0),
        re.search(r"function silentFold\(ctx\) \{.*?\n\}", _js, re.S).group(0),
        """const row = (id, lh) => ({ sensor_id: id, name: 'Station ' + id, km: 3.2, indoor: false, source: 'src', last_heard: lh });
const ctx = { S: { issues: { stations_silent: { read: true, within_days: 30 } } },
  H: { silent: [row('a', '2026-10-01T07:30:00+08:00'), row('b', null)] },
  ISS: { air: { buckets: ['2026-10-06T07:00:00+01:00'] } }, ORDER: ['air'] };
let html = '', err = null;
try { html = silentFold(ctx); } catch (e) { err = String(e); }
console.log(JSON.stringify({ html, err }));""")))
    assert _sf["err"] is None, f"silentFold threw on a row with no last_heard: {_sf['err']}"
    assert "not known" in _sf["html"] and "last heard 2026-10-01 07:30" in _sf["html"], _sf["html"]

# A NODE THAT CHANGES CLOCK (final review I1, docs/SPEC_dashboard_figures.md §3.4, §4.2). /issues/days steps its
# buckets in UTC and gives each one its own offset, and a label says the bucket's own hour. Europe/Madrid falls back
# at 03:00+02:00 on 25 October 2026; a page that read every bucket in the last one's +01:00 drew 00:00+02:00 as 23:00
# the day before, and 02:00+02:00 as 01:00. Plot is stubbed so the draw functions run: the cells they hand Plot and
# the readout they write are what is checked. The same page also holds Measure's count of hours over the line to its
# dashes, and a nulled hour of the day figure to "nothing recorded" (final review M1, M2, M6, M10).
if shutil.which("node"):
    _madrid = ["2026-10-24T23:00:00+02:00", "2026-10-25T00:00:00+02:00", "2026-10-25T01:00:00+02:00",
               "2026-10-25T02:00:00+02:00", "2026-10-25T02:00:00+01:00", "2026-10-25T03:00:00+01:00"]
    _over_src = re.search(r"function overRows\(ctx\) \{.*?\n\}", _js_raw, re.S).group(0)
    _dst = _node(r"""(() => {
const fs = require('fs'), vm = require('vm');
globalThis.window = globalThis;
globalThis.localStorage = globalThis.sessionStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
globalThis.location = { search: '', hash: '', pathname: '/', href: 'http://node/' };
const reads = {}, stub = () => ({ append() {}, style: {}, hidden: false });
globalThis.document = { addEventListener: () => {}, getElementById: id => (id.endsWith('-read') ? (reads[id] = reads[id] || { innerHTML: '' }) : null),
  querySelector: () => null, querySelectorAll: () => [], createElement: stub, documentElement: {} };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => '#000' });
globalThis.addEventListener = () => {};
globalThis.fetch = () => new Promise(() => {});
/* Plot, as far as the draw functions reach into it: every mark keeps its data, the drawing keeps its listeners. */
let svg;
globalThis.Plot = new Proxy({}, { get: (_, k) => (k === 'plot'
  ? o => (svg = { o, on: {}, value: null, addEventListener(t, f) { this.on[t] = f; },
    scale: () => ({ apply: () => 0, invert: () => 0 }), getBoundingClientRect: () => ({ left: 0, width: 1 }) })
  : (data, opts) => ({ mark: k, data, opts })) });
vm.runInThisContext(fs.readFileSync('app/static/dashboard.js', 'utf8'), { filename: 'dashboard.js' });
vm.runInThisContext(`S = { issues: { as_of: '2026-10-25T03:30:00+01:00', events: {} } };
ISS = { air: { name: { en: 'Air' }, dp: 0, unit: 'µg/m³' } }; DIST = ['room', 'yard', 'ring', 'region'];
LAB = { room: 'house', yard: 'street', ring: 'neighbours', region: 'region' }; LOC = 'en';`);
const K = window.K, FIGS = vm.runInThisContext('FIGS'), B = """ + json.dumps(_madrid) + r""";
const out = {};

/* The strips: each bucket in its own day and hour. */
const air = (line, perDay) => ({ days: 2, buckets: B, events: [], issues: { air: { distance: 'room', line,
  series: { room: [5, 6, 20, 7, 8, 9] }, per_day: perDay } } });
const D = air({ value: 15 }, [{ date: '2026-10-24', over: 0, read: 0, of: 1 }, { date: '2026-10-25', over: 1, read: 5, of: 5 }]);
out.card = K.strips('air', D);
FIGS.get('strips-air')(stub(), 720);
const marks = svg.o.marks, cells = marks.filter(m => m.mark === 'cell').at(-1).data;
const at = iso => { const c = cells.find(x => x.t === Date.parse(iso)); return c ? [c.day, c.hour] : null; };
out.c0 = at('2026-10-25T00:00:00+02:00'); out.c2 = at('2026-10-25T02:00:00+02:00'); out.c2b = at('2026-10-25T02:00:00+01:00');
out.c23 = at('2026-10-24T23:00:00+02:00');
svg.value = cells.find(x => x.t === Date.parse('2026-10-25T00:00:00+02:00')); svg.on.input();
out.read = reads['strips-air-read'].innerHTML;
const col = marks.find(m => m.mark === 'text' && m.opts && m.opts.dx >= 22 && m.opts.dx <= 30).opts;
out.col = ['2026-10-24', '2026-10-25'].map(col.text);
out.noLine = K.strips('air', air(null, [{ date: '2026-10-25', over: null, read: 5, of: 5 }]));

/* The day figure: the hour a key lands on, in its own offset, and a nulled hour said as nothing recorded. */
const day = { name: { en: 'Air' }, unit: 'µg/m³', dp: 0, headline: 'room', line: { value: 15, source: 'WHO' },
  buckets: B, series: { room: [5, 6, null, 7, 8, 9] }, usual: null, usual_absent: 'unread' };
K.dayFigure('air', day);
const el = stub(); FIGS.get('day-fig-air')(el, 720);
const key = k => el.onkeydown({ key: k, preventDefault() {} });
key('ArrowLeft'); key('ArrowLeft'); key('ArrowLeft'); key('ArrowLeft');
out.dayGap = reads['day-fig-air-read'].innerHTML;
key('ArrowLeft');
out.dayMidnight = reads['day-fig-air-read'].innerHTML;

/* Measure's hours over the line: a dash for a day nothing was read, and for a "today" that is not the node's today. */
window.overRows = vm.runInThisContext('(' + """ + json.dumps(_over_src) + r""" + ')');
const ctx = asOf => ({ ORDER: ['air'], ISS, LAB: { room: 'house' }, S: { issues: { as_of: asOf } } });
const days = (line, last) => ({ days: 2, buckets: B, issues: { air: { distance: 'room', line,
  per_day: [{ date: '2026-10-24', over: 0, read: 1, of: 1 }, last] } } });
window.DAYS = days({ value: 15 }, { date: '2026-10-25', over: 0, read: 0, of: 5 });
out.read0 = overRows(ctx('2026-10-25T03:30:00+01:00'));
window.DAYS = days({ value: 15 }, { date: '2026-10-25', over: 1, read: 5, of: 5 });
out.today = overRows(ctx('2026-10-25T03:30:00+01:00'));
out.stale = overRows(ctx('2026-10-25T23:30:00+00:00'));
window.DAYS = days(null, { date: '2026-10-25', over: null, read: 5, of: 5 });
out.noneLine = overRows(ctx('2026-10-25T03:30:00+01:00'));
console.log(JSON.stringify(out));
})()""")
    assert _dst["c0"] == ["2026-10-25", 0], f"00:00+02:00 is midnight on the 25th, not 23:00 the day before: {_dst['c0']}"
    assert _dst["c2"] == ["2026-10-25", 2] and _dst["c2b"] == ["2026-10-25", 2], \
        f"both 02:00s are 02:00, in their own offsets: {_dst['c2']} {_dst['c2b']}"
    assert _dst["c23"] == ["2026-10-24", 23], _dst["c23"]
    assert "<b>Sun, 25 Oct 00:00</b>" in _dst["read"], f"the strips' readout names the bucket's own hour: {_dst['read']}"
    assert _dst["col"] == ["—", "1 h over"], f"a day nothing was read is a dash, never a clean dot: {_dst['col']}"
    assert 'data-num="air.days.over"' in _dst["card"]
    assert 'data-num="air.days.over"' not in _dst["noLine"] and "over the line" not in _dst["noLine"] \
        and "5 hours read" in _dst["noLine"], f"an issue with no line counts no hours over it: {_dst['noLine']}"
    assert "<b>00:00</b>" in _dst["dayMidnight"], f"the day figure's hour is the bucket's own: {_dst['dayMidnight']}"
    assert "<b>01:00</b>" in _dst["dayGap"] and "house nothing recorded" in _dst["dayGap"] \
        and 'class="f-d f-room f-gone"' in _dst["dayGap"], f"a nulled hour is nothing recorded: {_dst['dayGap']}"
    assert 'data-num="air.over.today"' not in _dst["read0"] and _dst["read0"].count('<span class="none">—</span>') == 1, \
        f"a day nothing was read prints a dash, not 0 h: {_dst['read0']}"
    assert 'data-num="air.over.today"' in _dst["today"] and ">1 h<" in _dst["today"], _dst["today"]
    assert 'data-num="air.over.today"' not in _dst["stale"] and 'data-num="air.over.days"' in _dst["stale"], \
        f"after the node's midnight, the last counted day is not today: {_dst['stale']}"
    assert "No issue here has a line" in _dst["noneLine"], _dst["noneLine"]

print("test_dashboard: the engine's fence holds at three stations, the page has none of its own, "
      "a hole in a series is a hole in the line, the page is three files carrying one contract and "
      "ten sections, and a refused page says so on the wall and in the nav")
