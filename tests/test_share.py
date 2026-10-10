"""SHARE_LEVEL, and the two leaks it closes. No network, no database.

The static half reads app/main.py and asserts on it, the shape test_shipped.py uses — because the thing that recurs
here is structural. `SELECT *` in /sensors published every column added to the table on the day it landed (A7), so a
test that only checked today's redaction would pass the day someone adds `sensors.wifi_ssid`.

The request half drives FastAPI's TestClient with the database stubbed out. TestClient's peer address is
"testclient", which is not loopback, so by default every request here is exactly the case that matters: a stranger
on the house WiFi. Loopback is asked for explicitly where it is the subject.

Run: PYTHONPATH=app python3 tests/test_share.py
"""
import ast
import os
import re

SRC = open("app/main.py").read()
SETTINGS = open("app/settings.py").read()
ENV = open(".env.example").read()
# The page is three files since the renderer landed: a skeleton, a script and a
# stylesheet. "the GUI" means all of them, or an assertion passes by looking in the
# wrong one.
GUI = "".join(open("app/static/" + f).read()
                for f in ("index.html", "dashboard.js", "dashboard.css"))

# ---------------------------------------------------------------- the structural half
tree = ast.parse(SRC)
funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

# A7 · the star is the bug, not just the meta filter. Name the columns and a new one stays private until it is named.
# The docstring is stripped first: it explains why the star is gone, and naming it there must not read as using it.
def code_of(name):
    fn = funcs[name]
    stmts = fn.body[1:] if ast.get_docstring(fn) else fn.body
    return "\n".join(ast.get_source_segment(SRC, st) for st in stmts)
body = code_of("sensors_")
assert "SELECT *" not in body, "/sensors is back on SELECT *: every column added to `sensors` now publishes itself"
assert "FROM sensors" in body and "sensor_id" in body, "/sensors must name its columns"
for k in ("host", "firmware", "mesh_node", "gateway", "channel", "root_topic", "topic"):
    assert f'"{k}"' not in body, f"/sensors names {k} — the allowlist is what to keep, not a denylist of what to drop"
print("sensors: columns named, not SELECT *")

# F11 · every numeric query parameter in every route carries bounds. This walk found exactly one that did not.
unguarded = []
for node in ast.walk(tree):
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    if not any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") in ("get", "post", "put") for d in node.decorator_list):
        continue
    args = node.args.args[len(node.args.args) - len(node.args.defaults):]
    for a, d in zip(args, node.args.defaults):
        if getattr(a.annotation, "id", "") not in ("int", "float"):
            continue
        kw = {k.arg for k in d.keywords} if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "Query" else set()
        if not {"ge", "le"} <= kw:
            unguarded.append(f"{node.name}({a.arg})")
assert not unguarded, f"numeric route parameters with no ge=/le= bounds: {unguarded}"
print("routes: every numeric parameter is bounded")

# A12, then R25 · /health and /export hand an untrusted reader the centre of the res-8 cell, never a point.
assert "**_published_position(" in SRC, "/health must take its position from _published_position"
assert "_pos = _published_position()" in SRC, "/export must publish the cell's centre, not a point"
assert '"node": NODE' in SRC, "/health keeps the node name: /export publishes it by design and the dashboard prints it in five places"

# The two paths that are on no allowlist at any level, and the one the middleware must not decide twice.
mw = ast.get_source_segment(SRC, funcs["_share_level"])
allow = SRC[SRC.index("_SHARE_OFF = ("):SRC.index("_SHARE = {")]
for p in ("place/geojson", "settings/raw", "backups", "actions", "aggregates", "test-alert"):
    assert f'"/{p}"' not in allow, f"/{p} is on a SHARE_LEVEL allowlist and must never be"
assert 'startswith("/mcp")' in mw, "the middleware must pass /mcp through: _mcp_auth has already decided it"
assert "_bearer_ok" in mw, "the middleware must reuse _bearer_ok, which is constant-time"
assert "headers" not in code_of("_is_local"), \
    "_is_local reads a header: X-Forwarded-For would make the loopback bypass a one-line spoof. Use request.client only."
print("allowlists: the plan, the raw settings and every write are off them")

# The node calls its own API over the published port — update.sh's doctor, backup.sh's export, the CLI. Those
# arrive at the container as the Docker bridge gateway, not loopback, so SHARE_LEVEL judges them like any LAN
# client. Every such call must therefore either hit a path on the `off` allowlist or carry a token. v0.43 shipped
# without this check and update.sh's doctor reported two failures on a healthy node (found on bayu-ungasan).
_off_paths = set(re.findall(r'"(/[a-z0-9/._-]*)"', SRC[SRC.index("_SHARE_OFF = ("):SRC.index("_SHARE_OPEN = (")]))
_selfcalls = []
for f in ("update.sh", "backup.sh", "install.sh", "bin/planetai"):
    text = open(f).read()
    for i, line in enumerate(text.splitlines(), 1):
        # A literal path, or a variable one ($1 in a helper) — an unknown path is the dangerous case, because a
        # helper is reused: bin/planetai's api() reaches six endpoints through one curl and one $1.
        for path in re.findall(r'curl[^|;]*?localhost:[^/\s"]+(/[a-z0-9/._-]+|\$\{?\w+)', line):
            if path in _off_paths or "Authorization" in line:
                continue
            # the header may reach curl through a variable ($AUTH, $t, $tok): accept any name this file
            # assigns an Authorization header to, so the check follows the fix and not its spelling.
            names = set(re.findall(r'\$\{?(\w+)', line))
            if any(re.search(rf'^\s*(?:local\s+)?{n}=.*Authorization', text, re.M) for n in names):
                continue
            _selfcalls.append(f"{f}:{i} {path}")
assert not _selfcalls, ("these call the node's own API on a path SHARE_LEVEL=off refuses, with no token — they "
                        f"will fail on a default node: {_selfcalls}")
print("self-calls: every one is on the off allowlist or carries a token")

# A status line that reads .env reports what someone typed once, not what is in force: the database overlays
# .env for every key in settings.RUNTIME, and the dashboard writes to the database. `planetai ui` announced
# "SHARE_LEVEL is off, a screen gets no readings" to a household whose wall was drawing at `open`.
_cli = open("bin/planetai").read()
# A secret may be read from .env and only from .env: GET /settings masks it at every level, so the API
# cannot answer with one. Everything else in RUNTIME must come from the node, because the database overlays
# .env and the dashboard writes to the database — .env then holds what someone typed once, not what is in
# force. `planetai ui` announced "SHARE_LEVEL is off, a screen gets no readings" to a household whose wall
# was drawing at `open` (11 Sep 2026), because it asked .env.
_secret = set(re.findall(r'^\s*"([A-Z_]+)":\s*\([^)]*?,\s*True,\s*(?:True|False),', SETTINGS, re.M | re.S))
_runtime = set(re.findall(r'^\s*"([A-Z_]+)":\s*\(', SETTINGS, re.M))
assert "SHARE_LEVEL" in _runtime and "TELEGRAM_BOT_TOKEN" in _secret, "the settings.py parse above went stale"
_stale = [f"bin/planetai:{i} {k}" for i, line in enumerate(_cli.splitlines(), 1)
          for k in re.findall(r'envget (\w+)', line) if k in _runtime - _secret]
assert not _stale, ("these read a non-secret runtime setting from .env, which the database overlays, so they "
                    f"report or act on a value the node may not be using — use setting(): {_stale}")
assert "setting() {" in _cli, "bin/planetai needs the setting() helper that reads the effective value"
print("status lines: runtime settings are reported as the node has them, not as .env has them")

# The setting itself, and the reserved names that are refused rather than silently accepted.
assert '"SHARE_LEVEL"' in SETTINGS and '"ACT_TOKEN"' in SETTINGS, "settings.py: both new keys"
assert '"SHARE_LEVEL":   ("off", "open")' in SETTINGS, "settings.py: SHARE_LEVEL must refuse anything but off and open"
assert '"SHARE_LEVEL"}' in SETTINGS or '"SHARE_LEVEL",' in SETTINGS, "settings.py: SHARE_LEVEL must be PUBLIC"
for word in ("cell", "means"):
    assert word in SETTINGS.split('"SHARE_LEVEL":        (')[1][:1200], f"settings.py: {word} must be named in SHARE_LEVEL's help as reserved"
assert re.search(r"^SHARE_LEVEL=off", ENV, re.M) and re.search(r"^ACT_TOKEN=", ENV, re.M), ".env.example: both new keys"
assert "planetai_act" in GUI and "acttok" in GUI, "the dashboard's Unlock panel needs the second token field"
# The renderer handles the refusal in snapshot() and says so in render() and in the plan card,
# rather than in one `e===403` inside a paint function as the single-file page did.
assert "403" in GUI, "the page must notice a refusal at all"
assert "needs a token" in GUI, "the plan card must say why it is empty rather than going blank"
assert "refused" in GUI, "a refused read must reach render() as a state, not as a blank page"
print("setting: declared, bounded, documented, and in the dashboard")

import settings as S
assert "cell" not in S.CHOICES["SHARE_LEVEL"] and "means" not in S.CHOICES["SHARE_LEVEL"]
try:
    S.set("SHARE_LEVEL", "cell"); raise AssertionError("SHARE_LEVEL=cell must be refused: it would do nothing")
except ValueError as e:
    assert "cell" in str(e), "the refusal must quote the help text, which says what cell will mean"
print("reserved levels refused")

# ---------------------------------------------------------------- the request half
try:
    from fastapi.testclient import TestClient
except ImportError:
    print("share: request checks skipped (pip install -r app/requirements.txt)")
    raise SystemExit(0)

import logging
import time
logging.disable(logging.WARNING)      # main.py logs a failed bootstrap connect on import; that is the point of the stub
os.environ.update(ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok", NODE_LAT="-8.6478291", NODE_LON="115.1385412",
                  NODE_NAME="bayu-2", DATABASE_URL="postgresql://unused/never-connected")
import settings                                    # noqa: F811 — the same module; the stub below is what matters
settings._cache = {"at": time.time() + 1e9, "rows": {}}     # never touch a database: get() falls through to the environment
import main

# One sensor row shaped like the AirGradient on the clean node: a hostname on the WiFi, a room name, 7 decimals.
ROW = {"sensor_id": "ag-84fce6", "source": "airgradient", "name": "Kitchen, upstairs", "lat": -8.6478291,
       "lon": 115.1385412, "indoor": True, "local": True, "custody": True, "kind": "sensor", "scale": "community", "cadence": "PT5M",
       "meta": {"host": "airgradient_84fce6.local", "model": "I-9PSL", "firmware": "3.1.9", "licence": "CC BY 4.0",
                "mesh_node": "!8f491db0", "gateway": "gw-1", "channel": "0", "root_topic": "msh", "topic": "msh/x"}}
main.q = lambda sql, *a: [dict(ROW, meta=dict(ROW["meta"]))] if "FROM sensors" in sql else []
main.db = lambda: (_ for _ in ()).throw(RuntimeError("no database in this test"))

def level(v):
    settings._cache["rows"]["SHARE_LEVEL"] = v

lan = TestClient(main.app)                                   # peer "testclient": a stranger on the WiFi
local = TestClient(main.app, client=("127.0.0.1", 51000))    # the machine the node runs on
ADMIN, ACT = {"Authorization": "Bearer admin-tok"}, {"Authorization": "Bearer act-tok"}

def dp(x):
    return len(str(float(x)).split(".")[1].rstrip("0"))

level("off")
assert lan.get("/sensors").status_code == 403, "off: an unauthenticated /sensors from the WiFi must be refused"
assert "SHARE_LEVEL" in lan.get("/sensors").json()["error"], "the 403 must name the setting"
assert lan.get("/sensors", headers=ADMIN).status_code == 200, "off: the admin token still reads /sensors"
assert lan.get("/sensors", headers=ADMIN).json()[0]["meta"]["host"], "a token reads the unredacted row"
assert local.get("/sensors").status_code == 200, "off: this machine still reads everything"
assert lan.get("/health").status_code == 200 and lan.get("/").status_code == 200, "off: the shell stays readable"
assert lan.get("/export").status_code != 403, "off: backup.sh fetches /export over the published port to write the daily file"
print("off: /sensors refused from the WiFi, answered to a token and to this machine")

for lv in ("off", "open"):
    level(lv)
    h = lan.get("/health").json()
    assert dp(h["lat"]) <= 3 and dp(h["lon"]) <= 3, f"{lv}: /health hands out {h['lat']},{h['lon']}"
    # R25: the stranger on the WiFi gets the cell's centre, and is told so.
    assert h.get("position") == "cell", f"{lv}: an untrusted /health must say it carries the cell, got {h.get('position')!r}"
    assert (h["lat"], h["lon"]) == main._coarse(-8.6478291, 115.1385412), f"{lv}: /health is not the cell's centre"
    assert h.get("docs", "").startswith("https://planetai.fab.city/docs") and h.get("mcp") == "/mcp", \
        f"{lv}: /health must say where the documentation and the tools are"
    assert h["node"] == "bayu-2", f"{lv}: /health keeps the node name"
    assert lan.get("/place/geojson").status_code == 403, f"{lv}: the building's shape needs a token"
    assert lan.get("/settings/raw").status_code == 403, f"{lv}: the unmasked keys need a token"
    # The household's language, at every level, which is the whole reason it is on /health and not on
    # /issues. The dashboard read `snap.locale`, nothing ever set it, and the page pinned itself to
    # English on every node while the node sent every sentence in all three. At `off` /issues is
    # refused outright and /settings is reduced to two keys, so a refused page — the one screen a
    # household most needs in its own language — had nowhere else to read it from.
    assert h.get("locale") in ("en", "id", "es"), \
        f"{lv}: /health must carry the household's language, or the dashboard falls back to English: {h.get('locale')!r}"
print("every level: the cell's centre in /health, the household's language, the plan and the raw settings refused")

hl = local.get("/health").json()
assert hl.get("position") == "point" and (hl["lat"], hl["lon"]) == (-8.648, 115.139), \
    "this machine keeps three decimals: the household's own plan is drawn from it"
assert lan.get("/llms.txt").status_code == 200 and "distributed production" in lan.get("/llms.txt").text, \
    "/llms.txt answers at every level and says what the node is for"
print("this machine: three decimals; /llms.txt readable by anyone")

level("open")
r = lan.get("/sensors")
assert r.status_code == 200, "open: a wall screen with no token reads the sensors"
s0 = r.json()[0]
for k in ("host", "firmware", "mesh_node", "gateway", "channel", "root_topic", "topic"):
    assert k not in s0["meta"], f"open: /sensors still hands out meta.{k}"
assert s0["meta"]["licence"] == "CC BY 4.0", "open: provenance must survive the filter — it is what makes a reading citable"
assert dp(s0["lat"]) <= 3 and dp(s0["lon"]) <= 3, f"open: /sensors hands out {s0['lat']},{s0['lon']}"
assert (s0["lat"], s0["lon"]) == main._coarse(-8.6478291, 115.1385412), \
    "open: the household's own sensor must stand at its cell's centre for an untrusted reader (R25)"
assert s0["name"] == "Kitchen, upstairs", "open: the sensor's name is on the dashboard and stays"
print("open: sensors readable, hostnames and firmware gone, own sensors at their cell's centre")

# A FACILITY IS NOT A SENSOR, and the filter above was written about sensors. A fab lab is somebody
# else's building, published by name and coordinate in a public directory this node read; `host` and
# `firmware` are meaningless for it and `distance_km`, `capabilities` and the archive it came from
# are the whole of what makes it useful. Until 21 September the sensor list was applied to both, so
# a facility reached the page carrying `attribution` and nothing else — and the page runs in a
# browser on the LAN, so that was not a corner case, it was every reader. The dashboard could name a
# place and could not say how far away it was or what was in it.
FACILITY = {"sensor_id": "lab-fablabbali", "source": "fablabs-io", "name": "Fab Lab Bali",
            "lat": -8.793, "lon": 115.15, "indoor": False, "local": False, "kind": "facility",
            "scale": "community", "cadence": "P30D",
            "meta": {"slug": "fablabbali", "capabilities": ["laser", "cnc_milling"],
                     "distance_km": 3.3, "url": "https://www.fablabs.io/labs/fablabbali",
                     "snapshot": "2026.07.31_labs.json", "city": "Badung", "country_code": "ID",
                     "registry_slug": "economic/community/fablabs-io", "kind_name": "fab_lab",
                     "fetched": "2026-09-20T13:59:38+00:00",
                     "attribution": "fablabs.io — Fab Lab Network. Not openly licensed.",
                     # and one that is NOT a fact about the lab: it must still be cut.
                     "host": "should-never-be-published.local"}}
_sensors = main.q
main.q = lambda sql, *a: ([dict(FACILITY, meta=dict(FACILITY["meta"]))] if "FROM sensors" in sql
                          else _sensors(sql, *a))
f0 = lan.get("/sensors").json()[0]
for k in ("distance_km", "capabilities", "url", "snapshot", "city", "registry_slug", "attribution"):
    assert k in f0["meta"], f"open: a facility cannot say its own {k}, so the page cannot draw it"
assert f0["meta"]["distance_km"] == 3.3, "the distance is the one figure the ask needs"
assert "host" not in f0["meta"], \
    "the facility allowlist is not an amnesty: a key that describes a network is still cut"
main.q = _sensors
print("open: a facility publishes its own public facts, and still not a hostname")

# How far back this node's own record goes is not private: it is the length of the line the page
# already draws. It is on the open allowlist so a wall screen with no token can say that the
# satellite reaches ten years and the kit in this house reaches three weeks — which is the whole
# reason the readout exists.
_reach = [{"kind": "sensor", "oldest": "2026-09-01", "newest": "2026-09-21", "buckets": 32833,
           "sources": 21, "days": 20}]
_prev = main.q
main.q = lambda sql, *a: _reach if "FROM readings_1h" in sql else _prev(sql, *a)
_rr = lan.get("/reach")
assert _rr.status_code == 200, "open: a wall screen cannot ask how far back the record goes"
assert _rr.json()[0]["days"] == 20, f"/reach did not answer: {_rr.json()}"
main.q = _prev
level("off")
assert lan.get("/reach").status_code == 403, "off: /reach is not on the off allowlist and must refuse"
level("open")
print("open: /reach readable, and refused at off")

# F10 · closing a loop. The middleware refuses the anonymous case; the route refuses a read-only token.
level("open")
assert lan.post("/actions", json={"alert_id": 1, "stage": "acted"}).status_code == 403, "open: an anonymous action must be refused"
assert lan.post("/actions", json={"alert_id": 1, "stage": "bad"}, headers=ACT).status_code == 400, "open: ACT_TOKEN gets past the gate and reaches the route"
level("off")
_bad = local.post("/actions", json={"alert_id": 1, "stage": "bad"})
assert _bad.status_code == 400, "off: this machine records an action with no token"
# The dashboard prints this sentence as the node wrote it, so it must name every stage the route takes:
# it said "acknowledged or acted" for a release after `decided` was accepted.
assert _bad.json().get("detail") == "stage must be acknowledged, acted or decided", \
    f"the 400 names the stages POST /actions accepts: {_bad.json()}"
assert lan.post("/actions", json={"alert_id": 1, "stage": "acted"}).status_code == 403, "off: an action from the WiFi must be refused"
# Set up reads who last changed a key from the node's own `settings` rows. Plain GET /actions leaves them out.
_prev, _sql = main.q, []
main.q = lambda sql, *a: _sql.append((sql, a)) or []
assert lan.get("/actions?stage=settings", headers=ACT).status_code == 200
assert lan.get("/actions?stage=settings").status_code == 403, "off: who changed which setting is not for the WiFi"
lan.get("/actions", headers=ACT)
main.q = _prev
assert "stage = %s" in _sql[0][0] and _sql[0][1][0] == "settings", f"?stage=settings must read the settings rows: {_sql[0]}"
assert "alert_id IS NOT NULL" in _sql[1][0], f"a plain read must still leave the settings rows out: {_sql[1]}"
print("actions: open on this machine, ACT_TOKEN from anywhere else, ?stage=settings for Set up")

# The reduced settings read: the layout, because every screen in the house needs it, and the level, so a screen can say why.
level("off")
d = {r["key"]: r for r in lan.get("/settings").json()["runtime"]}
assert d["SHARE_LEVEL"]["value"] == "off", "off: a refused screen must be able to read what is refusing it"
assert d["UI_LAYOUT"]["value"] == "" or d["UI_LAYOUT"]["value"] is not None, "off: the layout read must keep working"
assert d["ALERT_LEVEL"]["value"] == "" or "••" in d["ALERT_LEVEL"]["value"], "off: everything else is masked"
assert d["TELEGRAM_BOT_TOKEN"]["value"] in ("", "•••• set"), "a secret is masked at every level"
level("open")
assert lan.get("/settings").json()["runtime"], "open: /settings still answers"
print("settings: at off, the layout and the level and nothing else")
# The 403 has to know whether its own advice is advice. /reach is refused at `off` and answered at `open`, so the
# setting is a real remedy; /version is on no allowlist at any level, so sending its reader to the Set up view is
# sending them to change a setting, come back, and read the same 403.
level("off")
_msg = lan.get("/reach").json()["error"]
assert "Set SHARE_LEVEL to open" in _msg, f"off: /reach is one `open` away and must say so: {_msg}"
level("open")
_msg = lan.get("/version").json()["error"]
assert "Set SHARE_LEVEL to open" not in _msg, f"open: /version must not advise the setting it already has: {_msg}"
assert "always needs a token" in _msg, f"open: /version must say a token is the only way in: {_msg}"
print("the refusal only offers the setting when the setting would answer")


# The derived `measured` stage is only honest while its window outlasts every act-level cooldown. A rule that waits
# longer than the window to re-fire would be counted as cleared while it was merely waiting its turn, turning "we have
# not looked yet" into "it worked" — the one lie this stage exists to avoid.
import yaml as _yaml, pathlib as _pl
import index as _index
_slow = []
for _f in [_pl.Path("config/rules.yml")] + sorted(_pl.Path("packs").glob("*/rules.yml")):
    try: _rules = _yaml.safe_load(_f.read_text()) or []
    except Exception as _e: raise AssertionError(f"{_f} does not parse, so its cooldowns cannot be checked: {_e}")
    for _r in _rules:
        if isinstance(_r, dict) and _r.get("level") == "act" and int(_r.get("cooldown_minutes", 60)) > _index.MEASURED_WINDOW_MIN:
            _slow.append(f"{_r.get('id')} ({_f.parent.name}) waits {_r.get('cooldown_minutes')}m")
assert not _slow, ("act-level rules slower than index.MEASURED_WINDOW_MIN="
                   f"{_index.MEASURED_WINDOW_MIN}m: {'; '.join(_slow)}. Raise the window to match, or the funnel will "
                   "call their alerts measured while they are still waiting to fire again.")
print(f"measured window {_index.MEASURED_WINDOW_MIN}m outlasts every act-level cooldown")

# The map ground's three vendored files and the doors' world coast are served by name, and nothing else under vendor/
# is: the allowlist is the whole of what /static answers, and a directory of libraries must not become one the LAN walks.
_vendor = {"maplibre-gl.js", "maplibre-gl.css", "deck.gl.min.js", "world-land-110m.json"}
for _n in sorted(_vendor):
    _r = lan.get(f"/static/{_n}")
    assert _r.status_code == 200 and len(_r.content) > 10000, f"/static/{_n} does not serve the vendored file"
_served = {k for k, (p, _t) in main.COMPANIONS.items() if p.parent.name == "vendor"}
assert _served == _vendor, f"/static serves vendored files nobody listed here: {sorted(_served - _vendor)}"
for _n in ("vendor/maplibre-gl.js", "maplibre-gl.LICENSE.txt", "deck.gl.LICENSE", "..%2Fmain.py"):
    assert lan.get(f"/static/{_n}").status_code == 404, f"/static/{_n} answered: the route takes a name, not a path"
print("static: the four vendored files are served, and nothing else under vendor/")

# The map workbench (GET /geo/*): the node computes every ring and distance the Place door draws, and none of it is
# on an allowlist, because the node's cell at a fine resolution and "metres from the node" give away its point.
for _lv in ("off", "open"):
    level(_lv)
    for _u in ("/geo/grid?bbox=115.13,-8.66,115.15,-8.64&res=8", "/geo/cell?lat=-8.65&lon=115.14&res=9",
               "/geo/measure?path=115.14,-8.65&from_node=true", "/geo/rings"):
        assert lan.get(_u).status_code == 403, f"{_u} answered a stranger at SHARE_LEVEL={_lv}: it locates the node"
level("off")
_g = local.get("/geo/grid?bbox=115.13,-8.66,115.15,-8.64&res=8").json()
_own = _g["node"][0]
assert _g["res"] == 8 and _g["may_leave"] is False and any(r[0] == _own for r in _g["cells_ll"]), _g
assert len(_g["cells_ll"][0]) == 1 + 12, "a cells_ll row is the id then six lat,lng pairs, as plates() publishes"
assert lan.get("/geo/grid?bbox=115.13,-8.66,115.15,-8.64&res=8", headers=ADMIN).status_code == 200, "a token reads it"
assert local.get("/geo/grid?bbox=100,-20,130,0&res=10").status_code == 422, "a covering past the cap is refused, not cut"
assert local.get("/geo/grid?bbox=115.15,-8.66,115.13,-8.64&res=8").status_code == 422, "west must be west of east"
_c = local.get(f"/geo/cell?id={_own}").json()
assert _c["is_node"] and _c["cells_from_node"] == 0 and _c["res"] == 8 and 600000 < _c["area_m2"] < 800000, _c
assert local.get("/geo/cell?id=not-a-cell").status_code == 422
_m = local.get("/geo/measure?path=115.14,-8.65;115.15,-8.65").json()
assert 1095 < _m["total_m"] < 1105 and _m["legs_m"] == [_m["total_m"]], _m      # 0.01 deg of longitude at 8.65 S
assert local.get("/geo/measure?path=115.1385412,-8.6478291&from_node=true").json()["total_m"] == 0
assert local.get("/geo/measure?path=115.14,-8.65").status_code == 422, "one point is not a path"
_r = local.get("/geo/rings?km=2,5").json()["rings"]
assert [x["km"] for x in _r] == [2, 5] and _r[0]["ring"][0] == _r[0]["ring"][-1], "rings come back closed"
assert local.get("/geo/rings?km=0").status_code == 422 and local.get("/geo/rings?km=1,2,3,4,5,6,7,8,9").status_code == 422
# The flow and the Node door: a cell's children, rings as distance and bearing, many distances in one answer, the planet.
_p6 = local.get("/geo/cell?lat=-8.6478291&lon=115.1385412&res=6&children=8&polar=true").json()
assert _p6["children_n"] == 49 and len(_p6["children_ll"]) == 49 and len(_p6["children_polar"]) == 49, _p6.keys()
assert len(_p6["ring_polar"]) == 1 + 12 and all(0 <= b < 360 for b in _p6["ring_polar"][2::2]), "polar rows are id then metres, bearing"
_r3 = local.get("/geo/cell?lat=-8.65&lon=115.14&res=3&children=8").json()
assert _r3["children_n"] == 7 ** 5 and "children_ll" not in _r3, "past 400 the count is given and the rings are not"
assert local.get("/geo/cell?lat=-8.65&lon=115.14&res=8&children=6").status_code == 422, "children are finer, not coarser"
_e = local.get("/geo/measure?from_node=true&each=true&path=115.1385412,-8.6378291;115.1485412,-8.6478291").json()["each"]
assert 1100 < _e[0]["m"] < 1120 and _e[0]["deg"] < 1, f"due north first: {_e[0]}"
assert 1090 < _e[1]["m"] < 1110 and abs(_e[1]["deg"] - 90) < 1, f"due east second: {_e[1]}"
assert len(local.get("/geo/planet?res=2").json()["cells_ll"]) == 5882 and local.get("/geo/planet?res=3").status_code == 422
assert lan.get("/geo/planet").status_code == 403
print("geo: grid, cell, measure and rings answer this machine and a token, refuse the LAN, and refuse bad boxes; children, polar, each and the planet too")

# The ground kept on disk (GET /ground/*): served from out/ground/ by name, private like /place/geojson.
import gzip as _gz, importlib.util as _iu, json as _json, sqlite3 as _sq, tempfile as _tf
from pathlib import Path as _P
_out = _P(_tf.mkdtemp()); main.OUT = _out; (_out / "ground" / "glyphs" / "Noto Sans Regular").mkdir(parents=True)
_db = _sq.connect(_out / "ground" / "vector.mbtiles")
_db.executescript("CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);")
_db.execute("INSERT INTO tiles VALUES (15, 26866, ?, ?)", ((1 << 15) - 1 - 17189, _gz.compress(b"mvt")))
_db.commit(); _db.close()
(_out / "ground" / "glyphs" / "Noto Sans Regular" / "0-255.pbf").write_bytes(b"glyphs")
(_out / "ground" / "meta.json").write_text(_json.dumps({"vector": {"tiles": 1}}))
for _lv in ("off", "open"):
    level(_lv)
    for _u in ("/ground/meta", "/ground/vector/15/26866/17189.pbf", "/ground/glyphs/Noto Sans Regular/0-255.pbf"):
        assert lan.get(_u).status_code == 403, f"{_u} answered a stranger at SHARE_LEVEL={_lv}: a tile pyramid locates the node"
level("off")
_t = local.get("/ground/vector/15/26866/17189.pbf")
assert _t.status_code == 200 and _t.content == b"mvt" and _t.headers["content-type"] == "application/x-protobuf", (_t.status_code, _t.headers)
assert local.get("/ground/vector/15/26866/17190.pbf").status_code == 204, "a tile the node does not hold is empty ground, not an error"
assert local.get("/ground/imagery/12/1/1.png").status_code == 204, "a layer never fetched is empty ground too"
assert local.get("/ground/elsewhere/1/1/1").status_code == 404 and local.get("/ground/vector/2/9/1.pbf").status_code == 204
assert local.get("/ground/glyphs/Noto Sans Regular/0-255.pbf").content == b"glyphs"
assert local.get("/ground/glyphs/..%2F..%2Fmeta/0-255.pbf").status_code == 404, "a font name is a name, not a path"
assert local.get("/ground/wind").status_code == 204, "no field until the forecast pack has written one"
(_out / "ground" / "wind.json").write_text(_json.dumps({"n": 8, "times": ["2026-10-07T06:00Z"]}))
assert local.get("/ground/wind").json()["n"] == 8 and lan.get("/ground/wind").status_code == 403
_m = local.get("/ground/meta").json()
assert _m["on_disk"]["wind"] and _m["fetch"]["wind"] == "planetai run forecast windfield"
assert _m["on_disk"]["vector"] and not _m["on_disk"]["imagery"] and _m["layers"]["vector"]["tiles"] == 1, _m
# The place pack reads Protomaps' archive by tile id: pmtiles' Hilbert order, and its directory encoding.
_s = _iu.spec_from_file_location("basemap", "packs/place/basemap.py"); _b = _iu.module_from_spec(_s); _s.loader.exec_module(_b)
assert [_b.zxy_to_id(1, *xy) for xy in [(0, 0), (0, 1), (1, 1), (1, 0)]] == [1, 2, 3, 4], "zoom 1 walks the Hilbert curve"
assert [_b.zxy_to_id(2, x, y) for x, y in [(0, 0), (1, 0), (1, 1), (0, 1), (0, 2)]] == [5, 6, 7, 8, 9]
def _v(n):
    out = b""
    while True:
        out += bytes([(n & 0x7F) | (0x80 if n > 0x7F else 0)]); n >>= 7
        if not n:
            return out
# two entries: tile 5 run 1 at offset 0 length 10; tile 6 run 2, offset 0 meaning "right after the previous"
assert _b.parse_dir(_v(2) + _v(5) + _v(1) + _v(1) + _v(2) + _v(10) + _v(20) + _v(1) + _v(0)) == [(5, 0, 10, 1), (6, 10, 20, 2)]
print("ground: tiles, fonts and meta answer this machine, refuse the LAN, read the archive by Hilbert id")

# GET /storage (the Set up page's Storage): what the machine holds is the keeper's, at every level.
for _lv in ("off", "open"):
    level(_lv)
    assert lan.get("/storage").status_code == 403, f"/storage answered a stranger at SHARE_LEVEL={_lv}"
    assert lan.get("/machine").status_code == 403, f"/machine answered a stranger at SHARE_LEVEL={_lv}"
level("off")
print("storage and machine: the keeper's, refused to the LAN at every level")

print("all share-level checks passed")
