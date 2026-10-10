Note (4 Oct 2026): the table this plan calls `events` was built as `alert_events`, because an `events` table already exists (v0.50); see the SDD ledger, ruling 11.

# Alert events, part 1: the decision engine in shadow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the event layer from `docs/SPEC_alerts.md` (§2–§5, §9, `ALERT_ENGINE`), run it in shadow beside
today's rules, and prove it against node #1's last 30 days before anything reaches a phone.

**Architecture:** Rules stay SQL. Two new core views give rules the measures they lack (`recent_15m`,
`usual_by_hour`). Kinded rules (`kind:` + `issue:`) produce candidate rows. A pure-Python engine
(`app/events.py`) folds candidates into one event per issue per house, decides open/escalate/clear, quiet hours and
the daily ceiling, and picks one action from the context. The same engine runs in the app (Postgres store) and in
the replay (memory store, DuckDB-run rules), so what is replayed is what ships. `ALERT_ENGINE=rules` (default)
changes nothing; `shadow` records what the engine would send and sends nothing.

**Tech Stack:** Python 3.12 app (stdlib + psycopg + PyYAML), Postgres 16 / PostGIS, DuckDB for replays (dev only),
plain-assert test suites run by `tests/all`.

**Spec:** `docs/SPEC_alerts.md`. Read it first; this plan implements its §11 steps 1–4 and the `ALERT_ENGINE`
switch. Telegram buttons and ρ (§7), anticipation (§6) and report settings (§10 except `ALERT_ENGINE`,
`ALERT_MAX_PER_DAY`, `HOME_HAS`) are plans 2–4.

## Global Constraints

- Work in your own git worktree off `origin/main`, never the checkout holding `main` (`skills/preflight/SKILL.md`).
- `make lint && make test` before every commit; the pre-commit hook runs both. Never `--no-verify`.
- `init.sql` is applied twice by CI and on every update: everything idempotent (`IF NOT EXISTS`, `DROP … IF EXISTS`
  before `CREATE VIEW`). Additive only: no dropped columns, no renames. A new `schema_version` row, `0.53`.
  `GOVERNANCE.md`: `init.sql` changes need two maintainers — say so in the PR body.
- Rule SQL runs as `planetai_ro` (SELECT only, no `settings`). Every new view gets `GRANT SELECT … TO planetai_ro`.
- Rules read local hours through the session time zone (`current_setting('TimeZone')`), which the app sets to
  `NODE_TZ`. Replays pin `Asia/Makassar` (`tests/trustdb.py`).
- `ALERT_ENGINE` default is `rules`, and with it the node behaves exactly as before: same rules, same sends.
- Old rules are not edited or removed in this plan. Kinded rules are new rules beside them; the old path skips any
  rule with a `kind:`.
- Messages in en, id and es with the same placeholders (`tests/test_packs.py`). The id and es strings are
  assistant-written; say so in a comment, as `app/issues/heat.yml` does.
- A new test suite is one line in `tests/all` and moves the expected count (55 today) by one, in the same commit.
  A suite ends in its last `print`, never `sys.exit()` with tests below it.
- Every new setting: `app/settings.py` (`RUNTIME` + `CHOICES`), `.env.example` (comment above the key),
  and a row in `docs/site/configuration.md` — `tools/check_docs.py` fails otherwise.
- Starting values (spec §3) are constants with a comment naming them as starting values; the replay sets them.
- Never import `main` in a process on node #1; never write to node #1. The replay data is fetched read-only and
  stays out of git (household data).
- Commit identity: `git -c user.name="Tomas Diez" -c user.email="tomas@fab.city" commit …`, trailer
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## File map

| file | responsibility |
|---|---|
| `init.sql` | `recent_15m` view, `usual_by_hour` materialized view, `events`, `event_messages`, `alerts.event_id`, `actions.event_id`, `dismissed` stage, version 0.53 |
| `app/events.py` (new) | the engine: candidates → events → messages; quiet hours; ceiling; pure, no I/O |
| `app/events_pg.py` (new) | the Postgres store and the per-minute step the app runs; context from the database |
| `app/actions.py` (new) | `when:` evaluation and action choice; template rendering |
| `app/main.py` | refresh `usual_by_hour` hourly; `run_rules` skips kinded rules on the old path and calls the engine in `shadow`/`events` |
| `app/settings.py`, `.env.example`, `docs/site/configuration.md` | `ALERT_ENGINE`, `ALERT_MAX_PER_DAY`, `HOME_HAS` |
| `app/issues/heat.yml`, `app/issues/air.yml` | `events:` templates and `actions:` lists |
| `packs/heat/rules.yml`, `packs/air-quality/rules.yml` | new kinded rules |
| `tests/trustdb.py` | the replay harness learns `recent_15m` and `usual_by_hour` |
| `tests/test_measures.py`, `tests/test_events.py`, `tests/test_actions.py`, `tests/test_kinded_rules.py` (new) | suites |
| `tools/replay_alerts.py`, `tools/fetch_replay.sh` (new) | the month replay and its read-only fetch |
| `tools/check_docs.py` | drop `tools/replay_alerts.py` and `ALERT_ENGINE` from `PROPOSED` once they exist |

---

### Task 1: The measures — `recent_15m` and `usual_by_hour`

**Files:**
- Modify: `init.sql` (append a block at the end)
- Modify: `app/main.py` (one loop, one function)
- Modify: `tests/trustdb.py` (build the two views at the replayed instant)
- Create: `tests/test_measures.py`
- Modify: `tests/all` (one line, count 55 → 56)

**Interfaces:**
- Produces (SQL, readable by rules): `recent_15m(bucket timestamptz, sensor_id text, metric text, mean double)` —
  15-minute means over the last 24 h for `kind='sensor'`, plus derived rows `metric='apparent'` (Steadman, as
  `packs/heat/rules.yml`) wherever a sensor has `temp` and `humidity` in the same bucket.
- Produces: `usual_by_hour(sensor_id text, metric text, hour int, median double, p75 double, p90 double, n bigint)` —
  per local hour, over the last 14 days of hourly means, metrics `temp`, `humidity`, `pm25`, `apparent`.
- Produces (Python): `trustdb.Node.refresh_usual(at: datetime)`; `Node.run()` rebuilds `recent_15m` at `at`.

- [ ] **Step 1: Write the failing test**

`tests/test_measures.py`:

```python
"""The core measures a kinded rule reads: recent_15m and usual_by_hour (docs/SPEC_alerts.md §3).

Run against node #1's own readings in DuckDB, the way tests/trustdb.py replays the trust rules. Needs duckdb.
Run: python3 tests/test_measures.py
"""
import datetime as dt
import sys

try:
    import trustdb as T
except ImportError as e:            # duckdb missing: the suite declares its skip
    print(f"  skipped: {e}")
    sys.exit(0)

K = "sc-19880"                       # an indoor kit in tests/data/node1-sensors.tsv with temp and humidity
rows = T.readings()
at = T.FIXTURE_NOW
node = T.Node(T.week(rows, at, days=15))
node.refresh_usual(at)

q = lambda sql: node.con.execute(sql.replace("now()", f"TIMESTAMPTZ '{at.isoformat()}'")).fetchall()

r15 = node.recent(at)
buckets = {b for b, s, m, v in r15 if s == K and m == "temp"}
assert buckets, "an indoor kit has 15-minute temp buckets"
assert all(b.minute in (0, 15, 30, 45) for b in buckets), "buckets fall on quarter hours"
assert max(buckets) <= at and min(buckets) > at - dt.timedelta(hours=24, minutes=15), "only the last 24 h"
app = [v for b, s, m, v in r15 if s == K and m == "apparent"]
assert app and all(20 < v < 50 for v in app), f"apparent temperature is derived and plausible: {app[:3]}"
print(f"  recent_15m: {len(buckets)} quarter-hour temp buckets for {K}, and an apparent row beside each")

u = q(f"SELECT hour, median, p75, p90, n FROM usual_by_hour WHERE sensor_id = '{K}' AND metric = 'apparent' ORDER BY hour")
assert len(u) == 24, f"one row per local hour, got {len(u)}"
assert all(med <= p75 <= p90 for _, med, p75, p90, _ in u), "median <= p75 <= p90"
assert all(n >= 10 for *_, n in u), "fourteen days give each hour at least ten samples"
day = {h: med for h, med, *_ in u}
assert day[16] > day[4], f"the room's afternoon is warmer than its night: 16h {day[16]:.1f} vs 04h {day[4]:.1f}"
print(f"usual_by_hour: 24 local hours for {K}; 04h {day[4]:.1f}, 16h {day[16]:.1f} °C apparent (median)")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=tests python3 tests/test_measures.py`
Expected: FAIL with `AttributeError: 'Node' object has no attribute 'refresh_usual'`.

- [ ] **Step 3: Add the views to `init.sql`**

Append at the end of `init.sql`, after every existing block (the `planetai_ro` role exists by then):

```sql
-- The measures a kinded rule reads (docs/SPEC_alerts.md §3). A rule asks "for how long" and "against what usual"
-- here instead of rebuilding either from raw readings every minute.
--
-- recent_15m: quarter-hour means over the last 24 h, sensors only, with `apparent` (Steadman's no-wind indoor
-- form, the same arithmetic as packs/heat/rules.yml) derived wherever temp and humidity share a bucket.
DROP VIEW IF EXISTS recent_15m CASCADE;
CREATE VIEW recent_15m AS
WITH b AS (
  SELECT date_trunc('hour', r.ts) + CAST(floor(extract(minute FROM r.ts) / 15) AS INTEGER) * INTERVAL '15 minutes' AS bucket,
         r.sensor_id, r.metric, avg(r.value) AS mean
  FROM readings r JOIN sensors s ON s.sensor_id = r.sensor_id
  WHERE r.ts > now() - INTERVAL '24 hours' AND s.kind = 'sensor'
  GROUP BY 1, 2, 3)
SELECT bucket, sensor_id, metric, mean FROM b
UNION ALL
SELECT t.bucket, t.sensor_id, 'apparent',
       t.mean + 0.33 * (h.mean / 100.0 * 6.105 * exp(17.27 * t.mean / (237.7 + t.mean))) - 4.0
FROM b t JOIN b h ON h.sensor_id = t.sensor_id AND h.bucket = t.bucket AND h.metric = 'humidity'
WHERE t.metric = 'temp';

-- usual_by_hour: this room's own normal for each local hour, from fourteen days of hourly means. Materialized,
-- because a percentile over two weeks is too much to recompute every minute; the app refreshes it hourly and at
-- start (app/main.py refresh_usual). Created empty: init.sql runs under psql in UTC, and a refresh from the app runs
-- in NODE_TZ, so only the app's refresh buckets hours the way the household lives them. A rule that reads it
-- before the first refresh fails and is logged, and runs again a minute later.
DROP MATERIALIZED VIEW IF EXISTS usual_by_hour;
CREATE MATERIALIZED VIEW usual_by_hour AS
WITH h AS (
  SELECT date_trunc('hour', r.ts) AS bucket, r.sensor_id, r.metric, avg(r.value) AS mean
  FROM readings r JOIN sensors s ON s.sensor_id = r.sensor_id
  WHERE r.ts > now() - INTERVAL '14 days' AND s.kind = 'sensor' AND r.metric IN ('temp', 'humidity', 'pm25')
  GROUP BY 1, 2, 3),
a AS (
  SELECT bucket, sensor_id, metric, mean FROM h
  UNION ALL
  SELECT t.bucket, t.sensor_id, 'apparent',
         t.mean + 0.33 * (u.mean / 100.0 * 6.105 * exp(17.27 * t.mean / (237.7 + t.mean))) - 4.0
  FROM h t JOIN h u ON u.sensor_id = t.sensor_id AND u.bucket = t.bucket AND u.metric = 'humidity'
  WHERE t.metric = 'temp')
SELECT sensor_id, metric, CAST(extract(hour FROM bucket) AS INTEGER) AS hour,
       percentile_cont(0.5)  WITHIN GROUP (ORDER BY mean) AS median,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY mean) AS p75,
       percentile_cont(0.9)  WITHIN GROUP (ORDER BY mean) AS p90,
       count(*) AS n
FROM a GROUP BY 1, 2, 3
WITH NO DATA;
GRANT SELECT ON recent_15m, usual_by_hour TO planetai_ro;
INSERT INTO schema_version (version) VALUES ('0.53') ON CONFLICT DO NOTHING;
```

- [ ] **Step 4: Teach the replay harness both views**

In `tests/trustdb.py`, add after `_stats_sql()`:

```python
def _measures_sql() -> tuple[str, str]:
    """recent_15m and usual_by_hour verbatim from init.sql, for DuckDB. The materialized view becomes a table built
    at the replayed instant (DuckDB has no materialized views), and `WITH NO DATA` goes with it."""
    sql = _schema()
    recent = re.search(r"CREATE VIEW recent_15m AS.*?;", sql, re.S).group(0)
    usual = re.search(r"CREATE MATERIALIZED VIEW usual_by_hour AS(.*?)WITH NO DATA;", sql, re.S).group(1)
    return recent, "CREATE OR REPLACE TABLE usual_by_hour AS" + usual
```

and to `class Node`:

```python
    def refresh_usual(self, at: dt.datetime) -> None:
        """Rebuild usual_by_hour as it would read at `at` (the app refreshes it hourly)."""
        self.con.execute(_measures_sql()[1].replace("now()", f"TIMESTAMPTZ '{at.isoformat()}'"))

    def recent(self, at: dt.datetime) -> list[tuple]:
        """recent_15m as it would read at `at`."""
        self._recent_at(at)
        return self.con.execute("SELECT bucket, sensor_id, metric, mean FROM recent_15m").fetchall()

    def _recent_at(self, at: dt.datetime) -> None:
        self.con.execute("DROP VIEW IF EXISTS recent_15m")
        self.con.execute(_measures_sql()[0].replace("now()", f"TIMESTAMPTZ '{at.isoformat()}'"))
```

and in `Node.run()`, after the `stats` view is rebuilt:

```python
        self._recent_at(at)
```

- [ ] **Step 5: Run the test**

Run: `PYTHONPATH=tests python3 tests/test_measures.py`
Expected: two lines, the last starting `usual_by_hour: 24 local hours`. If DuckDB rejects
`CAST(... AS INTEGER) * INTERVAL '15 minutes'`, write the bucket as
`date_trunc('hour', r.ts) + (CAST(extract(minute FROM r.ts) AS INTEGER) / 15) * INTERVAL '15 minutes'` in
`init.sql` (integer division in both engines) and rerun — never a DuckDB-only edit in the harness.

- [ ] **Step 6: Refresh it from the app**

In `app/main.py`, beside `run_rules`:

```python
def refresh_usual() -> None:
    """usual_by_hour is materialized (init.sql): rebuild it hourly, in this connection's NODE_TZ, so a rule's
    "usual for this hour" is the household's hour. Concurrent readers keep the old rows until it finishes."""
    with db() as con, con.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW usual_by_hour")
```

and register it with the other loops (after `loop(run_rules, 60, delay=30)`):

```python
loop(refresh_usual, 3600, delay=10)
```

- [ ] **Step 7: Prove the schema twice against a real Postgres, and register the suite**

Run (any scratch Postgres 16 with PostGIS, e.g. the one in `memory`/`docs/site/developing.md`):
`psql "$SCRATCH_DB" -f init.sql && psql "$SCRATCH_DB" -f init.sql && psql "$SCRATCH_DB" -c "REFRESH MATERIALIZED VIEW usual_by_hour"`
Expected: no error on either run, and the refresh succeeds on an empty `readings`.

In `tests/all`, add beside the other replays:

```
test_measures|PYTHONPATH=tests python3 tests/test_measures.py
```

add `test_measures` to `EXPECTED_SKIPS` (it skips without duckdb, like `test_season`), and change both `55`s in the
count lines to `56`.

- [ ] **Step 8: Run lint and test, commit**

Run: `make lint && make test`
Expected: `ok` from lint; `56 suites: 56 passed`.

```bash
git add init.sql app/main.py tests/trustdb.py tests/test_measures.py tests/all
git commit -m "measures: recent_15m and usual_by_hour, for rules that ask how long and against what usual"
```

---

### Task 2: The engine — candidates to events to messages (pure)

**Files:**
- Create: `app/events.py`
- Create: `tests/test_events.py`
- Modify: `tests/all` (count 56 → 57)

**Interfaces:**
- Consumes: nothing from Task 1 (pure).
- Produces:
  - `Candidate(rule_id: str, issue: str, kind: str, level: str, sensor_id: str, room: str, value: float, line: float, over: bool, where: str = "inside")`
  - `Event` (fields below), `Message(event: Event, reason: str, send: bool, held: str | None)`
  - `Policy(quiet: tuple[int, int] | None, max_per_day: int, alert_level: str)`
  - `MemoryStore()` with `open_events() -> list[Event]`, `save(e: Event) -> Event`, `sends_on(day: date) -> int`,
    `count_send(day: date) -> None`
  - `step(now: datetime, cands: list[Candidate], store, policy: Policy) -> list[Message]`
  - constants `KIND_RANK`, `ESCALATE_GAP`, `CLEAR_AFTER`, `ESCALATE_STEP`

- [ ] **Step 1: Write the failing test**

`tests/test_events.py`:

```python
"""The event engine (docs/SPEC_alerts.md §4): one event per issue per house; open, escalate, match, clear; quiet
hours send only danger; a daily ceiling outside danger. Pure: no database, a clock passed in.
Run: PYTHONPATH=app python3 tests/test_events.py
"""
import datetime as dt

import events as E

T0 = dt.datetime(2026, 9, 25, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
POL = E.Policy(quiet=(22, 6), max_per_day=4, alert_level="act")


def c(room, kind="sustained", value=36.0, over=True, issue="heat", sensor=None, line=35.0):
    return E.Candidate(rule_id=f"heat/heat_{kind}", issue=issue, kind=kind, level="act",
                       sensor_id=sensor or f"sc-{room}", room=room, value=value, line=line, over=over)


def at(minutes):
    return T0 + dt.timedelta(minutes=minutes)


# one story for three rooms
s = E.MemoryStore()
m = E.step(at(0), [c("K"), c("L"), c("S")], s, POL)
assert [x.reason for x in m] == ["open"] and m[0].send, m
assert m[0].event.rooms == {"K", "L", "S"}, m[0].event.rooms
print("  three rooms at once open one heat event and send one message")

# the same condition a minute later updates silently
assert E.step(at(1), [c("K"), c("L")], s, POL) == []
print("  rows that match an open event send nothing")

# a rule row below the line (over=False) keeps the event alive but never opens one
s2 = E.MemoryStore()
assert E.step(at(0), [c("K", over=False, value=34.5)], s2, POL) == [] and s2.open_events() == []
print("  a margin row (over=False) does not open an event")

# escalation: a climb in kind, not sooner than ESCALATE_GAP, except danger
m = E.step(at(30), [c("K", kind="unusual")], s, POL)
assert m == [], "unusual ranks with sustained's first open, no climb"
m = E.step(at(60), [c("K", kind="danger", value=40.5)], s, POL)
assert [x.reason for x in m] == ["escalate"] and m[0].send, "danger always escalates, inside the gap"
print("  a climb to danger sends at once; other climbs wait ESCALATE_GAP")

# clearing: no candidate for CLEAR_AFTER closes the event, with one all-clear because it had been sent
assert E.step(at(60 + 29), [], s, POL) == []          # last seen at minute 60: 29 minutes is not yet 30
m = E.step(at(60 + 30), [], s, POL)
assert [x.reason for x in m] == ["clear"] and m[0].send and s.open_events() == [], m
print("  thirty minutes without a row clears it, with one all-clear")

# a margin row holds an open event open
s3 = E.MemoryStore()
E.step(at(0), [c("K")], s3, POL)
E.step(at(40), [c("K", over=False, value=34.6)], s3, POL)
assert s3.open_events(), "a row inside the margin keeps the event open"
print("  the margin is hysteresis: inside it an open event stays open")

# quiet hours: only danger sends; others are held for the morning
night = T0.replace(hour=2)
q = E.MemoryStore()
m = E.step(night, [c("K")], q, POL)
assert m[0].send is False and m[0].held == "quiet", m
m = E.step(night, [c("X", kind="danger", value=41, issue="air", sensor="sc-x")], q, POL)
assert m[0].send is True, "danger sends in quiet hours"
print("  at 02:00 a sustained event is held for the morning; danger is sent")

# the daily ceiling counts sends outside danger, per local day
d = E.MemoryStore()
sent = 0
for i, issue in enumerate(["heat", "air", "land", "coast", "water"]):
    for x in E.step(at(i * 5), [c("K", issue=issue, sensor=f"s{i}")], d, POL):
        sent += x.send
        if i == 4:
            assert not x.send and x.held == "ceiling", x
assert sent == 4, sent
print("  the fifth non-danger push of the day is held: ceiling")

# ALERT_LEVEL: a warn event is recorded, and sent only when ALERT_LEVEL allows warn
w = E.MemoryStore()
m = E.step(at(0), [E.Candidate("air-quality/air_spike", "air", "spike", "warn", "s", "K", 40, 12, True)], w, POL)
assert m[0].send is False and m[0].held == "level", m
print("events: one story per issue, silent matches, hysteresis, quiet hours, a ceiling, ALERT_LEVEL")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=app python3 tests/test_events.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'events'`.

- [ ] **Step 3: Write `app/events.py`**

```python
"""Alerts become events (docs/SPEC_alerts.md §4). Pure: candidates and a clock in, messages out.

A kinded rule's row is a Candidate. Every candidate is folded into the one open Event for its issue (heat, air…)
at this house. An event opens on the first candidate that is `over` its line, escalates when its kind climbs or its
value clearly passes its peak, and clears when no candidate (over or inside the margin) has been seen for
CLEAR_AFTER. A margin row — `over` False — keeps an open event open and never opens one: that is the hysteresis.

Whether a message is sent: quiet hours send only `danger`; outside `danger`, at most Policy.max_per_day pushes a
local day; ALERT_LEVEL decides whether a warn event interrupts at all. A held message is still returned, with the
reason, because the report carries it. The same function runs in the app (events_pg.py) and in the replay
(tools/replay_alerts.py), so what is replayed is what ships.
"""
from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import dataclass, field

# Starting values (docs/SPEC_alerts.md §3–§4), set by the replay of node #1's month, not by this file.
KIND_RANK = {"ahead": 0, "unusual": 1, "spike": 1, "sustained": 2, "danger": 3}
ESCALATE_GAP = dt.timedelta(hours=3)            # never two messages for one event closer than this, unless danger
CLEAR_AFTER = dt.timedelta(minutes=30)          # no candidate for this long and the event clears
ESCALATE_STEP = {"heat": 2.0, "air": 25.0}      # a value this far past the peak is "clearly worse"
LEVELS = {"info": 0, "warn": 1, "act": 2}


@dataclass(frozen=True)
class Candidate:
    rule_id: str
    issue: str
    kind: str
    level: str
    sensor_id: str
    room: str
    value: float
    line: float
    over: bool
    where: str = "inside"


@dataclass
class Event:
    issue: str
    kind: str
    level: str
    opened_at: dt.datetime
    last_seen_at: dt.datetime
    peak: float
    rooms: set = field(default_factory=set)
    where: set = field(default_factory=set)
    last_sent_at: dt.datetime | None = None
    cleared_at: dt.datetime | None = None
    ever_sent: bool = False
    id: int | None = None
    action_id: str | None = None


@dataclass
class Message:
    event: Event
    reason: str                 # open | escalate | clear
    send: bool
    held: str | None            # quiet | ceiling | level | None


@dataclass(frozen=True)
class Policy:
    quiet: tuple[int, int] | None     # (from_hour, to_hour) local, or None when quiet hours are off
    max_per_day: int
    alert_level: str


class MemoryStore:
    """The store the tests and the replay use. events_pg.PgStore has the same four methods."""

    def __init__(self):
        self._events: list[Event] = []
        self._sends: dict[dt.date, int] = {}
        self._ids = itertools.count(1)

    def open_events(self) -> list[Event]:
        return [e for e in self._events if e.cleared_at is None]

    def save(self, e: Event) -> Event:
        if e.id is None:
            e.id = next(self._ids)
            self._events.append(e)
        return e

    def sends_on(self, day: dt.date) -> int:
        return self._sends.get(day, 0)

    def count_send(self, day: dt.date) -> None:
        self._sends[day] = self._sends.get(day, 0) + 1


def _quiet(now: dt.datetime, quiet: tuple[int, int] | None) -> bool:
    if not quiet:
        return False
    a, b = quiet
    return (a <= now.hour or now.hour < b) if a > b else (a <= now.hour < b)


def _decide(now: dt.datetime, e: Event, store, policy: Policy) -> tuple[bool, str | None]:
    if LEVELS.get(e.level, 0) < LEVELS.get(policy.alert_level, 2):
        return False, "level"
    if e.kind == "danger":
        return True, None
    if _quiet(now, policy.quiet):
        return False, "quiet"
    if store.sends_on(now.date()) >= policy.max_per_day:
        return False, "ceiling"
    return True, None


def _emit(now, e, reason, store, policy) -> Message:
    send, held = _decide(now, e, store, policy)
    if reason == "clear" and held == "ceiling":
        send, held = True, None             # an all-clear closes a loop already opened; it does not spend the ceiling
    if send:
        e.last_sent_at, e.ever_sent = now, True
        if e.kind != "danger" and reason != "clear":
            store.count_send(now.date())
    store.save(e)
    return Message(e, reason, send, held)


def step(now: dt.datetime, cands: list[Candidate], store, policy: Policy) -> list[Message]:
    out: list[Message] = []
    by_issue: dict[str, list[Candidate]] = {}
    for c in cands:
        by_issue.setdefault(c.issue, []).append(c)
    open_by_issue = {e.issue: e for e in store.open_events()}

    for issue, cs in sorted(by_issue.items()):
        over = [c for c in cs if c.over]
        e = open_by_issue.get(issue)
        if e is None:
            if not over:
                continue
            top = max(over, key=lambda c: (KIND_RANK.get(c.kind, 0), c.value))
            e = Event(issue=issue, kind=top.kind, level=max((c.level for c in over), key=lambda l: LEVELS.get(l, 0)),
                      opened_at=now, last_seen_at=now, peak=max(c.value for c in over),
                      rooms={c.room for c in over}, where={c.where for c in over})
            out.append(_emit(now, e, "open", store, policy))
            continue
        e.last_seen_at = now
        e.rooms |= {c.room for c in over}
        e.where |= {c.where for c in over}
        if not over:
            store.save(e)
            continue
        top = max(over, key=lambda c: (KIND_RANK.get(c.kind, 0), c.value))
        climbed = KIND_RANK.get(top.kind, 0) > KIND_RANK.get(e.kind, 0)
        worse = top.value >= e.peak + ESCALATE_STEP.get(issue, float("inf"))
        e.peak = max(e.peak, top.value)
        if climbed:
            e.kind = top.kind
        due = e.last_sent_at is None or now - e.last_sent_at >= ESCALATE_GAP or e.kind == "danger"
        if (climbed or worse) and due:
            out.append(_emit(now, e, "escalate", store, policy))
        else:
            store.save(e)

    for e in store.open_events():
        if e.issue in by_issue:
            continue
        if now - e.last_seen_at >= CLEAR_AFTER:
            e.cleared_at = now
            if e.ever_sent:
                out.append(_emit(now, e, "clear", store, policy))
            else:
                store.save(e)
    return out
```

- [ ] **Step 4: Run the test**

Run: `PYTHONPATH=app python3 tests/test_events.py`
Expected: eight lines ending `events: one story per issue, silent matches, hysteresis, quiet hours, a ceiling, ALERT_LEVEL`.

- [ ] **Step 5: Register and commit**

`tests/all`: add `test_events|PYTHONPATH=app python3 tests/test_events.py`; count 56 → 57 in both places.

Run: `make lint && make test` — expected `57 suites: 57 passed`.

```bash
git add app/events.py tests/test_events.py tests/all
git commit -m "events: the engine that folds rule rows into one story per issue per house"
```

---

### Task 3: Postgres store, schema, `ALERT_ENGINE`, and shadow wiring

**Files:**
- Modify: `init.sql` (append after Task 1's block)
- Create: `app/events_pg.py`
- Modify: `app/main.py` (`run_rules`)
- Modify: `app/settings.py`, `.env.example`, `docs/site/configuration.md`
- Modify: `tools/check_docs.py` (remove `ALERT_ENGINE` from `PROPOSED["docs/SPEC_alerts.md"]`)
- Test: `tests/test_events_pg.py` (new), `tests/all` (57 → 58)

**Interfaces:**
- Consumes: `events.step`, `events.Candidate`, `events.Event`, `events.Policy` (Task 2).
- Produces:
  - tables `events`, `event_messages`; columns `alerts.event_id`, `actions.event_id`; stage `dismissed`
  - `events_pg.PgStore(cur)` — the four `MemoryStore` methods, persisted
  - `events_pg.candidates(rule: dict, rows: list[dict]) -> list[events.Candidate]`
  - `events_pg.policy() -> events.Policy` from settings
  - `events_pg.run(cur, cands: list[Candidate], mode: str, now: datetime) -> list[events.Message]` — records
    every message in `event_messages`; sends only when `mode == "events"` (sending itself is wired in Plan 2;
    in this plan `events` mode logs and does not notify — see Step 6)
  - settings `ALERT_ENGINE` (`rules`|`shadow`|`events`, default `rules`), `ALERT_MAX_PER_DAY` (default `4`),
    `HOME_HAS` (comma list of `purifier`, `ac`, `fan`, `windows`; default empty)

- [ ] **Step 1: Write the failing test**

`tests/test_events_pg.py` — pure parts only (`make test` has no Postgres; the store is proved in Step 7):

```python
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
print("events_pg: candidates from kinded rules, a Policy from settings")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=app python3 tests/test_events_pg.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'events_pg'`.

- [ ] **Step 3: Schema**

Append to `init.sql` (still version `0.53`, which Task 1 inserted):

```sql
-- Events (docs/SPEC_alerts.md §4): one row per story — one issue at one house, from open to clear. Every alert
-- row still exists; the ones that fed an event point at it. event_messages is every message the engine decided,
-- sent or held, with the reason: in ALERT_ENGINE=shadow nothing is sent and this table is the comparison.
CREATE TABLE IF NOT EXISTS events (
  id           BIGSERIAL PRIMARY KEY,
  issue        TEXT NOT NULL,
  kind         TEXT NOT NULL,
  level        TEXT NOT NULL,
  opened_at    TIMESTAMPTZ NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL,
  last_sent_at TIMESTAMPTZ,
  cleared_at   TIMESTAMPTZ,
  peak         DOUBLE PRECISION,
  rooms        TEXT[] NOT NULL DEFAULT '{}',
  places       TEXT[] NOT NULL DEFAULT '{}',
  ever_sent    BOOLEAN NOT NULL DEFAULT FALSE,
  action_id    TEXT
);
CREATE INDEX IF NOT EXISTS events_open ON events (issue) WHERE cleared_at IS NULL;
CREATE TABLE IF NOT EXISTS event_messages (
  id        BIGSERIAL PRIMARY KEY,
  ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_id  BIGINT NOT NULL REFERENCES events(id),
  reason    TEXT NOT NULL CHECK (reason IN ('open','escalate','clear')),
  sent      BOOLEAN NOT NULL,
  held      TEXT,
  mode      TEXT NOT NULL,
  text      TEXT
);
ALTER TABLE alerts  ADD COLUMN IF NOT EXISTS event_id BIGINT REFERENCES events(id);
ALTER TABLE actions ADD COLUMN IF NOT EXISTS event_id BIGINT REFERENCES events(id);
-- `dismissed`: "Doesn't fit" (SPEC_alerts §7). Like `decided`, it moves nothing in rho's alert-level funnel.
ALTER TABLE actions DROP CONSTRAINT IF EXISTS actions_stage_check;
ALTER TABLE actions ADD CONSTRAINT actions_stage_check
  CHECK (stage IN ('acknowledged','acted','measured','settings','decided','dismissed'));
GRANT SELECT ON events, event_messages TO planetai_ro;
```

- [ ] **Step 4: Settings**

In `app/settings.py` `RUNTIME`, in the `alerts` group after `QUIET_TO`:

```python
    "ALERT_ENGINE":       ("alerts", "Alert engine", False, False,
                           "rules = every rule sends on its own, as before (default). shadow = the event engine "
                           "(docs/SPEC_alerts.md) decides what it would send and records it, and sends nothing; "
                           "the rules keep sending. events = the event engine sends instead of the rules."),
    "ALERT_MAX_PER_DAY":  ("alerts", "Most messages a day", False, False,
                           "With the event engine: pushes a day outside danger, default 4. Beyond it an event "
                           "is still recorded and waits for the next report. Danger is never held."),
    "HOME_HAS":           ("alerts", "What this home has", False, False,
                           "Comma-separated: purifier, ac, fan, windows (windows that open). The event engine "
                           "only suggests what is here to use."),
```

In `CHOICES`:

```python
    "ALERT_ENGINE":  ("rules", "shadow", "events"),
```

(`ALERT_MAX_PER_DAY` is a number and `HOME_HAS` a list: validate both in `events_pg`, not in `CHOICES`.)

In `.env.example`, after `QUIET_TO=6`:

```
# rules (default) | shadow | events. docs/SPEC_alerts.md: shadow records what the event engine would send, sends nothing.
ALERT_ENGINE=rules
# With the event engine: pushes a day outside danger.
ALERT_MAX_PER_DAY=4
# What this home has, comma-separated: purifier, ac, fan, windows.
HOME_HAS=
```

In `docs/site/configuration.md`, add three rows to the alerts table in the same shape as its neighbours (one row
per key above, with default and choices), and in `tools/check_docs.py` remove `"ALERT_ENGINE"` from
`PROPOSED["docs/SPEC_alerts.md"]`.

- [ ] **Step 5: Write `app/events_pg.py`**

```python
"""The event engine against Postgres: candidates from kinded rules, a Policy from settings, and a store.
docs/SPEC_alerts.md §4. The decisions are app/events.py's; this file only reads and writes."""
from __future__ import annotations

import datetime as dt
import logging

import events as E
import settings

log = logging.getLogger("planetai")
# a pack's domain is its issue unless a rule says otherwise
PACK_ISSUE = {"air-quality": "air", "heat": "heat"}
HOME_ITEMS = ("purifier", "ac", "fan", "windows")


def candidates(rule: dict, rows: list[dict]) -> list[E.Candidate]:
    kind = rule.get("kind")
    if not kind:
        return []                                     # report-only: never interrupts (SPEC_alerts §3)
    pack = rule["id"].split("/", 1)[0]
    issue = rule.get("issue") or PACK_ISSUE.get(pack, pack)
    out = []
    for r in rows:
        if r.get("value") is None or r.get("line") is None:
            continue
        out.append(E.Candidate(rule_id=rule["id"], issue=issue, kind=kind, level=rule.get("level", "info"),
                               sensor_id=str(r.get("sensor_id", "node")), room=str(r.get("name") or r.get("sensor_id")),
                               value=float(r["value"]), line=float(r["line"]), over=bool(r.get("over", True)),
                               where=str(r.get("where") or "inside")))
    return out


def policy() -> E.Policy:
    quiet = None
    if settings.get("QUIET_HOURS", "1") == "1":
        a, b = settings.get("QUIET_FROM", "22") or "22", settings.get("QUIET_TO", "6") or "6"
        if a.isdigit() and b.isdigit():
            quiet = (int(a), int(b))
    n = settings.get("ALERT_MAX_PER_DAY", "4") or "4"
    return E.Policy(quiet=quiet, max_per_day=int(n) if n.isdigit() else 4,
                    alert_level=settings.get("ALERT_LEVEL", "act") or "act")


def home_has() -> set[str]:
    return {x.strip() for x in (settings.get("HOME_HAS", "") or "").split(",") if x.strip() in HOME_ITEMS}


class PgStore:
    """MemoryStore's four methods, kept in `events` and `event_messages`."""

    def __init__(self, cur):
        self.cur = cur

    def open_events(self) -> list[E.Event]:
        self.cur.execute("SELECT * FROM events WHERE cleared_at IS NULL")
        return [E.Event(issue=r["issue"], kind=r["kind"], level=r["level"], opened_at=r["opened_at"],
                        last_seen_at=r["last_seen_at"], peak=r["peak"], rooms=set(r["rooms"]), where=set(r["places"]),
                        last_sent_at=r["last_sent_at"], cleared_at=r["cleared_at"], ever_sent=r["ever_sent"],
                        id=r["id"], action_id=r["action_id"]) for r in self.cur.fetchall()]

    def save(self, e: E.Event) -> E.Event:
        vals = (e.issue, e.kind, e.level, e.opened_at, e.last_seen_at, e.last_sent_at, e.cleared_at, e.peak,
                sorted(e.rooms), sorted(e.where), e.ever_sent, e.action_id)
        if e.id is None:
            self.cur.execute("""INSERT INTO events (issue, kind, level, opened_at, last_seen_at, last_sent_at,
                                cleared_at, peak, rooms, places, ever_sent, action_id)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""", vals)
            e.id = self.cur.fetchone()["id"]
        else:
            self.cur.execute("""UPDATE events SET issue=%s, kind=%s, level=%s, opened_at=%s, last_seen_at=%s,
                                last_sent_at=%s, cleared_at=%s, peak=%s, rooms=%s, places=%s, ever_sent=%s,
                                action_id=%s WHERE id=%s""", (*vals, e.id))
        return e

    def sends_on(self, day: dt.date) -> int:
        self.cur.execute("""SELECT count(*) AS n FROM event_messages m JOIN events e ON e.id = m.event_id
                            WHERE m.sent AND m.reason <> 'clear' AND e.kind <> 'danger'
                              AND (m.ts AT TIME ZONE current_setting('TimeZone'))::date = %s""", (day,))
        return self.cur.fetchone()["n"]

    def count_send(self, day: dt.date) -> None:
        pass                                          # counted from event_messages, which run() writes


def run(cur, cands: list[E.Candidate], mode: str, now: dt.datetime) -> list[E.Message]:
    """One engine step. Every decided message is recorded; in shadow, `sent` records what WOULD have gone out."""
    msgs = E.step(now, cands, PgStore(cur), policy())
    for m in msgs:
        cur.execute("INSERT INTO event_messages (ts, event_id, reason, sent, held, mode, text) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (now, m.event.id, m.reason, m.send, m.held, mode, None))
    return msgs
```

The `text` column is filled by Task 4.

- [ ] **Step 6: Wire `run_rules`**

In `app/main.py` `run_rules`, read the mode once before the loop, skip kinded rules on the old path, collect their
candidates, and run the engine after the loop:

```python
def run_rules() -> None:
    rules = packs.load_rules()
    mode = settings.get("ALERT_ENGINE", "rules") or "rules"
    cands = []
    with db() as con, con.cursor() as cur:
        try:
            run_report(cur)
        except Exception as e:  # noqa: BLE001
            log.warning("report failed: %s", e)
        for rule in rules:
            if rule.get("kind") and mode == "rules":
                continue                  # kinded rules belong to the event engine (docs/SPEC_alerts.md)
            try:
                rows = index.run_ro(cur, rule["sql"])
            except Exception as e:  # noqa: BLE001
                log.warning("rule %s failed: %s", rule.get("id"), e)
                continue
            if rule.get("kind"):
                cands += events_pg.candidates(rule, rows)
                continue                  # never through the old cooldown-and-send path
            ...  # the existing per-row body, unchanged, except: in mode "events" it does not call notify()
        if mode in ("shadow", "events"):
            try:
                events_pg.run(cur, cands, mode, _local_now())
            except Exception as e:  # noqa: BLE001
                log.warning("event engine failed: %s", e)
```

Kinded rules write no `alerts` row in this plan, on purpose. An act-level `alerts` row is an open ask on the
dashboard and a row in ρ's denominator, so writing them in shadow would change what the household sees and what ρ
says, which shadow must never do. Recording kinded rows in `alerts` and linking them through `alerts.event_id`
belongs to Plan 2, together with `events` mode actually sending; the column is created here so Plan 2 adds no
schema step.

Keep the existing per-row body exactly as it is (cooldown, insert into `alerts`, `ha_alert`), and change only its
`send` line to `send = mode != "events" and floor.get(...) >= ... and not _quiet(level)`. Add `import events_pg`
beside the other app imports. In `events` mode nothing notifies yet: Plan 2 wires the event messages to Telegram,
so `events` must not be set on a node until then — say so in the `ALERT_ENGINE` help text by appending
" Until the release that adds buttons, events records and sends nothing: use shadow."

- [ ] **Step 7: Run tests and prove the schema twice**

Run: `PYTHONPATH=app python3 tests/test_events_pg.py` — expected three lines, last `events_pg: …`.
Run against a scratch Postgres: `psql "$SCRATCH_DB" -f init.sql` twice, then
`psql "$SCRATCH_DB" -c "\d events" -c "\d event_messages"` — expected both tables, no errors.

Register `test_events_pg|PYTHONPATH=app python3 tests/test_events_pg.py` in `tests/all`, count 57 → 58.

- [ ] **Step 8: Lint, test, commit**

Run: `make lint && make test` — expected `ok` and `58 suites: 58 passed`.

```bash
git add init.sql app/events_pg.py app/main.py app/settings.py .env.example docs/site/configuration.md tools/check_docs.py tests/test_events_pg.py tests/all
git commit -m "events: the Postgres store, ALERT_ENGINE (rules|shadow|events), and the engine in run_rules"
```

PR body note: "`init.sql` changes: two maintainers (GOVERNANCE.md)."

---

### Task 4: Messages and actions chosen from the context

**Files:**
- Create: `app/actions.py`
- Modify: `app/issues/heat.yml`, `app/issues/air.yml` (append `events:` and `actions:`)
- Modify: `app/events_pg.py` (`context(cur, e)`, fill `event_messages.text` and `events.action_id`)
- Create: `tests/test_actions.py`; `tests/all` (58 → 59)

**Interfaces:**
- Consumes: `events.Event`, `events.Message`; `events_pg.home_has()`.
- Produces:
  - `actions.holds(when: dict, ctx: dict) -> bool`
  - `actions.choose(actions: list[dict], ctx: dict) -> dict | None` — first action whose `when:` holds
  - `actions.render(issue: dict, msg: events.Message, ctx: dict, locale: str) -> tuple[str, str | None]` — the text
    and the chosen action id
  - context keys (all optional, `None` when unknown): `inside_temp`, `outside_temp`, `inside_pm25`, `outside_pm25`,
    `outside_source`, `hour`, `home_has` (set), `where` (set of `inside`/`outside`), `kind`, `rooms`, `peak`

The `when:` vocabulary is closed (evaluated in Python, never `eval`):

| key | holds when |
|---|---|
| `kind: [sustained, danger]` | the event's kind is listed |
| `where: inside` | `inside` is among the event's places |
| `outside_cooler_by: 2` | `inside_temp - outside_temp >= 2` |
| `outside_hotter: true` | `outside_temp > inside_temp` |
| `outside_pm25_below: 15` | `outside_pm25 < 15` |
| `outside_worse: true` | `outside_pm25 > inside_pm25` |
| `home_has: ac` | `ac` is in `home_has` |
| `hour_from: 17` / `hour_to: 8` | the local hour is in [from, to), wrapping midnight |

A key whose context value is `None` does not hold.

- [ ] **Step 1: Write the failing test**

`tests/test_actions.py`:

```python
"""Actions are chosen from what is happening, one per event (docs/SPEC_alerts.md §5).
Run: PYTHONPATH=app python3 tests/test_actions.py
"""
import datetime as dt
from pathlib import Path

import yaml

import actions as A
import events as E

ROOT = Path(__file__).resolve().parent.parent
heat = yaml.safe_load((ROOT / "app/issues/heat.yml").read_text())
air = yaml.safe_load((ROOT / "app/issues/air.yml").read_text())

night = dict(inside_temp=29.3, outside_temp=24.9, outside_pm25=10, inside_pm25=8, hour=20, home_has=set(),
             where={"inside"}, kind="sustained")
assert A.choose(heat["actions"], night)["id"] == "heat/open_up", "outside 4.4 °C cooler and clean: open up"
noon = dict(night, outside_temp=32.3, inside_temp=30.2, hour=13)
assert A.choose(heat["actions"], noon)["id"] == "heat/keep_shut_shaded", "outside hotter: keep it shut"
smoky = dict(night, outside_pm25=60)
assert A.choose(heat["actions"], smoky)["id"] != "heat/open_up", "never open up into smoke"
print("  heat: open up when outside is cooler and clean, keep shut when it is hotter, never into smoke")

cook = dict(where={"inside"}, inside_pm25=59, outside_pm25=12, home_has={"purifier"}, kind="spike", hour=12)
assert A.choose(air["actions"], cook)["id"] == "air/ventilate_and_purify"
bad_out = dict(cook, where={"outside"}, outside_pm25=80, inside_pm25=20)
assert A.choose(air["actions"], bad_out)["id"] == "air/keep_shut_purify"
none = dict(bad_out, home_has=set())
assert A.choose(air["actions"], none)["id"] == "air/keep_shut", "no purifier: do not suggest one"
print("  air: ventilate a kitchen spike, keep shut when outside is worse, never a purifier the home has not got")

assert not A.holds({"outside_cooler_by": 2}, dict(night, outside_temp=None)), "unknown context does not hold"
assert A.holds({"hour_from": 17, "hour_to": 8}, dict(night, hour=2)) and not A.holds({"hour_from": 17, "hour_to": 8}, dict(night, hour=12))
print("  when: an unknown value never holds; hour windows wrap midnight")

t0 = dt.datetime(2026, 9, 25, 20, 0)
e = E.Event(issue="heat", kind="sustained", level="act", opened_at=t0, last_seen_at=t0, peak=36.7, rooms={"K ROOM"})
text, aid = A.render(heat, E.Message(e, "open", True, None), night, "en")
assert "K ROOM" in text and "👉" in text and aid == "heat/open_up", text
text_id, _ = A.render(heat, E.Message(e, "open", True, None), night, "id")
assert text_id != text, "id has its own sentence"
clear, aid2 = A.render(heat, E.Message(e, "clear", True, None), night, "en")
assert "👉" not in clear and aid2 is None, "an all-clear carries no action"
print("actions: one action per event, chosen from the context; messages in three languages")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=app python3 tests/test_actions.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'actions'`.

- [ ] **Step 3: Write `app/actions.py`**

```python
"""One action per event, chosen from what is happening (docs/SPEC_alerts.md §5), and the message around it.

An issue file lists candidate actions in order; the first whose `when:` holds is the one sent. `when:` is a closed
vocabulary evaluated here, never eval'd: a pack can add actions to an issue, and a pack is not trusted to run code
in this path. A context value the node does not know is None, and a condition on None does not hold, so an action
that needs the outside temperature is never chosen on a node that has none.
"""
from __future__ import annotations


def _in_window(h, a, b) -> bool:
    return (a <= h or h < b) if a > b else (a <= h < b)


def holds(when: dict, ctx: dict) -> bool:
    for k, want in (when or {}).items():
        if k == "kind":
            ok = ctx.get("kind") in want
        elif k == "where":
            ok = want in (ctx.get("where") or set())
        elif k == "home_has":
            ok = want in (ctx.get("home_has") or set())
        elif k in ("hour_from", "hour_to"):
            continue                                   # checked as a pair below
        else:
            it, ot = ctx.get("inside_temp"), ctx.get("outside_temp")
            ip, op = ctx.get("inside_pm25"), ctx.get("outside_pm25")
            if k == "outside_cooler_by":
                ok = it is not None and ot is not None and it - ot >= want
            elif k == "outside_hotter":
                ok = it is not None and ot is not None and (ot > it) == bool(want)
            elif k == "outside_pm25_below":
                ok = op is not None and op < want
            elif k == "outside_worse":
                ok = ip is not None and op is not None and (op > ip) == bool(want)
            else:
                return False                           # an unknown key never holds: a typo cannot widen an action
        if not ok:
            return False
    if "hour_from" in (when or {}):
        h = ctx.get("hour")
        if h is None or not _in_window(h, when["hour_from"], when.get("hour_to", 24)):
            return False
    return True


def choose(actions: list[dict], ctx: dict) -> dict | None:
    for a in actions or []:
        if holds(a.get("when") or {}, ctx):
            return a
    return None


def _say(block, locale):
    return (block or {}).get(locale) or (block or {}).get("en") or ""


def render(issue: dict, msg, ctx: dict, locale: str) -> tuple[str, str | None]:
    e = msg.event
    tpl = (issue.get("events") or {}).get(msg.reason if msg.reason == "clear" else e.kind) or {}
    fields = {"rooms": ", ".join(sorted(e.rooms)), "peak": round(e.peak, 1),
              "outside_temp": ctx.get("outside_temp"), "inside_temp": ctx.get("inside_temp"),
              "outside_pm25": ctx.get("outside_pm25"), "inside_pm25": ctx.get("inside_pm25"),
              "outside_source": ctx.get("outside_source") or "outside"}
    fields = {k: ("—" if v is None else v) for k, v in fields.items()}
    try:
        text = _say(tpl, locale).format(**fields)
    except (KeyError, ValueError):
        text = _say(tpl, locale)
    if msg.reason == "clear":
        return text, None
    a = choose(issue.get("actions") or [], ctx)
    if not a:
        return text, None
    try:
        line = _say(a.get("say"), locale).format(**fields)
    except (KeyError, ValueError):
        line = _say(a.get("say"), locale)
    return f"{text}\n\n👉 {line}", a["id"]
```

- [ ] **Step 4: Append templates and actions to the issue files**

At the end of `app/issues/heat.yml`:

```yaml
# Events (docs/SPEC_alerts.md §4–§5). One message per heat event at this house, whichever rooms it spans; one
# action, the first below whose `when:` holds. The id and es strings are ASSISTANT-WRITTEN.
events:
  unusual:
    en: "🌡️ Hotter than usual in {rooms}: it feels like {peak} °C, well above this room's normal for the hour."
    id: "🌡️ Lebih panas dari biasanya di {rooms}: terasa seperti {peak} °C, jauh di atas biasanya untuk jam ini."
    es: "🌡️ Más calor de lo habitual en {rooms}: la sensación es de {peak} °C, muy por encima de lo normal a esta hora."
  sustained:
    en: "🥵 {rooms} has been hot for hours: it feels like {peak} °C, longer than this room usually stays there."
    id: "🥵 {rooms} sudah panas berjam-jam: terasa seperti {peak} °C, lebih lama dari biasanya."
    es: "🥵 {rooms} lleva horas con calor: la sensación es de {peak} °C, más tiempo del que suele durar."
  danger:
    en: "🚨🥵 DANGER in {rooms}: it feels like {peak} °C. The body cannot shed heat at this level."
    id: "🚨🥵 BAHAYA di {rooms}: terasa seperti {peak} °C. Tubuh tidak bisa membuang panas di tingkat ini."
    es: "🚨🥵 PELIGRO en {rooms}: la sensación es de {peak} °C. A este nivel el cuerpo no consigue soltar calor."
  clear:
    en: "✅ {rooms} has cooled back to its usual."
    id: "✅ {rooms} sudah kembali sejuk seperti biasa."
    es: "✅ {rooms} ha vuelto a su temperatura habitual."
actions:
  - id: heat/leave_or_cool
    when: {kind: [danger]}
    say:
      en: "Cool the room or leave it: wet skin, a fan, shade, water. Do not leave anyone alone in it."
      id: "Dinginkan ruangan atau keluar: basahi kulit, kipas, teduh, air. Jangan tinggalkan siapa pun sendirian."
      es: "Enfría la habitación o sal de ella: piel mojada, ventilador, sombra, agua. No dejes a nadie solo ahí."
  - id: heat/open_up
    when: {outside_cooler_by: 2, outside_pm25_below: 35}
    say:
      en: "Open up now: {outside_source} is {outside_temp} °C and inside is {inside_temp} °C."
      id: "Buka sekarang: {outside_source} {outside_temp} °C, di dalam {inside_temp} °C."
      es: "Abre ahora: {outside_source} está a {outside_temp} °C y dentro hay {inside_temp} °C."
  - id: heat/keep_shut_shaded
    when: {outside_hotter: true}
    say:
      en: "Keep it shut and shaded: outside ({outside_temp} °C) is hotter than inside for now."
      id: "Tutup dan beri peneduh: di luar ({outside_temp} °C) masih lebih panas dari dalam."
      es: "Mantén cerrado y a la sombra: fuera ({outside_temp} °C) hace más calor que dentro por ahora."
  - id: heat/cool_sleeping_room
    when: {kind: [sustained], home_has: ac, hour_from: 17, hour_to: 23}
    say:
      en: "Cool the room you sleep in before 22:00."
      id: "Dinginkan kamar tidur sebelum pukul 22:00."
      es: "Enfría la habitación donde duermes antes de las 22:00."
  - id: heat/water_and_rest
    when: {}
    say:
      en: "Drink water, move air, and ease off hard work until it drops."
      id: "Minum air, gerakkan udara, dan kurangi kerja berat sampai turun."
      es: "Bebe agua, mueve el aire y afloja el trabajo duro hasta que baje."
```

At the end of `app/issues/air.yml`:

```yaml
# Events (docs/SPEC_alerts.md §4–§5). The id and es strings are ASSISTANT-WRITTEN.
events:
  spike:
    en: "📈 The air jumped in {rooms}: {peak} µg/m³ PM2.5. Outside is {outside_pm25}."
    id: "📈 Udara melonjak di {rooms}: PM2.5 {peak} µg/m³. Di luar {outside_pm25}."
    es: "📈 El aire empeoró de golpe en {rooms}: {peak} µg/m³ de PM2.5. Fuera hay {outside_pm25}."
  unusual:
    en: "😷 The air in {rooms} is worse than usual for this hour: {peak} µg/m³ PM2.5."
    id: "😷 Udara di {rooms} lebih buruk dari biasanya untuk jam ini: PM2.5 {peak} µg/m³."
    es: "😷 El aire en {rooms} está peor de lo habitual a esta hora: {peak} µg/m³ de PM2.5."
  sustained:
    en: "😷 The air in {rooms} has been unhealthy for an hour: {peak} µg/m³ PM2.5."
    id: "😷 Udara di {rooms} sudah tidak sehat selama satu jam: PM2.5 {peak} µg/m³."
    es: "😷 El aire en {rooms} lleva una hora siendo insalubre: {peak} µg/m³ de PM2.5."
  danger:
    en: "🚨😷 DANGER: the air in {rooms} is very unhealthy: {peak} µg/m³ PM2.5."
    id: "🚨😷 BAHAYA: udara di {rooms} sangat tidak sehat: PM2.5 {peak} µg/m³."
    es: "🚨😷 PELIGRO: el aire en {rooms} es muy insalubre: {peak} µg/m³ de PM2.5."
  clear:
    en: "✅ The air in {rooms} is back to normal."
    id: "✅ Udara di {rooms} sudah kembali normal."
    es: "✅ El aire en {rooms} ha vuelto a la normalidad."
actions:
  - id: air/ventilate_and_purify
    when: {where: inside, outside_worse: false, outside_pm25_below: 35, home_has: purifier}
    say:
      en: "Open the side where it started and run the purifier for 30 min: outside is cleaner ({outside_pm25})."
      id: "Buka sisi asal asapnya dan nyalakan pemurni udara 30 menit: di luar lebih bersih ({outside_pm25})."
      es: "Abre el lado donde empezó y enciende el purificador 30 min: fuera está más limpio ({outside_pm25})."
  - id: air/ventilate
    when: {where: inside, outside_worse: false, outside_pm25_below: 35}
    say:
      en: "Open the side where it started and let it through: outside is cleaner ({outside_pm25})."
      id: "Buka sisi asal asapnya dan biarkan mengalir: di luar lebih bersih ({outside_pm25})."
      es: "Abre el lado donde empezó y deja que corra: fuera está más limpio ({outside_pm25})."
  - id: air/keep_shut_purify
    when: {outside_worse: true, home_has: purifier}
    say:
      en: "Keep windows and doors shut and run the purifier until outside clears."
      id: "Tutup jendela dan pintu dan nyalakan pemurni udara sampai di luar bersih."
      es: "Mantén ventanas y puertas cerradas y enciende el purificador hasta que fuera se limpie."
  - id: air/keep_shut
    when: {outside_worse: true}
    say:
      en: "Keep windows and doors shut until outside clears."
      id: "Tutup jendela dan pintu sampai di luar bersih."
      es: "Mantén ventanas y puertas cerradas hasta que fuera se limpie."
  - id: air/find_source
    when: {}
    say:
      en: "Look for what started it, cooking, burning or dust, and keep people away from it."
      id: "Cari sumbernya, masak, pembakaran atau debu, dan jauhkan orang darinya."
      es: "Busca qué lo provocó, cocina, quema o polvo, y mantén a la gente lejos."
```

- [ ] **Step 5: Context from the database, and the text recorded**

In `app/events_pg.py` add:

```python
import actions as A
import issues

CTX_SQL = """
SELECT
  (SELECT avg(mean_15m) FROM stats WHERE local AND indoor AND metric = 'temp' AND name = ANY(%(rooms)s)) AS inside_temp,
  (SELECT avg(mean_15m) FROM stats WHERE local AND indoor AND metric = 'pm25' AND name = ANY(%(rooms)s)) AS inside_pm25,
  coalesce((SELECT avg(mean_1h) FROM stats WHERE local AND NOT indoor AND metric = 'temp'),
           (SELECT value FROM observations WHERE sensor_id = 'om-point' AND metric = 'temp_model' AND ts <= now())) AS outside_temp,
  (SELECT avg(mean_1h) FROM stats WHERE local AND NOT indoor AND metric = 'pm25') AS outside_pm25,
  CASE WHEN EXISTS (SELECT 1 FROM stats WHERE local AND NOT indoor AND metric = 'temp')
       THEN 'outside' ELSE 'the forecast model' END AS outside_source
"""


def context(cur, e, now) -> dict:
    cur.execute(CTX_SQL, {"rooms": sorted(e.rooms)})
    ctx = dict(cur.fetchone())
    for k in ("inside_temp", "inside_pm25", "outside_temp", "outside_pm25"):
        if ctx[k] is not None:
            ctx[k] = round(float(ctx[k]), 1)
    ctx.update(hour=now.hour, home_has=home_has(), where=set(e.where), kind=e.kind)
    return ctx
```

and in `run()` replace the `INSERT` loop with:

```python
    decl = issues.load()
    for m in msgs:
        text, aid = None, None
        if m.event.issue in decl:
            text, aid = A.render(decl[m.event.issue], m, context(cur, m.event, now), settings.get("ALERT_LOCALE", "en") or "en")
        if aid:
            m.event.action_id = aid
            cur.execute("UPDATE events SET action_id = %s WHERE id = %s", (aid, m.event.id))
        cur.execute("INSERT INTO event_messages (ts, event_id, reason, sent, held, mode, text) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (now, m.event.id, m.reason, m.send, m.held, mode, text))
```

Check `issues.load()`'s return shape against `app/issues/__init__.py:689` (a dict keyed by file stem: `heat`, `air`)
before relying on it; `om-point`'s temperature metric name is `temp_model` on node #1 — confirm in
`app/bootstrap.py` and use the name it writes.

- [ ] **Step 6: Run the tests**

Run: `PYTHONPATH=app python3 tests/test_actions.py` — expected four lines, last `actions: …`.
Run: `PYTHONPATH=app python3 tests/test_issues.py && PYTHONPATH=app python3 tests/test_issues_schema.py` — expected
pass: the new top-level keys must not break the issue contract. If `test_issues_schema` lists allowed keys, add
`events` and `actions` there with one comment line naming this spec.

- [ ] **Step 7: Register, lint, test, commit**

`tests/all`: `test_actions|PYTHONPATH=app python3 tests/test_actions.py`, count 58 → 59.
Run: `make lint && make test` — `59 suites: 59 passed`.

```bash
git add app/actions.py app/events_pg.py app/issues/heat.yml app/issues/air.yml tests/test_actions.py tests/all
git commit -m "events: one action per event, chosen from inside, outside, the hour and what the home has"
```

---

### Task 5: Kinded heat and air rules

**Files:**
- Modify: `packs/heat/rules.yml`, `packs/air-quality/rules.yml` (append rules; touch nothing existing)
- Create: `tests/test_kinded_rules.py`; `tests/all` (59 → 60)

**Interfaces:**
- Consumes: `recent_15m`, `usual_by_hour` (Task 1); `trustdb.Node` (Task 1).
- Produces rules (every row: `sensor_id, name, value, line, over`, air rows also `where`):
  - `heat/heat_unusual` — `kind: unusual`, `level: act`
  - `heat/heat_sustained` — `kind: sustained`, `level: act`
  - `heat/heat_extreme` — `kind: danger`, `level: act`
  - `air-quality/air_spike` — `kind: spike`, `level: warn`
  - `air-quality/air_unusual` — `kind: unusual`, `level: act`
  - `air-quality/air_sustained` — `kind: sustained`, `level: act`
  - `air-quality/air_extreme` — `kind: danger`, `level: act`

- [ ] **Step 1: Write the failing test**

`tests/test_kinded_rules.py`:

```python
"""Kinded rules over node #1's readings (docs/SPEC_alerts.md §3): they return the columns the engine reads, and
the heat rules do not fire on the room's ordinary afternoon. Needs duckdb.
Run: PYTHONPATH=tests:app python3 tests/test_kinded_rules.py
"""
import datetime as dt
import sys

try:
    import trustdb as T
except ImportError as e:
    print(f"  skipped: {e}")
    sys.exit(0)

heat, air = T.rules("heat"), T.rules("air-quality")
NEW_HEAT = ("heat_unusual", "heat_sustained", "heat_extreme")
NEW_AIR = ("air_spike", "air_unusual", "air_sustained", "air_extreme")
for name, rs in ((NEW_HEAT, heat), (NEW_AIR, air)):
    for r in name:
        assert rs[r].get("kind") in ("spike", "unusual", "sustained", "danger"), r
print("  seven kinded rules, each declaring its kind")

rows = T.readings()
node = T.Node(T.week(rows, T.FIXTURE_NOW, days=15))
node.refresh_usual(T.FIXTURE_NOW)
fired = {r: 0 for r in NEW_HEAT}
for h in range(24):                                  # one ordinary replayed day, hour by hour
    at = T.FIXTURE_NOW - dt.timedelta(hours=h)
    for r in NEW_HEAT:
        out = node.run(heat[r], at)
        for row in out:
            assert {"sensor_id", "name", "value", "line", "over"} <= set(row), (r, row)
        fired[r] += sum(1 for row in out if row["over"])
assert fired["heat_extreme"] == 0, "nothing on node #1's ordinary day is 40 °C apparent"
assert fired["heat_unusual"] == 0, "a replayed ordinary day is never above its own p90 + 2"
print(f"  an ordinary day replayed: unusual {fired['heat_unusual']}, extreme {fired['heat_extreme']}, "
      f"sustained {fired['heat_sustained']} hours over")

for r in NEW_AIR:
    for row in node.run(air[r], T.FIXTURE_NOW):
        assert {"sensor_id", "name", "value", "line", "over", "where"} <= set(row), (r, row)
print("kinded rules: the engine's columns, and no heat event on an ordinary day")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=tests:app python3 tests/test_kinded_rules.py`
Expected: FAIL with `KeyError: 'heat_unusual'`.

- [ ] **Step 3: Append the heat rules**

At the end of `packs/heat/rules.yml` (the existing rules stay: `ALERT_ENGINE=rules` still runs them):

```yaml
# ---- kinded rules: the event engine's (docs/SPEC_alerts.md §3). The old engine skips any rule with `kind:`. ----
# Every row carries value, line and over. A row with over=false is inside the margin: it keeps an open event open
# and never opens one. Thresholds are starting values for the replay of node #1's month.

- id: heat_unusual
  kind: unusual
  issue: heat
  level: act
  cooldown_minutes: 60
  sql: |
    WITH a AS (SELECT r.sensor_id, s.name, r.bucket, r.mean FROM recent_15m r JOIN sensors s ON s.sensor_id = r.sensor_id
               WHERE r.metric = 'apparent' AND s.local AND s.indoor AND r.bucket > now() - INTERVAL '1 hour'),
         u AS (SELECT sensor_id, p90 FROM usual_by_hour
               WHERE metric = 'apparent' AND hour = CAST(extract(hour FROM now()) AS INTEGER))
    SELECT a.sensor_id, a.name, round(CAST(avg(a.mean) AS NUMERIC), 1) AS value,
           round(CAST(min(u.p90) + 2 AS NUMERIC), 1) AS line,
           min(a.mean) >= min(u.p90) + 2 AS over
    FROM a JOIN u ON u.sensor_id = a.sensor_id
    GROUP BY a.sensor_id, a.name
    HAVING count(*) >= 3 AND avg(a.mean) >= min(u.p90) + 1
  message:
    en: "Heat in {name}: it feels like {value} °C, above this room's usual of the hour ({line})."
    id: "Panas di {name}: terasa seperti {value} °C, di atas biasanya untuk jam ini ({line})."
    es: "Calor en {name}: la sensación es de {value} °C, por encima de lo habitual a esta hora ({line})."

- id: heat_sustained
  kind: sustained
  issue: heat
  level: act
  cooldown_minutes: 60
  sql: |
    WITH a AS (SELECT r.sensor_id, s.name, r.bucket, r.mean FROM recent_15m r JOIN sensors s ON s.sensor_id = r.sensor_id
               WHERE r.metric = 'apparent' AND s.local AND s.indoor),
         l AS (SELECT sensor_id, name, max(bucket) AS b FROM a GROUP BY 1, 2),
         v AS (SELECT a.sensor_id, a.mean FROM a JOIN l ON l.sensor_id = a.sensor_id AND a.bucket = l.b),
         k AS (SELECT sensor_id, max(bucket) AS b FROM a WHERE mean < 35 GROUP BY 1),
         u AS (SELECT sensor_id, count(*) AS hours FROM usual_by_hour WHERE metric = 'apparent' AND p75 >= 35 GROUP BY 1)
    SELECT l.sensor_id, l.name, round(CAST(v.mean AS NUMERIC), 1) AS value, 35 AS line,
           round(CAST(extract(epoch FROM l.b - coalesce(k.b, l.b - INTERVAL '24 hours')) / 3600.0 AS NUMERIC), 1) AS hours,
           coalesce(u.hours, 0) AS usual_hours,
           extract(epoch FROM l.b - coalesce(k.b, l.b - INTERVAL '24 hours')) / 3600.0 >= greatest(3, coalesce(u.hours, 0) + 1) AS over
    FROM l JOIN v ON v.sensor_id = l.sensor_id
    LEFT JOIN k ON k.sensor_id = l.sensor_id LEFT JOIN u ON u.sensor_id = l.sensor_id
    WHERE v.mean >= 34
  message:
    en: "Heat in {name}: {hours} h at a feels-like of 35 °C or more (usually {usual_hours} h); now {value} °C."
    id: "Panas di {name}: {hours} jam terasa 35 °C atau lebih (biasanya {usual_hours} jam); sekarang {value} °C."
    es: "Calor en {name}: {hours} h con sensación de 35 °C o más (lo habitual, {usual_hours} h); ahora {value} °C."

- id: heat_extreme
  kind: danger
  issue: heat
  level: act
  cooldown_minutes: 60
  sql: |
    SELECT r.sensor_id, s.name, round(CAST(r.mean AS NUMERIC), 1) AS value, 40 AS line, r.mean >= 40 AS over
    FROM recent_15m r JOIN sensors s ON s.sensor_id = r.sensor_id
    WHERE r.metric = 'apparent' AND s.local AND s.indoor
      AND r.bucket = (SELECT max(bucket) FROM recent_15m WHERE sensor_id = r.sensor_id AND metric = 'apparent')
      AND r.mean >= 39
  message:
    en: "Danger in {name}: it feels like {value} °C."
    id: "Bahaya di {name}: terasa seperti {value} °C."
    es: "Peligro en {name}: la sensación es de {value} °C."
```

- [ ] **Step 4: Append the air rules**

At the end of `packs/air-quality/rules.yml`:

```yaml
# ---- kinded rules: the event engine's (docs/SPEC_alerts.md §3). The old engine skips any rule with `kind:`. ----
# Starting values for the replay. Rows carry value, line, over and where (inside | outside).

- id: air_spike
  kind: spike
  issue: air
  level: warn
  cooldown_minutes: 60
  sql: |
    WITH q AS (SELECT r.sensor_id, s.name, s.indoor, r.bucket, r.mean FROM recent_15m r JOIN sensors s ON s.sensor_id = r.sensor_id
               WHERE r.metric = 'pm25' AND s.local AND r.bucket > now() - INTERVAL '75 minutes'),
         l AS (SELECT sensor_id, max(bucket) AS b FROM q GROUP BY 1),
         now_v AS (SELECT q.sensor_id, q.name, q.indoor, q.mean FROM q JOIN l ON l.sensor_id = q.sensor_id AND q.bucket = l.b),
         before AS (SELECT q.sensor_id, avg(q.mean) AS mean FROM q JOIN l ON l.sensor_id = q.sensor_id AND q.bucket < l.b GROUP BY 1),
         u AS (SELECT sensor_id, p90 FROM usual_by_hour WHERE metric = 'pm25' AND hour = CAST(extract(hour FROM now()) AS INTEGER))
    SELECT n.sensor_id, n.name, round(CAST(n.mean AS NUMERIC), 1) AS value,
           round(CAST(greatest(b.mean + 12, coalesce(u.p90, 0) + 10) AS NUMERIC), 1) AS line,
           n.mean >= b.mean + 12 AND n.mean >= coalesce(u.p90, 0) + 10 AS over,
           CASE WHEN n.indoor THEN 'inside' ELSE 'outside' END AS "where"
    FROM now_v n JOIN before b ON b.sensor_id = n.sensor_id LEFT JOIN u ON u.sensor_id = n.sensor_id
    WHERE n.mean >= b.mean + 7
  message:
    en: "PM2.5 jumped at {name}: {value} µg/m³."
    id: "PM2.5 melonjak di {name}: {value} µg/m³."
    es: "El PM2.5 subió de golpe en {name}: {value} µg/m³."

- id: air_unusual
  kind: unusual
  issue: air
  level: act
  cooldown_minutes: 60
  sql: |
    WITH a AS (SELECT r.sensor_id, s.name, s.indoor, r.mean FROM recent_15m r JOIN sensors s ON s.sensor_id = r.sensor_id
               WHERE r.metric = 'pm25' AND s.local AND r.bucket > now() - INTERVAL '1 hour'),
         u AS (SELECT sensor_id, p90 FROM usual_by_hour WHERE metric = 'pm25' AND hour = CAST(extract(hour FROM now()) AS INTEGER))
    SELECT a.sensor_id, a.name, round(CAST(avg(a.mean) AS NUMERIC), 1) AS value,
           round(CAST(min(u.p90) + 15 AS NUMERIC), 1) AS line, min(a.mean) >= min(u.p90) + 15 AS over,
           CASE WHEN bool_and(a.indoor) THEN 'inside' ELSE 'outside' END AS "where"
    FROM a JOIN u ON u.sensor_id = a.sensor_id
    GROUP BY a.sensor_id, a.name
    HAVING count(*) >= 3 AND avg(a.mean) >= min(u.p90) + 10
  message:
    en: "PM2.5 at {name} is {value} µg/m³, above its usual for the hour ({line})."
    id: "PM2.5 di {name} {value} µg/m³, di atas biasanya untuk jam ini ({line})."
    es: "El PM2.5 en {name} es {value} µg/m³, por encima de lo habitual a esta hora ({line})."

- id: air_sustained
  kind: sustained
  issue: air
  level: act
  cooldown_minutes: 60
  sql: |
    WITH a AS (SELECT r.sensor_id, s.name, s.indoor, r.mean FROM recent_15m r JOIN sensors s ON s.sensor_id = r.sensor_id
               WHERE r.metric = 'pm25' AND s.local AND r.bucket > now() - INTERVAL '1 hour')
    SELECT sensor_id, name, round(CAST(avg(mean) AS NUMERIC), 1) AS value, 35 AS line, min(mean) >= 35 AS over,
           CASE WHEN bool_and(indoor) THEN 'inside' ELSE 'outside' END AS "where"
    FROM a GROUP BY sensor_id, name
    HAVING count(*) >= 3 AND avg(mean) >= 30
  message:
    en: "PM2.5 at {name} has been {value} µg/m³ for an hour."
    id: "PM2.5 di {name} sudah {value} µg/m³ selama satu jam."
    es: "El PM2.5 en {name} lleva una hora en {value} µg/m³."

- id: air_extreme
  kind: danger
  issue: air
  level: act
  cooldown_minutes: 60
  sql: |
    SELECT r.sensor_id, s.name, round(CAST(r.mean AS NUMERIC), 1) AS value, 125.5 AS line, r.mean >= 125.5 AS over,
           CASE WHEN s.indoor THEN 'inside' ELSE 'outside' END AS "where"
    FROM recent_15m r JOIN sensors s ON s.sensor_id = r.sensor_id
    WHERE r.metric = 'pm25' AND s.local
      AND r.bucket = (SELECT max(bucket) FROM recent_15m WHERE sensor_id = r.sensor_id AND metric = 'pm25')
      AND r.mean >= 115
  message:
    en: "Very unhealthy air at {name}: {value} µg/m³ PM2.5."
    id: "Udara sangat tidak sehat di {name}: PM2.5 {value} µg/m³."
    es: "Aire muy insalubre en {name}: {value} µg/m³ de PM2.5."
```

- [ ] **Step 5: Run the test, then the rule lint**

Run: `PYTHONPATH=tests:app python3 tests/test_kinded_rules.py` — expected three lines, last `kinded rules: …`.
If DuckDB rejects `bool_and`, `greatest` or `"where"` quoting, fix the SQL so both engines accept it (both support
all three; a rejection means a typo).
Run: `python3 tools/check_rules.py` — expected the count line with 7 more rules and cells than before. A
placeholder error means a `message` names a column the SQL does not return: fix the message.

- [ ] **Step 6: The old engine must not run them**

Run: `grep -n 'rule.get("kind")' app/main.py` — expected the two lines from Task 3, Step 6. With
`ALERT_ENGINE=rules` the kinded rules are skipped before their SQL runs.

- [ ] **Step 7: Register, lint, test, commit**

`tests/all`: `test_kinded_rules|PYTHONPATH=tests:app python3 tests/test_kinded_rules.py`, add it to
`EXPECTED_SKIPS`, count 59 → 60.
Run: `make lint && make test` — `60 suites: 60 passed`.

```bash
git add packs/heat/rules.yml packs/air-quality/rules.yml tests/test_kinded_rules.py tests/all
git commit -m "heat, air-quality: kinded rules for the event engine — unusual, sustained, spike, danger"
```

---

### Task 6: The replay — today's engine against the event engine, over node #1's month

**Files:**
- Create: `tools/replay_alerts.py`
- Modify: `tools/check_docs.py` (remove `tools/replay_alerts.py` from `PROPOSED["docs/SPEC_alerts.md"]`, and the
  entry itself if it is then empty)
- Test: `tests/test_replay.py` (new; small synthetic month, no node data); `tests/all` (60 → 61)

**Interfaces:**
- Consumes: `trustdb.Node` (Task 1), `events.step`/`MemoryStore`/`Policy` (Task 2), `events_pg.candidates`
  (Task 3), `actions.render` (Task 4), the kinded rules (Task 5).
- Produces: `replay_alerts.replay(node, rules_old, rules_new, start, end, step_min, policy, alert_level) -> dict`
  with keys `old` and `new`, each `{"pushes": [(ts, rule_or_issue, text)], "per_day": {date: n}, "night": n}`;
  CLI `python3 tools/replay_alerts.py --data DIR [--days 30] [--step 5]` printing the comparison table of
  `docs/SPEC_alerts.md` §9 and writing `DIR/old.txt` and `DIR/new.txt`, one message per block.

- [ ] **Step 1: Write the failing test**

`tests/test_replay.py`:

```python
"""tools/replay_alerts.py on a synthetic two days: the old engine repeats on its cooldown, the event engine sends
one story. Needs duckdb. Run: PYTHONPATH=tests:app:tools python3 tests/test_replay.py
"""
import datetime as dt
import sys

try:
    import trustdb as T
    import replay_alerts as R
except ImportError as e:
    print(f"  skipped: {e}")
    sys.exit(0)

import events as E

# two days of node #1's real readings, replayed on the calendar the rules need
rows = T.week(T.readings(), T.FIXTURE_NOW, days=16)
node = T.Node(rows)
end = T.FIXTURE_NOW
res = R.replay(node, R.old_rules(), R.new_rules(), start=end - dt.timedelta(days=2), end=end, step_min=15,
               policy=E.Policy(quiet=(22, 6), max_per_day=4, alert_level="warn"), alert_level="warn")
old, new = res["old"], res["new"]
assert old["pushes"], "the old engine sends something on node #1's days"
assert len(new["pushes"]) < len(old["pushes"]), (len(new["pushes"]), len(old["pushes"]))
night = [text for ts, _, text in new["pushes"] if ts.hour < 6 or ts.hour >= 22]
assert all("DANGER" in text for text in night), f"only danger is sent at night: {night}"
print(f"replay: old {len(old['pushes'])} pushes, new {len(new['pushes'])} over two replayed days")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=tests:app:tools python3 tests/test_replay.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'replay_alerts'`.

- [ ] **Step 3: Write `tools/replay_alerts.py`**

```python
#!/usr/bin/env python3
"""Replay node #1's month through today's rules and through the event engine (docs/SPEC_alerts.md §9).

    tools/fetch_replay.sh /tmp/replay           # read-only, from node #1; household data, never committed
    python3 tools/replay_alerts.py --data /tmp/replay [--days 30] [--step 5]

Rules run in DuckDB exactly as they ship, with now() set to the replayed instant (tests/trustdb.py). The old
engine is app/main.py's run_rules semantics: cooldown per rule and sensor, ALERT_LEVEL, quiet hours holding all
but act. The new engine is app/events.py itself. Prints the §9 table and writes old.txt and new.txt.
Needs duckdb (dev only).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "app"), str(ROOT / "tests")]
import trustdb as T          # noqa: E402
import events as E           # noqa: E402
import events_pg as P        # noqa: E402
import actions as A          # noqa: E402
import yaml                  # noqa: E402

OLD_PACKS = ("heat", "air-quality")
FLOOR = {"info": 0, "warn": 1, "act": 2}


def _pack_rules(pack):
    return [dict(r, id=f"{pack}/{r['id']}") for r in yaml.safe_load((ROOT / "packs" / pack / "rules.yml").read_text())
            if "contributes" not in r]


def old_rules():
    return [r for p in OLD_PACKS for r in _pack_rules(p) if not r.get("kind")]


def new_rules():
    return [r for p in OLD_PACKS for r in _pack_rules(p) if r.get("kind")]


def _quiet(now, quiet, level):
    return level != "act" and E._quiet(now, quiet)


def _fmt(tmpl, row):
    try:
        return tmpl.format(**{k: ("—" if v is None else v) for k, v in row.items()})
    except (KeyError, ValueError):
        return tmpl


def replay(node, rules_old, rules_new, start, end, step_min, policy, alert_level):
    issues = {k: yaml.safe_load((ROOT / "app/issues" / f"{k}.yml").read_text()) for k in ("heat", "air")}
    last = {}
    old = {"pushes": [], "per_day": {}, "night": 0}
    new = {"pushes": [], "per_day": {}, "night": 0}
    store = E.MemoryStore()
    refreshed = None
    t = start
    while t <= end:
        if refreshed is None or t - refreshed >= dt.timedelta(hours=1):
            node.refresh_usual(t)
            refreshed = t
        local = t.astimezone(dt.timezone(dt.timedelta(hours=8)))
        for r in rules_old:
            for row in node.run(r, t):
                key = (r["id"], str(row.get("sensor_id", "node")))
                if key in last and t - last[key] < dt.timedelta(minutes=int(r.get("cooldown_minutes", 60))):
                    continue
                last[key] = t
                lvl = r.get("level", "info")
                if FLOOR[lvl] >= FLOOR[alert_level] and not _quiet(local, policy.quiet, lvl):
                    old["pushes"].append((local, r["id"], _fmt(r["message"]["en"], row)))
        cands = []
        for r in rules_new:
            cands += P.candidates(r, node.run(r, t))
        for m in E.step(local, cands, store, policy):
            if m.send:
                ctx = {"hour": local.hour, "where": set(m.event.where), "kind": m.event.kind, "home_has": set()}
                text, _ = A.render(issues[m.event.issue], m, ctx, "en") if m.event.issue in issues else (m.reason, None)
                new["pushes"].append((local, m.event.issue, text))
        t += dt.timedelta(minutes=step_min)
    for side in (old, new):
        for ts, _, _ in side["pushes"]:
            side["per_day"][ts.date()] = side["per_day"].get(ts.date(), 0) + 1
            side["night"] += ts.hour < 6 or ts.hour >= 22
    return {"old": old, "new": new}


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--step", type=int, default=5)
    a = ap.parse_args()
    d = Path(a.data)
    rows = T.readings_from(d / "readings.tsv")
    node = T.Node(rows, who=T.sensors_from(d / "sensors.tsv"))
    end = max(r[0] for r in rows)
    pol = E.Policy(quiet=(22, 6), max_per_day=4, alert_level="warn")
    res = replay(node, old_rules(), new_rules(), end - dt.timedelta(days=a.days), end, a.step, pol, "warn")
    for side in ("old", "new"):
        s = res[side]
        print(f"{side:4} pushes {len(s['pushes']):4}   median/day {_median(list(s['per_day'].values())):3}   "
              f"non-danger at night {s['night']:3}")
        with open(d / f"{side}.txt", "w") as f:
            for ts, what, text in s["pushes"]:
                f.write(f"--- {ts:%Y-%m-%d %H:%M} {what}\n{text}\n\n")
    print(f"messages: {d / 'old.txt'} and {d / 'new.txt'}")


if __name__ == "__main__":
    main()
```

And in `tests/trustdb.py`, two loaders that take a path (the fixture loaders stay as they are):

```python
def readings_from(path) -> list[tuple]:
    rows = []
    with open(path) as f:
        for line in f:
            ts, sid, met, val = line.rstrip("\n").split("\t")
            rows.append((dt.datetime.fromisoformat(ts), sid, met, float(val)))
    return rows


def sensors_from(path) -> list[tuple]:
    rows = []
    with open(path) as f:
        for line in f:
            sid, source, name, lat, lon, indoor, local, kind = line.rstrip("\n").split("\t")
            rows.append((sid, source, name, float(lat or 0), float(lon or 0), indoor == "t", local == "t", kind))
    return rows
```

- [ ] **Step 4: Run the test**

Run: `PYTHONPATH=tests:app:tools python3 tests/test_replay.py`
Expected: one line `replay: old N pushes, new M over two replayed days` with M < N. If the run takes more than a
couple of minutes, raise `step_min` in the test, not the engine's constants.

- [ ] **Step 5: Register, lint, test, commit**

`tests/all`: `test_replay|PYTHONPATH=tests:app:tools python3 tests/test_replay.py`, in `EXPECTED_SKIPS`, count
60 → 61. Remove the replay tool (and the then-empty entry) from `PROPOSED` in `tools/check_docs.py`.
Run: `make lint && make test` — `61 suites: 61 passed`.

```bash
git add tools/replay_alerts.py tests/trustdb.py tests/test_replay.py tests/all tools/check_docs.py
git commit -m "replay: today's rules against the event engine, on the same readings, side by side"
```

---

### Task 7: Fetch node #1's month, run the replay, report

**Files:**
- Create: `tools/fetch_replay.sh`
- Create (not committed): `$SCRATCH/replay/{readings,sensors}.tsv`, `old.txt`, `new.txt`
- Create: `docs/plans/2026-10-04-alert-events-replay.md` — the report Tomas reads (numbers only, no household text
  beyond the message templates)

**Interfaces:**
- Consumes: `tools/replay_alerts.py` (Task 6).
- Produces: the §9 table filled with node #1's numbers, and a go/no-go for shadow mode.

- [ ] **Step 1: Write the fetch script**

`tools/fetch_replay.sh`:

```bash
#!/usr/bin/env bash
# Node #1's last 31 days, read-only, for tools/replay_alerts.py. Household data: write it outside the repository.
#   tools/fetch_replay.sh /some/scratch/dir
# Every query runs in a read-only transaction. Nothing on the node is written, restarted or imported.
set -euo pipefail
out="${1:?usage: tools/fetch_replay.sh DIR}"; mkdir -p "$out"
remote='export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH";
  docker exec -i planetai-db-1 psql -U planetai -d planetai -At -v ON_ERROR_STOP=1'
q() { ssh mini "$remote" <<SQL
SET default_transaction_read_only = on;
SET TimeZone = 'Asia/Makassar';
\copy ($1) TO STDOUT
SQL
}
q "SELECT r.ts, r.sensor_id, r.metric, r.value FROM readings r JOIN sensors s USING (sensor_id)
   WHERE r.ts > now() - interval '31 days' AND s.kind = 'sensor' AND r.metric IN ('temp','humidity','pm25')
   ORDER BY r.ts" > "$out/readings.tsv"
q "SELECT sensor_id, source, name, coalesce(lat,0), coalesce(lon,0), indoor, local, kind FROM sensors WHERE kind = 'sensor'" \
  > "$out/sensors.tsv"
wc -l "$out"/*.tsv
```

`chmod +x tools/fetch_replay.sh`. The `\copy … TO STDOUT` output is tab-separated with `t`/`f` booleans, which is
what `trustdb.readings_from` and `sensors_from` read. If `psql -U planetai` fails, read the user name from
`ssh mini 'docker exec planetai-db-1 printenv POSTGRES_USER'` — never print a password.

- [ ] **Step 2: Fetch and replay**

Run:
```bash
S=/private/tmp/replay-$(date +%Y%m%d)
tools/fetch_replay.sh "$S"
python3 tools/replay_alerts.py --data "$S" --days 30 --step 5
```
Expected: two lines, `old` and `new`, and the two message files. The `old` line should be near what node #1 really
sent (~13 a day, 23 at night): if it is far off, the replay is wrong — find why before reading `new`.

- [ ] **Step 3: Write the report and stop**

`docs/plans/2026-10-04-alert-events-replay.md`: the §9 table with both columns filled, the targets met and missed,
ten message pairs (an old burst and the new message for the same hour), and which starting values the numbers say
to change. Commit it with `tools/fetch_replay.sh`:

```bash
git add tools/fetch_replay.sh docs/plans/2026-10-04-alert-events-replay.md
git commit -m "replay: node #1's month through both engines — the numbers for the shadow decision"
```

Then stop and hand the report to Tomas. A missed target changes a rule, a constant in `app/events.py`, or an action
— re-run the replay after each change, never the target. Shadow mode on node #1 (`ALERT_ENGINE=shadow`, a setting
on his node) waits for his go.

---

## Spec coverage: this plan and the three after it

| `docs/SPEC_alerts.md` | here | later |
|---|---|---|
| §3 measures `recent_15m`, `usual_by_hour` | Task 1 | |
| §3 `ahead_12h`, the `ahead` kind | | Plan 3 (anticipation) |
| §4 events, lifecycle, quiet hours, ceiling, `ALERT_LEVEL` | Tasks 2–3 | |
| §4 kinded rows recorded in `alerts` and linked by `event_id` | column only (Task 3) | Plan 2, with `events` mode sending |
| §5 actions, context, `HOME_HAS` setting | Tasks 3–4 | |
| §5 learning: Done-to-clear ranking, Doesn't-fit muting | | Plan 2 (needs the buttons' data) |
| §6 morning plan, unusual day ahead, evening crossover, air arriving, Open-Meteo, coordinate rounding | | Plan 3 |
| §7 Telegram buttons, the bot's taps, `dismissed` written, ρ counts events, the decision record | stage added (Task 3) | Plan 2 |
| §7 the dashboard's Decide card | | v0.78, after Plan 2 |
| §8 pack contract (`kind:`, `issue:`, `actions:` from packs) | `kind:`/`issue:` (Tasks 3, 5) | pack `actions:` in Plan 2; `write-a-pack` skill update in Plan 2 |
| §9 replay and targets | Tasks 6–7 | |
| §9 shadow mode on node #1 | the switch (Task 3) | Tomas's go after Task 7 |
| §10 `ALERT_ENGINE`, `ALERT_MAX_PER_DAY`, `HOME_HAS` | Task 3 | |
| §10 `REPORT_AT`, `REPORT_SKIP_EMPTY`, reports built from events, quiet hours tightened for the rules engine | | Plan 4 |
| §11 step 8: retire the old rules, `events` as default | | after shadow |
