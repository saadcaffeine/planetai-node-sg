# Node trust layer — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the node able to say which of its own numbers it trusts, and stop it publishing a fleet average
across sensors that are not at the node and do not agree.

**Architecture:** Four layers, bottom-up. (L0) `local` becomes a fact about distance rather than a flag frozen on
first insert; (L0) a `channel_roles` registry declares what each metric *is*, so integrity checks are written
against roles and not against sensor names; (L1/L2) a new `trust` data pack turns coverage, channel silence and
collocated disagreement into three alerts, in SQL, with no new dependency and no stored feature series; (L3) the
`rhythm` rule stops claiming a cause the data contradicts. No Python in the new pack. One new table.

**Tech Stack:** Postgres 16 (views + `corr()`), FastAPI, psycopg 3, PyYAML. No new dependencies.

**Spec:** [`docs/archive/reviews/INSIGHTS_DESIGN_2026-09.md`](../reviews/INSIGHTS_DESIGN_2026-09.md) — read it first. This
plan implements §3 (L0 and the rhythm half of L3), §4 (the role registry), and steps 1, 2, 3, 5 and 6 of §6.
`fleet_reference` and the `Environmental|Community` repoint (§3 L1, §6 step 7) are **out of scope** and get their own
release.

## Global Constraints

- `make lint && make test` green before **every** commit. The pre-commit hook enforces lint.
- **One change per commit.** Message states what it does and for whom.
- `main` is the beta channel; two testers may install from it at any moment. Nothing lands half-done.
- Pack SQL runs as role `planetai_ro`: `SELECT` on every table except `settings`, no writes. A new table inherits
  `SELECT` through the default privileges in `init.sql`.
- Every statement in `init.sql` must be safe to run twice (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN
  IF NOT EXISTS`, `DROP VIEW` then `CREATE`).
- Rule messages carry `en` and `id`. (`es` is **not** enforced by `tests/test_packs.py`; no shipped pack has it.)
- Every column a rule message interpolates must be returned by that rule's SQL. `make lint` checks this.
- `tools/check_docs.py`: every unit-bearing threshold in a pack README (`>= 35 °C`, `60 %`, `50 m`) must appear
  literally somewhere else in that pack's folder. Write the number in `rules.yml` too, or lint fails.
- `tools/check_docs.py`: README's `docs/` index must list exactly the `.md` files in `docs/`. Dated documents go in
  `docs/archive/reviews/` (not globbed). Do not add a dated file to `docs/`.
- `tools/check_rules.py` validates every rule and cell's SQL against `init.sql`. New columns must exist there first.
- House voice: plain verbs, short sentences. No "genuinely / honestly / straightforward / seamless / robust /
  leverage", no rule-of-three padding, no em-dash chains. **Statistics stay out of alert messages** — the number
  goes in the SQL row and the dashboard, the message says what to do.
- No new pip dependencies. Nothing in this plan needs one.
- Node #1 (`bayu-2`, tailnet, app on **port 8081**) is **read-only**: `GET /health`, `/sensors`, `/stats`,
  `/observations`, `/aggregates`, `/series`, `/export`. Never `update`, `restore`, `packs install`, a migration, or
  `docker compose` against it.

## Where this branch sits, and the collision it does not resolve

Established 7 September 2026 by inspection, not assumption:

- `origin/main` is at **v0.34** (`b69fb1c`, "the years, as pictures you can play"). Tags `v0.33.8` and `v0.34` are
  both released and pushed.
- The main checkout's local `main` was **2 commits behind** origin, and its working tree holds Tomas's
  uncommitted heat calibration: `packs/heat/{README.md,pack.yaml,rules.yml}`, `tests/test_shipped.py`,
  `tools/check_docs.py`, `CHANGELOG.md`. `make lint` and `make test` both pass on it.
- That pending work carries the CHANGELOG heading `## v0.33.8 — the heat rule was measuring Bali, not a
  heatwave`, and **v0.33.8 is already a released tag** for a different release (the earth `change --all` one). It
  was drafted against the stale local HEAD. It needs renumbering and rebasing onto v0.34 before it can ship.

**Ruling:** this branch is cut from `origin/main` (v0.34) into a separate worktree, and the main checkout's
uncommitted work is left exactly where it is. Rebasing or renumbering someone else's unreleased release entry is
not this plan's business.

**The collision this leaves.** Task 3 edits `packs/heat/rules.yml` — the `WHERE t.local AND t.metric = 'temp'`
line of `heat_stress_now`. Tomas's pending work edits the threshold three lines below it, `>= 32` to `>= 35`. Both
changes are correct and complementary; git will most likely auto-merge them, and if it does not the resolution is
to keep both. Whoever merges second resolves it.

**Version numbers.** This plan does not pick one. `tools/release.sh <version>` takes it at release time, and that
release is Tomas's step, not this branch's (Task 9, step 5). The CHANGELOG entry Task 9 writes gets its heading
number chosen then, once it is known whether the heat release went out first.

---

## File Structure

| file | responsibility |
|---|---|
| `app/sources.py` | add `metres()` and `stamp_local()`; drop `aqi` from `SC_METRICS`, add `bme_iaq` |
| `app/main.py` | unfreeze `local` in both upserts; call `stamp_local()` at both storage sites; load `channel_roles` |
| `app/packs.py` | add `channels()`, the `channels.yml` loader |
| `app/settings.py` | register `LOCAL_RADIUS_M` |
| `init.sql` | one new table, `channel_roles`; schema version 0.22 |
| `config/channels.yml` | **new** — role declarations for the metrics `app/sources.py` produces |
| `packs/trust/` | **new** data pack: `pack.yaml`, `channels.yml`, `rules.yml`, `README.md` |
| `packs/heat/rules.yml` | `heat_stress_now` gains `AND t.indoor` |
| `packs/insight/rules.yml` | `rhythm` prefers local outdoor, reads `noise`, drops the traffic claim |
| `packs/insight/README.md` | the corrected finding and where it came from |
| `registry.json` | node #1's coordinates corrected to Ungasan |
| `tools/check_docs.py` | every `channels.yml` metric must be a metric the code produces |
| `tests/test_sources.py` | `stamp_local`, `metres`, `bme_iaq` |
| `tests/test_packs.py` | `channels()` loader |
| `tests/test_shipped.py` | pin what v0.35 promises |
| `docs/sensors.md`, `docs/PACKS.md`, `docs/DOMAINS.md`, `README.md`, `CHANGELOG.md` | documentation |

---

## Task 1: `local` stops being frozen on first insert

**Why.** `/sensors` on node #1 returns three kits with `source=smartcitizen` and `local=false`. `smartcitizen()`
hardcodes `"local": True`, so those values are impossible from current code. Both upserts update `indoor`, `lat`,
`lon`, `name` and `meta` but omit `local` from `DO UPDATE SET`, so it keeps whatever the row's first insert wrote.
The comment in `tests/test_sources.py` records how those rows were born: `sc-19236` and `bad-sc-19236` once both
existed, and the BAD-born row set `local=false`. Deduplication was fixed; the frozen flag was not.

**Files:**
- Modify: `app/main.py:103-105` (poll upsert), `app/main.py:128-131` (MQTT `_store` upsert)
- Test: `tests/test_shipped.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing new. Task 2 depends on this landing first, because deriving `local` correctly is pointless
  while the column ignores updates.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_shipped.py`:

```python
# v0.35 — `local` was written once and never corrected. Node #1 carried three smartcitizen kits at local=false
# that no current code path can produce: they were born from Bali Air Dispatch before the bad- prefix existed.
# Both upserts must now update it, or a wrong partition of house and street survives every poll forever.
_main = open("app/main.py").read()
assert _main.count("local=EXCLUDED.local") + _main.count("local = EXCLUDED.local") == 2, \
    "both sensor upserts (poll and MQTT) must update local, or a stale flag never heals"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
make test
```

Expected: `AssertionError: both sensor upserts (poll and MQTT) must update local, ...`

- [ ] **Step 3: Add `local` to both `DO UPDATE SET` clauses**

`app/main.py:103-105` becomes:

```python
                           ON CONFLICT (sensor_id) DO UPDATE SET name=EXCLUDED.name, lat=EXCLUDED.lat, lon=EXCLUDED.lon,
                             indoor=EXCLUDED.indoor, local=EXCLUDED.local, kind=EXCLUDED.kind, scale=EXCLUDED.scale,
                             cadence=EXCLUDED.cadence, meta=EXCLUDED.meta""",
```

`app/main.py:128-131` becomes:

```python
                           ON CONFLICT (sensor_id) DO UPDATE SET
                             name = COALESCE(EXCLUDED.name, sensors.name),
                             lat = COALESCE(EXCLUDED.lat, sensors.lat), lon = COALESCE(EXCLUDED.lon, sensors.lon),
                             indoor = EXCLUDED.indoor, local = EXCLUDED.local, meta = sensors.meta || EXCLUDED.meta""",
```

- [ ] **Step 4: Run lint and tests**

```bash
make lint && make test
```

Expected: both `ok`.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_shipped.py
git commit -m "fix: heal the local flag on every poll, for nodes whose sensors changed hands

local was omitted from both DO UPDATE SET clauses, so it kept whatever the row's first insert wrote. Node #1
carried three smartcitizen kits at local=false, born from Bali Air Dispatch before the bad- prefix existed."
```

---

## Task 2: `local` means ours **and** here

**Why.** `smartcitizen()` documents its own assumption: *"Every kit here is yours (listed by id or discovered from
your account), so every one is local."* That conflates ownership with presence. `init.sql` says `local` is
"TRUE = physically at this node (ours)". Node #1's `/health` reports `-8.8190516, 115.1644423` (Ungasan). Three of
the six kits on the account sit at `-8.8271, 115.15709`, **1.2 km away**. They are Tomas's and they are not here.

Measured distances from node #1's live coordinates:

| kit | distance | verdict |
|---|---|---|
| `sc-19236` | 250 m | here |
| `sc-19874` | 272 m | here |
| `sc-19849`, `sc-19880`, `sc-19897` | 1 207 m | ours, not here |
| `sc-19898` | 7 822 m | ours, not here |

`LOCAL_RADIUS_M` defaults to **500**: above 272 and far below 1 207, so the split is not a knife-edge. It is a
setting because a lab campus and a flat do not share a radius, and the physical world does not read defaults.

**Consequence, and it is the reason Task 3 exists.** After this task node #1 has two local *outdoor* kits and
**no local indoor kit**. `packs/heat/cells.yml` (`Social|Community`) and every indoor rule in `air-quality` and
`insight` filter `s.local AND s.indoor` and go quiet, except for `msh-8f491db0`, the mesh gateway's BME680 in its
own box. That is correct behaviour for a node with no indoor sensor at its site, and `docs/COVERAGE.md` already
states the principle: *the node does not fill what it cannot measure*. It must be in the CHANGELOG for testers
(Task 9), and it invalidates the 35 °C line v0.34 measured on `sc-19880`/`sc-19849` indoors — which Task 3 handles.

**Files:**
- Modify: `app/sources.py` (add `metres()` and `stamp_local()` near the top, after `epa_2021_correct`)
- Modify: `app/main.py` (call `stamp_local()` at both storage sites), `app/settings.py` (register the setting)
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: Task 1's healing upsert.
- Produces:
  - `sources.metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float`
  - `sources.stamp_local(sensors: list[dict], lat: float, lon: float, radius_m: float) -> list[dict]`
    — mutates and returns `sensors`; only ever turns `local` from `True` to `False`, never the reverse.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sources.py`:

```python
# `local` is ours AND here. An adapter says whether a sensor is ours; distance says whether it is at this node.
# Node #1 moved to Ungasan and kept three kits 1.2 km away marked local, so its "house" was three kits in
# another building and it had no local outdoor sensor at all.
assert round(sources.metres(-8.8190516, 115.1644423, -8.81983, 115.16657)) == 250, "sc-19236 is 250 m from node #1"
assert round(sources.metres(-8.8190516, 115.1644423, -8.8271, 115.15709)) == 1207, "the indoor cluster is 1.2 km away"
assert sources.metres(-8.8190516, 115.1644423, -8.8190516, 115.1644423) == 0.0

NODE = (-8.8190516, 115.1644423)
here     = {"sensor_id": "sc-19236", "local": True,  "lat": -8.81983, "lon": 115.16657}
far      = {"sensor_id": "sc-19880", "local": True,  "lat": -8.8271,  "lon": 115.15709}
theirs   = {"sensor_id": "bad-x",    "local": False, "lat": -8.81985, "lon": 115.16650}
nocoords = {"sensor_id": "msh-abc",  "local": True,  "lat": None,     "lon": None}
sources.stamp_local([here, far, theirs, nocoords], *NODE, 500)
assert here["local"] is True,  "250 m inside a 500 m radius stays local"
assert far["local"] is False,  "1.2 km away is ours but not here"
assert theirs["local"] is False, "a public station next door is still not ours"
assert nocoords["local"] is True, "a mesh pod on our own gateway has no coordinates and stays local"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
make test
```

Expected: `AttributeError: module 'sources' has no attribute 'metres'`

- [ ] **Step 3: Implement both functions**

In `app/sources.py`, after `epa_2021_correct`:

```python
# ---------------------------------------------------------------- is this sensor at this node?
# `packs/place/adapter.py` has its own metres(); core must not import from a pack, so this is the second copy.
# Equirectangular: within a metre of haversine at a kilometre, about nine metres at eight, and cheap. Measured on
# node #1's own four sensors. Exact enough for a radius that is a judgement call anyway.
def metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat2 - lat1) * 111_320.0
    dx = (lon2 - lon1) * 111_320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def stamp_local(sensors: list[dict], lat: float, lon: float, radius_m: float) -> list[dict]:
    """`local` is ours AND here. The adapter decides ours; distance decides here.

    Only ever narrows: a sensor an adapter did not claim never becomes local, whatever its coordinates. A public
    reference station across the street is not the node's own measurement. A sensor with no coordinates that an
    adapter claims (a Meshtastic pod reaching us over our own gateway) stays local, because we cannot measure a
    distance we do not have and the radio itself is the evidence."""
    for s in sensors:
        if not s.get("local"):
            continue
        if s.get("lat") is None or s.get("lon") is None:
            continue
        s["local"] = metres(lat, lon, float(s["lat"]), float(s["lon"])) <= radius_m
    return sensors
```

Confirm `import math` is already at the top of `app/sources.py` (it is — `epa_2021_correct` uses it). If not, add it.

- [ ] **Step 4: Run the test to verify it passes**

```bash
make test
```

Expected: `ok`.

- [ ] **Step 5: Call it at both storage sites**

In `app/main.py`, in the poll loop immediately before the sensor upsert loop, and in `_store()` immediately before
its own:

```python
        sources.stamp_local(sensors, float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]),
                            float(settings.get("LOCAL_RADIUS_M") or 500))
```

Read the surrounding lines first: the poll loop already has `sensors` in scope from the adapter call, and `_store`
takes it as a parameter. Match how the file already reaches `settings` and `os.environ` — do not introduce a second
style.

- [ ] **Step 6: Register the setting**

In `app/settings.py`, add `LOCAL_RADIUS_M` to the runtime-changeable list beside the other numeric settings, with
the one-line description: `how far from the node a sensor can be and still count as this node's own, in metres`.
Follow the file's existing shape for a numeric setting exactly; do not invent a new field.

- [ ] **Step 7: Add the setting to the env documentation**

In `docs/sensors.md`, under "The adapter contract", after the paragraph explaining `local`:

```markdown
`local` is two facts at once: an adapter says whether a sensor is *yours*, and the node checks whether it is
*here*. A kit on your account 1.2 km away is yours and is not this node's measurement. `LOCAL_RADIUS_M` (500 m by
default) is the line. A sensor with no coordinates that arrives over your own gateway stays local.
```

- [ ] **Step 8: Lint, test, commit**

```bash
make lint && make test
git add app/sources.py app/main.py app/settings.py docs/sensors.md tests/test_sources.py
git commit -m "fix: local means ours and here, not ours anywhere, for a node that moved

Node #1 moved to Ungasan and kept three kits 1.2 km away marked local, so its house was three kits in another
building and it had no local outdoor sensor. LOCAL_RADIUS_M, 500 m by default."
```

---

## Task 3: the consequences of Task 2, made honest

Three separate corrections, one commit each. All of them are things Task 2 exposes rather than causes.

**Files:**
- Modify: `registry.json`, `packs/heat/rules.yml`, `packs/heat/README.md`
- Test: `tests/test_shipped.py`

- [ ] **Step 1: Correct node #1's coordinates in the registry**

`registry.json` says `-8.8271, 115.15709`. Node #1's `/health` says `-8.8190516, 115.1644423`. Verify it yourself
before editing, read-only:

```bash
ssh fablabbali@bayu-2 'curl -s localhost:8081/health' | python3 -m json.tool | grep -E '"lat"|"lon"|"node"'
```

Set `lat` and `lon` in `registry.json` to what `/health` returns, and `place` to `"Ungasan, Badung, Bali, ID"`.

```bash
make lint && git add registry.json
git commit -m "fix: node #1's registry coordinates, which were its old site 1.2 km away"
```

- [ ] **Step 2: Write the failing test for the heat rule's scope**

Append to `tests/test_shipped.py`:

```python
# v0.35 — heat_stress_now fired on any local sensor. Steadman's no-wind form is the indoor form (the pack's own
# README says so), and after LOCAL_RADIUS_M node #1's local sensors are two OUTDOOR kits, where the no-wind form
# overstates the load. The 35 °C line was measured on two indoor kits and only holds indoors.
assert "t.local AND t.indoor AND t.metric = 'temp'" in _heat["heat_stress_now"]["sql"], \
    "the no-wind apparent temperature form is indoor-only; so is the 35 °C line measured for it"
```

`_heat` is already defined by the v0.34 block above it. Reuse it; do not re-read the file.

- [ ] **Step 3: Run it to verify it fails**

```bash
make test
```

Expected: `AssertionError: the no-wind apparent temperature form is indoor-only; ...`

- [ ] **Step 4: Add the indoor filter**

In `packs/heat/rules.yml`, `heat_stress_now`, change:

```sql
      WHERE t.local AND t.metric = 'temp' AND t.mean_15m IS NOT NULL AND h.mean_15m IS NOT NULL)
```

to:

```sql
      -- indoor only: the no-wind Steadman form is the indoor form, and the 35 °C line was measured on two indoor
      -- kits. Outdoors, with wind unaccounted for, the same arithmetic overstates the load.
      WHERE t.local AND t.indoor AND t.metric = 'temp' AND t.mean_15m IS NOT NULL AND h.mean_15m IS NOT NULL)
```

- [ ] **Step 5: Say so in the pack README**

In `packs/heat/README.md`, in **What it assumes**, replace "the stress rules fire on any local sensor" with:

```markdown
Indoor for all of it. The night rule, the cell and the stress rules all read local indoor sensors, because the
no-wind Steadman form is the indoor form and the 35 °C line was measured indoors. A node whose only local sensors
are outdoors gets no heat alerts, which is the right answer rather than a wrong number.
```

Do not add a new unit-bearing threshold to the README. `check_docs.py` requires every `>= N °C` in a README to
appear elsewhere in the pack, and 35 and 40 already do.

- [ ] **Step 6: Lint, test, commit**

```bash
make lint && make test
git add packs/heat/rules.yml packs/heat/README.md tests/test_shipped.py
git commit -m "fix: heat stress is an indoor rule, because its formula and its threshold both are

Steadman's no-wind form and the 35 C line were both measured indoors. After LOCAL_RADIUS_M node #1's local
sensors are outdoor kits, where the same arithmetic overstates the load."
```

---

## Task 4: `aqi` from our own kits is the BME680's index, not an AQI

**Why.** The Smart Citizen API names the channel `Bosch BME68X - AQI`: the BME680's own internal gas index. It is
stored under metric `aqi`, next to `bad-iqs-*` rows whose `aqi` is a genuine air quality index from IQAir. Two
different quantities, one metric name, and any average across them is meaningless.

**Files:**
- Modify: `app/sources.py` (`SC_METRICS`), `docs/sensors.md` (the metric list)
- Test: `tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_sources.py`, extend the existing Smart Citizen fixture. Add to `sc["data"]["sensors"]`:

```python
          {"id": 241, "measurement": {"name": "AQI"}, "value": 55},
```

and after the existing `assert {m for _, _, m, _ in r} == {...}` line, replace that assertion with:

```python
# the Smart Citizen "AQI" channel is `Bosch BME68X - AQI`, the BME680's own gas index, not an air quality index.
# Stored as `aqi` it sat in the same column as IQAir's real AQI from Bali Air Dispatch.
assert {m for _, _, m, _ in r} == {"pm25", "temp", "humidity", "bme_iaq"}
assert "aqi" not in {m for _, _, m, _ in r}, "our kits must not publish a metric named aqi"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
make test
```

Expected: the set contains `aqi`, not `bme_iaq`.

- [ ] **Step 3: Rename it in the map**

In `app/sources.py`, `SC_METRICS`, replace `"AQI": "aqi",` with:

```python
    # `Bosch BME68X - AQI` is the BME680's own gas index, not an air quality index. Bali Air Dispatch's IQAir rows
    # publish a real `aqi`; keeping both under one name made an average of two different quantities.
    "AQI": "bme_iaq",
```

- [ ] **Step 4: Update the metric list in the docs**

In `docs/sensors.md`, in the `Metrics:` line, replace `aqi` with `bme_iaq` and add `iaq` if it is missing (the
Meshtastic map already produces `iaq`). Keep the line one line.

- [ ] **Step 5: Lint, test, commit**

```bash
make lint && make test
git add app/sources.py docs/sensors.md tests/test_sources.py
git commit -m "fix: our kits' AQI channel is the BME680's gas index, named bme_iaq

It shared the metric name aqi with IQAir's real air quality index from Bali Air Dispatch. Existing aqi rows from
smartcitizen stay in the database as history; nothing reads them."
```

**Note for Task 9's CHANGELOG:** existing `aqi` rows from `smartcitizen` sensors stay in `readings` as history. No
migration deletes them, no rule reads them, and the new metric starts fresh. Say that to testers.

---

## Task 5: the channel role registry

**Why.** §4 of the spec. The integrity rules need to know what a metric *is*, not what it is called: `temp` from a
kit is ambient, `temp` from the mesh gateway's BME680 inside its own box is not, `battery_pct` is neither, and
`bme_iaq` is a vendor index that must never be pooled. Hard-coding metric lists into three rules is how the
`aqi` mistake happened once already.

Keyed on `(source, metric)`, because a role is a property of the instrument that produced the number.

**Files:**
- Modify: `init.sql` (new table, schema 0.22), `app/packs.py` (loader), `app/main.py` (write at startup),
  `tools/check_docs.py` (lint), `docs/PACKS.md` (document the file)
- Create: `config/channels.yml`
- Test: `tests/test_packs.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `packs.channels() -> list[dict]` — every declaration from `config/channels.yml` and every enabled
    `packs/*/channels.yml`. Each dict: `{"source": str, "metric": str, "role": str, "comparable": bool,
    "unit": str | None, "reference": str | None, "declared_by": str}`. `declared_by` is `"core"` for
    `config/channels.yml`, else the pack id.
  - table `channel_roles (source, metric, role, comparable, unit, reference, declared_by)`, primary key
    `(source, metric)`. Task 6's rules join it.

- [ ] **Step 1: Add the table to `init.sql`**

Append, before the `settings` block:

```sql
-- What a metric IS, as declared by whoever produces it. Integrity checks are written against roles, not against
-- metric names: `temp` from a kit is ambient, `temp` from a gateway's BME680 inside its own box is not, and
-- `bme_iaq` is a vendor index that must never be pooled. Keyed on the source because the role belongs to the
-- instrument, not to the word. Written at startup from config/channels.yml and every pack's channels.yml.
CREATE TABLE IF NOT EXISTS channel_roles (
  source      TEXT NOT NULL,
  metric      TEXT NOT NULL,
  role        TEXT NOT NULL CHECK (role IN ('ambient','enclosure','device_health','derived','index')),
  comparable  BOOLEAN NOT NULL DEFAULT FALSE,   -- may be compared between sensors at the same place
  unit        TEXT,
  reference   TEXT,                             -- instrument family, so peer comparison groups like with like
  declared_by TEXT NOT NULL,
  PRIMARY KEY (source, metric)
);
INSERT INTO schema_version (version) VALUES ('0.22') ON CONFLICT DO NOTHING;
```

- [ ] **Step 2: Write `config/channels.yml`**

Core's own declarations, for the metrics `app/sources.py` produces. Every `source` string here must match the
`source` an adapter writes.

```yaml
# What each metric IS, per the source that produces it. See docs/PACKS.md.
#   ambient       — the air, water or land at a place. Comparable between sensors at the same place.
#   enclosure     — the inside of the instrument's own box. Never comparable, never an ambient average.
#   device_health — the instrument talking about itself. Feeds liveness, never a measurement.
#   derived       — computed by us from other readings. Carries the provenance of its inputs.
#   index         — a vendor's own composite number. Never pooled, never averaged across makers.

- { source: smartcitizen, metric: pm25,           role: ambient, comparable: true,  unit: "µg/m³", reference: sc }
- { source: smartcitizen, metric: pm10,           role: ambient, comparable: true,  unit: "µg/m³", reference: sc }
- { source: smartcitizen, metric: pm1,            role: ambient, comparable: true,  unit: "µg/m³", reference: sc }
- { source: smartcitizen, metric: temp,           role: ambient, comparable: true,  unit: "°C",    reference: sc }
- { source: smartcitizen, metric: humidity,       role: ambient, comparable: true,  unit: "%",     reference: sc }
- { source: smartcitizen, metric: pressure,       role: ambient, comparable: true,  unit: "kPa",   reference: sc }
- { source: smartcitizen, metric: noise,          role: ambient, comparable: true,  unit: "dB",    reference: sc }
- { source: smartcitizen, metric: light,          role: ambient, comparable: true,  unit: "lux",   reference: sc }
- { source: smartcitizen, metric: gas_resistance, role: ambient, comparable: false, unit: "Ohm",   reference: bme680 }
- { source: smartcitizen, metric: bme_iaq,        role: index,   comparable: false }
- { source: smartcitizen, metric: eco2,           role: index,   comparable: false, unit: "ppm" }
- { source: smartcitizen, metric: tvoc,           role: index,   comparable: false }

- { source: baliairdispatch, metric: pm25,     role: ambient, comparable: true, unit: "µg/m³" }
- { source: baliairdispatch, metric: pm25_raw, role: ambient, comparable: false, unit: "µg/m³" }
- { source: baliairdispatch, metric: pm10,     role: ambient, comparable: true, unit: "µg/m³" }
- { source: baliairdispatch, metric: pm1,      role: ambient, comparable: true, unit: "µg/m³" }
- { source: baliairdispatch, metric: temp,     role: ambient, comparable: true, unit: "°C" }
- { source: baliairdispatch, metric: humidity, role: ambient, comparable: true, unit: "%" }
- { source: baliairdispatch, metric: aqi,      role: index,   comparable: false }

- { source: airgradient, metric: pm25,       role: ambient, comparable: true,  unit: "µg/m³", reference: plantower }
- { source: airgradient, metric: pm25_raw,   role: ambient, comparable: false, unit: "µg/m³", reference: plantower }
- { source: airgradient, metric: pm10,       role: ambient, comparable: true,  unit: "µg/m³", reference: plantower }
- { source: airgradient, metric: pm1,        role: ambient, comparable: true,  unit: "µg/m³", reference: plantower }
- { source: airgradient, metric: co2,        role: ambient, comparable: true,  unit: "ppm" }
- { source: airgradient, metric: temp,       role: ambient, comparable: true,  unit: "°C" }
- { source: airgradient, metric: humidity,   role: ambient, comparable: true,  unit: "%" }
- { source: airgradient, metric: tvoc_index, role: index,   comparable: false }
- { source: airgradient, metric: nox_index,  role: index,   comparable: false }

- { source: purpleair, metric: pm25,     role: ambient, comparable: true,  unit: "µg/m³", reference: plantower }
- { source: purpleair, metric: pm25_raw, role: ambient, comparable: false, unit: "µg/m³", reference: plantower }
- { source: purpleair, metric: humidity, role: ambient, comparable: true,  unit: "%" }
- { source: purpleair, metric: temp,     role: ambient, comparable: true,  unit: "°C" }

# A radio in a sealed case reports its own box, not the street. Marking these ambient is how a radiation shield's
# temperature becomes the neighbourhood's.
- { source: meshtastic, metric: temp,             role: enclosure,     comparable: false, unit: "°C" }
- { source: meshtastic, metric: humidity,         role: enclosure,     comparable: false, unit: "%" }
- { source: meshtastic, metric: pressure_hpa,     role: enclosure,     comparable: false, unit: "hPa" }
- { source: meshtastic, metric: gas_resistance,   role: enclosure,     comparable: false, unit: "Ohm" }
- { source: meshtastic, metric: iaq,              role: index,         comparable: false }
- { source: meshtastic, metric: pm25,             role: ambient,       comparable: true,  unit: "µg/m³" }
- { source: meshtastic, metric: pm10,             role: ambient,       comparable: true,  unit: "µg/m³" }
- { source: meshtastic, metric: pm1,              role: ambient,       comparable: true,  unit: "µg/m³" }
- { source: meshtastic, metric: co2,              role: ambient,       comparable: true,  unit: "ppm" }
- { source: meshtastic, metric: battery_pct,      role: device_health,  comparable: false, unit: "%" }
- { source: meshtastic, metric: battery_v,        role: device_health,  comparable: false, unit: "V" }
- { source: meshtastic, metric: lora_util_pct,    role: device_health,  comparable: false, unit: "%" }
- { source: meshtastic, metric: lora_channel_pct, role: device_health,  comparable: false, unit: "%" }

- { source: openmeteo, metric: pm25_model, role: derived, comparable: false, unit: "µg/m³" }
- { source: cams,      metric: pm25_model, role: derived, comparable: false, unit: "µg/m³" }
```

**Before writing this file, verify every `(source, metric)` pair against the code.** Read `SC_METRICS`,
`AG_METRICS`, `MESH_METRICS` and each adapter's `"source":` string in `app/sources.py`. A pair that does not exist
fails Step 6's lint. `meshtastic` metrics not listed above (`wind_speed`, `soil_moisture`, `uv_lux`, `rainfall_1h`,
`pm25_env`, …) are in `MESH_METRICS` but no node produces them yet — leave them out and let the lint tell you if
that is wrong.

- [ ] **Step 3: Write the failing test for the loader**

Append to `tests/test_packs.py`:

```python
# The channel role registry. Integrity rules read roles, not metric names.
import packs as _packs
_ch = _packs.channels()
_by = {(c["source"], c["metric"]): c for c in _ch}
assert _by[("smartcitizen", "pm25")]["role"] == "ambient" and _by[("smartcitizen", "pm25")]["comparable"] is True
assert _by[("smartcitizen", "bme_iaq")]["role"] == "index", "a vendor index is never pooled"
assert _by[("meshtastic", "temp")]["role"] == "enclosure", "a radio in a sealed case reports its own box"
assert _by[("meshtastic", "battery_pct")]["role"] == "device_health"
assert _by[("smartcitizen", "pm25")]["declared_by"] == "core"
assert all(c["role"] in ("ambient", "enclosure", "device_health", "derived", "index") for c in _ch)
assert len({(c["source"], c["metric"]) for c in _ch}) == len(_ch), "one declaration per source and metric"
print(f"{len(_ch)} channel roles declared")
```

- [ ] **Step 4: Run it to verify it fails**

```bash
make test
```

Expected: `AttributeError: module 'packs' has no attribute 'channels'`

- [ ] **Step 5: Implement the loader**

In `app/packs.py`, after `cells()`, following that function's exact shape (same `_enabled()` iteration, same
`yaml.safe_load`, same warn-and-skip on a bad file):

```python
ROLES = ("ambient", "enclosure", "device_health", "derived", "index")


def channels() -> list[dict]:
    """Channel role declarations: core's own, then every enabled pack's. A pack may not redeclare a pair core has
    already claimed; the first declaration wins and the duplicate is logged, so a merged pack cannot quietly
    relabel PM2.5 as a vendor index."""
    out, seen = [], set()
    files = [(Path("config/channels.yml"), "core")] + [(d / "channels.yml", d.name) for d in _enabled()]
    for f, who in files:
        if not f.exists():
            continue
        try:
            decls = yaml.safe_load(f.read_text()) or []
        except Exception as e:  # noqa: BLE001
            log.warning("channels.yml in %s did not parse: %s", who, e); continue
        for c in decls:
            key = (c.get("source"), c.get("metric"))
            if not all(key) or c.get("role") not in ROLES:
                log.warning("%s: skipping channel declaration %r", who, c); continue
            if key in seen:
                log.warning("%s: %s/%s is already declared; keeping the first", who, *key); continue
            seen.add(key)
            out.append({"source": key[0], "metric": key[1], "role": c["role"],
                        "comparable": bool(c.get("comparable", False)), "unit": c.get("unit"),
                        "reference": c.get("reference"), "declared_by": who})
    return out
```

Check the top of `app/packs.py` for how it resolves paths — if it uses a `PACKS_DIR` env var or a module-level
`Path`, resolve `config/channels.yml` the same way rather than from the process's working directory.

- [ ] **Step 6: Run the test to verify it passes**

```bash
make test
```

Expected: `N channel roles declared`.

- [ ] **Step 7: Write the declarations into the table at startup**

In `app/main.py`, in the same startup path that already loads packs (find where `packs.cells()` or
`packs.manifests()` is first called), add:

```python
def load_channel_roles() -> int:
    """Declarations are the file's, not the database's: replace the table on every start so a removed pack's
    claims go with it."""
    rows = packs.channels()
    with db() as con, con.cursor() as cur:
        cur.execute("DELETE FROM channel_roles")
        cur.executemany(
            """INSERT INTO channel_roles (source, metric, role, comparable, unit, reference, declared_by)
               VALUES (%(source)s,%(metric)s,%(role)s,%(comparable)s,%(unit)s,%(reference)s,%(declared_by)s)""",
            rows)
    log.info("channel roles: %d declared", len(rows))
    return len(rows)
```

Call it once at startup, after the schema is known to be current and inside the same try/except the neighbouring
startup steps use. It must not take the node down: a node whose database predates 0.22 has no table, and the
call must log once and continue.

- [ ] **Step 8: Add the lint check**

In `tools/check_docs.py`, beside the existing pack checks:

```python
# Every declared channel must be a metric some adapter actually produces. A declaration for a metric that does not
# exist is a role nothing will ever wear, and a typo in one is silent: the rule that reads roles just returns
# nothing.
_src = open("app/sources.py").read()
_produced = set(re.findall(r'"[^"]+":\s*"([a-z0-9_]+)"', _src)) | {"pm25", "pm25_raw"}
for f in ["config/channels.yml"] + sorted(glob.glob("packs/*/channels.yml")):
    for d in yaml.safe_load(open(f)) or []:
        if d.get("metric") not in _produced:
            errs.append(f"{f}: declares metric `{d.get('metric')}`, which no adapter produces")
```

`tools/check_docs.py` may not import `yaml` or `glob` yet — check its imports and add what is missing.

- [ ] **Step 9: Document the file**

In `docs/PACKS.md`, in the pack folder listing, add `channels.yml` with its one-line purpose, and add a short
subsection after "Data packs" explaining the five roles in one sentence each. Keep it under fifteen lines.

- [ ] **Step 10: Lint, test, commit**

```bash
make lint && make test
git add init.sql config/channels.yml app/packs.py app/main.py tools/check_docs.py docs/PACKS.md tests/test_packs.py
git commit -m "feat: channel roles, so integrity checks read what a metric is and not what it is called

ambient | enclosure | device_health | derived | index, keyed on (source, metric). A radio's BME680 in a sealed
case is not the street, and a vendor index is not a measurement. Schema 0.22."
```

---

## Task 6: the `trust` pack

**Why.** §3 L0 of the spec. Three things node #1 would have said this week and did not: a kit at 3% coverage
reporting a fresh timestamp, a channel frozen under a live kit, and one of three kits in the same room reading
1.5× the other two.

**No cells.** Decided: a trust score never becomes an Index cell. Coverage and drift are facts about our
instruments, not about the place, and a cell that scores our own competence invites us to optimise it.

**No stored features and no Python.** Each rule's SQL computes what it needs. Storing a feature series is for when
a second consumer exists; today the rules are the only one. `data` pack, YAML only.

**Files:**
- Create: `packs/trust/pack.yaml`, `packs/trust/channels.yml`, `packs/trust/rules.yml`, `packs/trust/README.md`
- Modify: `README.md` (pack list), `docs/PACKS.md` (What ships table)
- Test: `tests/test_shipped.py`

**Interfaces:**
- Consumes: `channel_roles` from Task 5; `local` from Task 2.
- Produces: three rule ids — `channel_dead`, `coverage_low`, `peer_disagreement`.

- [ ] **Step 1: `packs/trust/pack.yaml`**

```yaml
id: trust
name: Trust
description: >-
  Whether the node's own sensors are telling it the truth. Coverage over the last week, channels that have stopped
  changing under a kit that still reports, and collocated sensors that disagree about the level. SQL over what the
  node already holds; nothing leaves the machine and nothing reaches the Index.
author: PLANETAI core (official)
version: 0.1.0
requires: { node: ">=0.35.0" }
kind: data
domain: cross-domain
scales: [community]
```

- [ ] **Step 2: `packs/trust/channels.yml`**

```yaml
# The trust pack produces no readings. This file exists so `planetai packs` shows it declares nothing, rather than
# leaving a reader to wonder.
[]
```

- [ ] **Step 3: Write the failing test**

Append to `tests/test_shipped.py`:

```python
# v0.35 — the trust pack. Node #1 held a kit at 3% coverage reporting a timestamp four minutes old, and three
# collocated indoor kits where one read 1.5x the other two. Nothing said so.
_trust = {r["id"]: r for r in yaml.safe_load(open("packs/trust/rules.yml"))}
assert set(_trust) == {"channel_dead", "coverage_low", "peer_disagreement"}, "three rules, no more"
assert not os.path.exists("packs/trust/cells.yml"), "a trust score is never an Index cell"
assert "60" in _trust["coverage_low"]["sql"], "coverage_low's floor is 60% of the last 7 days"
assert "50" in _trust["peer_disagreement"]["sql"], "collocation is 50 m"
assert "0.85" in _trust["peer_disagreement"]["sql"] and "1.15" in _trust["peer_disagreement"]["sql"]
assert "channel_roles" in _trust["peer_disagreement"]["sql"], "peer comparison is ambient-only, by role"
for _r in _trust.values():
    assert set(_r["message"]) >= {"en", "id"}, "every alert speaks English and Indonesian"
    assert "µg" not in _r["message"]["en"], "statistics stay out of alert messages"
print("the trust pack ships three rules and no cells")
```

Check `os` is imported in `tests/test_shipped.py`; add it if not.

- [ ] **Step 4: Run it to verify it fails**

```bash
make test
```

Expected: `FileNotFoundError: packs/trust/rules.yml`

- [ ] **Step 5: Write `packs/trust/rules.yml`**

```yaml
# Whether the node's own numbers are worth saying out loud. Every rule reads only local sensors: a public
# reference station's coverage is not ours to police.
#
# Silence is defined by VALUE CHANGE, not by a timestamp. Smart Citizen's per-kit `recorded_at` is null on every
# kit node #1 reads, so the adapter stamps every channel with the kit-level `last_reading_at`. A dead channel then
# carries a fresh timestamp forever, and its frozen value is re-inserted under new timestamps, which pulls the
# 24-hour mean toward itself and shrinks the variance. The reading looks steadier as it dies.

# ---------------------------------------------------------------- a channel that stopped changing under a live kit
- id: channel_dead
  level: warn
  cooldown_minutes: 720
  sql: |
    WITH ours AS (
      SELECT r.sensor_id, r.metric, s.name, s.source
      FROM readings_1h r JOIN sensors s USING (sensor_id)
      JOIN channel_roles c ON c.source = s.source AND c.metric = r.metric
      WHERE s.local AND s.kind = 'sensor' AND c.role IN ('ambient', 'enclosure')
      GROUP BY 1, 2, 3, 4),
    frozen AS (
      SELECT o.sensor_id, o.metric, o.name,
             count(*) AS flat_hours,
             max(r.bucket) AS last_bucket
      FROM ours o JOIN readings_1h r ON r.sensor_id = o.sensor_id AND r.metric = o.metric
      WHERE r.bucket > now() - interval '24 hours' AND r.max - r.min = 0
      GROUP BY 1, 2, 3),
    alive AS (
      SELECT sensor_id, max(ts) AS kit_ts FROM readings
      WHERE ts > now() - interval '2 hours' GROUP BY 1)
    SELECT f.sensor_id, f.name, f.metric, f.flat_hours
    FROM frozen f JOIN alive a USING (sensor_id)
    WHERE f.flat_hours >= 6
  message:
    en: "🧊 One reading at {name} has stopped moving.\n\nIts {metric} has been the same number for hours while the rest of the kit keeps reporting. That usually means one sensor has failed, not the kit.\n\n👉 Power-cycle it. If the number stays frozen, the sensor needs replacing, and anything I have told you about {metric} since it froze was wrong."
    id: "🧊 Satu bacaan di {name} berhenti bergerak.\n\nNilai {metric} sama selama berjam-jam padahal kit-nya masih melapor. Biasanya itu satu sensor yang rusak, bukan kit-nya.\n\n👉 Matikan lalu nyalakan lagi. Kalau angkanya tetap beku, sensornya harus diganti, dan semua yang saya sampaikan soal {metric} sejak itu salah."

# ---------------------------------------------------------------- a local sensor with holes in the week
- id: coverage_low
  level: info
  cooldown_minutes: 1440
  sql: |
    WITH have AS (
      SELECT r.sensor_id, s.name, count(DISTINCT r.bucket) AS hours
      FROM readings_1h r JOIN sensors s USING (sensor_id)
      JOIN channel_roles c ON c.source = s.source AND c.metric = r.metric
      WHERE s.local AND s.kind = 'sensor' AND c.role = 'ambient' AND c.comparable
        AND r.bucket > now() - interval '7 days'
      GROUP BY 1, 2)
    SELECT sensor_id, name, hours, round(100.0 * hours / 168) AS pct
    FROM have
    WHERE 100.0 * hours / 168 < 60
  message:
    en: "🕳️ {name} is missing most of the week.\n\nIt reported for only part of the last seven days, so any weekly figure that includes it is really a figure about the hours it was awake. Its own latest reading still looks current, which is why this needs saying.\n\n👉 Check its power and its WiFi. If it cannot hold a connection where it is, it needs moving or a better aerial."
    id: "🕳️ {name} kehilangan sebagian besar data minggu ini.\n\nIa hanya melapor sebagian dari tujuh hari terakhir, jadi angka mingguan yang memakainya sebenarnya hanya soal jam-jam saat ia hidup. Bacaan terakhirnya tetap tampak baru, dan itu sebabnya ini perlu disebut.\n\n👉 Periksa listrik dan WiFi-nya. Kalau tidak bisa menjaga koneksi di tempatnya sekarang, ia perlu dipindah atau antena yang lebih baik."

# ---------------------------------------------------------------- two sensors in the same place, different levels
- id: peer_disagreement
  level: warn
  cooldown_minutes: 1440
  sql: |
    WITH ambient AS (
      SELECT r.sensor_id, s.name, s.lat, s.lon, r.metric, avg(r.mean) AS mean
      FROM readings_1h r JOIN sensors s USING (sensor_id)
      JOIN channel_roles c ON c.source = s.source AND c.metric = r.metric
      WHERE s.local AND s.kind = 'sensor' AND c.role = 'ambient' AND c.comparable
        AND s.lat IS NOT NULL AND r.bucket > now() - interval '24 hours'
      GROUP BY 1, 2, 3, 4, 5 HAVING count(*) >= 12),
    -- collocated: within 50 m of each other. Equirectangular, which is exact enough at this distance.
    pairs AS (
      SELECT a.sensor_id, a.name, a.metric, a.mean AS mine, b.mean AS theirs
      FROM ambient a JOIN ambient b
        ON b.metric = a.metric AND b.sensor_id <> a.sensor_id
       AND sqrt(power((b.lat - a.lat) * 111320, 2)
              + power((b.lon - a.lon) * 111320 * cos(radians((a.lat + b.lat) / 2)), 2)) <= 50),
    ratio AS (
      SELECT sensor_id, name, metric, mine / nullif(percentile_cont(0.5) WITHIN GROUP (ORDER BY theirs), 0) AS r
      FROM pairs GROUP BY 1, 2, 3, mine)
    SELECT sensor_id, name, metric, round(r::numeric, 2) AS r
    FROM ratio
    WHERE r < 0.85 OR r > 1.15
  message:
    en: "⚖️ Two sensors in the same place disagree at {name}.\n\nIts {metric} sits well above or below its neighbours a few metres away. They see the same air, so one of them is reading off, or it is sitting closer to something the others cannot smell.\n\n👉 Swap the two units' positions for a day. If the gap follows the box it is the sensor; if it stays with the spot it is the siting."
    id: "⚖️ Dua sensor di tempat yang sama tidak sepakat di {name}.\n\nNilai {metric}-nya jauh di atas atau di bawah tetangganya yang hanya beberapa meter. Mereka menghirup udara yang sama, jadi salah satunya membaca keliru, atau ia lebih dekat ke sesuatu yang tidak tercium yang lain.\n\n👉 Tukar posisi dua unit itu selama sehari. Kalau selisihnya ikut kotaknya, sensornya; kalau tetap di tempatnya, penempatannya."
```

- [ ] **Step 6: Run lint to check the SQL against the schema**

```bash
make lint
```

`tools/check_rules.py` parses every rule's SQL against `init.sql`. Expected: `N rules and cells check out`. If it
rejects a column, the column does not exist — read `init.sql` and fix the SQL, do not weaken the check.
All four of this pack's SQL bodies were parsed against sqlglot's postgres dialect before this task was dispatched
and all four parse, `percentile_cont(0.5) WITHIN GROUP (ORDER BY ...)` included. Keep the median. If the gate
rejects something, it has found a real problem, not a dialect limitation.

- [ ] **Step 7: Run the SQL against node #1, read-only, before trusting it**

The rules must return the rows the spec says they should. Node #1 is read-only, so run each `sql:` body through a
read-only psql session and confirm: `coverage_low` names `sc-19898`, `peer_disagreement` names `sc-19849` for
`pm25` at roughly 1.5. If either returns nothing, the SQL is wrong, not the data.

```bash
ssh fablabbali@bayu-2 'docker exec -i planetai-db-1 psql -U planetai -d planetai -c "SET ROLE planetai_ro" -c "<paste the rule SQL>"'
```

`SET ROLE planetai_ro` first, so the query cannot write even by accident. If `channel_roles` does not exist on
node #1 yet (it will not — it ships in this release), run the join against a literal `VALUES` list standing in for
the table and note that you did.

- [ ] **Step 8: Write `packs/trust/README.md`**

Must state: what each rule fires on and its exact number (60% of 168 hours, 6 flat hours, 50 m, 0.85–1.15); that
silence is defined by value change and why; that it reads local sensors only; that it writes no Index cell and why;
what it does not know (it cannot tell a badly sited sensor from a badly calibrated one, which is why the message
asks the reader to swap two units rather than telling them which is wrong); and the place and week the numbers came
from — node #1, Ungasan, 1–7 September 2026, six kits, PM2.5 means of 6–10 µg/m³. Say plainly that the thresholds
were chosen against one low-PM week and have never met a burn season.

Every unit-bearing number in the README must appear in `rules.yml` too, or `check_docs.py` fails.

- [ ] **Step 9: Add the pack to the two lists**

`README.md`, the `packs/` line in **Layout**: add `trust` after `insight`.
`docs/PACKS.md`, the **What ships** table: a row for `trust`, `data`, and one line of what it does. The prose at
the top says "Node #1 runs nine" — count the packs and correct the number.

- [ ] **Step 10: Lint, test, commit**

```bash
make lint && make test
git add packs/trust README.md docs/PACKS.md tests/test_shipped.py
git commit -m "feat: the trust pack, so the node can say which of its own numbers it doubts

Coverage under 60% of the week, a channel flat for 6 hours under a live kit, a collocated sensor outside
0.85-1.15 of its neighbours. Three alerts, no Index cell: a trust score is a fact about our instruments."
```

---

## Task 7: the `rhythm` rule stops blaming traffic

**Why.** `packs/insight/rules.yml` tells households *"That is the burning and the traffic, not the weather."*
Measured on `sc-19236` over the same seven days, in WITA: PM2.5 peaks at 18:00 (14.7 µg/m³) with a second peak at
06:00–07:00, while noise peaks 10:00–17:00 (49–51 dB) and sits at 36–37 overnight. r(PM2.5, noise) = **−0.239**.
The loud hours are the cleanest hours. The evening peak arrives as noise falls and the light goes.

The kit that measures noise is `sc-19236`, at the node's own site — `local` after Task 2, which is what makes this
rule possible at all.

**Files:**
- Modify: `packs/insight/rules.yml` (`rhythm`), `packs/insight/README.md`
- Test: `tests/test_shipped.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_shipped.py`:

```python
# v0.35 — the rhythm rule told households the evening PM peak was "the burning and the traffic". The noise channel
# we already store says otherwise: r(pm25, noise) = -0.24 at node #1, and the loud hours are the clean ones.
_ins = {r["id"]: r for r in yaml.safe_load(open("packs/insight/rules.yml"))}
assert "traffic" not in _ins["rhythm"]["message"]["en"], "the noise channel contradicts the traffic claim"
assert "'noise'" in _ins["rhythm"]["sql"], "rhythm reads the noise channel it has been discarding"
assert "quiet_hr" in _ins["rhythm"]["sql"], "the message needs the hour the street is loudest to contrast with"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
make test
```

Expected: `AssertionError: the noise channel contradicts the traffic claim`

- [ ] **Step 3: Rewrite the rule**

In `packs/insight/rules.yml`, replace the `rhythm` rule's `sql` and `message`. The SQL keeps its existing shape and
adds two things: it prefers **local** outdoor sensors over the pooled `NOT s.indoor` set (the order
`docs/sensors.md` already documents), and it returns the hour noise peaks.

```yaml
- id: rhythm
  level: info
  cooldown_minutes: 1440
  sql: |
    WITH by_hour AS (
      SELECT extract(hour FROM r.bucket AT TIME ZONE current_setting('TimeZone'))::int AS hr,
             avg(r.mean) FILTER (WHERE s.local AND NOT s.indoor AND r.metric = 'pm25')  AS outdoor,
             avg(r.mean) FILTER (WHERE s.local AND s.indoor AND r.metric = 'pm25')      AS indoor,
             avg(r.mean) FILTER (WHERE s.local AND NOT s.indoor AND r.metric = 'noise') AS noise
      FROM readings_1h r JOIN sensors s USING (sensor_id)
      WHERE r.metric IN ('pm25', 'noise') AND r.bucket > now() - interval '7 days' AND s.kind = 'sensor'
      GROUP BY 1),
    worst AS (SELECT hr, outdoor FROM by_hour WHERE outdoor IS NOT NULL ORDER BY outdoor DESC LIMIT 1),
    best  AS (SELECT hr, outdoor FROM by_hour WHERE outdoor IS NOT NULL ORDER BY outdoor ASC  LIMIT 1),
    loud  AS (SELECT hr, noise   FROM by_hour WHERE noise   IS NOT NULL ORDER BY noise   DESC LIMIT 1)
    SELECT 'node' AS sensor_id,
           lpad(worst.hr::text, 2, '0') AS worst_hr, round(worst.outdoor::numeric) AS worst_v,
           lpad(best.hr::text, 2, '0')  AS best_hr,
           lpad(loud.hr::text, 2, '0')  AS quiet_hr
    FROM worst, best, loud
  message:
    en: "🕐 Your street has a rhythm.\n\nThis week the outside air was worst around {worst_hr}:00 and cleanest around {best_hr}:00. The street was at its loudest around {quiet_hr}:00, which was not when the air was worst — so the evening peak is not the traffic. Something is being burned after dark.\n\n👉 If you air the house, {best_hr}:00 is the hour."
    id: "🕐 Jalan Anda punya ritme.\n\nMinggu ini udara luar terburuk sekitar pukul {worst_hr}:00 dan terbersih sekitar pukul {best_hr}:00. Jalan paling ramai sekitar pukul {quiet_hr}:00, dan itu bukan saat udaranya terburuk — jadi puncak sore itu bukan lalu lintas. Ada yang dibakar setelah gelap.\n\n👉 Kalau ingin membuka rumah, pukul {best_hr}:00 waktunya."
```

Every interpolated column (`worst_hr`, `best_hr`, `quiet_hr`) is returned by the SQL. `worst_v` is returned and not
used, which `make lint` allows; keep it, the dashboard reads it.

**A node with no noise sensor gets no `rhythm` alert at all**, because `loud` is empty and the cross join yields
nothing. That is deliberate: the old message asserted a cause with no evidence, and no message is better than a
wrong one. Say it in the README.

- [ ] **Step 4: Correct the pack README**

In `packs/insight/README.md`, rewrite the `rhythm` bullet and the **Where the numbers came from** paragraph. It
must record: the noise anti-correlation (r = −0.24), the hour-of-day figures, that the pooled indoor/outdoor
average in the older numbers is why r = 0.55 there and r = 0.20 pairwise, and that `rhythm` now needs a local
outdoor noise sensor and stays silent without one. Do not delete the old numbers — date them and say what replaced
them.

- [ ] **Step 5: Lint, test, commit**

```bash
make lint && make test
git add packs/insight/rules.yml packs/insight/README.md tests/test_shipped.py
git commit -m "fix: rhythm stops blaming traffic for an evening peak the noise channel rules out

r(pm25, noise) = -0.24 at node #1: the loud hours are the clean hours, and PM peaks at 18:00 as noise falls. The
rule now reads the noise it was discarding, prefers local outdoor sensors, and says nothing without one."
```

---

## Task 8: the dashboard shows what the node doubts

**Why.** L3 of the spec: the storyteller must be able to say it does not know. Three alerts exist now and nowhere
on the node's own surface says "this sensor is at 45% of the week".

**Files:**
- Modify: `app/agent.py` (`health_check`), `app/static/index.html` (one card)
- Test: `tests/test_shipped.py`

- [ ] **Step 1: Extend `health_check()` with quiet channels**

`app/agent.py`'s `health_check()` already reports quiet radios from `/stats`. Add one check beside it, following
the same `chk(name, ok, fix)` shape: every local sensor has at least one ambient channel that changed in the last
six hours. Read `/stats` as the existing check does; do not add an endpoint.

The `fix` string must say what it means and what to do, in the voice the LoRa check already uses: which sensor,
that its kit still reports, and that any figure including it is about the hours it was awake.

- [ ] **Step 2: Add the card**

`app/static/index.html`, one file, cards by `data-card`. Add `data-card="trust"` in the **room** band: one line per
local sensor with its 7-day coverage and the count of frozen channels. Empty state when every sensor is above the
floor: "Every sensor reported all week." Never render an empty box — `docs/archive/reviews/BETA_READINESS_2026-09.md`
records that bug in the act strip.

The card needs coverage per sensor, which no endpoint returns. Add it to the existing `/stats` rows as
`coverage_7d` rather than adding an endpoint: one more expression in the `stats` view in `init.sql`, or computed in
the `/stats` route. Prefer the route — the `stats` view is 24-hour rolling by design and a 7-day column does not
belong in it.

- [ ] **Step 3: Measure the card at three widths**

375, 768 and 1440 px. No horizontal overflow, the numbers legible, the empty state correct. `tools/check_ui.py`
must pass: it checks that every id, endpoint and field the script references resolves.

- [ ] **Step 4: Pin it**

Append to `tests/test_shipped.py`:

```python
assert 'data-card="trust"' in _gui, "the node shows what it doubts about its own sensors"
assert "Every sensor reported all week" in _gui, "the trust card needs an empty state, not an empty box"
```

- [ ] **Step 5: Lint, test, commit**

```bash
make lint && make test
git add app/agent.py app/static/index.html app/main.py tests/test_shipped.py
git commit -m "feat: a trust card and a quiet-channel health check, so coverage is visible before it misleads"
```

---

## Task 9: documentation, CHANGELOG, release

**Files:**
- Modify: `docs/sensors.md`, `docs/DOMAINS.md`, `docs/COVERAGE.md`, `CHANGELOG.md`, `README.md`

- [ ] **Step 1: `docs/sensors.md` — the rules we inherit**

Rule 2 currently reads *"Latest held ≠ latest measured. A dead sensor still has a 'latest'. `stats` looks back 24 h
and exposes `silent_minutes`."* That is true per kit and false per channel. Rewrite it to say silence is defined by
value change, name Smart Citizen's null `recorded_at` as the case that forced it, and point at `packs/trust`.

Add a rule 8: **Sensors in the same place disagree.** Three kits at one address, one reading 1.5× the others.
Collocation is the cheapest calibration a node can run and most nodes have it by accident.

- [ ] **Step 2: `docs/DOMAINS.md` and `docs/COVERAGE.md`**

`DOMAINS.md`: `trust` in the **Running** paragraph, one clause.
`COVERAGE.md`: the *Filled today, node #1* table is now wrong for node #1 — `Environmental|Community` was the three
indoor kits and is now the two outdoor kits at the node's site, and `Social|Community` has no local indoor sensor.
Correct the table against `/cells` on node #1 after the release, not before, and say when it was read.

- [ ] **Step 3: The CHANGELOG entry for testers**

Follow the shape of the v0.32.1 and v0.34 entries. It must tell a tester, in plain sentences, five things:

1. `local` now means ours **and** within `LOCAL_RADIUS_M` (500 m). On a node whose sensors are not all at one
   address, some sensors will stop being local, and rules and cells that read local sensors will change value or go
   quiet. That is a correction, not a regression.
2. Node #1 specifically: it has no local indoor sensor at Ungasan, so the heat rules, the indoor air rules and the
   `Social|Community` cell are quiet until an indoor kit is installed there.
3. The 35 °C heat line was measured on two indoor kits at the old site. It holds for indoor sensors. It has not
   been measured for Ungasan.
4. `aqi` from Smart Citizen kits is now `bme_iaq`. Old `aqi` rows stay as history; nothing reads them.
5. The new `trust` pack, off nothing and needing no configuration, and the three things it will tell them.

- [ ] **Step 4: Break each new gate on purpose**

Every gate is a bug that shipped. For each one added in this plan — the `local=EXCLUDED.local` assertion, the
`channels.yml` metric check, the trust-pack pins, the `rhythm` traffic assertion — break the thing it guards, run
`make lint && make test`, and watch it fail with a message that names the problem. Then put it back. Record in the
commit that you did.

- [ ] **Step 5: Release**

```bash
make lint && make test
git add -A && git commit -m "docs: v0.35 — trust layer, local by distance, channel roles"
```

Then, from the main checkout with the branch merged and the tree clean:

```bash
tools/release.sh 0.35
```

`tools/release.sh` requires a clean tree, a CHANGELOG section, green gates, and it tags, pushes `main` and rebuilds
the site tarball. **Deploying the site is Tomas's** — do not run `make deploy`.

- [ ] **Step 6: Verify on a node that never had any of this**

`pai-clean` (Lima, `limactl list`) from `main`: `planetai update`, then confirm the trust card shows its empty
state, `planetai packs` lists `trust`, `/cells` still answers, and a node with one sensor and no collocation gets no
`peer_disagreement`. A fresh node must not be told its instruments are broken because it only has one.

---

## Out of scope, and why

| thing | why not now |
|---|---|
| `fleet_reference` and repointing `Environmental|Community` | It changes a published Index number. Own release, own CHANGELOG note, after the trust layer can say what to leave out. |
| `source_signature` (event attribution) | Needs the trust layer under it, and a burn season to test against. |
| Per-sensor role overrides | `channel_roles` is keyed on `(source, metric)`. The mesh gateway's BME680 is `enclosure` for every Meshtastic node, which is right today. When a pod is genuinely ambient, add `MESH_AMBIENT_NODES` beside the existing `MESH_INDOOR_NODES`. One consumer, no framework. |
| Mapping `PN0.5`–`PN10.0`, `Typical Particle Size`, `PM4.0` | Measured redundant: r(PM2.5, PN0.5) = 0.999, and typical particle size is flat (range 40.4–52.1, r = −0.11 against PM2.5). Five more columns, no knowledge. |
| A humidity correction for Smart Citizen | r(PM2.5, RH) is 0.05–0.32 across the fleet. The inter-unit scale factor is about five times larger. Revisit at 40–60 µg/m³. |
| Per-channel timestamps from Smart Citizen | The API gives none: `data.recorded_at` is null on all six kits and there is no per-sensor time field. Value-change silence is the fix that does not need upstream to change. |
| Two-site support (`site` alongside `local`) | Tomas ruled node #1 single-site at Ungasan. `LOCAL_RADIUS_M` covers a campus. Revisit when a node genuinely operates two addresses. |

## Self-review notes

- **Spec coverage.** §3 L0 → Tasks 1, 2, 5, 6. §3 L3 → Tasks 7, 8. §4 → Task 5. §6 step 1 → done in exploration
  and re-run in Task 6 step 7. §6 steps 2, 3, 5, 6 → Tasks 2, 6, 7, 5. §6 step 4 (move the 19849 unit) is physical
  and is now the `peer_disagreement` message's own instruction. §6 step 7 and §3 L1 `fleet_reference` are out of
  scope above. §5 (satellite joins) is untouched by this release.
- **Names used consistently.** `sources.metres`, `sources.stamp_local`, `packs.channels`, `packs.ROLES`,
  `channel_roles`, `LOCAL_RADIUS_M`, `channel_dead`, `coverage_low`, `peer_disagreement` — each defined once, in
  the task that creates it, and referenced by the same name everywhere after.
- **Known soft spots, flagged rather than hidden.** Task 6 step 6 anticipates sqlglot rejecting
  `percentile_cont … WITHIN GROUP` and says what to do. Task 8 step 2 leaves the choice of where `coverage_7d` is
  computed to the implementer with a stated preference, because the `/stats` route was not read closely enough
  during planning to write the diff. Task 5 step 2 requires verifying every `(source, metric)` pair against the
  adapters before the file is trusted.
