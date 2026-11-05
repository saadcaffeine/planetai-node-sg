"""POST /actions with a `choice` (a pack button's answer, app/buttons.py): the endpoint refuses a value the alert did not
offer (400), an unknown alert (404) and an alert older than 72 hours (409); takes the stage from the button and
ignores a sent one; keeps DECISION_REQUIRED for `acted` buttons only; writes one row per (alert, actor, choice), where
a repeat tap with no words changes nothing and a later note replaces the earlier one. `action` is lifted from
app/main.py by AST against a fake cursor, as tests/test_rule_buttons.py lifts run_rules (importing main starts a second
MQTT client); `buttons` is the real module. Run: PYTHONPATH=app python3 tests/test_action_choice.py
"""
import ast
import contextlib
import pathlib
import sys
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import buttons  # noqa: E402

tree = ast.parse((ROOT / "app" / "main.py").read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "action")
fn.decorator_list = []                    # the route's decorator needs the app; the function does not
NS = {"HTTPException": HTTPException, "Request": object, "Header": lambda d: d, "buttons": buttons,
      "datetime": datetime, "timezone": timezone, "_is_local": lambda r: True}
exec(compile(ast.Module([fn], []), "action", "exec"), NS)
action = NS["action"]

NOW = datetime.now(timezone.utc)
BTNS = [[{"text": {"en": "Uluwatu 👍"}, "value": "good", "stage": "acted", "ask": None}],
        [{"text": {"en": "Didn't go"}, "value": "didnt-go", "stage": "acknowledged", "ask": None}]]


def run(body, *, alert="open", existing=None, decided=False, required=0):
    """action() against a database with one alert; returns (result or the HTTPException, the writes it made)."""
    calls = []
    row = {"open": {"buttons": BTNS, "ts": NOW - timedelta(hours=1)},
           "old": {"buttons": BTNS, "ts": NOW - timedelta(hours=73)}, "none": None}[alert]

    class Cur:
        def execute(self, sql, args=None):
            calls.append((sql, args))

        def fetchone(self):
            sql = calls[-1][0]
            if "FROM alerts" in sql:
                return row
            if "stage = 'decided'" in sql:
                return {"?column?": 1} if decided else None
            return existing                               # SELECT note FROM actions

    class Con:
        def cursor(self):
            return contextlib.nullcontext(Cur())

    @contextlib.contextmanager
    def db():
        yield Con()

    class Settings:
        num = staticmethod(lambda key, default: required)

    NS.update(db=db, settings=Settings)
    try:
        out = action(body, None, "")
    except HTTPException as e:
        out = e
    return out, [c for c in calls if c[0].startswith(("INSERT", "UPDATE"))]


def refused(out, writes, code, detail=None):
    assert isinstance(out, HTTPException) and out.status_code == code and not writes, (out, writes)
    assert detail is None or out.detail == detail, out.detail


ANA = {"alert_id": 7, "choice": "good", "actor": "Ana"}

refused(*run({**ANA, "choice": "nope"}), 400, "that answer was not offered")
refused(*run(ANA, alert="old"), 409, "this question has closed")
refused(*run(ANA, alert="none"), 404, "no such alert")
print("  refused: a value not offered (400), an unknown alert (404), an alert past 72 hours (409); nothing written")

# the button sets the stage; a stage in the body is ignored
out, writes = run({**ANA, "stage": "acknowledged"})
assert out == {"ok": True} and len(writes) == 1 and writes[0][0].startswith("INSERT INTO actions"), (out, writes)
assert writes[0][1] == (7, "acted", "Ana", "", "good"), writes
out, writes = run({"alert_id": 7, "choice": "didnt-go", "actor": "Ana", "stage": "acted"})
assert writes[0][1] == (7, "acknowledged", "Ana", "", "didnt-go"), writes
print("  inserted: the stage is the button's, a sent one is ignored")

# the actor is cut to 80 and the note to 500, as for a typed answer
out, writes = run({**ANA, "actor": "A" * 90, "note": "n" * 600})
assert writes[0][1] == (7, "acted", "A" * 80, "n" * 500, "good"), writes[0][1][:3]

# DECISION_REQUIRED stops an `acted` button until a decision is recorded, and never an acknowledged one
refused(*run(ANA, required=1), 409)
assert "DECISION_REQUIRED" in run(ANA, required=1)[0].detail
out, writes = run(ANA, required=1, decided=True)
assert out == {"ok": True} and len(writes) == 1, (out, writes)
out, writes = run({"alert_id": 7, "choice": "didnt-go", "actor": "Ana"}, required=1)
assert out == {"ok": True} and writes[0][1][1] == "acknowledged", (out, writes)
print("  DECISION_REQUIRED: only an acted button needs a decision first")

# one row per (alert, actor, choice): a repeat with no words is kept, a note replaces the note, never a second row
out, writes = run(ANA, existing={"note": ""})
assert out == {"ok": True, "kept": True} and not writes, (out, writes)
out, writes = run({**ANA, "note": "head high"}, existing={"note": ""})
assert out == {"ok": True} and len(writes) == 1 and writes[0][0].startswith("UPDATE actions SET note"), (out, writes)
assert writes[0][1] == ("head high", 7, "Ana", "good"), writes
out, writes = run({**ANA, "note": "chest high"}, existing={"note": "head high"})
assert writes[0][1] == ("chest high", 7, "Ana", "good"), "the later note replaces the earlier one"
out, writes = run({**ANA, "actor": "Ben"})
assert writes[0][0].startswith("INSERT") and writes[0][1][2] == "Ben", "a second person's tap is a second row"
print("  one row per actor and choice: a repeat is kept, a later note replaces the note")
print("test_action_choice: all checks passed")
