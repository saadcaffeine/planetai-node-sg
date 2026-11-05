# Place microGIS, steps 1 and 2: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Place becomes the McHarg layer cake with a black map screen and a tool column (spec step 1), and every
tool becomes a command in one registry that the panel and the Ask agent both call (spec step 2).

**Architecture:** Two pull requests. **Part A** redraws the Place door from data the node already serves: a new pure
helper file `doors-cake.js` orders the layers into the cake, `doors-placemap.js` draws the cake column and the
screen, `doors-place.js` draws the header, tool column and lower band. **Part B** adds `app/place_tools.py` (the
registry and the look tools), two token-only routes in `app/geo.py`, two MCP tools in `app/agent.py`, and wires the
page's tool column to the registry. Spec steps 3 to 9 get their own plans when their inputs exist.

**Tech Stack:** FastAPI + PostGIS (Python 3.11), no-build-step browser JS, MapLibre 5.24.0 UMD + deck.gl (vendored),
h3 (already in `app/requirements.txt`), plain `assert`/`check()` suites run by `bash tests/all`.

**Spec:** `docs/SPEC_place_microgis.md`. Read §4, §5, §6 and §8 before any task.

## Global Constraints

- No new dependency: no Python package, no JS library, no build step (spec §2).
- The node computes, the page draws: no H3 and no distance computed in the page (spec §2 anti-goals, R40).
- Nothing from inside the house on Place: a sensor with `indoor: true` is never drawn, listed or labelled there (spec §1, §8).
- Token-only: `/place/tools`, `/place/run/*` and `/place/runs` go on no SHARE_LEVEL allowlist, like `/place/geojson` (spec §6, §8).
- The screen is black in both registers: the map draws with `PAL.dark` whatever the page register (spec §4, Tomas 4 Nov 2026).
- Provenance words are the existing five: `live`, `partial`, `model`, `cached`, `example` (`doors-core.js` PROV).
- Map tools stay 44 px (spec §4, node rule).
- The frozen layer's three copies are not edited here. The black-screen rule is a line in `../planetai-design/decisions/design-log.md` (spec §4).
- Every new suite gets its line in `tests/all` and the expected count there goes up by one (`tests/all:202-207`, now 105).
- Ship Part B from a branch cut from main **after** Part A merges. Never stack it on Part A's branch: a stacked PR merges into its base, not into main.
- Gate every push on an open PR: `[ "$(gh pr view --json state -q .state)" = OPEN ] && git push`.
- Node #1 runs each part on its branch for a real cycle before merge. Never pipe `planetai update` into `grep`. A branch update can rewrite `PACKS_ENABLED`, so check it after switching.
- Copy on the page and in docs is plain, first-hand and short. It never explains McHarg (spec §10).

## Review Focus

1. **A screen without a token:** the cake shows its rows with sources and counts, the screen says what it is not drawing and why, and the tool column says "token-only". Nothing 403s visibly. Test in Task 2 and Task 7.
2. **A fresh node with no place pack and no basemap:** every cake row it cannot fill reads "not yet", the screen shows its offline line, and the console shows no error. Test in Task 1 (rows) and Task 2 (offline).
3. **Phone width, 390 px:** no horizontal overflow, the cake and tools sit in a sheet under the screen, and targets are 44 px. Checked by the visual gate in Task 3.
4. **Bad tool arguments:** a path of one point, 201 points, a latitude of 95 or an unknown tool id give a 422 or 404 with the reason, shown beside the tool. The page does not break. Test in Task 4 and Task 5.
5. **An unwritable or corrupt run log:** a run still answers, the log line is skipped with a warning, and `/place/runs` returns what it can read. Test in Task 5.

---

## Part A: the page (spec step 1)

Branch: `place-page-2026-11-04` from `origin/main`.

### Task 1: The cake, as pure functions

**Files:**
- Create: `app/static/doors-cake.js`
- Modify: `app/main.py` (`COMPANIONS`, ~line 1891: add `"doors-cake.js"`), `app/static/doors.html` (a `<script src="/static/doors-cake.js">` before `doors-placemap.js`, ~line 944)
- Test: `tests/test_doors.py` (append before its final `sys.exit`, see memory: tests after `sys.exit` never run)

**Interfaces:**
- Produces, on `window` and on `module.exports` when `module` exists:
  - `CAKE`: array, screen order top to bottom, each `{id, name, classes, ceiling}`. The ids, names, flows classes and ceilings are exactly spec §5's table: `results`, `microclimate` (`['electricity']`, `'climate'`), `flows` (`['*']`, `'each class'`), `built` (`[]`, `'materials'`), `animals` (`['animal']`, `'biosphere'`), `plants` (`['plant','habitat']`, `'biosphere, land system'`), `soil` (`['compost']`, `'biogeochemical'`), `water` (`['water']`, `'freshwater'`), `ground` (`[]`, `'land system'`), `frame` (`[]`, `null`). Lowercase names as on the v2 mockup.
  - `cakeSections(layers: Layer[], on: {[id]: bool}) -> Section[]`: one `Section` per `CAKE` entry, in `CAKE` order, `{id, name, classes, ceiling, rows: [{id, name, sub, state}]}`. `state` is `'on'` | `'off'` | `'soon'` (a layer with `soon: true`). A section with no rows is kept, and its rows are `[]`.
  - `outside(sensors: Sensor[]) -> Sensor[]`: the sensors with `indoor` not `true`.
- `Layer` is `doors-placemap.js`'s LAYERS entry, which gains `cake: <CAKE id>` in Task 2.

- [ ] **Step 1: Write the failing test** (in `tests/test_doors.py`, run through `node -e`, as the file already runs `buildD`)

```python
cake = subprocess.run(["node", "-e", """
const K = require('./app/static/doors-cake.js');
const L = [{id:'own', cake:'microclimate', name:'Outdoor kit'}, {id:'soil1', cake:'soil', name:'SoilGrids', soon:true},
           {id:'street', cake:'frame', name:'Street map'}];
console.log(JSON.stringify({ids: K.CAKE.map(s => s.id), secs: K.cakeSections(L, {own:true, street:false}),
  out: K.outside([{sensor_id:'a', indoor:true}, {sensor_id:'b', indoor:false}, {sensor_id:'c'}]).map(s => s.sensor_id)}));
"""], capture_output=True, text=True, check=True)
C = json.loads(cake.stdout)
assert C["ids"] == ["results", "microclimate", "flows", "built", "animals", "plants", "soil", "water", "ground", "frame"], C["ids"]
sec = {s["id"]: s for s in C["secs"]}
assert [r["state"] for r in sec["microclimate"]["rows"]] == ["on"]
assert [r["state"] for r in sec["soil"]["rows"]] == ["soon"]
assert [r["state"] for r in sec["frame"]["rows"]] == ["off"]
assert sec["water"]["rows"] == [] and sec["water"]["classes"] == ["water"] and sec["water"]["ceiling"] == "freshwater"
assert C["out"] == ["b", "c"], C["out"]
print("  place: the cake in McHarg's order, sky first; nothing indoor")
```

- [ ] **Step 2: Run it and see it fail**

Run: `python3 tests/test_doors.py`
Expected: FAIL, `Cannot find module './app/static/doors-cake.js'`.

- [ ] **Step 3: Write `doors-cake.js`** with the three exports above. Keep it pure (no DOM, no `D`), with `'use strict'` and the file's opening comment in the house style naming SPEC_place_microgis §5. Add it to `COMPANIONS` and to `doors.html`.

- [ ] **Step 4: Run it and see it pass**

Run: `python3 tests/test_doors.py`
Expected: PASS, including the existing check that every file `doors.html` names is in `COMPANIONS`.

- [ ] **Step 5: Commit**

```bash
git add app/static/doors-cake.js app/main.py app/static/doors.html tests/test_doors.py
git commit -m "Place: the cake as pure functions, in McHarg's order, and nothing indoor"
```

### Task 2: The Place door redrawn

**Files:**
- Modify: `app/static/doors-placemap.js`: LAYERS (lines 47-71), `marks()` (351-363), `panel()` (421-~440), `P()` (32)
- Modify: `app/static/doors-place.js`: `VIEWS.place`, `PVIEWS`, `layer()`, `reach()` call
- Modify: `app/static/doors.html`: Place section (845-861) and its CSS (259-~300)
- Modify: `app/static/learn.json`: entries and order list for `place-layers`, `place-tools`, `place-orbit`, `place-reach`, `place-changed`
- Test: `tests/test_doors.py`

**Interfaces:**
- Consumes: `CAKE`, `cakeSections`, `outside` (Task 1).
- Produces: DOM ids `#cake` (the left column), `#ptools` (the right column), `#ptable` (lower band, left), `#pfigures` (lower band, right), `#pask` (the header's Ask line). Task 7 fills `#ptools` and `#ptable`.

- [ ] **Step 1: Write the failing tests** (`tests/test_doors.py`)

```python
pm = (STATIC / "doors-placemap.js").read_text(); pl = (STATIC / "doors-place.js").read_text()
assert "const P = () => PAL.dark" in pm, "the screen is black in both registers (SPEC_place_microgis §4)"
assert "outside(D.sensors)" in pm and "D.sensors.filter(s => s.lat != null)" not in pm, "Place draws no indoor sensor"
assert all("cake:" in l for l in re.findall(r"\{ id: '[a-z]+'.*?\}", pm.split("const LAYERS = [")[1].split("];")[0])), "every layer names its cake section"
assert "PVIEWS" not in pl and 'class="pviews"' not in html, "one map: From orbit and What changed are no longer views"
for i in ("cake", "ptools", "ptable", "pfigures", "pask"):
    assert f'id="{i}"' in html, i
assert "Where the readings come from" not in html, "each cake row names its source instead"
assert "Tools run on this node with a token. Unlock this screen in Set up." in pl, "a tokenless screen says why the tools are quiet"
print("  place: one map, black screen, the cake on the left, tools on the right")
```

- [ ] **Step 2: Run them and see them fail**

Run: `python3 tests/test_doors.py` — Expected: FAIL on the first new assertion.

- [ ] **Step 3: Give every LAYERS entry `cake:` and add the not-yet rows.**
  Map the existing layers this way: `street`, `imagery`, `drone`, `grid`, `mine`, `rings`, `peers`, `images` → `frame`; `own`, `public`, `models`, `wind` → `microclimate`; `labs` → `flows`; `radio`, `satonly` → `built`; `species` → `animals`; `earth` → `plants`. Remove `index`, which moves to the lower band's figures. Add these rows with `soon: true, empty: true`, each with `sub` naming its source exactly as spec §5 does: flows log (`flows`), canopy Meta/WRI 1 m (`plants`), SoilGrids 2.0 250 m (`soil`), soil samples (`soil`), where the rain goes (`water`), water samples (`water`), terrain GLO-30 (`ground`), geology (`ground`). Delete `group:` everywhere.

- [ ] **Step 4: Redraw the panel as the cake.** `panel()` renders `cakeSections(LAYERS, PM.on)` into `#cake`. Each section is a heading (name, then "n of m" on the right). Each row is a `<button class="ly" aria-pressed>` with the dot (`on` filled with a ring, `off` hollow, `soon` dotted and disabled), the name and the `sub`. Keep the wind hour slider and the opacity slider under their rows, as now. Drop the group tab strip and its `#lydrop`.

- [ ] **Step 5: Black screen and outside-only marks.** Set `const P = () => PAL.dark;`. In `marks()`, build `st` from `outside(D.sensors).filter(s => s.lat != null)`.

- [ ] **Step 6: Redraw the door.** In `doors.html`, replace the Place section's children with the v2 anatomy: `#placehead` (title "The ground around the house", the cell line, `#pask`, an underlined input that opens the existing Ask pane with its text), then `.bench` holding `#cake` | the existing `.mapc` | `#ptools`, then `.plow` holding `#ptable` | `#pfigures`. Keep `.altc` and `#mapalt` only as the satellite year compare drawn on the screen when the `imagery` row is on. Move the yearly issues (`yearly()`) and the Index cells into `#pfigures`. The species table moves under the `species` row and opens from it. In `doors-place.js`, remove `PVIEWS`, `PVIEW`, the views nav and the `reach()` block. `#ptools` lists today's tools: Rings and distance (it toggles the `rings` layer), and the spec §6 analyses and fitness tools each with a dotted "not yet" pill. Its tokenless line reads "Tools run on this node with a token. Unlock this screen in Set up."
  The header keeps "+ Add an image" as it is: "+ Add an observation" is spec step 4.
  CSS: the v2 tokens and controls, from `.superpowers/brainstorm/7690-1793751265/content/place-v2.html` in the FAB CITY folder. Use the frozen layer's variables (`--ink`, `--ground`, `--cells`, `--mono`) and no raw hex outside the screen. The screen gets the bezel `box-shadow: 0 0 0 1px #000, 0 0 0 5px #1b1b1b, 0 0 0 6px #000` and `border-radius: 10px`. At width 760 px and under, `.bench` becomes one column: the screen first, then the cake and the tools in a sheet under it, each a disclosure that opens over the lower band.

- [ ] **Step 7: learn.json.** Rewrite `place-layers` to describe the cake ("what this place is made of, from the sky to the ground, and what the node does not hold yet"). Rewrite `place-tools` for the tool column. Delete `place-orbit`, `place-reach` and `place-changed` from the entries and the order list, unless a remaining `data-learn` still names one.

- [ ] **Step 8: Run the tests**

Run: `python3 tests/test_doors.py && python3 tests/test_learn.py`
Expected: both PASS.

- [ ] **Step 9: Commit**

```bash
git add app/static/doors-placemap.js app/static/doors-place.js app/static/doors.html app/static/learn.json tests/test_doors.py
git commit -m "Place: the layer cake on the left, a black screen, tools on the right; rooms leave Place"
```

### Task 3: Visible, documented, measured, proven

**Files:**
- Modify: `docs/site/dashboard.md` (`## Place`, line 140), `CHANGELOG.md` (`## Unreleased`), `tests/visual/measure.mjs` (only selectors that named removed Place elements)
- Modify (other repo): `../planetai-design/decisions/design-log.md`

- [ ] **Step 1: Docs.** Rewrite `## Place` in `docs/site/dashboard.md` to describe what a person sees: the cake and its order, the dots, the black screen, the tool column, the lower band, and what a screen without a token sees. Do not explain McHarg. Add one `## Unreleased` bullet to `CHANGELOG.md`.
- [ ] **Step 2: Design log.** Append one line to `../planetai-design/decisions/design-log.md`: "R44, 4 Nov 2026: the map screen is black on both registers (Place microGIS, SPEC_place_microgis §4); controls: OP-XY dots for layers, pill for the chosen tool, provenance by stroke." Commit it in that repo on its own branch, and open its PR with the node PR's link.
- [ ] **Step 3: Lint and the full suite**

Run: `make lint && bash tests/all`
Expected: lint clean; `105 suites: 105 passed, 0 failed`. If lint flags a docs page "checked against" an older release, follow `skills/release-docs/SKILL.md` for that page only.

- [ ] **Step 4: The visual gate, locally**

Run: `PAI_OUT="$(mktemp -d)" bash tests/visual/gate.sh`
Expected: green at 1440 and 390, with no page overflow. Fix any selector in `measure.mjs` that named a removed element. Look at the Place shots yourself, because the gate checks only page-level overflow.

- [ ] **Step 5: Node #1.** Open the PR and gate the push on its state. Wait for CI to go green. Then on node #1 (`ssh mini`, checkout `~/planetai/planetai-node`): `git fetch && git checkout place-page-2026-11-04 && planetai update > /tmp/upd.log 2>&1`. Confirm the schema step landed in the log and `PACKS_ENABLED` is unchanged. Open Place with the token at 1440 and 390, check no room appears anywhere on it, then let a full poll cycle run. Afterwards switch node #1 back to `main`.
- [ ] **Step 6: Commit docs**

```bash
git add docs/site/dashboard.md CHANGELOG.md tests/visual/measure.mjs
git commit -m "docs: Place as the layer cake; changelog"
```

---

## Part B: tools are commands (spec step 2)

Branch: `place-tools-2026-11-xx`, cut from `origin/main` after Part A merges.

### Task 4: The registry and the look tools

**Files:**
- Create: `app/place_tools.py`
- Modify: `app/issues/geometry.py` (add `area`)
- Create: `tests/test_place_tools.py`; Modify: `tests/all` (add the suite line, expected count 105 → 106, and the comment's list; add `test_place_tools` to the allowed skips with "needs app/requirements.txt installed (h3)")

**Interfaces:**
- Produces:
  - `geometry.area(ring: list[tuple[float, float]]) -> float`: square metres of a closed lon,lat ring on the sphere (R = 6371008.8 m), ring auto-closed, 3 to 200 points.
  - `place_tools.describe() -> list[dict]`: each `{id, name, kind, reads, args, can_run}`. `kind` is one of `look`, `interaction`, `fitness`. `args` is a JSON Schema object.
  - `place_tools.run(tool_id: str, args: dict, lat: float, lon: float) -> dict`: returns `{id, args, features, figures, word, inputs, as_of}`. `features` is a GeoJSON FeatureCollection. `figures` is a list of `{name, value, unit}`. `inputs` is a list of `{layer, word}`. `word` is the weakest input word in the order `live` > `partial` > `cached` > `model`, or `None` when `inputs` is empty. It raises `KeyError(tool_id)` for an unknown id and `ValueError(reason)` for bad args.
  - The first tools, all `kind: "look"`, `inputs: []`, `word: None`:
    - `geo.select {lat, lon, res}`: the cell's facts from `geometry.cell`, as figures (area, edge, cells from the node) plus its ring as a feature.
    - `geo.measure {path: [[lon, lat], ...]}`: from `geometry.measure`. Figures: `{name: "total", value: <m>, unit: "m"}`, then one `{name: "leg <n>", ...}` per leg. Feature: the path as a LineString.
    - `geo.rings {km: [..]}`: from `geometry.rings`, with the same bounds as `/geo/rings`.
    - `geo.area {ring: [[lon, lat], ...]}`: from `geometry.area`.
  - The analysis and fitness ids from spec §6 are listed with `can_run: false`. `run` on one of them raises `ValueError("not yet on this node")`.

- [ ] **Step 1: Write the failing tests** (`tests/test_place_tools.py`, the repo's `check()` style, ending in `sys.exit`)

```python
import place_tools as T
from issues import geometry as G
ids = [t["id"] for t in T.describe()]
check(ids[:4] == ["geo.select", "geo.measure", "geo.rings", "geo.area"], ids)
check({"place.sun", "place.sealed", "fit.roof", "fit.rain"} <= set(ids), "spec §6's tools are listed")
check(all(t["can_run"] is False for t in T.describe() if t["kind"] != "look"), "only the look tools run in step 2")
r = T.run("geo.measure", {"path": [[115.17, -8.818], [115.18, -8.818]]}, -8.818, 115.171)
check(set(r) == {"id", "args", "features", "figures", "word", "inputs", "as_of"} and r["word"] is None and r["inputs"] == [], r)
check(1090 < next(f["value"] for f in r["figures"] if f["name"] == "total") < 1110, "about 1.1 km along the equator-ish line")
sq = [[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001]]
check(abs(G.area(sq) - 12364) < 60, G.area(sq))              # 0.001° square at the equator ≈ 111.2 m × 111.2 m
for bad in ({"path": [[1, 2]]}, {"path": [[0, 0]] * 201}, {"path": [[0, 95], [0, 0]]}):
    try: T.run("geo.measure", bad, 0, 0); check(False, bad)
    except ValueError: pass
try: T.run("nope", {}, 0, 0); check(False, "unknown id")
except KeyError: pass
try: T.run("place.sun", {}, 0, 0); check(False, "place.sun ran")
except ValueError as e: check("not yet" in str(e), str(e))
```

- [ ] **Step 2: Run it and see it fail**

Run: `python3 tests/test_place_tools.py` — Expected: FAIL, `No module named 'place_tools'`.

- [ ] **Step 3: Implement `geometry.area` and `place_tools.py`.** Each tool is a plain dict in a list `TOOLS`, with `run` a function taking `(args, lat, lon)`. Validate the args by hand, with no jsonschema. Reuse the bounds `/geo/measure` and `/geo/rings` already enforce.
- [ ] **Step 4: Run it and see it pass**

Run: `python3 tests/test_place_tools.py && bash tests/all`
Expected: PASS; `106 suites: 106 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/place_tools.py app/issues/geometry.py tests/test_place_tools.py tests/all
git commit -m "place tools: one registry, the four look tools, the rest listed as not yet"
```

### Task 5: The routes and the run log

**Files:**
- Modify: `app/geo.py` (three routes)
- Test: `tests/test_share.py` (the `/geo/*` block, ~line 435), `tests/test_place_tools.py`

**Interfaces:**
- Consumes: `place_tools.describe`, `place_tools.run` (Task 4).
- Produces:
  - `GET /place/tools` → `describe()`.
  - `POST /place/run/{tool_id}` with a JSON body of args → `run(...)` at the node's point, 404 for an unknown id, 422 with the reason for bad args. When the request carries no `X-Agent` header, it appends one JSON line `{at, id, args, figures, word}` (no features) to `OUT / "place_tool_runs.jsonl"`, keeping the newest 200.
  - `GET /place/runs?limit=20` → the newest runs first, skipping unreadable lines.
  - A log write that fails (read-only, missing dir) logs one warning and the run still answers.

- [ ] **Step 1: Write the failing tests.** In `tests/test_share.py`'s `/geo` block, assert `lan.get("/place/tools").status_code == 403`, `lan.post("/place/run/geo.measure", json={...}).status_code == 403` and `lan.get("/place/runs").status_code == 403`. Assert `local` gets 200 on all three, 404 for `/place/run/nope`, and 422 for a one-point path. In `tests/test_place_tools.py`, with `PACK_OUT` set to a temp dir, use a `local` TestClient built the way `test_share.py` builds it:
  - a person's run adds one line, and `GET /place/runs` returns it first
  - a run with header `X-Agent: agent` adds no line
  - with the log path made a directory (unwritable as a file), the run still returns 200
  - a log holding one corrupt line still lists the good ones
- [ ] **Step 2: Run them and see them fail**

Run: `python3 tests/test_share.py; python3 tests/test_place_tools.py` — Expected: FAIL (404 on the new routes).

- [ ] **Step 3: Implement the three routes** in `app/geo.py`, beside `/geo/*`, using `_here()` for the point. Keep them off `_SHARE_OPEN`.
- [ ] **Step 4: Run them and see them pass**

Run: `python3 tests/test_share.py && python3 tests/test_place_tools.py && bash tests/all` — Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/geo.py tests/test_share.py tests/test_place_tools.py
git commit -m "place tools: GET /place/tools, POST /place/run/<id>, the run log of what a person pressed"
```

### Task 6: The Ask agent calls the same tools

**Files:**
- Modify: `app/agent.py` (two `@mcp.tool()`), `app/tool_classes.py` (`TOOL_CLASS`), `app/ask.py` (`HOUSE_TOOLS`, line 417)
- Modify: `docs/site/mcp.md`, `docs/site/ask.md` (the tool lists)
- Test: `tests/test_ask.py` (the `learned` block, ~line 585)

**Interfaces:**
- Produces MCP tools:
  - `place_tools() -> list`: `GET /place/tools` with `_admin_headers("agent")`.
  - `place_run(tool: str, args: dict) -> dict`: `POST /place/run/{tool}` with `_admin_headers("agent")`, which carry `X-Agent`, so the run is not logged. It returns the answer **without `features`**, and maps 404/422 to `{"error": detail}`.
  - Both `"read"` in `TOOL_CLASS`; both in `ask.HOUSE_TOOLS`, so a tokenless screen and the Wall never get them.

- [ ] **Step 1: Write the failing tests** (`tests/test_ask.py`, beside the `learned` checks)

```python
_listed2 = [_NS(name=n, description="", input_schema=None) for n in ("learned", "issues", "place_tools", "place_run")]
_names2 = lambda house: {t["function"]["name"] for t in ask.menu(_listed2, house)}  # noqa: E731
check(_names2(False) == {"issues"}, "no place tool for a screen without the household's token")
check({"place_tools", "place_run"} <= _names2(True), "the household's pane runs place tools")
check(TOOL_CLASS["place_tools"] == TOOL_CLASS["place_run"] == "read", "place tools change nothing")
```

  Add a check that `agent.place_run` drops `features`: monkeypatch `agent.httpx.post` to return a response with `{"features": {...}, "figures": [...]}` and assert `"features" not in agent.place_run("geo.measure", {...})`. Assert the call's headers carry `X-Agent`.
- [ ] **Step 2: Run them and see them fail** — Run: `python3 tests/test_ask.py` — Expected: FAIL (`KeyError: 'place_tools'`).
- [ ] **Step 3: Implement** the two tools, the two `TOOL_CLASS` entries and the `HOUSE_TOOLS` entries. Write both docstrings the way the existing tools are written. `place_run`'s docstring says that results are figures and words, and that the page draws the shapes.
- [ ] **Step 4: Docs.** Add both tools to the tool tables in `docs/site/mcp.md` and `docs/site/ask.md`.
- [ ] **Step 5: Run** `python3 tests/test_ask.py && make lint && bash tests/all` — Expected: all PASS, lint clean.
- [ ] **Step 6: Commit**

```bash
git add app/agent.py app/tool_classes.py app/ask.py docs/site/mcp.md docs/site/ask.md tests/test_ask.py
git commit -m "Ask: the household's pane calls the place tools; figures only, nothing logged, never tokenless"
```

### Task 7: The tool column runs the registry

**Files:**
- Modify: `app/static/doors-place.js` (`#ptools`, `#ptable`), `app/static/doors-placemap.js` (a `result` deck.gl layer and the `results` cake rows)
- Modify: `docs/site/dashboard.md` (`## Place`), `CHANGELOG.md`
- Test: `tests/test_doors.py`

**Interfaces:**
- Consumes: `GET /place/tools`, `POST /place/run/{id}`, `GET /place/runs` (Task 5); `#ptools`, `#ptable` (Task 2).
- Produces: `PM.result` (the last answer) drawn as a deck.gl GeoJsonLayer in `--cells` blue for selection. It lands as a `results` cake row with a clear button.

- [ ] **Step 1: Write the failing tests** (string checks in `tests/test_doors.py`):
  - `doors-place.js` fetches `/place/tools` and posts to `/place/run/`
  - it prints the command as `${id} ${JSON.stringify(args)}`
  - it reads `/place/runs`
  - `doors-load.js`'s `DOORS_LOCKED` matches `/place/tools`, `/place/run/geo.measure` and `/place/runs`, so a tokenless screen never asks. Run the regex in `node -e`, as Task 1 does.
- [ ] **Step 2: Run** `python3 tests/test_doors.py` — Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `#ptools` lists `describe()`: tools with `can_run` as plain rows with their id in mono, the rest with the dotted "not yet" pill.
  - The chosen tool opens its settings, drawn from its `args` schema: enums as pills, numbers in mono. The on-map tools fill `path`, `ring` and `lat/lon` from clicks, as measure does today.
  - Run is a pill with ↵, and Clear is a text link.
  - Under the settings sits the printed command, then the 5 newest runs from `/place/runs`.
  - A 422 shows its `detail` beside the tool.
  - `#ptable` lists the answer's `figures`, plus `word` as a provenance pill when it is not null.
  - In `DOORS_LOCKED`, replace `place\/geojson` with `place\/(geojson|tools|runs?)`.
- [ ] **Step 4: Run** `python3 tests/test_doors.py && bash tests/all`, then `PAI_OUT="$(mktemp -d)" bash tests/visual/gate.sh` — Expected: all PASS and the gate green.
- [ ] **Step 5: Docs.** Add the tool column and the printed command to `## Place`, and one CHANGELOG bullet.
- [ ] **Step 6: Commit**

```bash
git add app/static/doors-place.js app/static/doors-placemap.js app/static/doors-load.js docs/site/dashboard.md CHANGELOG.md tests/test_doors.py
git commit -m "Place: the tool column runs the registry; every run printed as the agent's call"
```

### Task 8: Node #1, with a local model

- [ ] **Step 1: A local model on node #1** (Tomas agreed on 4 Nov 2026). On `ssh mini`, run `planetai agent local`, read its recommendation for the machine's memory, and pull exactly that tag, expected `qwen3.5:4b` on 8 GB: `planetai agent local pull <tag>`. Confirm `AGENT_MODEL` now names it, and that the Ask pane answers a plain question with the token held.
- [ ] **Step 2: The branch on node #1.** Do this once CI is green on the PR, with the push gated on its state: `git fetch && git checkout place-tools-2026-11-xx && planetai update > /tmp/upd.log 2>&1`. Check the log shows the schema step, and check `PACKS_ENABLED`.
- [ ] **Step 3: A real cycle.** With the token, at 1440:
  - run `geo.measure` from the house to a public station and confirm the figure matches the station's distance in the cake row
  - in the Ask pane, ask "how far is the nearest public station from the house?" and confirm the pane called `place_run` and answered with the figure, with no coordinates in its text
  - confirm `/place/runs` lists the first run and not the agent's

  Let a full poll cycle pass.
- [ ] **Step 4: Back to main** on node #1 after merge (`git checkout main && planetai update > /tmp/upd.log 2>&1`), and delete the branch there.
