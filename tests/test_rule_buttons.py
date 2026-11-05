"""A rule may return a `buttons` column (app/buttons.py is its contract). run_rules stores the normalized rows with the
alert, never lets the column into the message, and sends them as a Telegram keyboard only when the alert is sent and
the bot has announced itself (TELEGRAM_BUTTONS=1). An invalid column costs the alert its buttons, never the alert
(Review Focus 2). run_rules is exec'd from app/main.py's source against fakes, as in test_rule_act_placeholder
(importing main starts a second MQTT client); `buttons` is the real module. tools/check_rules.py must accept a rule
whose SQL returns `buttons`. Run: PYTHONPATH=app python3 tests/test_rule_buttons.py
"""
import ast
import contextlib
import json
import logging
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

warnings = []                           # buttons.normalize's one warning per bad column, caught here so the output stays clean
buttons.log.addHandler(type("H", (logging.Handler,), {"emit": lambda self, r: warnings.append(r.getMessage())})())
buttons.log.propagate = False

RULE = {"id": "surf/tomorrow", "sql": "SQL", "message": "go {x}", "level": "act"}
GOOD = [[{"text": {"en": "Uluwatu 👍", "es": "Uluwatu"}, "value": "uluwatu:good"}]]
NORMAL = [[{"text": {"en": "Uluwatu 👍", "es": "Uluwatu"}, "value": "uluwatu:good", "stage": "acted", "ask": None}]]


def run(row, tg, level="act", quiet=False):
    calls, sent, warned = [], [], []

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
    packs.load_rules = lambda: [{**RULE, "level": level}]
    packs.emit = lambda *a: None
    index.run_ro = lambda cur, sql: [row]
    settings.get = lambda k, d=None: d
    settings.num = lambda k, d=0: tg if k == "TELEGRAM_BUTTONS" else d
    log.warning = log.info = lambda *a: warned.append(a)
    os.environ["COMPOSE_PROFILES"] = "agent"
    g = dict(packs=packs, index=index, events_pg=events_pg, settings=settings, log=log, db=db, _act=actions, os=os,
             buttons=buttons, json=json,
             notify=lambda lvl, text, keyboard=None, home="": sent.append((text, keyboard)),
             _alert_home=lambda issue: "", run_report=lambda cur: None, _quiet=lambda lvl: quiet,
             LOCALE=lambda: "en", _local_now=lambda: "now")
    exec(code, g)
    g["run_rules"]()
    ins = [a for s, a in calls if s.startswith("INSERT INTO alerts")]
    assert len(ins) == 1 and len(ins[0]) == 5, calls
    return ins[0], sent


def row(**kw):
    return {"sensor_id": "s", "x": 1, **kw}


ins, sent = run(row(buttons=json.dumps(GOOD)), 1)
assert json.loads(ins[4]) == NORMAL, ins
assert sent == [("go 1", [[{"text": "Uluwatu 👍", "callback_data": "al:812:uluwatu:good"}]])], sent
assert "uluwatu" not in sent[0][0] and "{" not in sent[0][0], "the column is not part of the message"
print("  buttons + TELEGRAM_BUTTONS=1: stored normalized, sent as al:<id>:<value>, the text has no JSON")

ins, sent = run(row(buttons=GOOD), 1)
assert json.loads(ins[4]) == NORMAL and sent[0][1] is not None, "a driver may hand back parsed JSON, not a string"
print("  buttons already parsed (a JSONB column): the same")

ins, sent = run(row(buttons=json.dumps(GOOD)), 0)
assert json.loads(ins[4]) == NORMAL and sent == [("go 1", None)], (ins, sent)
print("  TELEGRAM_BUTTONS=0: stored, sent bare")

ins, sent = run(row(buttons=json.dumps(GOOD)), 1, level="info")
assert json.loads(ins[4]) == NORMAL and sent == [], "an alert that is not sent has no keyboard to send"
print("  not sent (info): stored, nothing goes out")

for bad in ("not json", json.dumps([[{"text": "x", "value": "BAD VALUE"}]]), json.dumps([[{"text": "x", "value": "a"}]] * 9)):
    warnings.clear()
    ins, sent = run(row(buttons=bad), 1)
    assert len(warnings) == 1, (bad, warnings)
    assert ins[4] is None and len(sent) == 1 and sent[0][1] is None and sent[0][0] == "go 1", (bad, ins, sent)
print("  invalid buttons (not JSON, bad value, 9 rows): stored without, sent once, no keyboard")

ins, sent = run(row(), 1)
assert ins[4] is None and sent == [("go 1", None)], (ins, sent)
ins, sent = run(row(buttons=None), 1)
assert ins[4] is None and sent == [("go 1", None)], (ins, sent)
print("  no buttons: stored NULL, sent as before")

# tools/check_rules.py on a pack whose SQL returns `buttons` and whose message never names it
tmp = pathlib.Path(tempfile.mkdtemp())
try:
    shutil.copy(ROOT / "init.sql", tmp / "init.sql")
    (tmp / "packs" / "p").mkdir(parents=True)
    (tmp / "packs" / "p" / "rules.yml").write_text(
        "- id: r\n  level: warn\n  sql: SELECT 'node' AS sensor_id, 1 AS x, '[]' AS buttons FROM readings\n"
        "  message:\n    en: \"go {x}\"\n")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check_rules.py")], cwd=tmp, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
finally:
    shutil.rmtree(tmp)
print("  check_rules accepts a rule whose SQL returns buttons")
print("test_rule_buttons: all checks passed")
