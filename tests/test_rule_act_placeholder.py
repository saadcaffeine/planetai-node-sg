"""`{act}` in a rule's message becomes that alert's own act_hint: `/act 812` where the bot runs, `planetai act 812`
where it does not. A message is formatted before its alerts row exists, so without this a rule could not tell the
household which number to answer. run_rules is exec'd from app/main.py's source against fakes, as in
test_run_rules_modes (importing main starts a second MQTT client). Then tools/check_rules.py must accept `{act}` as a
placeholder no SQL returns. Run: python3 tests/test_rule_act_placeholder.py
"""
import ast
import json
import re
import contextlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
src = ROOT / "app" / "main.py"
tree = ast.parse(src.read_text())
fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("run_rules", "act_hint", "_event_keyboard")]
code = compile(ast.Module(body=fns, type_ignores=[]), "run_rules", "exec")

sys.path.insert(0, str(src.parent))
import actions  # noqa: E402
import buttons  # noqa: E402

ACT = {"id": "surf/tomorrow", "sql": "ACT_SQL", "message": "go {x} {act}", "level": "act"}
PLAIN = {"id": "heat/plain", "sql": "PLAIN_SQL", "message": "plain {x}", "level": "act"}


def run(rules, profiles):
    calls, notified = [], []

    class Cur:
        def execute(self, sql, args=None):
            calls.append((sql, args))

        def fetchone(self):
            return {"id": 812} if calls[-1][0].startswith("INSERT") else None

    class Con:
        def cursor(self):
            return contextlib.nullcontext(Cur())

    @contextlib.contextmanager
    def db():
        yield Con()

    class NS:
        pass

    packs, index, events_pg, settings, log = NS(), NS(), NS(), NS(), NS()
    packs.load_rules = lambda: rules
    packs.emit = lambda *a: None
    index.run_ro = lambda cur, sql: [{"sensor_id": "s", "x": 1}]
    settings.get = lambda k, d=None: d
    settings.num = lambda k, d=0: d
    log.warning = log.info = lambda *a: None
    os.environ["COMPOSE_PROFILES"] = profiles
    g = dict(packs=packs, index=index, events_pg=events_pg, settings=settings, log=log, db=db, _act=actions, os=os, buttons=buttons, json=json,
             notify=lambda lvl, text, keyboard=None, home="": notified.append(text),
             _alert_home=lambda issue: "", run_report=lambda cur: None, _quiet=lambda lvl: False,
             LOCALE=lambda: "en", _local_now=lambda: "now")
    exec(code, g)
    g["run_rules"]()
    return calls, notified


calls, notified = run([ACT], "agent")
assert notified == ["go 1 /act 812"], notified
stored = [a for s, a in calls if s.startswith("UPDATE alerts")]
assert stored and stored[-1][0] == "go 1 /act 812" and stored[-1][1] == 812, f"the stored text carries the id: {calls}"
print("  {act} with the bot: the message and the stored row say /act 812")

calls, notified = run([ACT], "")
assert notified == ["go 1 planetai act 812"], notified
print("  {act} without the bot: planetai act 812")

calls, notified = run([PLAIN], "agent")
assert notified == ["plain 1"], notified
assert not any(s.startswith("UPDATE alerts") for s, _ in calls), "a message without {act} is written once, as before"
ins = [a for s, a in calls if s.startswith("INSERT INTO alerts")]
assert ins and ins[0][3] == "plain 1", ins
print("  no {act}: inserted once, unchanged")

# tools/check_rules.py on a pack whose message has {act} and whose SQL returns only x
tmp = pathlib.Path(tempfile.mkdtemp())
try:
    shutil.copy(ROOT / "init.sql", tmp / "init.sql")
    (tmp / "packs" / "p").mkdir(parents=True)
    (tmp / "packs" / "p" / "rules.yml").write_text(
        "- id: r\n  level: warn\n  sql: SELECT 'node' AS sensor_id, 1 AS x FROM readings\n"
        "  message:\n    en: \"go {x} {act}\"\n")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check_rules.py")], cwd=tmp, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
finally:
    shutil.rmtree(tmp)
print("  check_rules accepts {act} as a placeholder the node fills")

# Where the bot does not run, {act} reads `planetai act 812`, and a message that asks for "your words" gets them
# unquoted. Every word after the id is the note, not only the first.
STUBS = r'''
curl() { while [ $# -gt 0 ]; do [ "$1" = -d ] && printf '%s' "$2" > "$OUT"; shift; done; }
envget() { :; }; port() { echo 8080; }; say() { :; }; warn() { :; }; api() { :; }; json() { :; }
'''


def cli_note(*args):
    out = pathlib.Path(tempfile.mkdtemp()) / "body.json"
    fn = re.search(r"^cmd_act\(\) \{.*?^\}", (ROOT / "bin" / "planetai").read_text(), re.S | re.M).group(0)
    subprocess.run(["bash", "-c", STUBS + fn + '\ncmd_act "$@"', "x", *args], env={**os.environ, "OUT": str(out)},
                   check=True, capture_output=True)
    return json.loads(out.read_text())["note"]


assert cli_note("812", "Uluwatu", "good,", "head", "high") == "Uluwatu good, head high", cli_note("812", "Uluwatu", "good")
assert cli_note("812", "closed the windows") == "closed the windows", "a quoted note is kept as it was"
assert cli_note("812") == "acted", "no words keeps the old default"
print("  planetai act 812 <words>: every word is the note")
print("test_rule_act_placeholder: all checks passed")
