"""events_pg without a database: rule rows become Candidates, and settings become a Policy.
Run: PYTHONPATH=app python3 tests/test_events_pg.py
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
import events_pg as P  # noqa: E402

rule = {"id": "heat/heat_sustained", "kind": "sustained", "issue": "heat", "level": "act"}
rows = [{"sensor_id": "sc-1", "name": "K ROOM", "value": 36.1, "line": 35, "over": True},
        {"sensor_id": "sc-2", "name": "L ROOM", "value": 34.5, "line": 35, "over": False}]
cs = P.candidates(rule, rows)
assert [(c.room, c.over) for c in cs] == [("K ROOM", True), ("L ROOM", False)], cs
assert cs[0].issue == "heat" and cs[0].kind == "sustained" and cs[0].where == "inside"
assert P.candidates({"id": "air-quality/x", "level": "act"}, rows) == [], "a rule without kind: is report-only"
print("  rows of a kinded rule become candidates; a rule without kind: gives none")

rule2 = {"id": "air-quality/air_spike", "kind": "spike", "level": "warn"}
c2 = P.candidates(rule2, [{"sensor_id": "o", "name": "OUT", "value": 40, "line": 12, "over": True, "where": "outside"}])
assert c2[0].issue == "air" and c2[0].where == "outside", "issue defaults from the pack's domain; where passes through"
print("  issue defaults from the pack (air-quality -> air); where passes through")

os.environ.update(QUIET_HOURS="1", QUIET_FROM="22", QUIET_TO="6", ALERT_MAX_PER_DAY="4", ALERT_LEVEL="warn")
pol = P.policy()
assert pol.quiet == (22, 6) and pol.max_per_day == 4 and pol.alert_level == "warn", pol
os.environ["QUIET_HOURS"] = "0"
assert P.policy().quiet is None
print("  candidates from kinded rules, a Policy from settings")

class Cur:
    def __init__(self, has):
        self.has, self.sql = has, []

    def execute(self, sql, args=()):
        self.sql.append((sql, args))

    def fetchone(self):
        return {"?column?": 1} if self.has else None


c = Cur(True)
P.answer(c, 7, "dismissed", "tomas", "ran the AC instead")
ins = c.sql[-1]
assert ins[0].startswith("INSERT INTO actions (event_id, stage, actor, note)") and ins[1] == (7, "dismissed", "tomas", "ran the AC instead"), ins
for bad_stage in ("decided", "measured", "settings", None):
    try:
        P.answer(Cur(True), 7, bad_stage, "t", "")
        raise SystemExit(f"stage {bad_stage!r} must be refused for an event")
    except ValueError:
        pass
for bad_id in (True, "7; DROP", None, 1.5):
    try:
        P.answer(Cur(True), bad_id, "acted", "t", "")
        raise SystemExit(f"event_id {bad_id!r} must be refused")
    except ValueError:
        pass
try:
    P.answer(Cur(False), 7, "acted", "t", "")
    raise SystemExit("an event this node does not have must be a LookupError")
except LookupError:
    pass
P.answer(c, "8", "acted", "x" * 200, "y" * 900)
assert c.sql[-1][1] == (8, "acted", "x" * 80, "y" * 500), "a numeric string id is fine; actor and note are capped"
print("  answer: Done, Not now and Doesn't fit write one actions row; any other stage, a bad id or no event is refused")

print("events_pg: candidates from kinded rules, a Policy from settings")
