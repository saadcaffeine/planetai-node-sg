# Dashboard figures, part A: the wire — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /issues` carries each issue's usual day, an open event's own rooms hour by hour, and the stations
that stopped; `GET /issues/days` serves up to 90 days of the same hourly series with the node's own count of hours
over the line; a snapshot and the visual rig carry the new route. The page that draws all of it is part B.

**Architecture:** Everything is in the issues engine (`app/issues/engine.py`), so there is one definition of "the
house". `_series` is split so its inner loop (`_values`) also computes an event's rooms and a 90-day window. Two
optional reads (`usual_by_hour`, the silent stations) go through `_optional`, which answers `None` instead of failing
`/issues`; a replay hands both over from the capture, as it already does the events block. `days()` is a new pure
function behind a new route on the `/issues` router, so it inherits `/issues`' sharing rule.

**Tech stack:** Python 3.11 app (FastAPI, psycopg 3, dict rows), Postgres 16, plain-`assert` test scripts run by
`tests/all`, a bash CLI (`bin/planetai`), the Playwright rig `tests/visual/measure.mjs`.

**Spec:** `docs/SPEC_dashboard_figures.md` §3 (the server piece). Read §1–§3 before Task 1. Part B (the page) is
`docs/plans/2026-10-06-dashboard-figures-part-b.md`, part C (Grafana) `docs/plans/2026-10-06-dashboard-figures-part-c.md`.

## Global constraints

- Work in your own git worktree off `origin/main` (`skills/preflight/SKILL.md`), never in `planetai-node-main`,
  which holds `main`.
- Never import app `main` in a test or a container: it starts a second MQTT client and kicks node #1 off its broker.
- `make lint && make test` before every commit. The pre-commit hook runs both; allow 300000 ms. Never `--no-verify`.
- No change to `init.sql` (schema 0.53 has every table and view used here), `app/static/`, or `packs/`.
- `tests/all`'s suite count is hand-written: Task 1 raises it from 64 to 65. Before merging, check no other open PR
  changes it.
- In a test file that ends in `sys.exit(...)` or a final `print(...)`, add checks **above** that last line; anything
  below `sys.exit` never runs.
- Timestamps: live rows are `datetime`, captured rows are ISO strings. Every function here takes both.
- The page computes nothing from these keys. Every count it prints is the node's.
- **Rebase risk.** Branch `issue-state-events-2026-10-06` (an issue's state follows the events) also edits the
  `if events is not None:` block of `engine.compute`. If it merges first, rebase and keep both changes: its `owned`
  set moves earlier, and this plan's `"open": [...]` key sits beside its `uncovered_asks`.
- Commit messages end with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Files

| file | what changes |
|---|---|
| `app/issues/engine.py` | `_values` split out of `_series`; `_room_series`; `_word`; `_optional`, `USUAL_*`, `SILENT_*`, `_usual`; `_stations(..., silent)`; `compute(..., usual, silent)` and the keys `usual`, `usual_absent`, `events.open[].series`, `stations_silent`; `replay` carries usual and silent; `DAYS_MAX`, `_local_days`, `days()` |
| `app/issues/api.py` | `GET /issues/days` |
| `tests/test_figures_wire.py` (new) | every check in this plan |
| `tests/test_issues_engine.py` | the per-call query count, 5 → 7 |
| `tests/all` | the new suite, and the count 64 → 65 |
| `tools/check_wire.py`, `tests/data/wire/issues-v0.json`, `tests/data/wire/days-v0.json` (new) | `stations_silent`; the `days-v0` format |
| `bin/planetai` | `planetai snapshot` fetches `/issues/days?days=7` |
| `tests/visual/measure.mjs` | serves `/issues/days` from a fixture |
| `docs/site/api.md`, `CHANGELOG.md` | the keys and the route; the Unreleased line |
| `docs/SPEC_dashboard_figures.md`, `tools/check_docs.py` | the spec's names corrected to what was built |

---

### Task 1: the usual day, and the new suite

**Files:**
- Modify: `app/issues/engine.py` (constants and two functions above `def _read`; `compute`; `replay`)
- Create: `tests/test_figures_wire.py`
- Modify: `tests/test_issues_engine.py:437-440`, `tests/all`
- Modify: `docs/SPEC_dashboard_figures.md` §6, `tools/check_docs.py` `PROPOSED`

**Interfaces:**
- Produces:
  - `engine.USUAL_DAYS = 14`, `engine.USUAL_SQL: str`
  - `engine._optional(cur, sql: str, *args) -> list[dict] | None`
  - `engine._usual(d: dict, dist: str, cell: dict | None, rows: list[dict] | None) -> tuple[dict | None, str | None]`
  - `compute(..., usual: dict | None = None)`: `usual` maps an issue key to `(block, usual_absent)`; a replay passes it.
  - On every issue entry: `usual: {window_days, distance, hours: [{hour, median, p90}] ×24} | None` and
    `usual_absent: None | "unread" | "no_source" | "no_history" | "not_watched"`.

- [ ] **Step 1: Write the failing test.** Create `tests/test_figures_wire.py`:

```python
"""The wire part of docs/SPEC_dashboard_figures.md §3: the usual day, an open event's rooms, the stations that
stopped, and GET /issues/days. No database: a capture and hand-made rows.
Run: PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py
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
import issues as I                # noqa: E402
from issues import engine          # noqa: E402


class Settings:
    def get(self, key, default=""):
        return default

    def num(self, key, default):
        return default


SNAP = json.loads((ROOT / "app/issues/fixtures/node1-2026-10-06-events.json").read_text())
DECL = I.load()


def fresh():
    return json.loads(json.dumps(SNAP))


# --- §3.1 the usual day --------------------------------------------------------------------------
ROWS = [{"sensor_id": "a", "metric": "apparent", "hour": 7, "median": 30.0, "p90": 31.0},
        {"sensor_id": "b", "metric": "apparent", "hour": 7, "median": 32.0, "p90": 35.0},
        {"sensor_id": "b", "metric": "temp", "hour": 7, "median": 99.0, "p90": 99.0},       # another metric
        {"sensor_id": "c", "metric": "apparent", "hour": 7, "median": 99.0, "p90": 99.0}]   # another distance
heat = {"metric": "apparent"}
block, why = engine._usual(heat, "room", {"sensors": ["a", "b"]}, ROWS)
assert why is None and block["window_days"] == 14 and block["distance"] == "room", (block, why)
assert len(block["hours"]) == 24 and [h["hour"] for h in block["hours"]] == list(range(24))
assert block["hours"][7] == {"hour": 7, "median": 31.0, "p90": 33.0}, block["hours"][7]
assert block["hours"][8] == {"hour": 8, "median": None, "p90": None}, "an hour with no history is null, not zero"
assert engine._usual(heat, "room", {"sensors": ["a"]}, None) == (None, "unread")
assert engine._usual(heat, "room", None, ROWS) == (None, "no_source")
assert engine._usual(heat, "room", {"sensors": ["z"]}, ROWS) == (None, "no_history")
print("  usual: the mean over the hero distance's sensors of each hour's median and p90, the issue's own metric")

rep = engine.replay(fresh(), Settings(), DECL)
for k, v in rep["issues"].items():
    assert "usual" in v and "usual_absent" in v, k
    if v.get("watched"):
        assert v["usual"] is None and v["usual_absent"] == "unread", (k, v["usual_absent"])
snap = fresh()
carried = {"window_days": 14, "distance": "room", "hours": [{"hour": h, "median": 30.0, "p90": 31.0} for h in range(24)]}
snap["issues"]["issues"]["heat"]["usual"], snap["issues"]["issues"]["heat"]["usual_absent"] = carried, None
assert engine.replay(snap, Settings(), DECL)["issues"]["heat"]["usual"] == carried, "a capture's usual replays verbatim"
print("  usual: a capture without it replays as unread; a capture with it replays it verbatim")

print("figures_wire: the usual day")
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py`
  Expected: `AttributeError: module 'issues.engine' has no attribute '_usual'`

- [ ] **Step 3: Add the read and the helper.** In `app/issues/engine.py`, directly above `def _read(cur) -> dict:`:

```python
# usual_by_hour (init.sql): each sensor's median and p90 for each local hour, over the 14 complete days before today.
USUAL_DAYS = 14
USUAL_SQL = "SELECT sensor_id, metric, hour, median, p90 FROM usual_by_hour"


def _optional(cur, sql: str, *args) -> list[dict] | None:
    """A read a fresh node may not answer and a capture does not carry: None, never a failed /issues.

    usual_by_hour is created WITH NO DATA and raises until the app's first hourly refresh, and on a live cursor an
    error inside the /issues transaction would abort every read after it, so the read gets a savepoint of its own. A
    Replay has no connection and refuses a query it cannot answer with LookupError, which ends in the same None."""
    conn = getattr(cur, "connection", None)
    try:
        if conn is None:
            return _rows(cur, sql, *args)
        with conn.transaction():
            return _rows(cur, sql, *args)
    except Exception as e:  # noqa: BLE001
        log.info("issues: an optional read did not answer (%s)", type(e).__name__)
        return None


def _usual(d: dict, dist: str, cell: dict | None, rows: list[dict] | None) -> tuple[dict | None, str | None]:
    """The issue's usual day at its hero distance (docs/SPEC_dashboard_figures.md §3.1): for each local hour, the mean
    over that distance's sensors of usual_by_hour's median and p90, for the issue's own metric. The same reading
    events_wire.USUAL_SQL makes for an event's card, so the band and the card agree. (block, None) or (None, why)."""
    if rows is None:
        return None, "unread"
    ids = set((cell or {}).get("sensors") or [])
    if not ids:
        return None, "no_source"
    by: dict[int, list[dict]] = {}
    for r in rows:
        if r.get("sensor_id") in ids and r.get("metric") == d.get("metric") and r.get("median") is not None:
            by.setdefault(int(r["hour"]), []).append(r)
    if not by:
        return None, "no_history"

    def mean(xs):
        xs = [float(x) for x in xs if x is not None]
        return round(statistics.fmean(xs), 2) if xs else None
    return {"window_days": USUAL_DAYS, "distance": dist,
            "hours": [{"hour": h, "median": mean(r["median"] for r in by.get(h, [])),
                       "p90": mean(r.get("p90") for r in by.get(h, []))} for h in range(24)]}, None
```

- [ ] **Step 4: Wire it into `compute`.** Three edits in `app/issues/engine.py`:

  a. The signature gains `usual`:

```python
def compute(cur, settings, decl: dict, earth: dict | None = None, now: datetime | None = None,
            place: tuple[float, float] | None = None, mesh: dict | None = None,
            peers=(), facilities=(), events: dict | None = None, usual: dict | None = None) -> dict:
```

  and add one paragraph at the end of its docstring:

```
    `usual` maps an issue to the (usual, usual_absent) pair a capture carried; a replay passes it, because a snapshot
    holds the /issues answer and not usual_by_hour. None reads the view, on a savepoint of its own.
```

  b. Directly above `out = {}` (before `for key in declared + undeclared:`):

```python
    # The usual band (docs/SPEC_dashboard_figures.md §3.1): a replay hands it over as the capture carried it.
    usual_rows = None if usual is not None else _optional(cur, USUAL_SQL)
```

  c. In the undeclared branch, the dict's last line `"hero": None}` becomes
     `"hero": None, "usual": None, "usual_absent": "not_watched"}`. And directly below
     `out[key]["hero"] = _hero(d, stack, headline, out[key]["sentence"], now, clock)`:

```python
        out[key]["usual"], out[key]["usual_absent"] = (usual[key] if usual is not None and key in usual
                                                       else _usual(d, headline, stack.get(headline), usual_rows))
```

- [ ] **Step 5: Carry it through `replay`.** Replace the `return compute(...)` at the end of `replay` with:

```python
    body = snapshot.get("issues") if isinstance(snapshot.get("issues"), dict) else {}
    captured = body.get("issues") if isinstance(body.get("issues"), dict) else {}
    usual = {k: (v.get("usual"), v.get("usual_absent")) for k, v in captured.items()
             if isinstance(v, dict) and "usual" in v} or None
    return compute(Replay(snapshot), settings, decl, earth=snapshot.get("earth"), now=now,
                   place=place, mesh=health.get("mesh"), peers=[peer] if peer else [],
                   facilities=facilities, events=body.get("events"), usual=usual)
```

  and add to `replay`'s docstring: "`usual` is each issue's usual day as the capture carried it, verbatim; a capture
  from before v0.78 has none, and the engine's own read of `usual_by_hour` then fails on the Replay and says `unread`."

- [ ] **Step 6: The query count.** `tests/test_issues_engine.py` lines 437 and 440 assert `c.n == 5`. The usual is one
  more read per call, never per issue. Change both to `c.n == 6` and their messages to
  `"...; it must read each table once, and the usual once"` / `"...; the reads are not per-issue"`. Task 3 makes it 7.

- [ ] **Step 7: Register the suite.** In `tests/all`, below the `test_events_wire|...` line, add
  `test_figures_wire|PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py`. Change both `64`s in the
  count check to `65`, and the comment above it to `Sixty-five ... (test_figures_wire added 6 Oct 2026)`.

- [ ] **Step 8: Name the suite in the spec.** In `docs/SPEC_dashboard_figures.md` §6, the "The server." bullet names
  `tests/test_issues.py`, `tests/test_events_wire.py` and `tests/test_days.py`; replace that bullet with:

```
- **The server.** `tests/test_figures_wire.py` covers `usual` (null, present and carried by a replay),
  `events.open[].series` against node #1's 6 October capture, §3.3's silent stations on node #1's eight rows of that
  day, and `/issues/days`: one day reproduces `/issues`' own 24 values, `per_day` counts what the series shows, and
  the window is held to 1–90 days.
```

  In `tools/check_docs.py`, remove `"tests/test_days.py", ` from the `docs/SPEC_dashboard_figures.md` entry of
  `PROPOSED`.

- [ ] **Step 9: Run it and watch it pass.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py && PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues_engine.py | tail -1`
  Expected: `figures_wire: the usual day`, then the engine suite's summary line with no `x`.

- [ ] **Step 10: Commit.**

```bash
git add app/issues/engine.py tests/test_figures_wire.py tests/test_issues_engine.py tests/all docs/SPEC_dashboard_figures.md tools/check_docs.py
git commit -m "issues: each issue carries its usual day, from usual_by_hour at its hero distance

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: an open event's own rooms

**Files:**
- Modify: `app/issues/engine.py` (`_series`, a new `_values` and `_room_series`, the events block in `compute`)
- Test: `tests/test_figures_wire.py` (above the final `print`)

**Interfaces:**
- Produces:
  - `engine._values(spec: dict, hourly: dict, buckets: list, keep) -> list[float | None]`: Task 4's `days()` uses it
    through `_series`.
  - `engine._room_series(d: dict, hourly: dict, buckets: list, names: dict, rooms) -> dict | None`
  - `events.open[].series: {"rooms": [names, sorted], "values": [float | None] on /issues' own buckets} | None`

- [ ] **Step 1: Write the failing test.** Above the final `print(...)` of `tests/test_figures_wire.py`:

```python
# --- §3.2 an open event's own rooms --------------------------------------------------------------
rep = engine.replay(fresh(), Settings(), DECL)
ev = rep["events"]["open"][0]
assert ev["issue"] == "air" and ev["series"]["rooms"] == sorted(ev["rooms"]), ev.get("series")
vals = ev["series"]["values"]
assert len(vals) == len(rep["issues"]["air"]["buckets"]), "on /issues' own buckets"
# The 08:00 bucket by hand: air combines its house as a mean of pm25, so the rooms' 08:00 pm25 means, averaged.
names = {r["sensor_id"]: r.get("name") for r in SNAP["stats"]}
at = rep["issues"]["air"]["buckets"].index("2026-10-06T08:00:00+08:00")
hand = [r["mean"] for r in SNAP["readings_1h"] if r["bucket"] == "2026-10-06T08:00:00+08:00" and r["metric"] == "pm25"
        and (names.get(r["sensor_id"]) in ev["rooms"] or r["sensor_id"] in ev["rooms"])]
assert hand and abs(vals[at] - sum(hand) / len(hand)) < 1e-4, (vals[at], hand)
# Heat combines each room's apparent temperature, then the median: two rooms, one hour.
B = dt.datetime(2026, 10, 6, 13, tzinfo=dt.timezone(dt.timedelta(hours=8)))
hourly = {B: [{"sensor_id": "k", "metric": "temp", "mean": 34.0}, {"sensor_id": "k", "metric": "humidity", "mean": 60.0},
              {"sensor_id": "l", "metric": "temp", "mean": 30.0}, {"sensor_id": "l", "metric": "humidity", "mean": 50.0},
              {"sensor_id": "x", "metric": "temp", "mean": 40.0}, {"sensor_id": "x", "metric": "humidity", "mean": 90.0}]}
got = engine._room_series(DECL["heat"], hourly, [B], {"k": "K ROOM", "l": "L ROOM"}, ["K ROOM", "L ROOM"])
want = (engine.apparent(34.0, 60.0) + engine.apparent(30.0, 50.0)) / 2           # median of two is their mean
assert got == {"rooms": ["K ROOM", "L ROOM"], "values": [round(want, 6)]}, (got, want)
assert engine._room_series(DECL["heat"], hourly, [B], {}, []) is None, "no rooms, no series"
assert engine._room_series(DECL["coast"], hourly, [B], {}, ["K ROOM"]) is None, "an issue with no room distance"
print("  event series: the event's rooms combined as the issue combines its house, on /issues' buckets")
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py`
  Expected: `KeyError: 'series'`

- [ ] **Step 3: Split `_series`.** Replace the whole of `def _series(d, hourly, buckets, names) -> dict:` in
  `app/issues/engine.py` with:

```python
def _values(spec: dict, hourly: dict, buckets: list, keep) -> list:
    """One distance's value at each bucket: the rows `keep` admits, the function per sensor, then the aggregate."""
    vals = []
    for b in buckets:
        per: dict[str, dict] = {}
        for r in hourly.get(b, []):
            if not keep(r) or r["metric"] not in spec["metrics"]:
                continue
            per.setdefault(r["sensor_id"], {})[r["metric"]] = r.get("mean")
        v, _, _ = _combine(per, spec["metrics"], spec.get("function"), spec["aggregate"])
        vals.append(None if v is None else round(v, 6))
    return vals


def _series(d, hourly, buckets, names) -> dict:
    """Twenty-four hourly values at each distance, on the same buckets, so the traces line up."""
    out = {}
    for dist in DISTANCES:
        spec = (d.get("distances") or {}).get(dist)
        if not spec or spec.get("from") != "stats":
            out[dist] = None
            continue
        vals = _values(spec, hourly, buckets, lambda r, place=spec["place"]: _ambient(r, place))
        out[dist] = vals if any(v is not None for v in vals) else None
    return out


def _room_series(d: dict, hourly: dict, buckets: list, names: dict, rooms) -> dict | None:
    """An open event's own rooms, hour by hour, combined the way the issue combines its house: air the mean, heat the
    median of each room's apparent temperature (docs/SPEC_dashboard_figures.md §3.2). The page draws it beside the
    house, so a one-room event inside a cooler house is visible as the room it is. Rooms are names or ids, as the
    engine writes them on alert_events."""
    spec = (d.get("distances") or {}).get("room")
    want = set(rooms or [])
    if not spec or spec.get("from") != "stats" or not want:
        return None
    vals = _values(spec, hourly, buckets,
                   lambda r: r.get("sensor_id") in want or names.get(r.get("sensor_id")) in want)
    return {"rooms": sorted(want), "values": vals} if any(v is not None for v in vals) else None
```

- [ ] **Step 4: Put it on the wire.** In `compute`, inside `if events is not None:`, the assignment
  `events = {**events, "uncovered_asks": [` becomes:

```python
        events = {**events, "open": [{**e, "series": _room_series(decl.get(e.get("issue")) or {}, hourly, buckets,
                                                                     names, e.get("rooms"))}
                                     for e in events.get("open") or []],
                  "uncovered_asks": [
```

  (the rest of that statement is unchanged).

- [ ] **Step 5: Run it and watch it pass.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py && PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py | tail -1`
  Expected: both suites end on their summary line with no assertion error.

- [ ] **Step 6: Commit.**

```bash
git add app/issues/engine.py tests/test_figures_wire.py
git commit -m "issues: an open event carries its own rooms, hour by hour, as the issue combines its house

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: the stations that stopped

**Files:**
- Modify: `app/issues/engine.py` (`SILENT_*` beside `USUAL_*`; `_stations`; `compute`; `replay`)
- Modify: `tests/test_issues_engine.py:437-440` (6 → 7), `tests/data/wire/issues-v0.json` (via `--update`)
- Test: `tests/test_figures_wire.py`

**Interfaces:**
- Produces:
  - `engine.SILENT_DAYS = 30`, `engine.SILENT_SQL: str`
  - `engine._stations(stats, hourly, lat, lon, sited=True, silent: list[dict] | None = None) -> list[dict]`: a silent
    station is a normal station row with `read: {}`, `series: {}` and `last_heard: str` (ISO).
  - `compute(..., silent: list[dict] | None = None)`; top-level `stations_silent: {"read": bool, "within_days": 30}`.

- [ ] **Step 1: Write the failing test.** Above the final `print(...)` of `tests/test_figures_wire.py`. The rows are
  node #1's of 6 October 2026, read from its `sensors` and `readings` tables:

```python
# --- §3.3 the stations that stopped (node #1, 6 October 2026) -----------------------------------
def heard(i, name, lat, lon, local=False):
    return {"sensor_id": i, "name": name, "lat": lat, "lon": lon, "local": local, "indoor": False, "kind": "sensor",
            "metric": "pm25", "mean_15m": 5.0, "silent_minutes": 5}


def stopped(i, name, lat, lon, when, indoor=False):
    return {"sensor_id": i, "name": name, "lat": lat, "lon": lon, "local": False, "indoor": indoor, "kind": "sensor",
            "last_heard": when}


HEARD = [heard("sc-19874", "BAYU NEW ENCLOSURE ", -8.82008, 115.16669, True),
         heard("sc-19236", "Ungasan Kit - TEST", -8.81983, 115.16657, True),
         heard("sc-19898", "Suluban Entrance - AIR", -8.81645, 115.09271),
         heard("bad-ag-197980", "Padang2 Uluwatu (AirGradient)", -8.81121, 115.10252),
         heard("bad-sc-19768", "Bayu Sensor by Fab Lab - Kios Serangan (Smart Citizen)", -8.72582, 115.23585)]
STOPPED = [stopped("bad-sc-19874", "BAYU NEW ENCLOSURE (Smart Citizen)", -8.82008, 115.16669, "2026-10-04T15:00:37+00:00"),
           stopped("bad-sc-19236", "Ungasan Kit - TEST (Smart Citizen)", -8.81983, 115.16657, "2026-10-04T15:00:37+00:00"),
           stopped("bad-sc-19898", "Suluban Entrance - AIR (Smart Citizen)", -8.81645, 115.09271, "2026-10-01T20:30:26+00:00"),
           stopped("bad-oq-6432409", "Padang2 Uluwatu (OpenAQ)", -8.81121, 115.10252, "2026-09-07T23:00:42+00:00"),
           stopped("bad-sc-19995", "Bayu Sensor Demo Test Lora (Smart Citizen)", -8.72591, 115.23600, "2026-10-03T22:45:24+00:00"),
           stopped("bad-iqs-jimbaran-s", "Jimbaran (IQAir)", -8.79122, 115.16740, "2026-09-07T22:07:41+00:00", True),
           stopped("bad-pa-36601", "Jimbaran by Lumi Clinic (PurpleAir)", -8.79122, 115.16740, "2026-09-07T23:00:42+00:00", True),
           stopped("bad-ag-208245", "Suluban (AirGradient)", -8.81882, 115.08806, "2026-10-03T09:45:22+00:00")]
out = engine._stations(HEARD, [], -8.8190516, 115.1644423, True, STOPPED)
gone = sorted(s["name"] for s in out if s.get("last_heard"))
# Four of the eight are relays (bad-sc-*, OpenAQ) of kits heard today at the same point: they are not listed.
assert gone == ["Bayu Sensor Demo Test Lora (Smart Citizen)", "Jimbaran (IQAir)",
                "Jimbaran by Lumi Clinic (PurpleAir)", "Suluban (AirGradient)"], gone
one = next(s for s in out if s["sensor_id"] == "bad-ag-208245")
assert one["read"] == {} and one["series"] == {} and one["last_heard"] == "2026-10-03T09:45:22+00:00" and one["km"] > 0
assert not any(s.get("last_heard") for s in engine._stations(HEARD, [], -8.8, 115.16, True, None)), "none given, none listed"
print("  silent stations: four of node #1's eight are kept; four are relays of kits heard today, at the same point")

rep = engine.replay(fresh(), Settings(), DECL)
assert rep["stations_silent"] == {"read": False, "within_days": 30}, rep["stations_silent"]
snap = fresh()
snap["issues"]["stations_silent"] = {"read": True, "within_days": 30}
snap["issues"]["stations"].append({**{k: v for k, v in STOPPED[-1].items()}, "read": {}, "series": {}})
again = engine.replay(snap, Settings(), DECL)
assert again["stations_silent"]["read"] is True
assert [s["name"] for s in again["stations"] if s.get("last_heard")] == ["Suluban (AirGradient)"]
print("  silent stations: a capture says whether it read them, and replays the ones it carried")
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py`
  Expected: `TypeError: _stations() takes from 4 to 5 positional arguments but 6 were given`

- [ ] **Step 3: The read.** Below `USUAL_SQL` in `app/issues/engine.py`:

```python
# The archive of silence (docs/SPEC_dashboard_figures.md §3.3): stations heard within SILENT_DAYS and not in the last
# day. `stats` holds the last 24 hours only, so without this a station silent for a day leaves /issues with no word.
SILENT_DAYS = 30
SILENT_SQL = ("SELECT s.sensor_id, s.name, s.lat, s.lon, s.local, s.indoor, s.kind, max(r.ts) AS last_heard "
              "FROM readings r JOIN sensors s USING (sensor_id) "
              "WHERE s.kind = 'sensor' AND r.ts > now() - make_interval(days => %s) "
              "GROUP BY 1, 2, 3, 4, 5, 6, 7 HAVING max(r.ts) <= now() - interval '24 hours'")
```

- [ ] **Step 4: `_stations` keeps them.** Change the signature to

```python
def _stations(stats: list[dict], hourly: list[dict], lat: float, lon: float, sited: bool = True,
              silent: list[dict] | None = None) -> list[dict]:
```

  and replace the body from `import h3` down to (not including) `for h in hourly or []:` with:

```python
    import h3  # noqa: PLC0415 — only this path needs it, and geometry.py already requires it

    def row(r: dict) -> dict:
        return {"sensor_id": r["sensor_id"], "name": r.get("name"), "lat": r["lat"], "lon": r["lon"],
                "local": bool(r.get("local")), "indoor": bool(r.get("indoor")), "kind": r.get("kind") or "sensor",
                **_source_of(r["sensor_id"]),
                "km": round(h3.great_circle_distance((lat, lon), (r["lat"], r["lon"]), unit="km"), 1) if sited
                else None,
                "read": {}, "series": {}}
    by: dict[str, dict] = {}
    for r in stats:
        if r.get("lat") is None or r.get("lon") is None:
            continue
        s = by.setdefault(r["sensor_id"], row(r))
        m = METRICS.get(r.get("metric"))
        if m and r.get("mean_15m") is not None:
            s["read"][r["metric"]] = {"value": round(float(r["mean_15m"]), 2), "unit": m["unit"], "dp": m["dp"],
                                       "silent_minutes": None if r.get("silent_minutes") is None
                                       else round(r["silent_minutes"])}
    # The archive of silence (docs/SPEC_dashboard_figures.md §3.3): a station heard in the last 30 days and not in the
    # last day keeps its row, with when it was last heard. Unless a station heard today stands at the same point: Bali
    # Air Dispatch relays Smart Citizen kits as bad-sc-<kit> and AirGradient ones through OpenAQ, so a relay that
    # stopped is a second road to a kit that still reports, and listing it would call a working kit dead.
    heard = {(round(float(s["lat"]), 5), round(float(s["lon"]), 5)) for s in by.values()}
    for r in silent or []:
        if r.get("lat") is None or r.get("lon") is None or r["sensor_id"] in by:
            continue
        if (round(float(r["lat"]), 5), round(float(r["lon"]), 5)) in heard:
            continue
        lh = r.get("last_heard")
        by[r["sensor_id"]] = {**row(r), "last_heard": lh.isoformat() if hasattr(lh, "isoformat") else lh}
```

  Add one sentence to its docstring: "`silent` is the stations heard within SILENT_DAYS and not in the last day; they
  keep a row with `last_heard`, unless a station heard today stands at the same point."

- [ ] **Step 5: `compute` and `replay`.**
  - `compute`'s signature gains `silent: list[dict] | None = None` after `usual`, and its docstring the line
    "`silent` is the capture's own silent stations, from a replay; None reads them."
  - Below the `usual_rows = ...` line add:
    `    silent_rows = silent if silent is not None else _optional(cur, SILENT_SQL, SILENT_DAYS)`
  - `stations = _stations(data["stats"], data.get("hourly"), lat, lon, sited)` becomes
    `stations = _stations(data["stats"], data.get("hourly"), lat, lon, sited, silent_rows)`.
  - In the returned dict, directly below `"stations": stations,`:

```python
            # whether the stations that stopped were read, and how far back (docs/SPEC_dashboard_figures.md §3.3)
            "stations_silent": {"read": silent_rows is not None, "within_days": SILENT_DAYS},
```

  - In `replay`, below the `usual = ...` statement:

```python
    silent = ([s for s in body.get("stations") or [] if isinstance(s, dict) and s.get("last_heard")]
              if (body.get("stations_silent") or {}).get("read") else None)
```

    and add `, silent=silent` after `usual=usual` in its `return compute(...)`.

- [ ] **Step 6: The count and the wire.** In `tests/test_issues_engine.py` change both `c.n == 6` (Task 1) to
  `c.n == 7` and the first message to `"...; it must read each table once, and the usual and the silent once"`. Then
  run `python3 tools/check_wire.py --update`; `tests/data/wire/issues-v0.json` gains `stations_silent`.

- [ ] **Step 7: Run it and watch it pass.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py && PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues_engine.py | tail -1 && python3 tools/check_wire.py`
  Expected: the three suites' summary lines and no `x`.

- [ ] **Step 8: Commit.**

```bash
git add app/issues/engine.py tests/test_figures_wire.py tests/test_issues_engine.py tests/data/wire/issues-v0.json
git commit -m "issues: a station that stopped keeps its row, unless a kit heard today stands at the same point

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: GET /issues/days

**Files:**
- Modify: `app/issues/engine.py` (`_word`, used by `_from_stats`; `DAYS_MAX`, `_local_days`, `days` above `def _sections`)
- Modify: `app/issues/api.py` (the route)
- Modify: `tools/check_wire.py` (`FORMATS`); create `tests/data/wire/days-v0.json` (via `--update`)
- Test: `tests/test_figures_wire.py`

**Interfaces:**
- Consumes: `_series` and `_values` (Task 2).
- Produces:
  - `engine.DAYS_MAX = 90`
  - `engine.days(cur, settings, decl: dict, n: int, now: datetime | None = None) -> dict` with keys
    `schema ("days-v0"), as_of, tz, days, buckets, issues, events`; each `issues[key]` is
    `{distance, series: {room, yard, ring, region}, provenance: {dist: word}, per_day: [{date, over, read, of}], line}`.
  - `GET /issues/days?days=N`, N from 1 to 90, default 7. Part B reads it; `planetai snapshot` stores it as
    `issues_days`.

- [ ] **Step 1: Write the failing test.** Above the final `print(...)` of `tests/test_figures_wire.py`:

```python
# --- §3.4 GET /issues/days ----------------------------------------------------------------------
class Cur:
    """Answers days()'s three reads from the capture: the session zone, readings_1h from a bucket on, alert_events."""
    def __init__(self, snap, events=()):
        self.snap, self.events, self.rows = snap, list(events), []

    def execute(self, sql, args=()):
        if "current_setting('TimeZone')" in sql:
            self.rows = [{"tz": "Asia/Makassar"}]
        elif "FROM readings_1h" in sql:
            self.rows = [dict(r, bucket=dt.datetime.fromisoformat(r["bucket"])) for r in self.snap["readings_1h"]
                         if dt.datetime.fromisoformat(r["bucket"]) >= args[0]]
        elif "FROM alert_events" in sql:
            self.rows = list(self.events)
        else:
            raise LookupError(sql[:60])

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


NOW = dt.datetime.fromisoformat(SNAP["as_of"])                     # 09:00 in Bali; the capture's last hour is 08:00
EV = [{"id": 2, "issue": "air", "kind": "danger", "level": "act",
       "opened_at": dt.datetime(2026, 10, 5, 23, 18, tzinfo=dt.timezone.utc), "cleared_at": None}]
one = engine.days(Cur(SNAP, EV), Settings(), DECL, 1, now=NOW)
rep = engine.replay(fresh(), Settings(), DECL)
assert one["schema"] == "days-v0" and one["days"] == 1 and one["tz"] == "Asia/Makassar"
assert len(one["buckets"]) == 24 and one["buckets"][-1] == "2026-10-06T09:00:00+08:00", one["buckets"][-1]
for k, v in one["issues"].items():
    r = rep["issues"][k]
    if v["distance"] is None:
        assert not any(r["series"].values()), f"{k}: /issues has a series that /issues/days lost"
        continue
    want = dict(zip(r["buckets"], r["series"][v["distance"]]))
    got = dict(zip(one["buckets"], v["series"][v["distance"]]))
    assert all(got[b] == want[b] for b in want), f"{k}: one day of /issues/days is not /issues' own 24 values"
    assert got["2026-10-06T09:00:00+08:00"] is None, "an hour with no rows is a null, never a skipped column"
    assert sum(p["of"] for p in v["per_day"]) == 24
    vals = [x for x in v["series"][v["distance"]] if x is not None]
    assert sum(p["read"] for p in v["per_day"]) == len(vals)
    assert sum(p["over"] for p in v["per_day"]) == sum(1 for x in vals if x > v["line"]["value"]), k
    assert v["provenance"][v["distance"]] == ("live" if v["distance"] in ("room", "yard") else "partial")
assert [p["date"] for p in one["issues"]["air"]["per_day"]] == ["2026-10-05", "2026-10-06"], "local days, not UTC"
assert one["events"] == [{"id": 2, "issue": "air", "kind": "danger", "level": "act",
                          "opened_at": "2026-10-05T23:18:00+00:00", "cleared_at": None}]
assert engine.days(Cur(SNAP), Settings(), DECL, 0, now=NOW)["days"] == 1
assert engine.days(Cur(SNAP), Settings(), DECL, 500, now=NOW)["days"] == engine.DAYS_MAX == 90
print("  /issues/days: one day is /issues' own 24 values; the node counts hours over per local day; 1 to 90 days")
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py`
  Expected: `AttributeError: module 'issues.engine' has no attribute 'days'`

- [ ] **Step 3: `_word`.** In `app/issues/engine.py`, directly above `def _from_stats`:

```python
def _word(place: str) -> str:
    """A distance's provenance word: ours is measured here; somebody else's is theirs, which is a different word
    whatever its quality."""
    return "live" if place in ("room", "yard") else "partial"
```

  and in `_from_stats` replace the comment line and `word = "live" if place in ("room", "yard") else "partial"` with
  `word = _word(place)`.

- [ ] **Step 4: `days`.** Directly above `def _sections(` in `app/issues/engine.py`:

```python
DAYS_MAX = 90


def _local_days(buckets: list, tz) -> list[tuple]:
    """(local date, [indexes into buckets]) in order. A window starts and ends inside a day, so `of` says how many of
    that day's hours the window holds."""
    out: list[tuple] = []
    for i, b in enumerate(buckets):
        day = b.astimezone(tz).date()
        if out and out[-1][0] == day:
            out[-1][1].append(i)
        else:
            out.append((day, [i]))
    return out


def days(cur, settings, decl: dict, n: int, now: datetime | None = None) -> dict:
    """GET /issues/days: each declared issue's hourly series over n local days, computed by the same `_series` that
    gives /issues its 24 hours, so a cell of the page's strip is what the lead's numeral said at that hour
    (docs/SPEC_dashboard_figures.md §3.4). The node counts the hours over the line, so the page prints a count it did
    not make. Buckets are generated, not observed: an hour with no row at all is a null, never a skipped column.
    Node #1 reads 90 days of readings_1h in 164 ms (6 October 2026), so there is no cache."""
    now = now or datetime.now(timezone.utc)
    n = max(1, min(int(n), DAYS_MAX))
    cur.execute("SELECT current_setting('TimeZone') AS tz")
    tzname = (cur.fetchone() or {}).get("tz") or "UTC"
    try:
        tz = ZoneInfo(tzname)
    except (ZoneInfoNotFoundError, ValueError):
        tz = timezone.utc
    top = now.astimezone(tz).replace(minute=0, second=0, microsecond=0)
    buckets = [top - timedelta(hours=k) for k in range(n * 24 - 1, -1, -1)]
    hourly: dict = {b: [] for b in buckets}
    for r in _rows(cur, "SELECT h.bucket, h.sensor_id, h.metric, h.mean, s.indoor, s.local, s.kind "
                        "FROM readings_1h h JOIN sensors s USING (sensor_id) WHERE h.bucket >= %s", buckets[0]):
        b = r["bucket"] if isinstance(r["bucket"], datetime) else datetime.fromisoformat(r["bucket"])
        if b in hourly:
            hourly[b].append(r)
    declared, _ = order(settings.get("NODE_ISSUES", ""), decl)
    groups = _local_days(buckets, tz)
    issues: dict = {}
    for key in declared:
        d = decl[key]
        series = _series(d, hourly, buckets, {})
        dist = next((x for x in DISTANCES if series.get(x)), None)
        line = d.get("line")
        lv = float(line["value"]) if line and line.get("value") is not None else None
        per_day = []
        for day, idx in (groups if dist else []):
            got = [series[dist][i] for i in idx if series[dist][i] is not None]
            per_day.append({"date": day.isoformat(), "over": None if lv is None else sum(1 for v in got if v > lv),
                            "read": len(got), "of": len(idx)})
        issues[key] = {"distance": dist, "series": series,
                       "provenance": {x: _word(x) for x in DISTANCES if series.get(x)},
                       "per_day": per_day, "line": line}
    events = _rows(cur, "SELECT id, issue, kind, level, opened_at, cleared_at FROM alert_events "
                        "WHERE opened_at >= %s OR cleared_at IS NULL OR cleared_at >= %s", buckets[0], buckets[0])
    iso = lambda v: v.isoformat() if hasattr(v, "isoformat") else v  # noqa: E731
    return {"schema": "days-v0", "as_of": now.isoformat(), "tz": tzname, "days": n,
            "buckets": [b.isoformat() for b in buckets],
            "issues": issues,
            "events": [{**e, "opened_at": iso(e["opened_at"]), "cleared_at": iso(e["cleared_at"])} for e in events]}
```

- [ ] **Step 5: The route.** In `app/issues/api.py`, import `Query` beside `PathParam`
  (`from fastapi import APIRouter, HTTPException, Path as PathParam, Query`) and add below `issues_now`:

```python
@router.get("/days")
def issues_days(days: int = Query(7, ge=1, le=engine.DAYS_MAX)):
    """Each issue's hourly series over the last `days` local days, the hero distance's hours over the line counted per
    day, and the alert events in the window (docs/SPEC_dashboard_figures.md §3.4). The same engine as `/issues`, so a
    day here is the 24 hours `/issues` draws. Under the `/issues` prefix, so it shares exactly as `/issues` does."""
    import main                    # noqa: PLC0415
    with main.db() as con, con.cursor() as cur:
        return engine.days(cur, main.settings, load(), days)
```

- [ ] **Step 6: Pin the format.** In `tools/check_wire.py`, add to `FORMATS`:
  `"days-v0":       ("app/issues/engine.py", ("func", "days")),`. Change the docstring's first line from "The five
  wire formats'" to "The six wire formats'". Run `python3 tools/check_wire.py --update`; it writes
  `tests/data/wire/days-v0.json`.

- [ ] **Step 7: Run it and watch it pass.**
  Run: `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_figures_wire.py && python3 tools/check_wire.py && make lint`
  Expected: the suite's summary, no `x` from the wire gate, and lint's `ok` (lint's import check loads the route).

- [ ] **Step 8: Commit.**

```bash
git add app/issues/engine.py app/issues/api.py tools/check_wire.py tests/data/wire/days-v0.json tests/test_figures_wire.py
git commit -m "issues: GET /issues/days, the same series over up to 90 days, hours over the line counted by the node

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: a snapshot carries it, and the rig serves it

**Files:**
- Modify: `bin/planetai` (`cmd_snapshot`'s `PATHS`)
- Modify: `tests/visual/measure.mjs` (`serveNodeAPI`)

**Interfaces:**
- Produces: a snapshot key `issues_days` (the verbatim body of `GET /issues/days?days=7`), served by the rig at
  `/issues/days`. Part B's fixture-mode page reads it from `/issues/fixtures/<name>` as `issues_days`.

- [ ] **Step 1: The snapshot.** In `bin/planetai`, `cmd_snapshot`'s python block, append `"/issues/days?days=7"` to
  the end of `PATHS`. The key the loop derives is `issues_days`. Do not add any apostrophe anywhere in that block: it
  is inside a single-quoted shell string.

- [ ] **Step 2: The rig.** In `tests/visual/measure.mjs`, `serveNodeAPI`, directly above
  `if (u.pathname === '/issues' || u.pathname === '/issues/') {`:

```js
  /* GET /issues/days, from the capture (docs/SPEC_dashboard_figures.md §3.4). A capture taken before v0.78 has no
     issues_days, and the answer is the 404 a node without the route gives: the strips then draw their own empty
     state, which is the truth about that capture. */
  if (u.pathname === '/issues/days') {
    const data = computeNodeData(FIXTURE);
    if (data.error) { await failNodeAPI(route, u.pathname, data); return true; }
    const body = data.snapshot.issues_days;
    await (body == null
      ? route.fulfill({ status: 404, contentType: 'application/json',
          body: JSON.stringify({ detail: 'this snapshot carries no issues_days' }) })
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) }));
    return true;
  }
```

- [ ] **Step 3: Check both parse.**
  Run: `bash -n bin/planetai && node --check tests/visual/measure.mjs && echo parsed`
  Expected: `parsed`

- [ ] **Step 4: Commit.**

```bash
git add bin/planetai tests/visual/measure.mjs
git commit -m "snapshot: carry GET /issues/days; the visual rig serves it from a capture

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: the docs, the PR, and node #1

**Files:**
- Modify: `docs/site/api.md`, `CHANGELOG.md`, `docs/SPEC_dashboard_figures.md` (§3 names, to what was built)

- [ ] **Step 1: `docs/site/api.md`.**
  - In `### GET /issues`, the bullet listing each entry's keys gains `usual` and `usual_absent` after `hero`. Add a
    bullet below it:

```
- `usual` is the issue's usual day at its hero distance: for each local hour 0–23, the mean over that distance's
  sensors of `usual_by_hour`'s median and 90th percentile for the issue's own metric, over the 14 complete days before
  today. It is `null` when the node cannot say, and `usual_absent` says why: `unread` (a capture from before v0.78, or
  a node that has not refreshed the view since it started), `no_source`, `no_history`, or `not_watched`.
- Each open event in `events.open` carries `series`: its own rooms, hour by hour on the issue's `buckets`, combined
  as the issue combines its house (air the mean of PM2.5, heat the median of each room's apparent temperature).
- `stations` keeps a station heard in the last 30 days and not in the last day, with `read: {}`, `series: {}` and
  `last_heard`, unless a station heard today stands at the same point (a relay of a kit that still reports).
  `stations_silent` says whether they were read (`read`) and how far back (`within_days`).
```

  - Add a section after `### GET /issues/fixtures/{name}`:

```
### GET /issues/days

`?days=` from 1 to 90, default 7. Each declared issue's hourly series over that many local days, by the same engine
as `/issues`, so one day of it is the 24 hours `/issues` draws. Buckets are every local hour of the window, oldest
first; an hour with nothing recorded is `null`. For each issue: `distance` (the hero distance, the nearest with data),
`series` (room, yard, ring and region, each an array or `null`), `provenance` (the word for each distance drawn),
`per_day` (`date`, `over` the hours over the line at the hero distance, `read` the hours with a value, `of` the hours
of that day inside the window), and `line`. `events` lists the alert events opened in the window or still open.
Wire format `days-v0`. It is under the `/issues` prefix, so it is readable exactly where `/issues` is.
```

- [ ] **Step 2: Correct the spec's names to what was built.** In `docs/SPEC_dashboard_figures.md`:
  - §3.1: replace "and `usual` is `null` with `usual_absent: "capture"` on the issue, rather than the `LookupError`…"
    through the end of that bullet with: "Replay carries each issue's `usual` from the capture's own `/issues`, as it
    carries the events block; a capture from before v0.78 has none, so `usual` is `null` with `usual_absent: "unread"`
    rather than the `LookupError` the five required tables raise."
  - §3.3: replace "a snapshot without it replays with no silent stations and says so in `dropped`." with "the
    top-level `stations_silent: {read, within_days}` says whether they were read, and a replay carries the capture's
    own." Replace the "This PR decides how a silent row is matched…" sentence with: "A silent row is not listed when a
    station heard in the last day stands at the same point, to five decimal places. On node #1 that drops the three
    `bad-sc-*` relays and the OpenAQ relay of Padang2 Uluwatu, and keeps four."
  - §3.4: the heading becomes `GET /issues/days?days=7 (1 to 90)`; "stores the answer as `days`" becomes "stores the
    answer as `issues_days`"; replace the "Who may read it" bullet with "**Who may read it.** It is under the `/issues`
    prefix, so it is readable exactly where `/issues` is."

- [ ] **Step 3: `CHANGELOG.md`.** Under `## Unreleased`, add:

```
- `GET /issues` carries what the page's new drawings need: each issue's usual day (`usual`), an open event's own rooms
  hour by hour (`events.open[].series`), and the stations that stopped reporting in the last 30 days, kept with when
  they were last heard (relays of kits that still report are left out). `GET /issues/days?days=7` (up to 90) gives the
  same hourly series over many days with the hours over the line counted per day, and `planetai snapshot` captures it.
```

- [ ] **Step 4: Gates.**
  Run: `python3 tools/check_docs.py && make lint && make test`
  Expected: `97 documents check out` (or the current count), lint `ok`, `65 suites: 65 passed`.

- [ ] **Step 5: Commit.**

```bash
git add docs/site/api.md docs/SPEC_dashboard_figures.md CHANGELOG.md
git commit -m "docs: /issues' usual, event series and silent stations; GET /issues/days

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: The pull request.** Push the branch and open the PR against `main`, milestone `v0.78`, label
  `needs testing`. The body says what changed for a node, lists the six commits, names the spec and this plan, states
  the rebase note from Global constraints if `issue-state-events-2026-10-06` is still open, and ends with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Do not merge it: Tomas merges.

- [ ] **Step 7: After Tomas merges, prove it on node #1** (`docs/WORKFLOW.md` §2).

```bash
ssh mini 'export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"; cd ~/planetai/planetai-node && planetai update'
```

  Then, on node #1 (`ssh mini`, port 8081, the admin token from `planetai ui`, never printed into a log):
  - `curl -s localhost:8081/issues | python3 -c 'import json,sys; d=json.load(sys.stdin); print({k:(v.get("usual") or {}).get("distance") or v.get("usual_absent") for k,v in d["issues"].items()}, d["stations_silent"], [s["name"] for s in d["stations"] if s.get("last_heard")])'`
    Expected: air and heat show `room` (or `unread` within an hour of a restart), `{'read': True, 'within_days': 30}`,
    and the four names Task 3's test holds, or fewer if one has come back.
  - `time curl -s 'localhost:8081/issues/days?days=90' -o /dev/null -w '%{http_code}\n'`: `200`, well under a second.
  - `cd ~/planetai/planetai-node && planetai snapshot --out /tmp/snap.json && python3 -c 'import json; print(sorted(json.load(open("/tmp/snap.json"))["issues_days"]["issues"]))'`:
    the declared issues.
  - `docker compose logs app --since 10m | grep -iE 'error|traceback'`: nothing new.
  Swap the label to `tested: node 1` and leave one comment saying what you saw.
