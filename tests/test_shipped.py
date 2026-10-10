"""Every feature the CHANGELOG and docs claim must exist in the files. On 5 September two versions shipped with edit
blocks that failed silently: the loop landed, the compose service, settings, GUI tab, CLI command and .env keys did not,
and lint passed because nothing inconsistent was present. This test names each artifact a version promised."""
import datetime
import re
import yaml

compose = yaml.safe_load(open("docker-compose.yml"))
settings = open("app/settings.py").read()
cli = open("bin/planetai").read()
env = open(".env.example").read()
# The page is three files since the renderer landed: a skeleton, a script and a
# stylesheet. "the GUI" means all of them, or an assertion passes by looking in the
# wrong one.
gui = "".join(open("app/static/" + f).read()
                for f in ("index.html", "dashboard.js", "dashboard.css"))
main = open("app/main.py").read()

# v0.17 storage
assert "${DATA_DIR:-db}" in open("docker-compose.yml").read(), "compose: DATA_DIR volume var"
assert "ipfs" in compose["services"] and "ipfs" in compose["services"]["ipfs"].get("profiles", []), "compose: ipfs profile"
for k in ("BACKUP_KEEP", "BACKUP_REMOTE", "EXPORT_ENABLED", "IPFS_PUBLISH", "DATA_DIR"):
    assert re.search(rf"^{k}=", env, re.M), f".env.example: {k}"
assert "def export(" in main and "cmd_storage()" in cli and "cmd_ipfs()" in cli
# v0.18 NAS pull
assert "def list_backups" in main and "./backups:/app/backups:ro" in open("docker-compose.yml").read()
assert '"BACKUP_TOKEN"' in settings and "BACKUP_TOKEN" in open("update.sh").read()
# v0.20 agents
assert "_mcp_auth" in main and "def settings_raw" in main and "x_agent" in main
assert "JSON -eq 1" in cli and "--answers" in cli and "cmd_agent()" in cli
assert "sc-user" in open("install.sh").read()
# v0.21/22 local model and the ladder
assert "agent" in compose["services"] and compose["services"]["agent"]["command"][-1] == "agent_loop.py", "compose: agent service"
for k in ("AGENT_PREFER", "AGENT_REMOTE_URL", "AGENT_REMOTE_MODEL", "AGENT_REMOTE_KEY", "AGENT_ONLINE_URL", "AGENT_ONLINE_MODEL", "AGENT_ONLINE_KEY"):
    assert f'"{k}"' in settings, f"settings.py: {k}"
    assert re.search(rf"^{k}=", env, re.M), f".env.example: {k}"
assert re.search(r"^\s*model: \['", gui, re.M), "gui: a tab for the model group, where the AGENT_* keys are"
# v0.63: `local` dispatches to the setup OR to `pull`, which is the whole point of that release — the
# setup no longer fetches weights. Both halves must exist and `local)` must reach both.
assert "cmd_agent_local()" in cli and "cmd_agent_local_pull()" in cli
assert "local) if" in cli and "cmd_agent_local_pull" in cli and "else cmd_agent_local" in cli, \
    "`planetai agent local [pull]` no longer dispatches to both"
# cmd_agent_local_pull() is defined ABOVE cmd_agent_local(), so splitting on it reads the wrong half —
# which this assertion did until an injected `ollama pull` walked straight through it. Slice the setup
# function's own body and look in there.
_body = cli[cli.index("\ncmd_agent_local() {"):]
_body = _body[:_body.index("\n}\n")]
assert "ollama pull" not in _body, \
    "`planetai agent local` fetches a model again; the setup must download nothing"
assert "ollama pull" in cli, "`planetai agent local pull` must still be able to fetch one"
assert "def refresh_ladder" in open("app/agent_loop.py").read()
print("all shipped claims present")

# v0.32 — the LAN write that could wake the household. Every POST that writes raw data must check a token before touching
# the database. Found on the clean node: a curl from the WiFi created an indoor sensor at 999 µg/m³ and two act-level alerts.
def _handler(name):
    m = re.search(rf"^@app\.post\(\"/{name}\"\)\n(.*?)(?=^@app\.|\Z)", main, re.M | re.S)
    assert m, f"main.py: no POST /{name}"
    return m.group(1)
_body = _handler("readings")
assert "_admin(authorization)" in _body.split("with db()")[0], "POST /readings must check the admin token before it opens the database"
print("write endpoints gated")
# v0.32 — tokens are compared in constant time, by one helper. A `!=` on a token is the pattern to refuse.
assert "secrets.compare_digest" in main and "def _bearer_ok" in main, "main.py: token compares go through _bearer_ok"
assert not re.search(r'!= f"Bearer|not in tokens', main), "main.py: a token is still compared with != or `in`"
print("token compares constant-time")
# v0.32 — dumps leave the settings rows behind (the Telegram token lived there on node #1 and travelled to the NAS)
assert "--exclude-table-data=settings" in open("backup.sh").read(), "backup.sh: settings rows must stay out of dumps"
print("dumps carry no settings rows")
# v0.32 — pack SQL runs as a read-only role that cannot see settings
_sql = open("init.sql").read()
assert "CREATE ROLE planetai_ro" in _sql and "REVOKE ALL ON settings FROM planetai_ro" in _sql, "init.sql: read-only role for pack SQL"
assert "index.run_ro(cur, rule[\"sql\"])" in main, "main.py: rules run through run_ro"
assert "run_ro(cur, c[\"sql\"])" in open("app/index.py").read(), "index.py: cells run through run_ro"
print("pack SQL runs read-only")
# v0.32 — every container's log is capped; db, agent and ipfs were not, and the agent logs every tool call
for _svc, _def in compose["services"].items():
    assert _def.get("logging", {}).get("options", {}).get("max-size"), f"docker-compose.yml: service {_svc} has no log cap"
print("every container log is capped")
# v0.32 — `planetai packs` lists; only `planetai packs install` touches .env and the image
assert 'packs) shift; cmd_packs "$@"' in cli and "packs_install()" in cli and 'install" ]]; then packs_install' in cli, "CLI: packs vs packs install"
_list = cli[cli.index("cmd_packs() {"):cli.index("packs_install() {")]
assert "docker compose build" not in _list and ">> .env" not in _list, "planetai packs (the listing) must not build or write .env"
print("packs listing is read-only")
# v0.32 — envset escapes what sed would swallow (a CKAN list carries `|` and `&`), and the setup log is capped
assert "sed -e 's/[\\\\&|]/\\\\&/g'" in cli, "CLI: envset must escape \\ & | before the sed replacement"
assert "tail -c 200000" in cli, "CLI: .planetai-setup.log is trimmed"
print("envset escapes, setup log capped")
# v0.32 — a report or a test alert says `/act N` only when the bot that reads it is running; otherwise `planetai act N`
# v0.37 took the third caller: briefing()'s "Still waiting on you" list went with the briefings. What is left is
# the definition and the test alert, which is the one place a household is deliberately taught to close the loop.
assert "def act_hint" in main and main.count("act_hint(") >= 2, "main.py: the /act hint goes through act_hint()"
assert "→  /act {" not in main and "Reply /act with the number" not in main, "main.py: an unconditional /act instruction remains"
# v0.37 — an act alert says what to do and stops. No id to quote back, no button to press, nothing waiting on a
# household: the node watches what the sensors do next. The test alert is the exception, and teaches on purpose.
assert "#{alert_id}" not in main, "main.py: an act alert must not end in an id a household is expected to quote back"
assert "Still waiting on you" not in main, "main.py: the report does not nag"
print("act hints honest without a bot, and an act alert asks for nothing")
# v0.37 — one report every REPORT_EVERY hours, written by the node, and every surface that reaches it
assert '"REPORT_EVERY"' in settings and '"REPORT_ANCHOR"' in settings and '"REPORT_DEPTH"' in settings, "settings.py: the report keys"
for k in ("REPORT_EVERY", "REPORT_ANCHOR", "REPORT_DEPTH"):
    assert re.search(rf"^{k}=", env, re.M), f".env.example: {k}"
assert not re.search(r"^BRIEF", env, re.M), ".env.example: the briefing keys are retired"
assert "BRIEF_HOUR" not in open("docker-compose.yml").read(), "compose: the agent's own report hour is gone"
assert "def run_report" in main and "def briefing(" not in main and "def run_briefings(" not in main, "main.py: one scheduler"
assert "def report_latest" in main and "def report_bundle" in main and "def report_now" in main, "main.py: the report endpoints"
assert 'RedirectResponse("/report/latest", status_code=301)' in main, "main.py: /briefing must not 404 a dashboard left open"
assert "reports_due" in open("init.sql").read() and "held_quiet" in open("init.sql").read(), "init.sql: the reports table"
assert "def bundle(" in open("app/report.py").read() and "def sheet(" in open("app/report.py").read(), "app/report.py"
assert "FROM reports ORDER BY ts DESC LIMIT 1" in main, "main.py: /report/latest orders by ts — a report written on request has no due hour"
assert "coalesce(due_local, ts)" in main, "main.py: a report written on request still ends the held stretch"
assert "cmd_report()" in cli and "report) shift; cmd_report" in cli, "CLI: planetai report"
assert "planetai report every" in cli and "planetai report at" in cli, "CLI: the report rhythm is settable and documented"
assert "planetai report level" in cli and 'runtime_set ALERT_LEVEL' in cli, "CLI: report level — the docs promise it"
assert "contributes: report" in open("packs/insight/rules.yml").read(), "the digest contributes to the report"
assert "def contributors" in open("app/packs.py").read() and "def alerts" in open("app/packs.py").read(), "packs.py: a contributor is not an alert"
print("one report, its table, its endpoints, its settings and its command all ship")
# v0.32.1 — a reinstall over an earlier node's volume left an app that could not log in while every check said fine
# The guard once looked for "planetai_db" literally, then derived the name from the folder's basename —
# both wrong in one direction each: docker-compose.yml pins `name: planetai`, so the volume is planetai_db
# whatever the folder is called (a tarball install lives in planetai-node), and COMPOSE_PROJECT_NAME is the
# only override. Assert the pin, not a derivation.
_ish = open("install.sh").read()
assert 'DBVOL="${COMPOSE_PROJECT_NAME:-planetai}_db"' in _ish and 'docker volume inspect "$DBVOL"' in _ish \
    and "NEWPW" in _ish, "install.sh: refuse a new password over an old volume, whatever the folder is called"
assert "app logs in to the database" in cli, "doctor: the locked-out app must be a named failure"
print("reinstall over a leftover volume is refused and diagnosed")
# v0.33 — the earth pack. A pack whose files, endpoint, card and cell must ship together: the pack alone
# leaves the dashboard blank, the endpoint alone has nothing to serve, the card alone renders an empty box.
import os as _os
for _f in ("pack.yaml", "README.md", "adapter.py", "cells.yml", "fetch.py", "change.py", "status.py", "verify.py", "similar.py"):
    assert _os.path.exists(f"packs/earth/{_f}"), f"packs/earth/{_f}"
_earth = yaml.safe_load(open("packs/earth/pack.yaml"))
assert _earth["pip"] == ["rasterio", "numpy"] and _earth["kind"] == "code"
assert "EARTH_RADIUS_M=5000" in "".join(_earth["env"]) and "EARTH_YEARS=" in "".join(_earth["env"])
assert "Google and Google DeepMind" in _earth["attribution"], "the licence's own wording, not a paraphrase"
_cells = yaml.safe_load(open("packs/earth/cells.yml"))
assert len(_cells) == 1 and _cells[0]["cell"] == "Environmental|City" and _cells[0]["state"] == "partial"
print("the earth pack, its endpoint, its card and its cell all ship")
# v0.33.1 — one number for the land. earth-engine published a second land-change score with different
# provenance; it was retired and the alert moved to the pack that owns the metric.
for _f in ("adapter.py", "pack.yaml", "cells.yml"):
    assert "land_change" not in open(f"packs/earth-engine/{_f}").read(), f"earth-engine/{_f} still has land change"
assert not _os.path.exists("packs/earth-engine/rules.yml"), "earth-engine's land_changed was retired"
# and no pack alerts on land change until the number can be calibrated across climates: any threshold that
# fires in Kuta Selatan (0.041) also fires in Boston (0.040), most likely on snow and leaf-off.
assert not _os.path.exists("packs/earth/rules.yml"), "the earth pack must ship no alert; see its README"
assert "a household would ignore" in open("packs/earth/README.md").read(), \
    "packs/earth/README.md must say WHY there is no alert, not just that there is none"
for _n in ("0.0414", "0.0404", "0.0164", "0.0151"):
    assert _n in open("packs/earth/README.md").read(), f"the README must carry the {_n} measurement"
# v0.33.1 — every comparison is reachable, so a NAS can archive the ones that cannot be recomputed cheaply
assert 'def _earth_changes' in main and '"changes": changes' in main
assert 'pattern=r"^(\\d{4}_\\d{4})?$"' in main, "main.py: the pair must be a pattern, not a path"
assert 'def earth(ddir)' in open("tools/nas/pull.py").read(), "tools/nas/pull.py: archive the earth results"
print("one land-change number, its alert, and the results a NAS can archive")
# v0.33.3 — `planetai update` ships a pack's code, not its libraries. Node #1 got ModuleNotFoundError nine
# times with no remedy named. Every entry point that needs a pack library must say which command installs it.
assert "def require(" in open("packs/earth/adapter.py").read(), "packs/earth/adapter.py: the preflight"
for _s in ("fetch", "change", "similar"):
    assert "A.require(" in open(f"packs/earth/{_s}.py").read(), f"packs/earth/{_s}.py must preflight its libraries"
assert "planetai packs install" in open("update.sh").read(), "update.sh must say when a pack needs installing"
assert 'grep -q "planetai packs install" <<<' in open("update.sh").read(), "under pipefail, not a pipe into grep -q"
print("a pack that lacks its libraries says which command installs them")
# v0.33.8 — `planetai run earth change --all` is documented. Its behaviour, and the refusal of an argument
# the script does not know, are tested by running the script in tests/test_earth.py: a string check here
# would have passed while --all quietly did the default pair, which is the bug being fixed.
assert "planetai run earth change --all" in open("packs/earth/README.md").read(), "the README must document --all"
print("change --all is documented; tests/test_earth.py runs it")
# v0.34 — the years as pictures: a frame per cached year, animated in the card, one shared projection.
assert _os.path.exists("packs/earth/frames.py"), "packs/earth/frames.py"
assert "def fit_view" in open("packs/earth/adapter.py").read(), "the projection must be fittable once"
assert '"view"' in open("packs/earth/frames.py").read(), "the projection must be kept, not refitted per year"
assert '@app.get("/earth/year.png")' in main and 'f"year_{year}.png"' in main, \
    "main.py: a frame is addressed by an integer year, never by a name from the request"
assert '"frames": frames' in main and '"dir": str(d)' in main
# The satellite card's controls are hooked by data-sat= rather than by ids: the same component is
# drawn more than once on a page (the node's own record and the imagery), and an id cannot be.
#
# `mode` is gone as of 18 September, and deliberately. It toggled to a "what changed" composite
# frame; v0.53 emitted an image with data-i="change" for it to show, the modular page never did, and
# no route serves one — /earth/frame.png takes sentinel or landsat and /earth/year.png takes a year.
# So it had nothing to toggle to for five releases, on top of having no handler at all. A control
# that does nothing is worse than no control. `year` became `frame` on the images and `label` on the
# year readout when both records became one player; the capability is what is asserted here, not the
# spelling.
for _hook in ('data-sat="play"', 'data-sat="slider"', 'data-sat="frame"', 'data-sat="label"'):
    assert _hook in gui, f"gui: the satellite card lost {_hook}"
# And the controls are live. They were markup with no listener from v0.54 to v0.59: Play did nothing.
assert "function wireSat(root)" in gui and "play.onclick" in gui and "slider.oninput" in gui, \
    "gui: the year player's controls are not wired again"
assert "--motion-satellite-year" in gui, \
    "gui: the player no longer takes its cadence from the frozen layer, so reduced motion cannot stop it"
for _id in ():
    assert f'id="{_id}"' in gui, f"gui: #{_id}"
assert "not a photograph" in gui.lower() or "Not a photograph" in gui, \
    "gui: a rendering of a model must not be presented as a photograph"
print("the years render, animate, and are not called photographs")
assert 'libexpat1' in open("app/Dockerfile").read(), "app/Dockerfile: rasterio cannot import without libexpat1"
assert '@app.get("/earth")' in main and '@app.get("/earth/change.png")' in main
assert 'Path(str((want or {}).get("png", ""))).name' in main, "main.py: the png name must be stripped of path components"
# The earth card became the `satellite` component, drawn twice on the Land band — the node's own
# AlphaEarth record and the Earth Engine imagery — which is why it is a component and not an id.
assert 'data-component="satellite"' in gui, "gui: the satellite card"
assert "'/earth/year.png?year='" in gui or '/earth/year.png?year=' in gui, "gui: the node's own frames"
assert '/earth/frame.png?source=sentinel' in gui, "gui: the imagery frames"
# `prov` in the class, whatever else is beside it — tools/check_ui.py's ink-only rule keys on that
# word, so a pill without it is a pill no gate guards.
assert re.search(r'class="[^"]*\bprov\b', gui), "gui: the satellite card needs its provenance pill"
assert "planetai run earth fetch" in gui, "gui: the empty state must name the command that fills it"
# v0.33.6 — the dashboard must not be cacheable: a node that updates has to reach the screens looking at it
_ui = re.search(r"^def ui\([^)]*\):(.*?)(?=^def |\Z)", main, re.M | re.S).group(1)
assert "no-cache" in _ui, "the dashboard route must send a cache-control header, or an update never reaches an open browser"
print("the dashboard is not cacheable")
# v0.33.7 — one unusual OpenStreetMap object must not blank the plan. A poi mapped as an open way made
# drawPlan destructure a number and the kilometre stayed empty, silently, because drawPlan() is not awaited.
_gui = gui
# Matched loosely on whitespace: these were written against a single file whose script was packed,
# and the renderer that replaced it is formatted. What is being asserted is the behaviour, not the
# spacing — a reformat must not be able to turn one of these red, and must not turn it green either.
assert re.search(r"const\s+firstPt\s*=\s*g\s*=>", _gui), \
    "the plan needs a geometry-agnostic first point for its poi markers"
assert re.search(r"px\(\s*firstPt\(g\)\s*\)", _gui), "the poi marker must not index coordinates[0][0]"
assert re.search(r"catch\s*\(\s*e\s*\)\s*\{\s*skipped\+\+", _gui), \
    "the plan's feature loop must survive one undrawable feature"
print("the plan survives real OpenStreetMap geometry")
# v0.35 — `local` was written once and never corrected. Node #1 carried three smartcitizen kits at local=false
# that no current code path can produce: they were born from Bali Air Dispatch before the bad- prefix existed.
# Both upserts must now update it, or a wrong partition of house and street survives every poll forever.
_main = open("app/main.py").read()
assert _main.count("local=EXCLUDED.local") + _main.count("local = EXCLUDED.local") == 2, \
    "both sensor upserts (poll and MQTT) must update local, or a stale flag never heals"

# The no-wind Steadman form is the indoor form, as packs/heat/README.md says. Both heat rules compute it, so both
# read indoor sensors only. After LOCAL_RADIUS_M a node's local sensors may all be outdoors, where the same
# arithmetic overstates the load; going quiet is the right answer, a wrong number is not.
_heat = {r["id"]: r for r in yaml.safe_load(open("packs/heat/rules.yml"))}
for _rule in ("heat_stress_now", "heat_danger"):
    assert "t.local AND t.indoor AND t.metric = 'temp'" in _heat[_rule]["sql"], \
        f"{_rule}: apparent temperature indoors only, and its threshold was measured indoors"

# The channel role registry is replaced on every start. Under an autocommit connection a bare DELETE commits on
# its own, so a reader during a restart sees an empty table — and a trust rule joining an empty registry returns
# nothing, which reads as "no problems found" instead of "the registry was reloading".
_main_ch = open("app/main.py").read()
_load = _main_ch[_main_ch.index("def load_channel_roles"):]
_load = _load[:_load.index("\ndef ")]
assert "with con.transaction():" in _load, \
    "the delete and reinsert of channel_roles must be one transaction, not two autocommitted statements"
assert "DELETE FROM channel_roles" in _load

# v0.35 — the trust pack. Node #1 held a kit at 3% coverage reporting a timestamp four minutes old, and three
# collocated indoor kits where one read 1.5x the other two. Nothing said so.
_trust = {r["id"]: r for r in yaml.safe_load(open("packs/trust/rules.yml"))}
assert set(_trust) == {"channel_dead", "coverage_low", "peer_disagreement"}, "three rules, no more"
assert not _os.path.exists("packs/trust/cells.yml"), "a trust score is never an Index cell"
assert "60" in _trust["coverage_low"]["sql"], "coverage_low's floor is 60% of the last 7 days"
assert "50" in _trust["peer_disagreement"]["sql"], "collocation is 50 m"
assert "0.85" in _trust["peer_disagreement"]["sql"] and "1.15" in _trust["peer_disagreement"]["sql"]
# ... and a ratio is not enough: at 7 ug/m3 that band is +/-1 ug/m3, under a Plantower's own resolution (v0.40).
assert "('pm1', 5.0)" in _trust["peer_disagreement"]["sql"], "pm needs an absolute floor of 5 ug/m3 as well as the band"
assert "a.sensor_id < b.sensor_id" in _trust["peer_disagreement"]["sql"], "A != B and B != A are one fact, one row"
assert "channel_roles" in _trust["peer_disagreement"]["sql"], "peer comparison is ambient-only, by role"
# channel_dead: six flat hours out of the last 24, latest bucket flat too, is what dusk looks like on any light
# channel — node #1's fired every evening (v0.40). Frozen means a whole day: every bucket of the last 24 present
# and flat, and a flat value of 0 is a floor, not a freeze.
assert "f.hours >= 24 AND f.moved = 0" in _trust["channel_dead"]["sql"], \
    "channel_dead: a day of flat buckets with none of them moving, not 6 scattered flat hours"
assert "f.stuck_at <> 0" in _trust["channel_dead"]["sql"], "a channel sitting at 0 has a floor, not a freeze"
assert "last_flat_bucket" not in _trust["channel_dead"]["sql"], "the 'frozen right now' condition is gone with the 6-hour form"
for _r in _trust.values():
    assert set(_r["message"]) >= {"en", "id"}, "every alert speaks English and Indonesian"
    assert "µg" not in _r["message"]["en"], "statistics stay out of alert messages"
print("the trust pack ships three rules and no cells")

# v0.35 — the rhythm rule told households the evening PM peak was "the burning and the traffic". The noise channel
# we already store says otherwise: r(pm25, noise) = -0.24 at node #1, and the loud hours are the clean ones.
_ins = {r["id"]: r for r in yaml.safe_load(open("packs/insight/rules.yml"))}
assert "traffic" not in _ins["rhythm"]["message"]["en"], "the noise channel contradicts the traffic claim"
assert "'noise'" in _ins["rhythm"]["sql"], "rhythm reads the noise channel it has been discarding"
assert "quiet_hr" in _ins["rhythm"]["sql"], "the message needs the hour the street is loudest to contrast with"
print("rhythm no longer blames traffic")

# v0.36 — the trust card. Three alerts existed (channel_dead, coverage_low, peer_disagreement) and nowhere on the
# node's own surfaces did a person see that a sensor sat at 32% coverage while its kit reported a fresh timestamp.
assert '@app.get("/trust")' in main, "coverage is a new endpoint: the stats view is 24h by construction, no 7-day column belongs in it"
assert 'data-card="trust"' in gui, "the node shows what it doubts about its own sensors"
assert "Every sensor reported all week" in gui, "the trust card needs an empty state, not an empty box"
assert "still gathering its first week" in gui, "a sensor under 7 days old must not read 0% coverage as a fault"
_agent_src = open("app/agent.py").read()
assert '_get("/trust")' in _agent_src, "health_check reads the same /trust the card reads, not its own recomputation"
assert "frozen" in _agent_src.lower()
print("the trust card and its health check are wired")

# Task 8 review — /trust's frozen CTE dropped channel_dead's third condition (the kit itself still producing raw
# readings in the last 2 hours). Without it, a sensor gone fully dark that happened to be flat before it died
# reads as "1 channel frozen" on the card, and the health check's fix text calls it a kit that "still reports" —
# both false for a sensor that is simply offline.
assert "alive AS (\n          SELECT sensor_id, max(ts) AS kit_ts FROM readings\n          WHERE ts > now() - interval '2 hours'" in main, \
    "/trust must join the same 'alive' CTE channel_dead uses (2-hour freshness gate), or a dead kit reads as a merely frozen channel"
assert "JOIN alive a USING (sensor_id)" in main, "frozen_channels must be gated by the kit still being alive, not just by the flat hours"
# v0.33.8 — the heat rule fired on Kuta Selatan's ordinary weather: node #1's hot room was over 32 °C apparent for
# 86% of every reading, so 32 was its baseline, not an event. The line is 35 for the rule and 32 for the cell (a
# count of exposure is not an interruption), and the alert texts must not move without Tomas. 9 October: they
# moved WITH him — release D of the language split names whose line in every threshold alert (rule 10 of
# docs/SPEC_language.md), and heat_stress_now drops "dangerously" (danger is a register, not a volume).
_heat = {r["id"]: r for r in yaml.safe_load(open("packs/heat/rules.yml"))}
assert ">= 35" in _heat["heat_stress_now"]["sql"], "heat_stress_now: 32 is node #1's baseline; the line is 35"
assert ">= 40" in _heat["heat_danger"]["sql"], "heat_danger stays at the heat-index danger line"
assert ">= 32" in open("packs/heat/cells.yml").read(), "the Social cell counts hours over 32, unchanged"
assert _heat["heat_stress_now"]["cooldown_minutes"] == 240, "at 35 the cooldown stops mattering; it stays 240"
for _r, _lang, _words in (("heat_stress_now", "en", "It is too hot at {name}: it feels like {at} °C — this house's own line is {line} °C, measured here."),
                          ("heat_danger", "en", "DANGER at {name}: it feels like {at} °C — the danger line here is {line} °C.")):
    assert _words in _heat[_r]["message"][_lang], f"{_r} [{_lang}]: the message template needs Tomas's sign-off to change"
assert "Kuta Selatan" in open("packs/heat/README.md").read(), "docs/PACKS.md: say which place you wrote for"
print("the heat line is this place's, and every threshold alert names whose line it is")

# v0.38 — the hero's ground is the node's own cell, drawn from NODE_LAT/NODE_LON, and the line naming that
# cell is on the page rather than stamped in the drawing, where object-fit:cover crops it away.
assert "h3" in open("app/requirements.txt").read(), "app/requirements.txt: h3"
assert "def facts(" in open("app/ground.py").read() and "def svg(" in open("app/ground.py").read()
assert '"cell": _cell()' in main and "ground.facts(" in main and "ground.svg(" in main, "/health and /static"
# The stamp used to be two ids written into a fixed skeleton, #hero-stamp and #wall-stamp, each
# filled by its own line. The page is a renderer now: there is one `stamp` component, listed in the
# hero's anatomy and in the wall's, so it is drawn in both places from one piece of code. Asserting
# the anatomy is the same guarantee the two ids gave and a stronger one — an id can exist in the
# markup while nothing writes to it.
# Rewritten with the modular page, which has no ANATOMY object. Same three guarantees, read off the
# code that draws today: the stamp is a component, it is drawn on both surfaces from one piece of
# code, and its caption is /health's own cell rather than anything the page worked out.
assert 'data-component="stamp"' in gui, "gui: the cell stamp"
# The two used to be asserted as one adjacent string. They are not adjacent since
# 21 September 2026: the lead's stamp line carries the open-ask reference between them,
# because the ask strip moved to Act and T1 still wants an ask on the first screen. What
# this guards is that the LEAD draws the stamp at all — one stamp(), called from here and
# from the wall — not the order of the line it sits in.
assert "${window.K.stamp()}" in gui, "gui: the lead no longer draws the cell stamp"
assert "${asof()}" in gui, "gui: the lead no longer draws its as-of"
assert "${K.asof()}${K.stamp()}" in gui, "gui: the wall no longer draws the cell stamp"
assert "const c = (S.health || {}).cell;" in gui, "gui: the caption is the cell's own, from /health"
assert "const said = c ? c.caption : '';" in gui, "gui: and a node with no cell prints nothing"
assert "THE CELL THIS NODE STANDS IN" not in open("app/static/node-ground.svg").read(), (
    "the shipped file is the fallback for a node with no coordinates; it must name no cell")
print("the ground is drawn from the node's own coordinates and the caption is on the page")

# v0.40 — the trust pack's three rules each asked 24 hours and called the answer an alert. At 21:17 on 7 September
# they sent node #1's household three warnings on Telegram, all wrong, and would have sent them again every
# evening. The fault under all three: a statement about an instrument needs a week. Every rule now joins
# `seasoned`, so a sensor with under seven days of readings on this node is never named.
_trust = {r["id"]: r for r in yaml.safe_load(open("packs/trust/rules.yml"))}
for _id in ("channel_dead", "coverage_low", "peer_disagreement"):
    assert "HAVING min(ts) < now() - interval '7 days'" in _trust[_id]["sql"], \
        f"{_id}: a sensor with under a week of readings here is never named"
    assert "JOIN seasoned USING (sensor_id)" in _trust[_id]["sql"], f"{_id}: the gate must be joined, not just declared"
    assert _trust[_id]["level"] == "info" and _trust[_id]["cooldown_minutes"] == 10080, \
        f"{_id}: what this pack finds goes in the week's instrument paragraph, once a week, not into an evening"
print("every trust rule needs a week of a sensor before it names it")

# The same three rules, run over node #1's own readings (tests/data/node1-*.tsv, out of the 7 September dump).
# Every kit there is under three days old: sc-19236, sc-19849, sc-19874 and sc-19897 first reported on 5 September
# and sc-19880 on 2 September. The shipped v0.35 rules named four of them — `coverage_low` at 35% of the week,
# `channel_dead` on Ungasan Kit's light channel at dusk, `peer_disagreement` five times over one collocated trio
# and one pair. A node this young must now hear nothing.
try:
    import trustdb
except ImportError:
    print("  - trust rule replay skipped (pip install duckdb)")
else:
    _at, _real = trustdb.FIXTURE_NOW, trustdb.readings()
    _node = trustdb.Node(_real)
    for _id, _rule in _trust.items():
        assert _node.run(_rule, _at) == [], f"{_id}: node #1's kits are two days old; the pack has nothing to say yet"
    # The same series with a week behind it is not silent, so the silence above is the age gate and not a harness
    # that never runs the SQL.
    assert trustdb.Node(trustdb.week(_real, _at)).run(_trust["peer_disagreement"], _at), \
        "given a week, the rules must still be able to speak — otherwise this test proves nothing"
    print("the trust pack says nothing about a sensor younger than a week")

    # channel_dead, over Ungasan Kit's real light series (5-7 September): 0 from dusk to dawn, eleven flat hours
    # ending in the latest bucket, then 4 -> 1259 lux through the day. The v0.35 rule matched it at 21:14 with
    # flat_hours = 11. It must now match at no hour of the day, and its age must not be the reason: the series is
    # given the week the pack asks for, so what is being tested is the flat rule itself.
    _ungasan = trustdb.week(trustdb.readings("sc-19236"), _at)
    _node = trustdb.Node(_ungasan)
    for _h in range(24):
        _when = _at - datetime.timedelta(hours=_h)
        assert _node.run(_trust["channel_dead"], _when) == [], \
            f"channel_dead fired on a light channel that reads 0 at night, {_h}h before the dump"
    # A channel that has genuinely stopped: 26 hours on one number, beside the same kit's pm25 still moving.
    _stuck = trustdb.week(trustdb.readings("sc-19874"), _at) + trustdb.flat("sc-19874", "light", 412, 26, _at)
    _rows = trustdb.Node(_stuck).run(_trust["channel_dead"], _at)
    assert [r["metric"] for r in _rows] == ["light"] and _rows[0]["name"] == "BAYU NEW ENCLOSURE", \
        f"a channel stuck on 412 lux for 26 hours is the failure this rule exists to catch, got {_rows}"
    # The same channel stuck on 0 is a floor, not a freeze — night, no rain, a quiet room.
    _floor = trustdb.week(trustdb.readings("sc-19874"), _at) + trustdb.flat("sc-19874", "light", 0, 26, _at)
    assert trustdb.Node(_floor).run(_trust["channel_dead"], _at) == [], "0 lux for a day is night, not a dead sensor"
    print("channel_dead: a day on one number, and a floor of 0 is not a freeze")

    # peer_disagreement, over the five kits' real pm1. Tonight it fired twice for one fact — Ungasan Kit at
    # 7.4 ug/m3 against BAYU NEW ENCLOSURE at 5.4, and then the same pair the other way round — where a ratio of
    # 1.37 is two units 30 m apart differing by 2 ug/m3, inside a Plantower's resolution. Over the week the pack
    # now asks for: the SENX unit's 16 against its two neighbours' 7 is a real disagreement and is named once per
    # pair, naming both units; the 6.8-against-7.2 pair is not named; the 7.4-against-5.4 pair is not either,
    # because the difference is under the 5 ug/m3 floor however far outside the band the ratio sits.
    _peers = trustdb.Node(trustdb.week(_real, _at)).run(_trust["peer_disagreement"], _at)
    assert [r["sensor_id"] for r in _peers] == ["sc-19849|sc-19880", "sc-19849|sc-19897"], \
        f"one row per pair, the low pair and the sub-resolution pair silent, got {_peers}"
    for _r in _peers:
        assert _r["name_a"] == "SENX ALL IN ONE" and _r["name_b"] in ("Bayu 2 - Indoor", "NEW FIRMWARE TEST")
        assert _trust["peer_disagreement"]["message"]["en"].format(**_r).startswith("⚖️ SENX ALL IN ONE and ")
    # Twenty-four hours of the same five kits says nothing at all: the rule no longer looks at 24 hours.
    assert trustdb.Node(trustdb.day(_real)).run(_trust["peer_disagreement"], _at) == [], \
        "a day of two boxes is a statement about the day"
    print("peer_disagreement: a week, an absolute floor, and one alert per pair")

    # coverage_low keeps its 60% of 168 hours; the gate is all it needed. SENX ALL IN ONE reported 59 of tonight's
    # last 168 hours — 35%, which is what the rule would have said, and true — but it had only been on the node
    # for two days. Given a fortnight behind it and the same 59 hours, it is named; two days old, it is not.
    _senx = trustdb.readings("sc-19849")
    _old = _senx + [(_ts - datetime.timedelta(days=14), _s, _m, _v) for _ts, _s, _m, _v in _senx]
    assert [(r["name"], r["hours"], float(r["pct"])) for r in trustdb.Node(_old).run(_trust["coverage_low"], _at)] \
        == [("SENX ALL IN ONE", 59, 35.0)], "a seasoned sensor with 35% of the week is still worth saying"
    assert trustdb.Node(_senx).run(_trust["coverage_low"], _at) == [], "two days old is not a hole in the week"
    print("coverage_low: the same 60%, over sensors old enough for the question")


# ---------------------------------------------------------------- v0.40  the ring, and the forecast
import os as _os  # noqa: E402

# both packs exist and are what they say they are
_np = yaml.safe_load(open("packs/nearby/pack.yaml"))
_fp = yaml.safe_load(open("packs/forecast/pack.yaml"))
assert _np["kind"] == "data" and _np["scales"] == ["community"], "nearby: a data pack about this address"
assert _fp["kind"] == "code" and _fp["scales"] == ["community"], "forecast: a code pack about this address"
assert not _os.path.exists("packs/nearby/adapter.py"), \
    "nearby has no adapter: the Bali Air Dispatch fetch lives in app/sources.py, and a second one would store " \
    "every station twice — the same duplicate the pack exists to refuse, one layer up"

# neither pack may grow an Index cell. `live` means measured here; the ring is other people's and a forecast is
# nobody's measurement of this place. Environmental|City already exists in air-quality over the same stations.
for _p in ("nearby", "forecast"):
    assert not _os.path.exists(f"packs/{_p}/cells.yml"), f"{_p}: no cell, by design — see its README"

# the forecast never speaks. Three wrong warnings reached node #1's Telegram at 21:17 on 7 September.
_fr = yaml.safe_load(open("packs/forecast/rules.yml"))
assert _fr and all(r.get("contributes") == "report" and "message" not in r and "level" not in r for r in _fr), \
    "forecast: every rule contributes to the report and none of them can reach a phone"

# the ring's three rules, and what each is for
_nr = {r["id"]: r for r in yaml.safe_load(open("packs/nearby/rules.yml"))}
assert set(_nr) == {"only_here", "everywhere", "alone"}, "nearby: three rules"
assert _nr["only_here"]["level"] == "act" and _nr["everywhere"]["level"] == "info"
assert _nr["alone"].get("contributes") == "report" and "message" not in _nr["alone"], \
    "alone is the honesty line in the report, not an alert"
for _id, _r in _nr.items():
    # the ring is the archive, by name. `NOT local` alone counted the operator's own kits beyond LOCAL_RADIUS_M
    # as neighbours: the node comparing itself against its own hardware.
    assert "source = 'baliairdispatch'" in _r["sql"], f"nearby/{_id}: the ring is scoped to the archive, not to NOT local"
    if "message" in _r:
        assert set(_r["message"]) == {"en", "id", "es"}, f"nearby/{_id}: three languages"

# the four exclusions, and the audit that proves them
_src = open("app/sources.py").read()
assert "def bad_verdicts(" in _src, "app/sources.py: one pure function decides the ring, so the audit cannot drift"
for _w in ("identity", "proximity", "by hand", "same device"):
    assert _w in _src, f"app/sources.py: the `{_w}` exclusion"
assert "BAD_MIRROR_PREFIXES" in _src
for _k in ("BAD_MIN_SEPARATION_M", "BAD_EXCLUDE", "BAD_INCLUDE_INDOOR"):
    assert re.search(rf"^{_k}=", env, re.M) and f'"{_k}"' in settings, f".env.example and settings.py: {_k}"
assert re.search(r"^BAD_RADIUS_KM=15$", env, re.M), \
    ".env.example: 15 km, which is 6 real neighbours at node #1 against 3 at 10 km and 1 at 5"

# both endpoints, and the two surfaces they reach
#
# Repointed 15 September 2026 with the modular page. The nearby ring and the nearby stations were two
# cards; in this direction they are one section — `sensors`, which draws every station with a
# coordinate, grouped by the cell it falls in, with its own distance and its own 15-minute mean. Two
# station lists on one page would be the design error, so each assertion below is the finding the old
# card carried, read off the section that carries it now. Each still goes red if the capability goes.
assert "def nearby(" in main and "def forecast(" in main, "main.py: /nearby and /forecast"
assert 'data-card="forecast"' in gui, "the dashboard: the forecast card"
assert re.search(r"^function drawForecast\(", gui, re.M), \
    "drawForecast must be top level: defined inside another body it still parses, and check_ui.py cannot see it"
# the ring is on the page: every station around this node, one row each, never one number.
# Protects what `nearby-ring` protected — that the neighbours are shown at all. Red if the section
# stops being registered or stops drawing a row per station.
assert "id: 'sensors'" in gui, "the dashboard: the section that draws the stations around this node"
assert 'data-component="station"' in gui, "the dashboard: one row per station, which is the ring"
# and each says how far away it is. Protects what `nearby-stations` protected: a reading from 12 km
# away must never be drawn as if it were from here.
assert "${esc(String(s.km))} km" in gui, "the dashboard: a station must say how far away it is"
# and the page says what the ring's single number hides, which is the reason to draw the stations
# at all. Red if that sentence goes.
assert "single fenced median and never a value per station" in gui, \
    "the dashboard: the page must say that the street is published as one median and this is what it hides"
# every card says where its numbers came from, on the card. The forecast names both archives in its
# own fallback credit; the stations name theirs from each station's own `attribution`, which is the
# stronger form — a required attribution line cannot drift from what the node actually sent.
assert "api.bmkg.go.id" in gui and "open-meteo.com" in gui, \
    "the dashboard: both forecast archives credited on the card itself"
assert "s.attribution" in gui and "sources: ${attrib" in gui, \
    "the dashboard: each station's own attribution line is printed under the list, as its source requires"
# a link only where the sensor has a page of its own — account kits, never a public station.
# `/issues` publishes `url` per station and only fills it where the source gives one.
assert 'esc(s.url)}" target="_blank" rel="noopener"' in gui, \
    "the dashboard: account kits link to their own page; a station with no page gets no link"

# v0.48 — presence. A node announcing "I am here" on Reticulum is the node speaking unprompted, so it is
# its own setting and it is off until somebody turns it on; SHARE_LEVEL governs what a node ANSWERS.
_bridge = open("app/reticulum_bridge.py").read()
assert '"RETICULUM_PRESENCE":' in settings and '"RETICULUM_PRESENCE_RES":' in settings, \
    "app/settings.py: presence is a runtime setting, so a household can turn it off from the dashboard"
assert re.search(r'PRESENCE_RES_FLOOR\s*=\s*[0-6]\b', main), \
    "main.py: a floor on how exact the announced cell may be. Without it a settings box publishes a street."
assert "min(r, PRESENCE_RES_FLOOR)" in main, "the floor has to be applied, not merely declared"
assert '"/presence"' in main[main.index("_SHARE_OFF = "):main.index("_SHARE = {")], \
    ("/presence must answer at SHARE_LEVEL=off: the reticulum bridge is another container with no token, "
     "and on the `open` list only it would be refused on a default node and never announce")
assert '"enabled": False' in main, "/presence says nothing at all until presence is on"
# scoped to /presence's own body: cell_to_parent also appears in the distance helper, so a bare
# substring check passed even with the coarsening taken out of the thing that announces
_pres = main[main.index('@app.get("/presence")'):main.index("def _cell(")]

# The Network view printed "It announces; it does not yet listen. Nothing here collects the announces
# other Reticulum nodes make" on every node whose bridge was up — directly beneath the card listing the
# nodes it had just heard, with a name and a distance in it. The bridge registers PresenceHandler at
# import and unconditionally, so a node has always listened; RETICULUM_PRESENCE governs whether it
# SPEAKS. The copy predated the handler and shipped in three languages. Seen on node #1, v0.53-2.
_bridge = open("app/reticulum_bridge.py").read()
assert "register_announce_handler" in _bridge, (
    "the bridge no longer collects other nodes' announces — if that is deliberate, the dashboard has "
    "to say so again, and this assertion is what stops it being said while the handler still runs")
for _claim in ("does not yet listen", "belum mendengarkan", "todavía no escucha"):
    assert _claim not in gui, (
        f"dashboard.js still tells the household {_claim!r} while reticulum_bridge.py registers an "
        "announce handler and the Network view lists heard peers above it")
assert "cell_to_parent" in _pres and "_presence_res()" in _pres, \
    "the announced cell is a COARSE parent of this node's own cell, never the cell itself"
assert "register_announce_handler" in _bridge, \
    "the bridge has to listen as well as announce, or no node ever hears another"
assert 'aspect_filter = "planetai.presence"' in _bridge, "on its own aspect, not on LXMF delivery"
assert "/peers" in _bridge, "and hand what it heard to the node"
assert "if h == RNS.hexrep(PRESENCE.hash" in _bridge, "a node must not list its own announce as a peer"
print("presence: off by default, coarse by construction, and the bridge listens as well as announces")

# the scripts each pack promises in its README
for _p, _s in (("nearby", ("stations", "status", "verify", "backfill")),
               ("forecast", ("fetch", "status", "verify"))):
    for _n in _s:
        assert _os.path.exists(f"packs/{_p}/{_n}.py"), f"packs/{_p}/{_n}.py"

print("v0.40: two packs, two endpoints, three cards, four exclusions, and not one new cell")

# v0.41.3 — the bot's MCP session is opened per question, not per process. Held for the life of the container it
# expires, every later POST /mcp answers 404 "session not found", and because call_tool's exception becomes the tool
# *result* the model reads "tool error" and replies "I am unable to reach the node" to everything, forever, with
# nothing in the log but the calls going out. Node #1, 9 September: three questions, twelve 404s, no error line.
agent = open("app/agent_loop.py").read()
assert "async def node_session(" in agent, "agent_loop.py: the node_session helper"
assert agent.count("streamable_http_client(") == 1, \
    "agent_loop.py: only node_session may open an MCP session — a second one is a session outliving a question"
assert re.search(r"^    offset, history, pins, pending = ", agent, re.M), \
    "agent_loop.py: main's poll loop must sit at the top of main, outside any MCP session — indented deeper it is " \
    "nested in one again, and that session outlives the question (refresh_ladder has a `while True` of its own, so " \
    "the loop keyword alone proves nothing)"
assert agent.count("async with node_session(") >= 2, \
    "agent_loop.py: /act and each question each open their own session"
assert "tool %s failed" in agent, \
    "agent_loop.py: a failed tool call must reach the log, not only the model"

print("v0.41.3: the node session lives for one question, and a failed tool call says so in the log")


# ---- v0.44 · the small ones. Each of these shipped once and nothing would have caught it a second time.

# F6: a stray `#` at 6 Sep's "/export returned 500 on every call" fix swallowed three keys out of the
# CC-BY export, so a consumer could not tell a CAMS model point-sample from a measured reading except by
# matching sensor-id strings — in a repository whose provenance rule is that live and derived never mix.
# Read the dict the function actually builds, not the SQL above it: the SQL still selected all three.
import ast as _ast  # noqa: E402

_export_keys = set()
for _n in _ast.walk(_ast.parse(main)):
    if isinstance(_n, _ast.FunctionDef) and _n.name == "export":
        for _d in _ast.walk(_n):
            if isinstance(_d, _ast.Dict) and any(
                isinstance(_k, _ast.Constant) and _k.value == "sensor" for _k in _d.keys if _k):
                _export_keys = {_k.value for _k in _d.keys if isinstance(_k, _ast.Constant)}
assert {"t", "sensor", "metric", "kind", "local", "indoor"} <= _export_keys, \
    f"/export's hourly rows must carry kind, local and indoor — a comment ate them once. Built: {sorted(_export_keys)}"

# S4: `planetai storage` printed the read-only backup token, and `planetai storage` is what somebody pastes
# into an issue when their backups have stopped. `planetai ui` is the one command that prints a token to a
# person sitting at the machine; nowhere else may.
_fn, _leaks = "", []
for _i, _line in enumerate(cli.split("\n"), 1):
    _m = re.match(r"^([a-z_]+)\(\)", _line)
    if _m:
        _fn = _m.group(1)
    if re.search(r"(printf|echo)\b.*envget [A-Z_]*TOKEN", _line) and _fn != "cmd_ui":
        _leaks.append(f"bin/planetai:{_i} ({_fn or 'top level'})")
assert not _leaks, "a token is printed outside cmd_ui: " + "; ".join(_leaks)

print("v0.44: /export carries its provenance columns, and only planetai ui prints a token")

# S5: a host-side `localhost:<port>` only works if compose publishes that port. The reticulum bridge's health
# poll used 4243 while compose published only 4242, so `planetai reticulum` and the doctor's "reticulum bridge
# up" row reported failure on every clean, successful start (#51). HOST_PORTS names what is deliberately not a
# container.
HOST_PORTS = {"11434"}          # Ollama, which runs on the host by design
_published = {_m.group(1) for _d in compose["services"].values() for _p in (_d.get("ports") or [])
              for _m in [re.search(r"(\d+):\d+$", _p)] if _m}
for _port in sorted(set(re.findall(r"localhost:(\d+)", cli)) - HOST_PORTS):
    assert _port in _published, \
        f"bin/planetai talks to localhost:{_port}, which docker-compose.yml publishes on no service"

print("every localhost port the CLI uses is published by a compose service")

# v0.61 the vendored source registry. A tarball that carries the code and not the snapshot gives a
# tester `planetai sources` that answers nothing and a doctor row that is red on arrival — and lint
# cannot see it, because lint runs in a checkout where data/sources is right there.
import pathlib as _pl
import subprocess as _sp
_tracked = set(_sp.run(["git", "ls-files"], capture_output=True, text=True).stdout.split())
for _f in ("data/sources/REGISTRY_VERSION", "data/sources/index.json"):
    assert _f in _tracked, f"{_f} is not tracked, so tools/bundle.sh will not ship it"
_ver = dict(l.split("=", 1) for l in _pl.Path("data/sources/REGISTRY_VERSION").read_text().split() if "=" in l)
assert len(_ver.get("sha", "")) == 40, "REGISTRY_VERSION: sha is not a full commit"
# The snapshot is mounted, not baked: app/Dockerfile COPYs *.py, issues/ and static/ and never data/,
# so without this line the container's /app/data does not exist and /sources 503s on a working node.
assert "./data:/app/data:ro" in compose["services"]["app"]["volumes"], "compose: the data mount"
assert "cmd_sources()" in cli and "sources) shift; cmd_sources" in cli, "bin/planetai: sources command"
assert "def sources_(" in main and "import registry" in main, "main.py: GET /sources"

print("v0.61: the tarball carries the source registry, and the app mounts it")
