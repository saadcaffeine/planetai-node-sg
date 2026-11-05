"""The node's fundamental sources (app/fundamentals.py, GET /health/sources) and the doctor that prints them.

Tomas, 15 Oct 2026: "During the install or update of the node planetai doctor should run, but also the user should be
guided to have the fundamental data sources of the node running." So: every fix names a setting, a Set up section and
a command that exist; the states partition a fresh node, a working node and a broken one the way a household would;
the doctor's block is the real function lifted out of bin/planetai, fed the real assess(); and install, update and
setup each run the doctor.

    PYTHONPATH=app python3 tests/test_fundamentals.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

import fundamentals as F
import settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = open(os.path.join(ROOT, "bin/planetai")).read()
fails = 0


def check(ok, what, detail=""):
    global fails
    print(("  ok   " if ok else "  FAIL ") + what + ("" if ok else f"\n       {detail}"))
    fails += 0 if ok else 1


# ---- 1. the list is consistent: every fix points at something real
dispatch = CLI[CLI.index('case "${1:-help}" in'):]
commands = set(re.findall(r"(?:^|;;)\s+([a-z|-]+)\)", dispatch, re.M))
commands = {c for group in commands for c in group.split("|")}
groups = {v[0] for v in settings.RUNTIME.values()}
ids = [f["id"] for f in F.FUNDAMENTALS]
check(len(ids) == len(set(ids)) == 7, "seven fundamental sources, each id once", ids)
for f in F.FUNDAMENTALS:
    for k in f["settings"]:
        check(k in settings.RUNTIME, f"{f['id']}: setting {k} is a runtime setting (Set up can change it)")
    if f["setup"]:
        check(f["setup"] in groups, f"{f['id']}: Set up section #{f['setup']} exists", sorted(groups))
    check(bool(f["setup"] or f["command"]), f"{f['id']}: names where to fix it, a Set up section or a command")
    for text in (f["fix"], f["fix_quiet"] or ""):
        for word in re.findall(r"planetai ([a-z][a-z-]*)", text):
            check(word in commands, f"{f['id']}: `planetai {word}` in its fix is a real command")
        for key in re.findall(r"config set ([A-Z_]+)", text):
            check(key in settings.RUNTIME, f"{f['id']}: `config set {key}` names a runtime setting")
        for sec in re.findall(r"--section ([a-z]+)", text):
            check(sec in groups, f"{f['id']}: `--section {sec}` is a settings group")
    if f["command"]:
        check(f["command"].split()[1] in commands, f"{f['id']}: its command {f['command']} exists")
check("--section" in CLI[CLI.index("cmd_config() {"):], "planetai config takes --section, which a fix names")

# ---- 2. the states
import yaml  # noqa: E402
_m = yaml.safe_load(open(os.path.join(ROOT, "packs/bali-air-dispatch/pack.yaml")))
_st = {**_m["stations"], "pack": _m["id"], "name": _m["name"], "switch": _m["switch"]}  # as packs.stations() gives it
ST_ON, ST_OFF = [dict(_st, on=True)], [dict(_st, on=False)]
bali = {"NODE_LAT": "-8.83", "NODE_LON": "115.16"}
madrid = {"NODE_LAT": "40.42", "NODE_LON": "-3.70"}
by = lambda rows: {r["id"]: r for r in rows}  # noqa: E731

new = by(F.assess(dict(madrid), [], polled=False))
check(new["own-sensors"]["state"] == "missing" and new["own-sensors"]["fix"] == F.FUNDAMENTALS[0]["fix"],
      "a fresh node with no sensor: own sensors missing, with the fix that adds one", new["own-sensors"])
check(new["alerts"]["state"] == "missing" and "planetai telegram" in new["alerts"]["fix"], "no Telegram: missing, fix is planetai telegram")
check(new["nearby-stations"]["state"] == "na" and new["nearby-stations"]["ok"] is None,
      "no stations pack at all: the public-station source does not apply, and is not a cross", new["nearby-stations"])
far = by(F.assess(dict(madrid), [], polled=True, stations=ST_OFF))["nearby-stations"]
check(far["state"] == "na" and far["name"] == "Air stations nearby" and "Bali" not in json.dumps(far),
      "outside Bali the pack is installed and off: na, and the line names no network", far)
near = by(F.assess(dict(bali), [], polled=True, stations=ST_OFF))["nearby-stations"]
check(near["state"] == "missing" and near["fix"] == "Turn on Bali Air Dispatch in Set up › Packs. Or: planetai config set BAD_ENABLED 1"
      and near["setup"] == "#setup/packs", "inside the pack's box and off: missing, the fix names the pack and its switch", near)
check(new["weather"]["state"] == "waiting" and new["weather"]["ok"] is None,
      "before the first poll the default-on models are waiting, not failing", new["weather"])
check(new["backup"]["state"] == "missing" and "03:17" in new["backup"]["fix"], "no dump yet: missing, says the nightly one is coming")
check(new["map"]["state"] == "missing" and new["map"]["ok"] is False and new["map"]["command"] == "planetai run place basemap"
      and "planetai run place basemap" in new["map"]["fix"] and "build.protomaps.com" in new["map"]["fix"],
      "no out/ground/vector.mbtiles: the map is missing, its fix is the command and says who learns where the node is", new["map"])

seen = [{"source": "smartcitizen", "own": True, "indoor": True, "minutes": 4.0},
        {"source": "airgradient", "own": True, "indoor": False, "minutes": 70.0},
        {"source": "baliairdispatch", "own": False, "indoor": False, "minutes": 30.0},
        {"source": "open-meteo", "own": False, "indoor": False, "minutes": 20.0},
        {"source": "open-meteo-cams", "own": False, "indoor": False, "minutes": 20.0}]
cfg = {**bali, "SC_DEVICES": "19880", "BAD_ENABLED": "1", "OPENMETEO_ENABLED": "1",
       "TELEGRAM_BOT_TOKEN": "1:x", "TELEGRAM_CHAT_IDS": "5"}
import time  # noqa: E402
fetched = time.mktime((2026, 10, 19, 12, 0, 0, 0, 0, -1))
good = F.assess(cfg, seen, polled=True, telegram_ok=True, backup_minutes=600, stations=ST_ON, map_at=fetched)
check(all(r["ok"] is True for r in good), "a working Bali node: every source ok", [r for r in good if r["ok"] is not True])
g = by(good)
check(g["own-sensors"]["minutes"] == 4.0 and g["own-sensors"]["detail"] == "inside and outside",
      "own sensors: the youngest counts, and inside and outside are both named", g["own-sensors"])
check(g["map"]["state"] == "ok" and g["map"]["detail"] == "fetched 19 Oct 2026" and g["map"]["age"] is None and g["map"]["fix"] is None,
      "the map on disk: a tick with the day it was fetched, never an age", g["map"])
check(by(F.assess(cfg, seen, polled=False, map_at=fetched))["map"]["state"] == "ok",
      "the map is judged by the file, not by a poll: no 'waiting' on a fresh start")
with tempfile.TemporaryDirectory() as d:
    check(F.map_fetched(d) is None, "map_fetched: an empty folder, None")
    open(os.path.join(d, "vector.mbtiles"), "wb").close()
    check(F.map_fetched(d) is None, "map_fetched: tiles with no finished fetch in meta.json (stopped before the fonts), None")
    with open(os.path.join(d, "meta.json"), "w") as fh:
        json.dump({"drone": {"fetched": "2026-10-07T07:19:51Z"}}, fh)
    check(F.map_fetched(d) is None, "map_fetched: only the drone layer finished, None")
    with open(os.path.join(d, "meta.json"), "w") as fh:
        json.dump({"vector": {"fetched": "2026-10-07T07:16:33Z"}}, fh)
    check(F.map_fetched(d) == 1791357393, "map_fetched: meta.json's vector.fetched, as UTC", F.map_fetched(d))
    os.remove(os.path.join(d, "vector.mbtiles"))
    check(F.map_fetched(d) is None, "map_fetched: meta.json without the tiles, None")
inside = by(F.assess(cfg, seen[:1], polled=True))["own-sensors"]
check(inside["ok"] is True and inside["detail"].startswith("inside only"), "inside only is fine, and says what one outside adds", inside)

bad = by(F.assess({**cfg, "TELEGRAM_BOT_TOKEN": "1:x"}, [s for s in seen if s["source"] != "open-meteo"], polled=True,
                  last_error="open-meteo: 429 Too Many Requests | ckan: down", telegram_ok=False, backup_minutes=4000))
check(bad["weather"]["state"] == "quiet" and "429" in (bad["weather"]["detail"] or "") and bad["weather"]["fix"] == F.FUNDAMENTALS[3]["fix_quiet"],
      "a model that stopped answering: quiet, its own last error, the quiet fix", bad["weather"])
check(bad["satellite-air"]["ok"] is True, "CAMS is judged on its own rows, not on Open-Meteo's error")
cams = by(F.assess(cfg, [s for s in seen if s["source"] != "open-meteo-cams"], polled=True,
                   last_error="air-quality: 502 Bad Gateway"))["satellite-air"]
check(cams["state"] == "quiet" and cams["detail"] == "last error: 502 Bad Gateway",
      "CAMS is packs/air-quality's adapter since 24 Oct 2026: its rows are open-meteo-cams, its error the pack's", cams)
ring = by(F.assess(cfg, [s for s in seen if s["source"] != "baliairdispatch"], polled=True, stations=ST_ON,
                   last_error="bali-air-dispatch: ReadTimeout"))["nearby-stations"]
check(ring["state"] == "quiet" and ring["detail"] == "last error: ReadTimeout" and ring["fix"].startswith("Bali Air Dispatch has not"),
      "a stations pack that stopped answering: quiet, the pack's own last error, the quiet fix in its name", ring)
check(bad["alerts"]["state"] == "quiet", "Telegram refused the last message: quiet, run planetai telegram again")
check(bad["backup"]["state"] == "quiet" and bad["backup"]["age"] == "2 days ago", "a dump older than two days: quiet", bad["backup"])
quiet_own = by(F.assess(cfg, [s for s in seen if not s["own"]], polled=True))
check(quiet_own["own-sensors"]["state"] == "quiet", "a sensor set up but silent for two days: quiet, not missing")
mqtt = by(F.assess({**madrid, "MQTT_HOST": "mosquitto"}, [], polled=False))
check(mqtt["own-sensors"]["state"] == "waiting", "a kit on the node's broker needs no setting: waiting, not missing")
off = by(F.assess({**madrid, "OPENMETEO_ENABLED": "0"}, [], polled=True))
check(off["weather"]["state"] == "missing" and "OPENMETEO_ENABLED 1" in off["weather"]["fix"], "models turned off: missing, how to turn them on")
nas = by(F.assess(dict(madrid), [], polled=True, backup_here=False))
check(nas["backup"]["state"] == "elsewhere" and nas["backup"]["ok"] is None, "a BACKUP_DIR the container cannot see is not judged in it")
keys = {"id", "name", "state", "ok", "minutes", "age", "detail", "fix", "setup", "command", "why"}
check(all(set(r) == keys for r in good), "every row carries the same keys (the route's shape)", [sorted(r) for r in good][:1])
check([r["id"] for r in good] == ids, "rows come in the list's order, most important first")
for rows in (new.values(), bad.values(), good):
    for r in rows:
        if r["ok"] is False and not r["fix"]:
            check(False, f"{r['id']}: a cross with no fix")

# ---- 3. the route
main = open(os.path.join(ROOT, "app/main.py")).read() + open(os.path.join(ROOT, "app/auth.py")).read()
route = main[main.index('@app.get("/health/sources")'):]
route = route[:route.index("\n\n\n")]
check("fundamentals.assess(" in route and "r.ts <= now()" in route, "GET /health/sources calls assess(), bounded by now()")
check("map_at=fundamentals.map_fetched(str(basemap.ground_dir()))" in route, "GET /health/sources reads the map where GET /ground/* serves it from")
share = main[main.index("_SHARE_OFF = ("):main.index("_SHARE = {")]
check("/health/sources" not in share, "GET /health/sources is on no share level's list: it needs a token or this machine")
check('"telegram"' not in main[main.index("state = {"):main.index("state = {") + 300],
      "Telegram's last result is kept out of `state`, which /health spreads to every reader")

# ---- 4. the doctor's block: the real doctor_sources() lifted out of bin/planetai, fed the real assess()
fn = re.search(r"^doctor_sources\(\) \{.*?^\}$", CLI, re.M | re.S).group(0)
with tempfile.TemporaryDirectory() as d:
    for name, rows in (("fresh", list(new.values())), ("good", good), ("bad", list(bad.values()))):
        with open(os.path.join(d, name + ".json"), "w") as fh:
            json.dump({"ok": not any(r["ok"] is False for r in rows), "sources": rows}, fh)
    stub = (f"{fn}\nenvget() {{ :; }}; port() {{ echo 8080; }}; G=; R=; D=; B=; N=; HOME_DIR={d}\n"
            'api() { echo "$1" >> "$DIR/urls"; [ -f "$DIR/$FIX.json" ] && cat "$DIR/$FIX.json"; }\n')

    def doctor(fix, mode):
        r = subprocess.run(["bash", "-c", stub + f'doctor_sources {mode}'], capture_output=True, text=True,
                           env={**os.environ, "DIR": d, "FIX": fix}, stdin=subprocess.DEVNULL, cwd=d)
        return r.returncode, r.stdout + r.stderr

    rc, out = doctor("fresh", "full")
    check(rc == 0 and "Data sources" in out and "✗ Your own sensors" in out and "→ Add your sensor" in out,
          "doctor: a Data sources block, each cross with its fix under it", out)
    check("– Air stations nearby" in out and "To finish" not in out, "doctor: n/a is a dash, and the full doctor has no second list", out)
    check("backup_age=-1" in open(os.path.join(d, "urls")).read(), "doctor: hands the node the age of the backups it finds here (-1: none)")
    rc, out = doctor("fresh", "quiet")
    lines = out.splitlines()
    todo = lines[lines.index("  To finish setting up") + 1:] if "  To finish setting up" in lines else []
    check(todo and todo[0].startswith("   1. Add your sensor") and "http://localhost:8080/#setup/sources" in todo[1]
          and todo[2].startswith("   2. Connect Telegram"), "quiet: To finish setting up, most important first, with the Set up link", out)
    check(any(t.startswith("   4. No map yet") and "planetai run place basemap" in t for t in todo),
          "quiet: the map is a step to finish, last, with its command", out)
    check("→" not in out and "\x1f" not in out, "quiet: no fix lines in the block and no marker leaks", out)
    rc, out = doctor("fresh", "--guide")
    check(rc == 0 and "Do the first one" not in out and "Open " not in out and "Fetch it now" not in out,
          "--guide with no terminal prints the list and asks nothing, the map included (an unattended update)", out)
    rc, out = doctor("fresh", "full")
    check("✗ The map of this place" in out and "→ No map yet. Fetch it once" in out, "doctor: no map is a cross, the fix under it", out)
    rc, out = doctor("good", "quiet")
    check("To finish" not in out and out.count("✓") == 7, "a working node: seven ticks, nothing to finish", out)
    line = next((x for x in out.splitlines() if "The map of this place" in x), "")
    check("✓" in line and line.rstrip().endswith("fetched 19 Oct 2026"), "doctor: the map ticked, with its date", out)
    rc, out = doctor("bad", "json")
    check(rc == 0 and [r["id"] for r in json.loads(out)] == ids, "json: the route's rows, as JSON", out)
    rc, out = doctor("missing-route", "full")
    check(rc == 0 and "did not answer GET /health/sources" in out, "a node that does not answer: one line, not a traceback", out)
    rc, out = doctor("missing-route", "json")
    check(rc != 0, "json with no answer fails, so --json prints null for sources")

# ---- 5. the map is offered on its own, after the first step, and only in a terminal
offer = CLI[CLI.index("offer_map() {"):]
offer = offer[:offer.index("\n}\n")]
check(offer.index("[[ -t 1 ]]") < offer.index("read -r"), "offer_map: asks only in a terminal (never cron, a pipe or an agent)")
check(offer.index("build.protomaps.com") < offer.index("bin/planetai\" run place basemap"),
      "offer_map: says who learns where the node is before it runs anything")
check('[[ "$map" == 1 ]] && offer_map' in fn, "the doctor's --guide offers the map when the node says it is missing")
check("read -r -n1" not in fn[fn.index("[[ -t 1 ]]"):] and "read -r -n1" not in offer,
      "the two questions read whole lines: a 'y' then Enter cannot leave the Enter to decline the next one")
check("|| offer_map" in CLI[CLI.index("finish_setup() {"):CLI.index("what_next() {")], "planetai setup offers the map before its last screen")
check('"$mode" == "--guide"' in fn and fn.index('"$mode" == "--guide"') < fn.index("offer_map"), "only --guide offers it: quiet and full print")

# ---- 6. install, update and setup run the doctor
inst, upd = open(os.path.join(ROOT, "install.sh")).read(), open(os.path.join(ROOT, "update.sh")).read()
check(re.search(r'\./bin/planetai doctor "\$\(\[\[ \$YES -eq 1 \]\] && echo quiet \|\| echo --guide\)" \|\| true', inst) is not None,
      "install.sh runs the doctor, asking only without --yes, never failing the install")
check(inst.rstrip().endswith("fi") and inst.index("bin/planetai doctor") > inst.index("install OK"),
      "install.sh: the doctor is the last thing on the screen")
check('PLANETAI_FROM_SETUP' in inst and CLI.count('PLANETAI_FROM_SETUP=1 PLANETAI_INSTALL_LOG') == 2,
      "the two setup paths that finish with the doctor tell install.sh not to print it twice")
check(re.search(r"\./bin/planetai doctor --guide \|\| true\s*$", upd) is not None, "update.sh ends with the doctor and its guidance")
check(upd.index("bin/planetai doctor --guide") > upd.index('|| die "something is off'), "update.sh: guidance only after an update that worked")
check("cmd_doctor quiet || true" in CLI[CLI.index("finish_setup() {"):], "planetai setup ends with the doctor")
check("doctor_sources " in CLI[CLI.index("cmd_doctor() {"):CLI.index("doctor_sources() {")], "the doctor prints the Data sources block")

print(f"fundamentals: {'all pass' if not fails else f'{fails} failed'}")
sys.exit(1 if fails else 0)
