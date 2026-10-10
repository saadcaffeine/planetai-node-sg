# Dashboard events, part A: events on the wire — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /issues` carries the open alert events, the event-led headline and everything the page's event card
needs, and `POST /actions` records Done / Not now / Doesn't fit against an event, so Plan 2's bot and the v0.78 page
both build on one server piece.

**Architecture:** A new module `app/events_wire.py` holds a pure `build()` (rows in, wire block out, tested on both
the live shape and the captured shape) and a `live()` that does the reads on the `/issues` route's cursor. The issues
engine takes the finished block as an input (`compute(events=…)`), ranks the headline from it and adds
`uncovered_asks`. A replay passes the block the fixture captured. `events_pg.answer()` writes a button press, and
`app/main.py`'s `POST /actions` routes an `event_id` to it.

**Tech stack:** Python 3.11 app (FastAPI, psycopg 3, dict rows), Postgres 16 + PostGIS, plain-`assert` test
scripts run by `tests/all`.

**Spec:** `docs/SPEC_dashboard_events.md`, §3 (the server piece), and §5 for the states the block must let the page
tell apart. Read §3 in full before Task 1.

## Global constraints

- Work in your own git worktree off `origin/main`, never in `planetai-node-main`, which holds `main`.
- Never import app `main` in a test or a container: it starts a second MQTT client and kicks node #1 off its broker.
- `make lint && make test` before every commit. The pre-commit hook runs both, and a commit takes about two minutes.
- No change to `init.sql`: every column used here already exists in schema 0.53 (`actions.event_id`, `dismissed`,
  `alert_events`, `event_messages`). A change there needs two maintainers (`GOVERNANCE.md`).
- No change under `app/static/` or `packs/`. This is v0.77 server work. The page is part B, in v0.78
  (`docs/NEXT_RELEASE.md` rule 2).
- `tests/all`'s suite count is hand-written. Task 2 raises it from 63 to 64. Before merging, check that no other open
  PR changes it (`docs/NEXT_RELEASE.md` rule 1).
- A test file ends in `sys.exit(...)` in some suites, and anything appended below that never runs. Add checks above
  the last line.
- Timestamps: live rows are `datetime`, captured rows are ISO strings. Every function here takes both.
- The page computes nothing from this block. Every number and sentence the card draws is in it.

## Files

| file | what changes |
|---|---|
| `app/actions.py` | `BUTTONS`: the three button labels in en, id and es |
| `app/events_wire.py` (new) | `engine_of`, `build` (pure) and `live` (the reads) |
| `app/issues/engine.py` | `compute(events=…)`, `_lead` led by an open event, `uncovered_asks`, the `events` key; `replay` passes the captured block |
| `app/issues/__init__.py` | `HEADLINE_RULE` gains its first sentence, in three languages |
| `app/issues/api.py` | `issues_now` builds the block and passes it to `compute` |
| `app/events_pg.py` | `answer()`: one button press, one `actions` row |
| `app/main.py` | `POST /actions` routes an `event_id`; `GET /actions?events=1` |
| `tests/test_events_wire.py` (new) | `build`, the headline, the replay |
| `tests/test_events_pg.py` | `answer` |
| `tests/test_actions.py` | `BUTTONS` |
| `tests/all` | the new suite, and the count 63 → 64 |
| `tests/data/wire/issues-v0.json` | `events` added, by `tools/check_wire.py --update` |
| `docs/site/api.md`, `CHANGELOG.md` | the new key, the two route changes, and the Unreleased line |

---

### Task 1: the button labels

**Files:**
- Modify: `app/actions.py` (add after the module docstring's imports)
- Test: `tests/test_actions.py` (add above the last `print`)

**Interfaces:**
- Produces: `actions.BUTTONS: dict[str, dict[str, str]]`, keyed by locale (`en`, `id`, `es`), each
  `{"done", "not_now", "doesnt_fit"}`. Task 2 reads it, and Plan 2's bot will too.

- [ ] **Step 1: Write the failing test.** In `tests/test_actions.py`, above the final
  `print("actions: one action per event…")`:

```python
for loc in ("en", "id", "es"):
    b = A.BUTTONS[loc]
    assert set(b) == {"done", "not_now", "doesnt_fit"} and all(isinstance(v, str) and v for v in b.values()), (loc, b)
assert A.BUTTONS["en"] == {"done": "Done", "not_now": "Not now", "doesnt_fit": "Doesn't fit"}
print("  buttons: Done / Not now / Doesn't fit in en, id and es, one table for the bot and the page")
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PYTHONPATH=app python3 tests/test_actions.py`
  Expected: `AttributeError: module 'actions' has no attribute 'BUTTONS'`

- [ ] **Step 3: Add the table** to `app/actions.py`, after `from __future__ import annotations`:

```python
# The three answers to an event (docs/SPEC_alerts.md §7), in the household's language. One table, so the dashboard's
# buttons and the bot's say the same words: the page holds no copy (docs/SPEC_dashboard_events.md §4.4).
BUTTONS = {
    "en": {"done": "Done", "not_now": "Not now", "doesnt_fit": "Doesn't fit"},
    "id": {"done": "Selesai", "not_now": "Nanti dulu", "doesnt_fit": "Tidak cocok"},
    "es": {"done": "Hecho", "not_now": "Ahora no", "doesnt_fit": "No encaja"},
}
```

- [ ] **Step 4: Run it and watch it pass.**
  Run: `PYTHONPATH=app python3 tests/test_actions.py`
  Expected: ends with `actions: one action per event, chosen from the context; messages in three languages`

- [ ] **Step 5: Commit.**

```bash
git add app/actions.py tests/test_actions.py
git commit -m "events: the three button labels, one table for the bot and the page"
```

Ask Tomas to confirm the Indonesian and Spanish labels in the PR. They are a first draft.

---

### Task 2: the events block, as a pure function

**Files:**
- Create: `app/events_wire.py`
- Create: `tests/test_events_wire.py`
- Modify: `tests/all` (one suite line, count 63 → 64)

**Interfaces:**
- Consumes: `actions.BUTTONS` (Task 1).
- Produces:
  - `events_wire.ENGINES = ("rules", "shadow", "events")`
  - `events_wire.engine_of(value) -> str`: anything not in `ENGINES` is `"rules"`.
  - `events_wire.rank(row: dict) -> tuple`: lower sorts first.
  - `events_wire.build(engine: str, events: list[dict], messages: list[dict], answers: list[dict], covered: dict[int, list[int]], contexts: dict[int, dict], decl: dict, locale: str, now: datetime, tz=None) -> dict`
  - The returned block's keys are `engine, buttons, open, recent, cleared_today, last_cleared`. Task 4 adds
    `uncovered_asks`.

**Inputs `build` takes:**
- `events`: `alert_events` rows with `id, issue, kind, level, opened_at, last_seen_at, cleared_at, peak, rooms, places, action_id`.
- `messages`: `event_messages` rows with `event_id, ts, text, sent, action_id`.
- `answers`: `actions` rows with `event_id, ts, stage, actor`.
- `contexts`: per open event id, `events_pg.context`'s dict plus `usual`.

- [ ] **Step 1: Write the failing test** as `tests/test_events_wire.py`:

```python
"""The events block of GET /issues, without a database (docs/SPEC_dashboard_events.md §3.1).
The same rows as a live node hands them over (datetimes) and as a capture holds them (ISO strings) must give one block.
Run: PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
os.environ.setdefault("PACKS_DIR", "packs")
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
sys.path.insert(0, str(ROOT / "app"))
import events_wire as W  # noqa: E402

UTC = dt.timezone.utc
BALI = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 10, 5, 7, 0, tzinfo=UTC)            # 15:00 in Bali
DECL = {"heat": {"metric": "apparent", "line": {"value": 35.0}}, "air": {"metric": "pm25", "line": {"value": 15.0}}}
H = dt.timedelta(hours=1)


def ev(i, issue, kind, opened, cleared=None, action_id=None):
    return {"id": i, "issue": issue, "kind": kind, "level": "act", "opened_at": opened, "last_seen_at": opened,
            "cleared_at": cleared, "peak": 35.8, "rooms": ["L ROOM", "K ROOM"], "places": ["inside"],
            "action_id": action_id}


EVENTS = [ev(1, "heat", "sustained", NOW - 2 * H, action_id="heat/open_up"),
          ev(2, "air", "danger", NOW - H),
          ev(3, "heat", "unusual", NOW - 3 * H),
          ev(4, "air", "spike", NOW - 20 * H, cleared=NOW - 19 * H),          # 20:00 Bali yesterday: not today
          ev(5, "heat", "sustained", NOW - 8 * H, cleared=NOW - 5 * H),       # 10:00 Bali today
          ev(6, "air", "spike", NOW - 9 * 24 * H, cleared=NOW - 8 * 24 * H)]  # older than 7 days: dropped
MESSAGES = [{"event_id": 1, "ts": NOW - 2 * H, "text": "Hot inside.\n\n👉 Open up now: outside is 29.1 °C.",
             "sent": True, "action_id": "heat/open_up"},
            {"event_id": 1, "ts": NOW - H, "text": "Still hot inside.\n\n👉 Open up now: outside is 28.0 °C.",
             "sent": False, "action_id": "heat/open_up"},
            {"event_id": 5, "ts": NOW - 5 * H, "text": "Cooler now.", "sent": True, "action_id": None}]
ANSWERS = [{"event_id": 1, "ts": NOW - 90 * dt.timedelta(minutes=1), "stage": "acknowledged", "actor": "tomas"},
           {"event_id": 2, "ts": NOW - 30 * dt.timedelta(minutes=1), "stage": "acknowledged", "actor": "ana"},
           {"event_id": 5, "ts": NOW - 6 * H, "stage": "acted", "actor": "tomas"}]
COVERED = {1: [578, 571], 2: [], 3: [], 4: [], 5: [500]}
CONTEXTS = {1: {"inside_temp": 35.8, "outside_temp": 29.1, "outside_pm25": 12.0, "outside_source": "outside",
                "usual": 33.4},
            2: {"inside_pm25": 140.0, "outside_pm25": 12.0, "outside_source": "outside", "usual": 9.0},
            3: {"usual": None}}


def iso(rows):
    return [{k: (v.isoformat() if isinstance(v, dt.datetime) else v) for k, v in r.items()} for r in rows]


live = W.build("events", EVENTS, MESSAGES, ANSWERS, COVERED, CONTEXTS, DECL, "en", NOW, BALI)
captured = W.build("events", iso(EVENTS), iso(MESSAGES), iso(ANSWERS), COVERED, CONTEXTS, DECL, "en", NOW, BALI)
assert json.dumps(live, sort_keys=True) == json.dumps(captured, sort_keys=True), "live and captured rows differ"
json.dumps(live)                                            # every value is JSON: no datetime, no set
print("  a live row (datetimes) and a captured row (ISO strings) give one block, and it is all JSON")

assert [e["id"] for e in live["open"]] == [2, 1, 3], "danger first, then sustained, then unusual"
assert [e["id"] for e in live["recent"]] == [5, 4], "cleared in 7 days, newest first; older dropped"
print("  open: danger > sustained > unusual; recent: 7 days, newest first")

one = live["open"][1]
assert one["action"] == {"id": "heat/open_up", "text": "Open up now: outside is 28.0 °C."}, one["action"]
assert one["message"]["text"].startswith("Still hot") and one["message"]["sent"] is False, one["message"]
assert one["line"] == 35.0 and one["rooms"] == ["K ROOM", "L ROOM"] and one["alerts"] == [571, 578]
assert one["context"] == {"usual": 33.4, "outside": 29.1, "outside_metric": "temp", "outside_from": "outside"}
assert live["open"][0]["context"]["outside"] == 12.0 and live["open"][0]["context"]["outside_metric"] == "pm25"
assert live["open"][2]["action"] is None and live["open"][2]["message"] is None
print("  the action is the line as sent; the message is the latest; heat's outside is the air temperature")

held = (NOW - 90 * dt.timedelta(minutes=1) + 3 * H).isoformat()
assert one["answer"] == {"stage": "acknowledged", "actor": "tomas", "ts": (NOW - 90 * dt.timedelta(minutes=1)).isoformat(),
                         "held_until": held}, one["answer"]
assert live["open"][0]["answer"]["held_until"] is None, "Not now never holds a danger event"
assert live["recent"][0]["cleared_after_min"] == 60, live["recent"][0]
assert "context" not in live["recent"][0]
print("  Not now holds for 3 h except at danger; a Done followed by a clear says how long it took")

assert live["cleared_today"] == 1 and live["last_cleared"] == {"issue": "heat", "ts": (NOW - 5 * H).isoformat()}
print("  cleared today counts the node's local day, not UTC's")

assert live["buttons"] == {"done": "Done", "not_now": "Not now", "doesnt_fit": "Doesn't fit"}
assert W.build("events", [], [], [], {}, {}, DECL, "xx", NOW)["buttons"]["done"] == "Done", "unknown locale: en"
rules = W.build("rules", EVENTS, MESSAGES, ANSWERS, COVERED, CONTEXTS, DECL, "en", NOW, BALI)
assert rules["open"] == [] and rules["engine"] == "rules" and len(rules["recent"]) == 2
assert W.engine_of("shadow") == "shadow" and W.engine_of("typo") == "rules" and W.engine_of(None) == "rules"
print("  on rules nothing is open (the engine is not running); a typo behaves as rules")
print("events_wire: the open events, their actions as sent, answers and holds, the local day")
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py`
  Expected: `ModuleNotFoundError: No module named 'events_wire'`

- [ ] **Step 3: Write `app/events_wire.py`:**

```python
"""The alert events as GET /issues carries them (docs/SPEC_dashboard_events.md §3.1).

`build` is pure, so a live node (datetimes) and a capture (ISO strings) go through the same code and are tested apart.
`live` (Task 3) is the reads, on the cursor the /issues route already has open. The page computes nothing from this
block: every number and sentence the event card draws is here.
"""
from __future__ import annotations

import datetime as dt

import actions as A

ENGINES = ("rules", "shadow", "events")
ORDER = ("danger", "sustained", "unusual", "spike", "ahead")   # which open event leads (§3.1)
HOLD = dt.timedelta(hours=3)                                   # Not now: docs/SPEC_alerts.md §7
RECENT = dt.timedelta(days=7)                                  # Act's record (§4.3)
OUTSIDE = {"apparent": "temp", "temp": "temp", "pm25": "pm25"}  # an issue's metric -> events_pg.context's outside_*
SENT_ACTION = "\n\n👉 "                                         # how actions.render puts the action under the story


def engine_of(value) -> str:
    """run_rules' own reading of ALERT_ENGINE: anything else behaves as rules."""
    return value if value in ENGINES else "rules"


def _t(v):
    if v is None or isinstance(v, dt.datetime):
        return v
    return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _iso(v):
    v = _t(v)
    return v.isoformat() if v else None


def _latest(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        k = r["event_id"]
        if k not in out or _t(r["ts"]) > _t(out[k]["ts"]):
            out[k] = r
    return out


def rank(row: dict) -> tuple:
    """Lower sorts first: the most serious kind, then the one open longest."""
    k = row["kind"]
    return (ORDER.index(k) if k in ORDER else len(ORDER), _t(row["opened_at"]))


def _answer(a: dict | None, kind: str) -> dict | None:
    if not a:
        return None
    held = _t(a["ts"]) + HOLD if a["stage"] == "acknowledged" and kind != "danger" else None
    return {"stage": a["stage"], "actor": a.get("actor"), "ts": _iso(a["ts"]), "held_until": _iso(held)}


def build(engine, events, messages, answers, covered, contexts, decl, locale, now, tz=None) -> dict:
    tz = tz or now.tzinfo or dt.timezone.utc
    last_msg = _latest(messages)
    last_act = _latest([m for m in messages if m.get("action_id")])
    last_ans = _latest(answers)
    opened, recent, cleared_today, last = [], [], 0, None
    for e in events:
        eid, cleared = e["id"], _t(e.get("cleared_at"))
        if cleared is not None and now - cleared > RECENT:
            continue
        if cleared is None and engine == "rules":
            continue                     # the engine is not running: an event a shadow spell left open is not open
        issue = decl.get(e["issue"]) or {}
        m, am, a = last_msg.get(eid), last_act.get(eid), last_ans.get(eid)
        said = (am.get("text") or "") if am else ""
        row = {"id": eid, "issue": e["issue"], "kind": e["kind"], "level": e["level"],
               "opened_at": _iso(e["opened_at"]), "last_seen_at": _iso(e["last_seen_at"]), "cleared_at": _iso(cleared),
               "peak": e.get("peak"), "line": (issue.get("line") or {}).get("value"),
               "rooms": sorted(e.get("rooms") or []), "places": sorted(e.get("places") or []),
               "action": ({"id": am["action_id"], "text": said.split(SENT_ACTION, 1)[1] if SENT_ACTION in said else None}
                          if am else None),
               "message": {"text": m.get("text"), "ts": _iso(m["ts"]), "sent": bool(m.get("sent"))} if m else None,
               "alerts": sorted(covered.get(eid) or []),
               "answer": _answer(a, e["kind"])}
        if cleared is None:
            ctx, key = contexts.get(eid) or {}, OUTSIDE.get(issue.get("metric"))
            row["context"] = {"usual": ctx.get("usual"), "outside": ctx.get(f"outside_{key}") if key else None,
                              "outside_metric": key, "outside_from": ctx.get("outside_source")}
            opened.append(row)
            continue
        if a and a["stage"] == "acted" and cleared > _t(a["ts"]):
            row["cleared_after_min"] = round((cleared - _t(a["ts"])).total_seconds() / 60)
        recent.append(row)
        if cleared.astimezone(tz).date() == now.astimezone(tz).date():
            cleared_today += 1
            if last is None or cleared > _t(last["ts"]):
                last = {"issue": e["issue"], "ts": cleared.isoformat()}
    opened.sort(key=rank)
    recent.sort(key=lambda r: _t(r["opened_at"]), reverse=True)
    return {"engine": engine, "buttons": A.BUTTONS.get(locale) or A.BUTTONS["en"],
            "open": opened, "recent": recent, "cleared_today": cleared_today, "last_cleared": last}
```

- [ ] **Step 4: Run it and watch it pass.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py`
  Expected: ends with `events_wire: the open events, their actions as sent, answers and holds, the local day`

  If `cleared_after_min` is not 60: event 5 was answered `acted` at `NOW - 6h` and cleared at `NOW - 5h`, so 60 is
  right and `build` is wrong.

- [ ] **Step 5: Register the suite** in `tests/all`. After the line
  `test_actions|PYTHONPATH=app python3 tests/test_actions.py`, add:

```
test_events_wire|PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py
```

  Then change `if [ "$total" -ne 63 ]; then` to `if [ "$total" -ne 64 ]; then`, and update any count of suites in
  that file's comments or in `docs/DEVELOPING.md` that says 63. Find them with
  `grep -rn "\b63\b" tests/all docs/DEVELOPING.md`.

- [ ] **Step 6: Run the whole suite.**
  Run: `make test`
  Expected: `64 suites`, all passing.

- [ ] **Step 7: Commit.**

```bash
git add app/events_wire.py tests/test_events_wire.py tests/all
git commit -m "events: the /issues events block, built the same from a live node and a capture"
```

---

### Task 3: the reads, on the `/issues` cursor

**Files:**
- Modify: `app/events_wire.py` (add `live` and its helpers below `build`)
- Test: `tests/test_events_wire.py` (add above the last `print`)

**Interfaces:**
- Consumes: `events_pg.context(cur, e, now) -> dict` (reads `e.rooms`, `e.where`, `e.kind`), and
  `events_pg.PACK_ISSUE`.
- Produces: `events_wire.live(cur, decl: dict, locale: str, now: datetime) -> dict`, the same block `build` returns.

**What this task can and can't prove:** there is no Postgres in CI. This test proves the plumbing: the reads it
makes, what it passes to `build`, and that a failed optional read is `null`, not an exception. Task 8 proves the SQL
on node #1 and node #3.

- [ ] **Step 1: Write the failing test,** above the last `print` of `tests/test_events_wire.py`:

```python
import contextlib  # noqa: E402

class FakeCur:
    """Answers live()'s reads in the order it makes them; `fail` names a statement that raises, as an unpopulated
    usual_by_hour does after a restart."""
    def __init__(self, fail=""):
        self.sql, self.fail, self.last = [], fail, ""
        self.connection = type("C", (), {"transaction": lambda s: contextlib.nullcontext()})()

    def execute(self, sql, args=()):
        self.sql.append(sql)
        self.last = sql
        if self.fail and self.fail in sql:
            raise RuntimeError("materialized view usual_by_hour has not been populated")

    def fetchone(self):
        if "current_setting" in self.last:
            return {"tz": "Asia/Makassar", "hour": 15}
        if "usual_by_hour" in self.last:
            return {"usual": 33.44}
        return {"inside_temp": 35.8, "inside_pm25": None, "outside_temp": 29.1, "outside_pm25": None,
                "outside_source": "outside"}

    def fetchall(self):
        if "FROM alert_events" in self.last:
            return [ev(1, "heat", "sustained", NOW - 2 * H, action_id="heat/open_up")]
        if "FROM alerts" in self.last:
            return [{"id": 578}]
        return []

os.environ["ALERT_ENGINE"] = "shadow"
got = W.live(FakeCur(), DECL, "en", NOW)
assert got["engine"] == "shadow" and [e["id"] for e in got["open"]] == [1], got
assert got["open"][0]["alerts"] == [578] and got["open"][0]["context"]["usual"] == 33.4, got["open"][0]
cold = W.live(FakeCur(fail="usual_by_hour"), DECL, "en", NOW)
assert cold["open"][0]["context"]["usual"] is None and cold["open"][0]["context"]["outside"] == 29.1, cold
print("  live: one read per table, alerts matched per event, a usual_by_hour that fails is null and costs nothing else")
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py`
  Expected: `AttributeError: module 'events_wire' has no attribute 'live'`

- [ ] **Step 3: Add the reads** to `app/events_wire.py`. Add `import logging`, `from types import SimpleNamespace`,
  `from zoneinfo import ZoneInfo` and `import settings` to the imports, `log = logging.getLogger("planetai")` under
  them, and below `build`:

```python
USUAL_SQL = """SELECT avg(u.median) AS usual FROM usual_by_hour u JOIN sensors s USING (sensor_id)
               WHERE u.metric = %s AND u.hour = %s AND (s.name = ANY(%s) OR s.sensor_id = ANY(%s))"""


def _context(cur, P, e: dict, metric: str | None, hour: int, now) -> dict:
    """Inside and outside from the resolver that chose the action, and this room's usual for this local hour. Each is a
    savepoint of its own: usual_by_hour is empty from a start until the app's first refresh, and a context that cannot
    be read is null on the card, not a failed /issues."""
    ctx: dict = {}
    rooms = sorted(e.get("rooms") or [])
    try:
        with cur.connection.transaction():
            ctx = dict(P.context(cur, SimpleNamespace(rooms=set(rooms), where=set(e.get("places") or []),
                                                      kind=e["kind"]), now))
    except Exception as ex:  # noqa: BLE001
        log.warning("event %s: no context (%s)", e["id"], type(ex).__name__)
    ctx["usual"] = None
    try:
        with cur.connection.transaction():
            cur.execute(USUAL_SQL, (metric, hour, rooms, rooms))
            u = (cur.fetchone() or {}).get("usual")
            ctx["usual"] = None if u is None else round(float(u), 1)
    except Exception as ex:  # noqa: BLE001
        log.info("event %s: no usual for this hour (%s)", e["id"], type(ex).__name__)
    return ctx


def live(cur, decl: dict, locale: str, now: dt.datetime) -> dict:
    """The block, read on the /issues route's cursor. The session runs in NODE_TZ (app/main.py), so the hour and the
    zone come from Postgres, the same clock usual_by_hour was bucketed on."""
    import events_pg as P            # noqa: PLC0415 — events_pg imports issues, whose route imports this module
    engine = engine_of(settings.get("ALERT_ENGINE", "rules"))
    cur.execute("SELECT current_setting('TimeZone') AS tz, extract(hour FROM now())::int AS hour")
    r = cur.fetchone()
    try:
        tz = ZoneInfo(r["tz"])
    except Exception:  # noqa: BLE001 — an offset Postgres names that zoneinfo does not: fall back to now's own zone
        tz = None
    cur.execute("SELECT id, issue, kind, level, opened_at, last_seen_at, cleared_at, peak, rooms, places, action_id "
                "FROM alert_events WHERE cleared_at IS NULL OR cleared_at > %s", (now - RECENT,))
    events = [dict(x) for x in cur.fetchall()]
    ids = [e["id"] for e in events]
    cur.execute("SELECT event_id, ts, text, sent, action_id FROM event_messages WHERE event_id = ANY(%s)", (ids,))
    messages = [dict(x) for x in cur.fetchall()]
    cur.execute("SELECT event_id, ts, stage, actor FROM actions WHERE event_id = ANY(%s)", (ids,))
    answers = [dict(x) for x in cur.fetchall()]
    covered, contexts = {}, {}
    for e in events:
        # Until Plan 2 writes alerts.event_id, an event covers its issue's packs' rows inside its own window.
        packs = [p for p, i in P.PACK_ISSUE.items() if i == e["issue"]] or [e["issue"]]
        cur.execute("SELECT id FROM alerts WHERE event_id = %s OR (split_part(rule_id, '/', 1) = ANY(%s) "
                    "AND ts >= %s AND ts <= %s)", (e["id"], packs, e["opened_at"], e["cleared_at"] or now))
        covered[e["id"]] = [x["id"] for x in cur.fetchall()]
        if e["cleared_at"] is None and engine != "rules":
            contexts[e["id"]] = _context(cur, P, e, (decl.get(e["issue"]) or {}).get("metric"), r["hour"], now)
    return build(engine, events, messages, answers, covered, contexts, decl, locale, now, tz)
```

- [ ] **Step 4: Run it and watch it pass.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py`
  Expected: the `live:` line, then the closing line.

- [ ] **Step 5: Commit.**

```bash
git add app/events_wire.py tests/test_events_wire.py
git commit -m "events: read the block on the /issues cursor; a missing usual is null, not an error"
```

---

### Task 4: the engine takes the block — headline, `uncovered_asks`, the wire key, the replay

**Files:**
- Modify: `app/issues/engine.py`: `compute` (signature and return), `_lead`, `replay`
- Modify: `app/issues/__init__.py`: `HEADLINE_RULE`
- Modify: `tests/data/wire/issues-v0.json`, through `python3 tools/check_wire.py --update`
- Test: `tests/test_events_wire.py`

**Interfaces:**
- Consumes: the block from `events_wire.build` / `live` (Tasks 2–3).
- Produces:
  - `engine.compute(..., events: dict | None = None)`, returning a document with top-level `"events"`: the block
    plus `uncovered_asks: list[int]`, or `None`.
  - `engine._lead(out, declared, events=None)`, which returns `{"issue", "by": "event"}` when an open event's issue
    can lead.

- [ ] **Step 1: Write the failing test,** above the last `print` of `tests/test_events_wire.py`:

```python
import issues as I                # noqa: E402
from issues import engine          # noqa: E402


class Settings:
    def get(self, key, default=""):
        return default

    def num(self, key, default):
        return default


SNAP = json.loads((ROOT / "app/issues/fixtures/node1-2026-09-21d.json").read_text())
DECLS = I.load()
plain = engine.replay(json.loads(json.dumps(SNAP)), Settings(), DECLS)
assert plain["events"] is None, "a fixture from before v0.77 replays with no events block: the older-node state"
heroes = [k for k in plain["order"] if plain["issues"][k].get("hero")]
other = next(k for k in heroes if k != plain["headline"])          # an issue that does not lead on its own
asks = [a["id"] for v in plain["issues"].values() for a in (v.get("open_asks") or []) if a.get("id") is not None]
assert asks, "the 21d fixture has open asks; pick another fixture if it ever stops having them"
snap = json.loads(json.dumps(SNAP))
snap["issues"]["events"] = {"engine": "events", "buttons": {}, "recent": [], "cleared_today": 0, "last_cleared": None,
                            "open": [{"id": 9, "issue": other, "kind": "sustained", "opened_at": "2026-09-21T10:00:00+08:00",
                                      "alerts": asks[:1]}]}
led = engine.replay(snap, Settings(), DECLS)
assert led["headline"] == other and led["lead"] == {"issue": other, "by": "event"}, led["lead"]
assert led["events"]["uncovered_asks"] == asks[1:], (led["events"]["uncovered_asks"], asks)
assert led["headline_rule"]["en"].startswith("An open event leads")
print("  replay: a captured block leads the headline with its event; uncovered_asks is every open ask no event covers")

out = {"air": {"hero": {"sign": "a"}, "state": "act", "moved": 0.9}, "heat": {"hero": {"sign": "h"}, "state": "quiet", "moved": 0.0}}
assert engine._lead(out, ["air", "heat"], {"open": [{"issue": "heat"}]}) == {"issue": "heat", "by": "event"}
assert engine._lead(out, ["air", "heat"], {"open": []})["by"] == "state", "nothing open: today's rule"
assert engine._lead(out, ["air", "heat"], {"open": [{"issue": "coast"}]})["issue"] == "air", "no hero: cannot lead"
print("  _lead: an open event's issue leads; with none open, or none that can lead, today's rule stands")
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py`
  Expected: `KeyError: 'events'`

- [ ] **Step 3: Change `_lead`** in `app/issues/engine.py`. The signature becomes `def _lead(out: dict, declared: list[str], events: dict | None = None) -> dict | None:`.
  Add a paragraph to its docstring:

```
    AN OPEN EVENT LEADS FIRST (docs/SPEC_dashboard_events.md §3.1). The bot has interrupted somebody about it, or would
    have in shadow, so the page opens on the same story. `events["open"]` is already ranked (danger, then sustained,
    then unusual, then spike; then the one open longest), so the first whose issue can lead is the lead, `by: event`.
```

  Then, immediately after `if not cands: return None`:

```python
    first = next((e["issue"] for e in ((events or {}).get("open") or []) if e.get("issue") in cands), None)
    if first:
        return {"issue": first, "by": "event"}
```

- [ ] **Step 4: Change `compute`.** Add `events: dict | None = None` as the last keyword of its signature, and this
  line at the end of its docstring:

```
    `events` is the alert events block (app/events_wire.py), built by the route on its own cursor, or the block a
    fixture captured. None is a node, or a capture, from before events: the page says so (SPEC_dashboard_events §5).
```

  Replace `lead = _lead(out, declared)` with:

```python
    lead = _lead(out, declared, events)
    if events is not None:
        covered = {a for e in events.get("open") or [] for a in e.get("alerts") or []}
        events = {**events, "uncovered_asks": [a["id"] for v in out.values() for a in (v.get("open_asks") or [])
                                               if a.get("id") is not None and a["id"] not in covered]}
```

  In the returned dict, after `"sections": …`, add:

```python
            # the alert events, one per issue per house, as the bot tells them (docs/SPEC_dashboard_events.md §3.1)
            "events": events}
```

  The `"sections"` line loses its closing `}`.

- [ ] **Step 5: Pass the captured block in `replay`.** In `replay`'s `return compute(...)`, add
  `events=(snapshot.get("issues") or {}).get("events") if isinstance(snapshot.get("issues"), dict) else None`.
  Add to its docstring:

```
    `events` is the block the capture carried in its own /issues, verbatim: the events are rows the node read, not
    arithmetic, and replaying them through compute is what ranks the headline and recomputes uncovered_asks.
```

- [ ] **Step 6: Give `HEADLINE_RULE` its first sentence.** In `app/issues/__init__.py`, each value gets a new
  opening sentence, and the old opening becomes the "with none open" clause. The rest is unchanged:

```python
HEADLINE_RULE = {
    "en": "An open event leads, the most serious first. With none open, the issue with most to say leads. Where two "
          "have as much to say, the one that has moved most in the last three hours. An even tie goes to the order "
          "this place chose, under Set up → Basics.",
    "id": "Kejadian yang masih terbuka memimpin, yang paling serius lebih dulu. Bila tidak ada, isu yang paling "
          "banyak bicara memimpin. Bila dua sama banyaknya, yang paling berubah dalam tiga jam terakhir. Bila tetap "
          "seri, urutannya mengikuti pilihan tempat ini, di Set up → Basics.",
    "es": "Lidera un evento abierto, el más grave primero. Si no hay ninguno, lidera el asunto que más "
          "tiene que decir. Si dos dicen otro tanto, el que más se ha movido en las últimas tres horas. Si "
          "hay empate exacto, manda el orden que eligió este lugar, en Set up → Basics.",
}
```

- [ ] **Step 7: Update the wire pin.**
  Run: `python3 tools/check_wire.py --update && git diff tests/data/wire/issues-v0.json`
  Expected: the diff adds `"events"` and nothing else.

- [ ] **Step 8: Run the suites that read the engine.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py && PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues_engine.py && python3 tools/check_wire.py`
  Expected: all pass. `test_issues_engine.py` replays fixtures with no block, so its `by` checks still see `state`,
  `moved` or `order`. If one fails on the headline's wording, it pinned the old sentence: update the pin to the new
  sentence, and never the other way round.

- [ ] **Step 9: Run `make lint && make test`, then commit.**

```bash
git add app/issues/engine.py app/issues/__init__.py tests/data/wire/issues-v0.json tests/test_events_wire.py
git commit -m "issues: an open event leads the headline; /issues carries events and uncovered_asks"
```

---

### Task 5: the live route builds the block

**Files:**
- Modify: `app/issues/api.py`, `issues_now`

**Interfaces:**
- Consumes: `events_wire.live` (Task 3), `engine.compute(events=…)` (Task 4).

No unit test: this is four lines of glue on a route that needs `main`, and importing `main` in a test is forbidden.
Task 8 proves it on node #1 and node #3.

- [ ] **Step 1: Change `issues_now`.** Add `from datetime import datetime, timezone` to the module's imports. In
  `issues_now`, after the facilities read:

```python
        # The alert events block. A node whose events cannot be read still draws every issue: the block then
        # carries the reason, which is a different fact from a node too old to have events (SPEC §5).
        import events_wire          # noqa: PLC0415 — events_wire imports events_pg, which imports this package
        now = datetime.now(timezone.utc)
        try:
            with con.transaction():
                events = events_wire.live(cur, load(), main.settings.get("ALERT_LOCALE", "en") or "en", now)
        except Exception as e:  # noqa: BLE001
            log.warning("issues: the events block did not read (%s: %s)", type(e).__name__, str(e)[:120])
            events = {"engine": events_wire.engine_of(main.settings.get("ALERT_ENGINE", "rules")),
                      "error": "this node could not read its alert events just now", "open": [], "recent": [],
                      "buttons": {}, "cleared_today": 0, "last_cleared": None}
```

  Then add `now=now, events=events` to the `engine.compute(...)` call.

- [ ] **Step 2: Add the error state to spec §5.** In `docs/SPEC_dashboard_events.md` §5's table, before the
  `/issues` row:

```
| the events block could not be read | the node's sentence (`events.error`), followed by the alert cards |
```

- [ ] **Step 3: Run `make lint && make test`.**
  Expected: pass. `make lint` includes the app import check (`app imports, N routes`).

- [ ] **Step 4: Commit.**

```bash
git add app/issues/api.py docs/SPEC_dashboard_events.md
git commit -m "issues: GET /issues reads the events block on its own cursor, and says so when it cannot"
```

---

### Task 6: a button press is an `actions` row

**Files:**
- Modify: `app/events_pg.py` (add `EVENT_STAGES` and `answer` at the end)
- Modify: `app/main.py`, `action()` (`POST /actions`) and `actions()` (`GET /actions`)
- Test: `tests/test_events_pg.py` (above the last `print`)

**Interfaces:**
- Produces:
  - `events_pg.EVENT_STAGES = ("acknowledged", "acted", "dismissed")`
  - `events_pg.answer(cur, event_id, stage, actor, note) -> None`, which raises `ValueError` (→ 400) or
    `LookupError` (→ 404).
  - Plan 2's bot handler calls this same function.

- [ ] **Step 1: Write the failing test,** above the last `print` of `tests/test_events_pg.py`:

```python
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
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PYTHONPATH=app python3 tests/test_events_pg.py`
  Expected: `AttributeError: module 'events_pg' has no attribute 'answer'`

- [ ] **Step 3: Add `answer`** to the end of `app/events_pg.py`:

```python
# The three buttons (docs/SPEC_alerts.md §7): Not now, Done, Doesn't fit. `decided` is not one: the buttons are the
# decision, and DECISION_REQUIRED applies to alert-based acts only (docs/SPEC_dashboard_events.md §3.2).
EVENT_STAGES = ("acknowledged", "acted", "dismissed")


def answer(cur, event_id, stage, actor, note) -> None:
    """A button pressed on an event, from the dashboard or (Plan 2) the bot: one actions row with event_id and no
    alert_id. Every ρ, funnel and effect query joins actions to alerts on alert_id, so this row changes no published
    number until Plan 2's decision record says how events count."""
    if stage not in EVENT_STAGES:
        raise ValueError("an event's stage must be acknowledged, acted or dismissed")
    if isinstance(event_id, bool) or isinstance(event_id, float):
        raise ValueError("event_id must be a whole number")
    try:
        eid = int(event_id)
    except (TypeError, ValueError):
        raise ValueError("event_id must be a whole number") from None
    cur.execute("SELECT 1 FROM alert_events WHERE id = %s", (eid,))
    if not cur.fetchone():
        raise LookupError("no such event")
    cur.execute("INSERT INTO actions (event_id, stage, actor, note) VALUES (%s,%s,%s,%s)",
                (eid, stage, str(actor or "")[:80], str(note or "")[:500]))
```

- [ ] **Step 4: Run it and watch it pass.**
  Run: `PYTHONPATH=app python3 tests/test_events_pg.py`
  Expected: the `answer:` line, then `events_pg: candidates from kinded rules, a Policy from settings`.

- [ ] **Step 5: Route `POST /actions`.** In `app/main.py`'s `action()`, after the token block and before
  `stage = body.get("stage")`:

```python
    if body.get("event_id") is not None:
        # An event's buttons (docs/SPEC_dashboard_events.md §3.2): the same tokens, the same refusals, one row.
        if body.get("alert_id") is not None:
            raise HTTPException(400, "send alert_id or event_id, not both")
        with db() as con, con.cursor() as cur:
            try:
                events_pg.answer(cur, body["event_id"], body.get("stage"), body.get("actor"), body.get("note"))
            except ValueError as e:
                raise HTTPException(400, str(e)) from None
            except LookupError as e:
                raise HTTPException(404, str(e)) from None
        return {"ok": True}
```

  Add to the docstring's first paragraph: `An event's button is {"event_id": 3, "stage": "dismissed", …}: acted,
  acknowledged or dismissed (Done, Not now, Doesn't fit).`

- [ ] **Step 6: Add `events=1` to `GET /actions`.** The signature becomes
  `def actions(limit: int = Query(500, ge=0, le=5000), stage: str = "", events: int = Query(0, ge=0, le=1)):`.
  Replace the last `return q(...)` with:

```python
    if events:
        # the event answers too, with event_id; without it the v0.76 page never meets a row with no alert_id
        return q("SELECT ts, alert_id, event_id, stage, actor, note FROM actions "
                 "WHERE alert_id IS NOT NULL OR event_id IS NOT NULL ORDER BY ts DESC LIMIT %s", limit)
    return q("SELECT ts, alert_id, stage, actor, note FROM actions WHERE alert_id IS NOT NULL "
             "ORDER BY ts DESC LIMIT %s", limit)
```

  Add to its docstring: `events=1 adds the answers to alert events, with their event_id (docs/SPEC_dashboard_events.md
  §3.4).`

- [ ] **Step 7: Run `make lint && make test`.**
  Expected: pass. If `tools/check_docs.py` says `api.md` does not document a parameter, Task 7 fixes that. Do Task 7
  before committing if the hook refuses.

- [ ] **Step 8: Commit.**

```bash
git add app/events_pg.py app/main.py tests/test_events_pg.py
git commit -m "actions: an event's Done, Not now and Doesn't fit are one actions row; GET /actions?events=1"
```

---

### Task 7: the API docs and the CHANGELOG

**Files:**
- Modify: `docs/site/api.md`: the `/issues` key list (line ~318), `POST /actions` (near "The node asks; a person
  answers"), `GET /actions`
- Modify: `CHANGELOG.md`, `## Unreleased`

- [ ] **Step 1: The `/issues` key list.** In `docs/site/api.md`, the sentence
  ``Returns `{schema, order, …, geometry, sections}` `` becomes `…, geometry, sections, events}`. Add a paragraph
  after it:

```markdown
`events` is the alert events (see [Alerts](alerts.md)), one per issue per house, as the bot tells them: which engine
the node runs (`rules`, `shadow` or `events`), the three button labels in the household's language, the `open` events
(kind, rooms, peak, the issue's line, the numbers the action was chosen from, the action and the latest message word
for word, the alerts each covers, and the latest answer), the events cleared in the last 7 days under `recent`,
`cleared_today`, and `uncovered_asks`: the open alerts no event covers. An open event's issue leads the page, and
`lead.by` is then `event`. A node older than v0.77 sends no `events` key, and a node that could not read them sends
`events.error`.
```

- [ ] **Step 2: `POST /actions`.** In the section that starts "The node asks; a person answers", add:

```markdown
An alert event is answered the same way, with `event_id` in place of `alert_id`: `{"event_id": 3, "stage":
"dismissed", "actor": "tomas", "note": "ran the AC instead"}`. The stage is the button: Done is `acted`, Not now is
`acknowledged`, Doesn't fit is `dismissed`. Any other stage is 400, an event this node does not have is 404, and the
tokens are the alert's. An event's answer is not in ρ yet.
```

- [ ] **Step 3: `GET /actions`.** Where `GET /actions` and its `stage` parameter are described, add: ``With
  `events=1` it also returns the answers to alert events, with their `event_id`.``

- [ ] **Step 4: The CHANGELOG line.** Under `## Unreleased` in `CHANGELOG.md`:

```markdown
- `GET /issues` carries the alert events (`events`): what is open, its one action as it was sent, its latest answer,
  and the alerts it covers; an open event now leads the page. `POST /actions` takes an `event_id` with Done (`acted`),
  Not now (`acknowledged`) or Doesn't fit (`dismissed`), and `GET /actions?events=1` lists those answers. The page
  that draws them is v0.78; the Telegram buttons are Plan 2.
```

- [ ] **Step 5: Run the docs gate, then everything.**
  Run: `python3 tools/check_docs.py && make lint && make test`
  Expected: `N documents check out`, lint `ok`, every suite passes.

- [ ] **Step 6: Commit.**

```bash
git add docs/site/api.md CHANGELOG.md
git commit -m "docs: /issues events, POST /actions by event, GET /actions?events=1"
```

---

### Task 8: the pull request, then the proof on two nodes

**Prerequisite for Steps 4–7:** the session finding why node #1 recorded no shadow events on 5 October must have an
answer. Until it does, a node can't show an open event, and Steps 4–7 wait. Steps 1–3 don't.

- [ ] **Step 1: Open the PR,** following `docs/WORKFLOW.md`:

```bash
git push -u origin HEAD
gh pr create --repo fabcity/planetai-node --milestone v0.77 --label "needs testing" \
  --title "events on the wire: /issues carries the alert events; POST /actions answers one" \
  --body-file "$SCRATCH/pr-body.md"      # a file in your session's scratchpad directory
```

  The body says what changed for a node, names `docs/SPEC_dashboard_events.md` §3, says the page is v0.78, asks Tomas
  to confirm the Indonesian and Spanish button labels, and notes the suite count moving 63 → 64. It ends with the
  attribution line from the session's instructions.

- [ ] **Step 2: Read CI** with the `ccd_pr` tools, and offer Auto-fix if a check fails. Don't poll.

- [ ] **Step 3: Merge only on Tomas's word.** Then update both test nodes as `docs/WORKFLOW.md` says.

- [ ] **Step 4: Prove the block on node #1** (`ssh mini`, port 8081, `ALERT_ENGINE=events`). Read-only:

```bash
ssh mini 'curl -s localhost:8081/issues | python3 -c "import json,sys; d=json.load(sys.stdin); e=d[\"events\"]; print(e[\"engine\"], len(e[\"open\"]), [x[\"id\"] for x in e[\"open\"]], e[\"uncovered_asks\"][:5], d[\"lead\"])"'
```

  Compare with Postgres. Start the psql session with `SET default_transaction_read_only = on`, and run
  `SELECT id, issue, kind FROM alert_events WHERE cleared_at IS NULL ORDER BY opened_at`. The ids must match.
  `lead.by` is `event` exactly when an open event's issue has a hero.

- [ ] **Step 5: Prove it on node #3** (`ssh omarchy-gmail`, port 8080, `ALERT_ENGINE=shadow`) the same way. Every
  open event's `message.sent` must be `false` there.

- [ ] **Step 6: One real press of each button on node #1, by Tomas or with his go,** from his machine with the act
  token, against an open event id from Step 4:

```bash
curl -s -X POST localhost:8081/actions -H 'Content-Type: application/json' \
  -d '{"event_id": <id>, "stage": "acknowledged", "actor": "tomas"}'
```

  `/issues` then shows `answer.stage: acknowledged` with a `held_until` three hours on. `/rho` must not change:
  read it before and after.

- [ ] **Step 7: Label the PR `tested: node 1` and `tested: node 3`,** and write what was proven in a PR comment:
  the ids compared, `lead.by`, and the unchanged ρ.
