# Handoff: the node knows its issues (Release 1 of prompt 5b)

11 September 2026. Branch `the-node-knows-its-issues`, six commits from `main` at `9ff1668` (v0.43.1).
Nothing on any screen has changed. Release 2 — the dashboard as a modular renderer — is a fresh
session and starts from this file.

Written against `PLANETAI_Dashboard_Review_and_Redesign_2026-09-10.md` and the prototype at
`planetai-design/prototypes/dashboard-issues/index.html`.

## What shipped

| commit | what |
|---|---|
| `20bec6c` | `app/issues/schema.py` — `place_of`, `stage_of`, `is_open`, and the 43-column CONTRACT |
| `7ec151f` | `app/issues/{air,heat,land,coast}.yml` and the loader/validator in `__init__.py` |
| `0513ec5` | `app/issues/engine.py` and the fixture `app/issues/fixtures/node1-2026-09-06.json` |
| `1164727` | `app/issues/api.py`, the two lines in `app/main.py`, the `issues` MCP tool, `/stack` |
| `24c6a22` | `planetai snapshot [--out FILE]` |
| `e4f9505` | `NODE_ISSUES`, the five presets, `.env.example`, DOMAINS.md, PACKS.md, AGENTS.md |

Four new tests, all in `make test`: `test_issues_schema.py`, `test_issues.py`,
`test_issues_engine.py`, plus a rewritten group guard in `test_settings.py`. Every gate was broken on
purpose before it was trusted; the commit messages say which ways.

## Files this release touched that the prompt did not allocate to it

Four, and each was forced. Say so in the PR.

1. **`app/Dockerfile`** — one `COPY issues ./issues`. `app/` is not volume-mounted (compose mounts
   `config`, `packs`, `out`, `backups`, `exports` and nothing else) and `COPY *.py` does not see a
   package directory or a `.yml`. Without this line the code never reaches the container.
2. **`Makefile`** — the `py_compile` and `pyflakes` globs stopped at `app/*.py`, so the new package
   would have had no gate at all; plus the three new tests registered in `test:`.
3. **`app/main.py` carries three added lines, not two.** `include_router` and the `/issues` prefix in
   `_SHARE_OPEN` are the two that were agreed; the third is `import issues.api`, which is what makes
   them legal. No other line in that file moved. Rebase over prompt B's PRs as they merge.
4. **`app/agent_loop.py`** — the `/stack` branch and `stack_text()`. 1.3 asked for it; it is not
   `app/main.py`, so it is not a STOP condition, but it is outside the ownership list.

`docs/design/fixtures/` holds only a README. **The fixture had to move to
`app/issues/fixtures/`**: `docker-compose.yml` builds the app image with `build: ./app`, so the build
context is that directory and a `COPY` cannot reach up into `docs/`. A fixture under `docs/` exists on
a dev laptop and is absent on every node.

## Five things the prompt was wrong about

1. **`/nearby` does not return a fenced median.** `app/main.py:820` is a plain
   `percentile_cont(0.5)` filtered only on `silent_minutes < 120`. The MAD fence was JavaScript —
   `app/static/index.html:761` — shipped in v0.41.2 to trim a chart axis, never moved to the node.
   It is now `engine.fenced_median()`, used by every issue's ring. **`/nearby` was not touched**: it
   answers a different question (who is out there) and the ring card still reads it.
2. **Open-Meteo humidity is already fetched.** `app/sources.py:365-366` maps
   `relative_humidity_2m → humidity_model` on `om-point`. Heat's region column needed no request
   change and is live on the VM at 28.1 °C. **Tracker 5.23 is closed as already true**; the review's
   "a real gap the release closes" is stale.
3. **`/alerts.acted_at` cannot be the openness test.** It is
   `min(ts) WHERE stage IN ('acknowledged','acted')` (`app/main.py:894`), so an ask somebody merely
   saw reads as answered. `schema.py` asks the `actions` table directly. ρ itself is unaffected — it
   has always counted both stages on purpose (`app/index.py:99`).
4. **No pack declares a threshold as data.** `thresholds:` is prose in both `pack.yaml` files that
   have one, so "imported from the pack's declared thresholds" was not possible. Each issue writes
   its line down once and names the pack rule whose SQL carries the same number; `test_issues.py`
   greps that rule and fails when the two drift. That is the guarantee importing would have given,
   with no pack edited.
5. **`land_change_score` was retired in v0.33.1 and must not come back as land's fallback.**
   `packs/earth/README.md` gives the reason, and it is the reason the fallback is a bad idea: it is
   1 − cosine of the *mean* embedding vector over 1 km computed in Earth Engine, while `earth` takes
   the mean of the *per-pixel* distances over 10 km computed here. On node #1 the two read 0.037 and
   0.041 with no way for a reader to tell why. Worse, `observations` keeps the latest row per source
   per metric forever, so node #1 **still holds** a `land_change_score` row — that is how 0.037
   reached the 6 September capture and how it reached the VM's first render as "0.0 % changed". The
   fallback and the mechanism behind it are gone, and the validator now refuses a `fallback:` key
   with the reason. Land with no record is `none` and says `planetai run earth fetch`.

## Decisions taken inside the release

- **`apparent()` is applied per sensor, then aggregated.** It is not linear in its inputs. On the
  6 September capture the four indoor units give **30.82** that way and 30.53 the other; the review's
  own target is 30.8. The test fails if the two ever stop differing, so it cannot become a tautology.
- **The ring reads `mean_15m`, not `mean_1h`.** The review does not name a field and `/nearby` uses
  `mean_1h`, but comparing a 15-minute room against a 1-hour ring puts two different quantities on one
  scale — the apparent-temperature mistake in another costume. It is also what gives the review's own
  target of 7.0; `mean_1h` gives 8.875.
- **Indoor sensors are excluded from every distance except the room**, in one function
  (`engine._ambient`) that both the stack and the series call. SPEC.md §1 has always said indoor
  sensors never enter an ambient average; `place_of` answers geography, so the ambient rule cannot
  live there. **This was a real bug the proof number caught**: two of node #1's eleven ring stations
  are other people's indoor kits, one reading 0.3 µg/m³, and including them moved the street to 6.1.
- **`compare: {mode, margin}` is declared per issue.** A concentration compares by ratio; 30 °C
  against 20 °C is ten degrees, not half again as hot. The engine never guesses from the unit.
- **`open_asks` holds act-level alerts only**, sorted current-first. ρ measures `level='act'`, so an
  `info` note was never an ask. Before this, `/stack` said "still open, the reading came back on its
  own" about a digest.
- **The Spanish region noun is "lo que dice el modelo".** Spanish contracts *de + el*, and every
  other phrasing that fixes "por encima de el modelo" breaks one of the three comparison templates.
- **An unwatched issue's sentence says "Not watched here."**, not "no source" — the node may well
  have a source for it.

## Proven on `pai-clean`

Rebuilt from this branch, `v0.43.1-6-ge4f9505`.

**Bali preset, node #1's capture replayed** (the room through `POST /readings`, which is the path it
would really arrive by; the ring, the models, the hourly shapes, the alerts and the actions by SQL,
because `POST /readings` forces `local=TRUE` and there is no write endpoint for an alert):

```
order: ['air','heat','land','coast']   headline: heat
AIR   notable  open_ask_stale    #53    room=5.12 live · ring=7 partial · region=15 model
HEAT  act      open_ask_current  #65    room=30.82 live · ring=31.71 partial · region=28.10 model
LAND  none     no_source                (no earth record on this VM)
COAST context  context_only             region=2.1 model
```

Every target in the prompt's 1.8: heat is the headline with **#65** as its current ask (60 min old),
air is notable with **#53** listed as open and not current, the room is 5.1, the street is 7.0, the
model says 15, and heat's room is 30.8 from four indoor units.

**Santiago preset, empty node:** `order: ['air','heat']` from the preset, both `none` with
`reason: no_source`, `coast` and `land` shown with `watched: false` and "Not watched here.", every
issue carrying a sentence in all three locales.

**Also proven:** `/issues` is 403 at `SHARE_LEVEL=off` with no token and 200 at `open`, while
`/place/geojson` stays 403 at both; `/issues/fixtures` lists the fixture and serves it through the
real engine; `planetai snapshot` answered 12 of 12 endpoints into 8.7 KB with no token in the file.

Reproduce it: `rsync` the branch into `~/planetai` in the VM (excluding `.env` and `VERSION`),
`docker compose up -d --build app`, then the replay generator in this session's scratchpad. It is not
committed — it exists to prove one capture once, and `planetai snapshot` is the shipped way to move a
node's state.

## What is NOT verified

- **Nothing has been seen by a person on a screen.** Release 1 has no visible surface by design.
- **Bahasa and Spanish** are assistant-written. The CHANGELOG says so and every `.yml` says so.
- **Live data.** Node #1 was read-only throughout; every number above is a replay of its
  6 September capture, and the VM's own live figures come from Open-Meteo at Barcelona coordinates.
- **`/issues` under load or with a large `readings` table.** Five queries, no per-issue query — the
  test asserts that — but `readings_1h` is a plain view and 24 h of it has never been timed on a node
  with millions of rows.
- **Heat's ring** (31.7 °C from six of other people's stations carrying both channels) is the
  replayed capture's arithmetic, not something anyone has checked against a thermometer.
- **`/stack` over real Telegram.** `stack_text()` was rendered from the fixture in all three
  locales; no message has been sent.

## Matched against node #1, live, 11 September

`bayu-ungasan`, `v0.43.1-1-g35cbd7b` — the same commit as current `main`. Read-only over the
tailnet; nothing was written. The engine was replayed against its live `/stats`, `/observations`,
`/alerts` and `/earth`, which is the closest thing to seeing the new page without building it.

```
headline: air     (NOT heat — the prototype's hero is a different evening)
AIR   act      #155, 17 min old, still true
      "Holding at 21 µg/m³ in the room, and the whole area reads the same.
       Level with the wall outside, level with the street, over the model."
      room=21 n=3 live · yard=16 n=1 live · ring=15 n=4 partial · region=12 n=1 model
      attribution: everywhere
HEAT  notable  #149 open 18 h, the reading came back
      room=29.8 n=4 live · yard=31.3 n=1 live · ring=34.2 n=4 partial · region=30.2 n=1 model
LAND  context  1.3 % of the square changed · built 91 %, trees 9 %
COAST context  2.0 m · swell 1.8 m, period 13 s, sea 26.8 °C
```

Seven ways the running node differs from what the prototype was drawn against:

1. **Node #1 has a yard now.** `sc-19236` (Ungasan Kit) and `sc-19874` (Bayu new enclosure) are
   local and outdoor. The 6 September capture had none, so **the prototype's Stack shows that column
   empty and the live one fills all four.** Anything designed around three columns is wrong.
2. ~~**`/earth` has no frames.**~~ **Run 11 Sep.** Nine frames, 2017–2025, all serving over
   `/earth/year.png?year=`, ~780 KB each. The four Sentinel frames from `earth-engine timelapse`
   (2016, 2019, 2022, 2025, ~320 KB each) were already in `out/` and now have a route too. Both
   records are live on node #1.
3. **`/forecast` is empty.** `sources: []`, `hours: []`; the BMKG village code is unset.
4. **ρ has moved**: 58 act alerts, 21 acted, ρ 0.362, median 104 min. The prototype draws 28 rings
   with 14 closed. The ρ row must take its count from `/rho`, not from a constant.
5. **The earth record has moved**: 2024→2025 is 1.29 % / 129.1 ha (the prototype has 1.19 % /
   119.2 ha) and the 2017→2025 span is 8.47 % / 846.8 ha (prototype: 8.8 % / 880 ha).
6. **`noise` is already being measured** — `sc-19236` reports it on the yard. A fifth issue is a
   fifth file and the data is there today. There is no indoor noise sensor, so it would be a
   yard-and-nothing-else stack.
7. **`ee-point.land_change_score` is still on the node**, value 0.0371, timestamped 2025-07-01 with
   cadence `P1Y` — so it is *current by its own cadence*, not stale. A fallback that checked
   freshness would have used it. This is claim 5 above, confirmed on the live node rather than
   argued from the README.

### The ring appears twice, with two different numbers

On live data the Stack's ring reads **14.6** and the ring card's `/nearby` median reads **13.9**,
and both are labelled the street. Both sets are Bali Air Dispatch stations; they differ because
`/issues` takes a fenced median of `mean_15m` over the 4 stations fresh within 15 minutes, and
`/nearby` takes a plain median of `mean_1h` over the 6 fresh within an hour.

Neither is wrong. Two of them on one page is. **Settled 11 Sep**: the Stack owns "the street" and
the ring card shows the ring's *shape* — lowest, p25, p75, highest, who and how far — not a second
median.

## Settled, 11 September — Release 2 touches no `.py` file

All three blockers are closed. Tomas decided; the node side landed in this branch.

**1. The dashboard's files are on the `/static` allowlist.** `COMPANIONS` gains `dashboard.js`,
`dashboard.css`, `planetai-theme.css`, `tokens.css`, `signs.svg` and `kilometre-cells.json`. They do
not exist yet and the route 404s a missing file exactly as before, so nothing changes today — the
point is that **Release 2 now touches nothing in `app/*.py`**, which is what the brief wanted.

The mono stays at the flat `/static/jetbrains-mono-latin.woff2` rather than the `fonts/`
subdirectory `planetai-theme.css` names. This route takes a *name*, not a path, deliberately, on a
port open to a household LAN. **`tools/check_theme.py` (Release 2) must therefore compare the node's
copy byte-for-byte against `../planetai-design/planetai-theme.css` EXCEPT the single `src:` line,
which it normalises and reports.** That exception is the whole of the decision; do not widen it.

**2. The Sentinel loop lands.** `GET /earth/frame.png?year=&source=sentinel|landsat` serves what
`planetai run earth-engine timelapse` left in `out/`, and `/earth` publishes the available years
under a new `imagery` key. It is on the `open` allowlist beside the other two image routes.

`imagery` is deliberately **not** merged into `frames`. `/earth/year.png` is this node's own
AlphaEarth layer — a model's 64-number description of every 10 m pixel, flattened to grey, never a
photograph, `model`. `/earth/frame.png` is Sentinel-2 or Landsat imagery from somebody else's
cluster, `partial`, with its own credit line (both lines are in `imagery.credit`). The `satellite`
component takes the same shape twice and the pill is what separates them.

**3. The ring is the Stack's.** The Stack owns "the street". The ring card stops showing a second
median and shows what only it gives — lowest, p25, p75, highest, who, and how far. No endpoint
changes; `/nearby` keeps answering exactly as it does.

### Still standing for Release 2

- **`check_ui.py` cannot find `/issues` in `app/main.py`.** Its route regex reads `@app.get(...)`
  decorators and this FastAPI defers `include_router`, so `app.routes` holds an `_IncludedRouter`
  with no `.path`. A dashboard calling `/issues` fails rule 3 today. Release 2's `check_ui` must
  also parse `app/issues/api.py`'s `@router.get` decorators with the router's prefix.
- **The satellite loop is ~7 MB.** Node #1's nine frames are ~780 KB each, and the four Sentinel
  frames ~320 KB. §2.7 budgets 60 KB per refresh. The loop must load once and animate from memory;
  it can never be part of a refresh, and a kiosk that reloads pays the 7 MB again.

## For prompt B (the improvement plan)

- **Skip PR 11.** Release 2 deletes `refresh()` and gives the same guarantee structurally — every
  component renders inside its own guard — with the gate in `check_ui`. `card()` is applied to 3 of
  18 cards today and none of those three survives.
- **Land PR 5.** Its three fixes are real and independent of the renderer: `act()`'s
  `prompt(…) || 'acted'` still posts on Cancel and still inflates ρ; `layoutReset` still writes only
  `localStorage`; `esc()` still lacks `'`. Release 2 will carry all three into `dashboard.js`, but if
  Release 2 slips, PR 5 should land on the shipped page on its own.
- Nothing in Release 1 conflicts with PRs 1–10 or 12–28. `app/main.py` carries three added lines in
  two places.

## Where the seams are

- **`place_of` is the one function the custody spec (docs/SPEC_custody.md, not written yet) changes** when it is accepted. Today
  `local` carries both "ours" and "here"; custody makes `kind IN ('own','child')` the ownership test
  and leaves `local` as geography. The file says so at the top and the test is written in those terms.
- **The place prompt's releases are not on main.** No `baselines` table, no `bundle().stack`, no
  `/stack` endpoint, no attribution classifier, and heat ships three rules rather than four. Both
  `[stack absent]` and `[baselines absent]` branches were taken: the engine computes the stack itself
  and heat speaks in degrees rather than in ranks. When baselines land, heat's `line` becomes the
  place's own p90 per hour with 41 as the medical floor, and `heat.yml` says so where the line is.
- **When the reports prompt's Release 3 lands** (`kind: condition`, `recovery:`, `alerts.outcome`), a
  condition-kind alert is never `act` and `outcome` replaces the current-condition test. Until then
  `engine.ASK_CURRENT_HOURS` and the over-the-line test are the `[R3 absent]` branch, in one place.
- **`ANATOMY` may later move into `/issues`** so the node can carry what each band shows. Do not do
  that in Release 2; the comment in `dashboard.js` should say so.
