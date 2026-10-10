# The node dashboard, walked as five readers

**13 September 2026.** A UX review of `app/static/` as it stands on `main`, walked view by view
against the `ui-ux-pro-max` Quick Reference, as the five people who open it. It changes nothing.
Every finding below has a screenshot and a rule.

**One correction, made after the first pass.** R1 was first filed as a P0 saying `/health` leaks the
node's res-8 cell. Measured, that is wrong: the cell is 0.716 km² and the 3-decimal coordinates
published beside it are 0.0093 km² — **77× finer**, so the cell adds nothing the coordinates have not
already given. `app/main.py:772` says exactly this and is right. What survives is a narrower point
about two settings disagreeing, and it is a decision rather than a defect; it has moved to Decisions
to revisit. **Four P0s, not five.**

## Header

| | |
|---|---|
| Under review | `planetai-node` `main`, tag **v0.52**, commit `43d508d` |
| The surface | **three static files**, not one: `app/static/index.html` (5.8 kB skeleton), `dashboard.js` (130 kB renderer), `dashboard.css` (33 kB), plus `tokens.css`, `planetai-theme.css`, `signs.svg`, `node-ground.svg`, `kilometre-cells.json`. Decision 19 of 10 Sep. |
| `/issues` | exists (`app/issues/api.py`) |
| `/issues/fixtures` | exists; ships one fixture, `node1-2026-09-06`, and `?fixture=node1-2026-09-06` renders |
| Where it ran | **pai-clean** (Lima VM), two containers built from v0.52's source: `:8081` bootstrapped + `SHARE_LEVEL=open`, `:8082` fresh install (`BOOTSTRAP=0`, no packs). Node #1 and node #2 were not touched, read or written. |
| Browser | Playwright + the Chromium already installed for `planetai-design` (1193), one device pixel, axe-core 4.x from `planetai-design/node_modules` |
| Shot library | `planetai-design/design/audit/2026-09/ux-review/` on branch `ux-review-2026-09` — **106 JPEGs, 10 MB**: 56 from the walk, and 50 named `FIX*` taken after the fixes. A finding's row cites the before; its `FIX` or `FIX2` twin is the after. |
| **Fixed since** | branch **`ux-p0-fixes-2026-09`** off v0.52, eleven commits, `3a2237f` at the head. **44 of the 64 findings closed**, two half, one withdrawn, one routed, sixteen open — all P2 or advisory. Touched: `app/static/`, `app/settings.py`, two lines of `app/main.py`, `tools/check_ui.py`, three test files. 727 insertions. `make lint` and 32/32 after every commit. |
| **Still open, and a P0** | **L2 — the wall shows a model estimate in 120 px type and never says `model`.** It is the only P0 in the tables that is not closed. `ANATOMY.wall` carries no `chips` and `miniStack`, which holds the pills, is not on it; the Now view names the source and the wall drops it. Putting a source and a word on the wall is a composition decision about the most designed surface in the product, so it was not taken here. |
| **axe, after** | **zero violations** on Now, Network, Set up locked and unlocked, the wall and Arrange, at 375 / 390 / 768 / 1440 / 1920, populated, empty and refused. It was 57 serious and 11 critical when this was written. |
| Skill | `~/.claude/skills/ui-ux-pro-max`, read in full. **There is no `skill.json`** in this install, so the version could not be recorded as the brief asks; the nearest stamp is `data/catalog-summary.json` → `schemaVersion 1, verifiedAt 2026-08-26`, 119 UX guidelines / 25 chart types / 22 stacks, which matches SKILL.md's own counts. Proof query `search.py "focus states" --domain ux -n 1` returns the **Focus States** row (Interaction, High). |
| Gates | `tools/check_ui.py` **pass**; `tools/check_theme.py` **pass** (3 frozen files match) |

The review is scoped to use and comprehension. The design language was read against this same
surface on 12 September in `docs/design/LANGUAGE_GAP.md` (7 of 8 checks pass at v0.52); nothing here
re-opens that reading.

---

## Ten lines

1. **The hero and the wall print milligrams where the node wrote micrograms.** `.k`'s
   `text-transform:uppercase` turns `17 µg/m³` into `17 MG/M³`, two lines above a sentence that says
   `5 µg/m³`. Household member · §1 `color-not-only` is the nearest id and it does not fit; the skill
   has no rule for a case transform that changes a unit — check written here. **P0** · **fixed `7745e01`**
2. **A gap in the day is drawn as a line through it.** Seven missing hours become a six-hour ramp that
   rises across the WHO line and back. The chart states a reading that was never taken, and states one
   that crosses the threshold the page judges against. Household member · §10 `data-table` /
   Trend-Over-Time A11y Fallback. **P0** · **fixed `d5f9ed3`**
3. **The node speaks Bahasa and Spanish; the dashboard only ever speaks English.** `/issues` carries
   no `locale` key at any level, so `mkCtx`'s `LOCALES.includes(snap.locale)` is always false and the
   page pins to `en` — with `ALERT_LOCALE=es` set on the node and every sentence delivered in three
   languages. Household member, tester · §1 `consistent-help`. **P0** · **fixed `ece79b7`**
4. **At `SHARE_LEVEL=off` the wall is a black screen and the Network view is an empty white one.**
   `render()`'s refused branch writes `#hero` and returns before it reaches `#wallbox` or `#netbody`.
   The surface that nobody is standing at is the one that goes blank. Household member, stranger ·
   §8 `error-recovery`, §10 `error-state-chart`. **P0** · **fixed `e4a810a`**
5. **At `SHARE_LEVEL=off` a tokenless stranger gets the node's position to ~110 m from `/health`, while
   the same node refuses to announce anything finer than ~35 km² over radio.** Measured: the 3-decimal
   coordinates localise to 0.0093 km²; the presence floor is 35.1 km². This is a **decision, not a
   bug** — `app/main.py:772` argues the rounding deliberately — so it is filed under Decisions to
   revisit, not as a finding. Stranger · no skill rule; check written here. · **withdrawn**
6. **Arrange has no way out and no instructions.** `.arrbar` carries no CSS rule, so the instruction
   line and the **Done** button sit at y≈3,746 on a 3,789 px page. Leaving by the nav does not end the
   mode. Keeper · §9 `modal-escape`, §1 `escape-routes`. **P1** · **fixed `4157d20`**
7. **Arrange's ✕ silently does nothing on five of nine bands, and the restore menu is dead markup.**
   `render()` skips a hidden id without clearing the mount, and `#arr-restore` is never referenced in
   `dashboard.js`. Keeper · §8 `error-recovery`, `success-feedback`. **P1** · **fixed `4157d20`**
8. **Every input in Set up is unlabelled and every toggle is nameless.** axe: `label` **critical** ×8
   in one group, `button-name` **critical** ×2, `select-name` **critical** ×1. Keeper · §1
   `form-labels`, §8 `input-labels`. **P1** · **fixed `4adb28d`**
9. **The node writes a perfect refusal and the page throws it away.** `"'5' is not a value
   REPORT_EVERY accepts. Hours between reports: 3, 4, 6, 8, 12 or 24."` becomes `Could not save
   (400).`; `"no such alert"` becomes `"try again in a moment"`, which will never work. Keeper ·
   §8 `error-clarity`, `error-placement`. **P1** · **fixed `4adb28d` and `1c446db`**
10. **The page carries no view in the URL and no `<h1>`.** Refresh, back and a shared link all land on
    Now; switching views drops scroll. axe `page-has-heading-one` on every render. Keeper, wall ·
    §9 `deep-linking`, `state-preservation`, §1 `heading-hierarchy`. **P1** · **fixed `4157d20`, `47beab1`**

---

## The header and switching between views

**Who it is for.** Everybody: it is the only thing on screen in all five states.

**What is coherent.** Five buttons, one row, legible at 375; the active one is filled black on paper
and reads unambiguously. The node name, the place line and one provenance pill sit together, and the
pill is honest about a fixture (`cached`, always) and about staleness on live data.

| id | P | skill | rule | reader | what happens | evidence | fix in one line | collides | status |
|---|---|---|---|---|---|---|---|---|---|
| H1 | P1 | High | §9 `deep-linking`, `state-preservation`, `back-stack-integrity` | keeper, wall | `show()` never touches the URL. Reload after switching to Network lands on Now; a link to Network cannot be sent; browser Back leaves the page entirely. Measured: `before.y=3000 → onNet.y=0 → back.y=0`, URL unchanged throughout. | `network_populated_1440_base.jpg`, probe `viewSwitch`/`reloadLandsOn`; `dashboard.js:1904` | Push the view into the hash and read it at boot. | no | **fixed** `4157d20` |
| H2 | P1 | Moderate | §1 `heading-hierarchy` | screen reader | No `<h1>` on any view, in any state. axe `page-has-heading-one` fires on all 14 renders. The node's name is a `<b>`. | every axe run; `index.html:31` | Make the node name or the hero sentence the `<h1>`. | no | **fixed** `47beab1` |
| H3 | P2 | High | §1 `skip-links` | keyboard | No skip link. `grep -c skip` = 0 in both `index.html` and `dashboard.css`. Now at 390 is 9,527 px tall. | `now_populated_390_base.jpg` (full page) | One visually-hidden skip link before the header. | no | open — P2 |
| H4 | P1 | Medium | §9 `state-preservation`, §5 `scroll-behavior` | keeper | `show()` ends in `window.scrollTo(0,0)`. Leaving a band to check Network and coming back returns you to the top of a nine-screen page. | probe `viewSwitch` | Remember scroll per view. | no | **fixed** `4157d20` |
| H5 | P1 | High | §9 `nav-state-active` | keeper | Pressing **Arrange** leaves **Now** filled in the nav (`navActive:["Now"]`). Nothing in the chrome says you are in a mode. | `arrange_populated_1440_base.jpg` | Mark Arrange active while `ARRANGING`. | no | **fixed** `4157d20` |
| H6 | P2 | High | §9 `focus-on-route-change` | screen reader | `show()` moves no focus. After a view change focus is still on the nav button; the new view is not announced. | probe `tab` | Focus the view's heading on change. | no | **fixed** `4157d20` |
| H7 | P1 | High | §1 `contextual-live-badge-updates` | household | The freshness pill's *timestamp* lives only in `title=` — hover only. On a phone there is no way to reach it. On the fixture the header shows no time at all, because the fixture's `/health` has no `city` and `as_of` is absent. | `now_populated_390_fold.jpg`, probe `pills` | Print the time beside the word. | no | **fixed** `1c446db` |
| H8 | P2 | Medium | §1 `contextual-live-badge-updates` | wall, keeper | The header is **not** sticky, so the node's name, version and freshness scroll away and are unreachable from anywhere below the first screen. | `now_populated_390_base.jpg` | — | no | open — P2; and see the note under H4 |
| H9 | P1 | Serious | §6 `color-dark-mode` | keeper | `?theme=dark` boots the wall; pressing its **Now** exit keeps `data-theme="dark"` and renders the whole paper view — buttons, forms and all — on ink. `ctx.register` reads a query parameter that never changes. Body background measured `rgb(23,23,23)` with 13 buttons on screen. Decision 15 is "paper by day, dark on the wall". | `now_populated_1440_dark-leak.jpg`; `dashboard.js:419` | Drop `theme` from the register once a view other than the wall is chosen. | no | **fixed** `4157d20` |

**Clean:** §1 `focus-not-obscured` (the header is not sticky; nothing covers focus), §1 `focus-states`
(every control measured `outline: solid 2px`), §5 `horizontal-scroll` (doc width equals viewport at
375/390/768/1440/1920).

---

## Now

**Who it is for.** The household member at 390 with five seconds, and the keeper at 1440 who closes
the loop.

**What is coherent.** The hero's anatomy reads in the order it should: issue, state, sentence, line,
sources, the four distances, then the ask. The Figures band — every number, its source and its word —
is the best thing on the page and has no equivalent on any comparable product.

**The five-second read at 390** (`now_populated_390_fold.jpg`, covered then revealed). First three
things read, in order: (1) `AIR QUIET`, (2) `· QUIET; THE DAY'S HIGH WAS 17 MG/M³ AT 08:00`,
(3) `Holding at 5 µg/m³…`. The three that matter are the headline condition, whether an ask is open,
and when this was last true. One of three lands. The second thing read is a thousand-fold wrong unit;
the ask strip is in the right-hand column, below the fold at 390; nothing says when.

| id | P | skill | rule | reader | what happens | evidence | fix in one line | collides | status |
|---|---|---|---|---|---|---|---|---|---|
| **N1** | **P0** | — | no rule; check written here (nearest: §6 `truncation-strategy`) | household, wall | `.k{text-transform:uppercase}` renders the node's `reason_text` in caps, so `µ` becomes `M`: the hero reads **`17 MG/M³`** while the sentence below reads `5 µg/m³`. Milligrams are 1000× micrograms. Present on the Now hero, on every issue band head, and on the wall at 1920. | `now_populated_390_fold.jpg`, `wall_populated_1920_base.jpg`, `/tmp/kicker.png`; `dashboard.css:65` | Stop uppercasing any string the node wrote. | no — this is the audit's known item, **regressed** from the wall onto the hero | **fixed** `7745e01` |
| **N2** | **P0** | High | §10 `data-table`, `axis-labels`; chart-domain **Trend Over Time** A11y Fallback | household | `day()` filters nulls out of the series and joins what is left, so a gap is drawn as a straight line across it. Rendered with seven hours nulled, the room trace ramps for six hours, crosses the WHO line and falls — a threshold crossing that never happened. Polyline carries 17 points where the series has 24; `aria-label` still says "2 traces over 24 hours". | `now_populated_1440_chart-gap.jpg`, probe `polylineCount/pointsPerLine`; `dashboard.js:1030` | Break the polyline at a null. | no | **fixed** `d5f9ed3` |
| **N3** | **P0** | High | §1 `consistent-help` | household, tester | The dashboard is English-only on every node. `/issues` top-level keys are `order, undeclared, dropped, headline, as_of, distances, labels, issues` — no `locale`; `snap.locale` is therefore always `undefined` and `mkCtx` pins `en`. Verified with `ALERT_LOCALE=es` set on the node and the page fully English, live and on the fixture. | `now_live_390_locale-es-node.jpg`, `now_populated_390_locale-id.jpg`, `/settings` row; `dashboard.js:415` | Publish the node's locale in `/issues` (or read it from `/settings`). | no | **fixed** `ece79b7` |
| N4 | P1 | High | §10 `axis-labels`, `time-scale-clarity`, `screen-reader-summary` | household | The 24 h chart has **no text inside it at all** (`textNodes: []`), one line element (the threshold), no axes, no units, no time origin, no tick values, no data table. The red dashed line is never named on the chart. | probe `dayChart`; `now_populated_1440_base.jpg` | Two axis labels, a first/last hour, and the unit. | no | **fixed** `47beab1`, corrected `d0821f9` |
| N5 | P1 | Serious | §1 `color-contrast` | household | axe: `color-contrast` serious ×37 at 1440 and 390 on the populated fixture, all on `.sensor .kits span` — the kit names under each source card. ×2 on the fresh node. | every `now_*` axe run | Lift `.kits span`. | no | **fixed** `47beab1` |
| N6 | P1 | Serious | §10 `focusable-elements`, §1 `keyboard-nav` | keyboard | axe `scrollable-region-focusable` serious on `.figwrap`. The Figures table scrolls horizontally at 390 (435 px in a 390 box) and cannot be scrolled from the keyboard. | `now_populated_390_base.jpg`, axe | `tabindex="0"` on `.figwrap`. | no | **fixed** `47beab1` |
| N7 | P2 | Minor | §10 `sortable-table` | screen reader | axe `empty-table-header`: the Figures table's value column has an empty `<th>`. | axe, all widths; `dashboard.js:1128` | Name the column. | no | **fixed** `47beab1` |
| N8 | P1 | — | no rule; nearest §10 `number-formatting` | household | On the empty node the mini stack prints `— — —` for room, yard and ring with no explanation: `mini` mode drops the `src` line and the pill. The full stack under it says "not watched here", which on a node whose sensors are not yet connected is the wrong sentence — the tester has not chosen not to watch. | `now_empty_1440_base.jpg` | Say "no sensor yet" on a node with none. | no | **fixed** `47beab1` — wording is mine, wants Tomas |
| N9 | P2 | Medium | §8 `empty-states` | tester | The loop band's three empty states are lowercase fragments with no instruction — `no asks yet`, `no report yet`, `nothing yet` — beside bands whose empty states name the exact command (`planetai run place refresh`, `planetai run earth-engine timelapse`). The land band points at `docs/PACKS.md`, a repo path a household does not have. | `now_empty_1440_base.jpg` | Match the good ones. | no | **half** — the fragments are translated (`eaad3c4`); they still carry no instruction |
| N10 | P1 | High | §2 `error-feedback`, §8 `confirmation-dialogs` | household | `act()` opens `prompt()` **before** checking for a token, so a person without one types what they did and is then told the screen cannot record it. The dialog string is hardcoded English and bypasses the locale layer entirely. | `now_populated_1440_act-no-token.jpg`, probe `actPrompt`/`actNoToken`; `dashboard.js:1813` | Check the token first. | no | **fixed** `1c446db` |
| N11 | P1 | High | §8 `error-clarity` | keeper | Pressing **I did this** against an alert the node does not have returns 404 `{"detail":"no such alert"}`; the page says *"The node did not record that. Nothing was written; try again in a moment."* Trying again never works. | probe `afterTokenAct`, `curl` 404 body | Show the node's own `detail`. | no | **fixed** `1c446db` |
| N12 | P1 | High | §1 `contextual-live-badge-updates` | design round, keeper | A fixture render shows the header pill `cached` and **every figure pill inside the page `live`** — 12 of them, from the snapshot's own captured provenance. `LANGUAGE_GAP.md` §7 claims "a fixture render says `cached` unconditionally" and "nothing wears `live` that was not read in the last poll"; that holds for the header pill only. | probe `pills`; `now_populated_1440_base.jpg` | Coerce every pill to `cached` under `?fixture=`. | no | **fixed** `1c446db` |
| N13 | P2 | High | §5 `chip-collection-reflow`, `compact-label-overflow` | household | At 390 the REGION source chip (`REGION · CAMS AIR QUALITY (MODEL POINT SAMPLE)`) wraps to two lines inside its own border. The skill's rule is explicit that a compact label should not wrap. | `now_populated_390_fold.jpg` | Shrink or truncate with the full text reachable. | no | open — P2 |
| N14 | P2 | Medium | §9 `nav-label-icon` | screen reader | Index rows are links whose accessible name is the concatenation with no separators: *"AirquietHolding at 5 µg/m³ in the…"*, *"Coastcontext2.1 m at…"*. Unwatched rows carry `aria-disabled="true"` while remaining focusable and still navigating. | probe `tab` 6–9; `dashboard.js:1195` | Separators, and either disable or don't claim to. | no | open — P2 |
| N15 | P2 | Serious | §1 `web-target-size` / §2 `touch-target-size` | household | Nothing is under the WCAG 2.2 **24 px** floor anywhere — that passes. The nav buttons are 32 px tall and **I did this** is 76×36, both under the **44 pt** advisory. Recorded as advisory per the skill's own scoping. | probe `targets_now/network/setup` | — | no | open — advisory only |
| N16 | P2 | Low | §10 `tooltip-on-interact`, `tooltip-keyboard` | household, wall | Every dot on the Stack's scale and every POI on the plan names itself only in an SVG `<title>` — hover only, unreachable by touch, by keyboard and on the wall. The values are in the stack above, so nothing is lost on Now; on the plan the place names are lost entirely. | probe `scale.titles`; `dashboard.js:783` | — | no | open — P2 |

**Clean:** §3 (Fast 3G: DOM 1.8 s, sentence 2.4 s, settled 3.4 s; one refresh 46 kB against the
60 kB budget; first load 379 kB), §5 `horizontal-scroll` and `dynamic-type` (200 % text at 390 and
1440: no overflow, no clipped container), §7 `reduced-motion` (0 animated elements, 0 SMIL nodes
under `prefers-reduced-motion`), §10 `color-guidance`/`pattern-texture` (the day's traces are told
apart by dash, not hue; legend present), §10 `empty-data-state` on the place, forecast, ring and land
bands.

---

## Network

**Who it is for.** The keeper, once, answering one question: **what leaves this house?**

**What is coherent.** It answers that question directly and in order — what is read on the left, what
leaves on the right, the machine's own vitals below. Every empty state names the setting that would
fill it, and "None. This node knows of no other, which is the ordinary state of a node nobody has
linked yet" is the right sentence.

| id | P | skill | rule | reader | what happens | evidence | fix in one line | collides | status |
|---|---|---|---|---|---|---|---|---|---|
| **W1** | **P0** | High | §8 `error-recovery` | household, stranger | At `SHARE_LEVEL=off` the view is header + nav over an empty page. `render()` returns from the refused branch before reaching `#netbody`. | `refused_network_1440.jpg` | Draw the refusal sentence in every view's mount. | no | **fixed** `e4a810a` |
| W2 | P1 | High | §1 `contextual-live-badge-updates` | household | On the same refused render the header pill reads **`live`** — `/health` answers at `off`, so the pill is computed while every reading is refused. The page asserts freshness over nothing. | `refused_network_1440.jpg`, `refused_now_390.jpg` | Say `refused`, not `live`. | no | **fixed** `e4a810a` |
| W3 | P1 | Medium | §7 `motion-meaning`, `excessive-motion` | tester | `rows()` draws a wire **and a travelling dot** for every row unconditionally. On a fresh node with `0 sensors` and `0 public stations` the figure animates data flowing along two links that carry nothing, and out to `nowhere yet`. `docs/GUI.md` says "Flows animate along real links only"; R6 says a motion with no datum is deleted. | `network_empty_1440_base.jpg`; `dashboard.js:1431` | Draw the wire, drop the dot, when the count is zero. | R6 — see Decisions to revisit | **fixed** `1c446db` |
| W4 | P1 | High | §1 `contextual-live-badge-updates` (nearest); no `date-formatting` id exists | keeper, wall | `ctx.hhmm` calls `toLocaleTimeString([])` — the **viewer's** locale and timezone, not the node's. The header read `As of 11:40 PM` for a poll at 15:35 UTC on a node whose `NODE_TZ` is `Europe/Madrid`, because the browser sits in UTC+8. Nothing on the page names a zone. | `network_populated_1440_base.jpg`, `setup_unlocked_1440_node_viewport.jpg` | Format in `NODE_TZ` and say so. | no | **fixed** `1c446db` |
| W5 | P2 | Low | §10 `number-formatting` | keeper | The Fab City Index row prints `–` for a pillar with zero sources (`hit.length \|\| '–'`). Four em-dashes in a row read as "no data" where the true answer is "zero". | `network_populated_1440_base.jpg`; `dashboard.js:1490` | Print `0`. | no | open — P2 |
| W6 | P2 | Moderate | §1 `voiceover-sr` | screen reader | The figure is an SVG with `role="img"` whose whole accessible name is the section title; the six facts inside it are `<text>` nodes. `.netlist` repeats them for narrow screens and is hidden at width. At 1440 a screen-reader user gets the title and nothing else. | `network_populated_1440_base.jpg`; `dashboard.js:1441` | Expose `.netlist` to AT at every width. | no | open — P2 |
| W7 | P2 | Moderate | §9 `navigation-consistency` | keeper | axe `landmark-unique` on `#views` at every render: `<nav>` inside `<header>` with no distinguishing label. | axe | Label the nav. | no | **fixed** `47beab1` |

**Position leak.** `/place/geojson` is correctly refused at every level (403 from a non-local
address, verified). `/health` is not — see the refused section.

**Clean:** §5 (no overflow at 390 or 1440), §3 (Fast 3G sentence at 2.8 s), §8 `empty-states` (every
one names its setting), §10 (nothing on this view is a chart).

---

## Set up

**Who it is for.** The keeper, and the tester in their first hour who has never seen a `.env`.

**What is coherent.** The blurb at the top is the clearest statement of the model anywhere in the
product — live in twenty seconds, blank returns the key to `.env`, a value here overrides it — and
every field carries a real help line written for a person. The `source` marker (`from .env` /
`set here · overrides .env` / `default`) is the right idea. Secrets are masked, never echoed, and a
saved one shows `Set — type to replace`.

| id | P | skill | rule | reader | what happens | evidence | fix in one line | collides | status |
|---|---|---|---|---|---|---|---|---|---|
| **S1** | **P1** | Critical | §1 `form-labels`, §8 `input-labels` | keeper, screen reader | No `<label for>` and no wrapping: the label is a sibling `<div>` of the input. axe `label` **critical** ×8 in the alerts group alone, ×4 in the tree, ×1 in issues. `select-name` **critical** on the locale select. | `setup_unlocked_1440_alerts.jpg`, `setup_unlocked_1440_node.jpg`, axe | Add `for`/`id`. | no | **fixed** `4adb28d` |
| **S2** | **P1** | Critical | §1 `aria-labels`, §8 `read-only-distinction` | keeper, screen reader | Every toggle is `<button class="switch"><span class="tr"></span></button>` — no text, no `aria-label`, no `role="switch"`, no `aria-pressed`. axe `button-name` **critical** ×2 in alerts; the same construction carries the pack switches. A screen reader hears "button" and cannot tell on from off. | `setup_unlocked_1440_alerts.jpg`, `setup_unlocked_1440_packs.jpg`, axe | Name them and carry `aria-pressed`. | no | **fixed** `4adb28d` |
| **S3** | **P1** | High | §8 `error-placement`, `inline-validation`, `error-clarity`, §1 `error-summary` | keeper, tester | There is no validation of any kind before the PUT. The node refuses with a written sentence — `"'5' is not a value REPORT_EVERY accepts. Hours between reports: 3, 4, 6, 8, 12 or 24. Default 6, which is four a day."` — and the page shows **`Could not save (400).`** in a toast that clears in 4.2 s, names no field, marks no field, and leaves the bad value in place. | `setup_unlocked_1440_bad-value.jpg`, probe `badSave`, `curl` 400 body; `dashboard.js:2085` | Render `detail` next to the field it names. | no | **fixed** `4adb28d` |
| **S4** | **P1** | High | §8 `form-autosave`, §9 `state-preservation` | keeper | Changing tab discards unsaved edits with no warning. Typed `5` into REPORT_EVERY, opened Sources, came back: the field is empty. `loadSetup()` re-renders the pane from the last `describe()`. | probe `unsavedEdit` | Warn, or keep the edit. | no | **fixed** `4adb28d` |
| **S5** | **P1** | High | §8 `input-helper-text`, `input-type-keyboard` | keeper, tester | Five settings are enumerations in `app/settings.py`'s `CHOICES` — `SHARE_LEVEL` (off\|open), `REPORT_EVERY`, `REPORT_ANCHOR`, `REPORT_DEPTH`, `AGENT_PREFER` — and every one renders as a free-text box. Only `ALERT_LOCALE` gets a `<select>` and only ten keys get a toggle (`BOOLS`). The node knows the valid values and the page does not offer them. | `setup_unlocked_1440_node_viewport.jpg` (SHARE_LEVEL as a text input reading `open`) | Drive the widget from `CHOICES`. | no | **fixed** `4adb28d` |
| **S6** | **P1** | — | no rule; check written here | keeper | **Nothing in the interface marks a setting that changes what leaves the machine.** `SHARE_LEVEL`, `CKAN_PORTALS`, `PARENT_API_URL`, `RETICULUM_PRESENCE` and `AGENT_ONLINE_KEY` are rendered in exactly the same box as `COAST_MAX_KM`. `AGENT_ONLINE_KEY`'s help line — *"The only thing that lets household data leave your network"* — is 10.5 px body text identical to every other help line. | `setup_unlocked_1440_node_viewport.jpg` | A visible mark on the keys that send data outward. | no | **fixed** `47beab1` |
| S7 | P1 | Serious | §1 `color-contrast`, §8 `contrast-feedback` | keeper | axe `color-contrast` serious ×12 in the alerts group, all on `label > .src` — the marker that says whether a value came from `.env`, from here, or from a default. The one thing that tells the keeper where a value came from is the least legible thing in the row. | axe, `setup_unlocked_1440_alerts.jpg`; `dashboard.css:341` | Lift `--dim` on `.src`. | no | **fixed** `4adb28d` |
| S8 | P1 | Medium | §8 `input-helper-text` | keeper, tester | A key at its code default renders an **empty box** while its marker says `DEFAULT`. The keeper cannot see what the node is actually doing, only that they have not changed it. Confirmed on `REPORT_EVERY` (effective default 6, box blank). | probe `unsavedEdit`, `setup_unlocked_1440_alerts.jpg` | Show the default as a placeholder. | no | **fixed** `4adb28d` |
| S9 | P1 | High | §8 `input-labels`, `password-toggle` | keeper, tester | The unlock gate's two token fields are **placeholder-only** — `admin token`, `token for closing a loop` — with no label and no reveal. A password typed on a phone cannot be checked before submitting. `autocomplete="off"` also blocks a password manager (§8 `autofill-support`, advisory). | `setup_gate_390_base.jpg`, `setup_gate_1440_base.jpg`; `index.html:87` | Labels and a reveal. | no | **fixed** `4adb28d` + `eaad3c4` (the reveal) |
| S10 | P2 | Medium | §8 `submit-feedback`, §2 `loading-buttons` | keeper | **Save changes** has no in-flight state and is never disabled, so it can be pressed twice and fire two PUTs. The only confirmation is a toast that disappears in 4.2 s; nothing on the page then says what changed. | `setup_unlocked_1440_node_viewport.jpg`; `dashboard.js:2061` | Disable while in flight. | no | open — P2 |
| S11 | P2 | Minor | §1 `heading-hierarchy` | screen reader | axe `empty-heading` on `#ptitle` in the locked state — the group heading is in the DOM and empty until unlock. | `setup_gate_390_base.jpg`, axe | Fill or hide it. | no | **fixed** `47beab1` — as a side effect of the `[hidden]` guard; see What the fixing found |
| S12 | P1 | — | no rule; check written here | keeper, tester | **The page never tells the keeper the address a wall or a phone should open.** `planetai ui` prints it in the terminal; the interface that a keeper is already looking at does not. The tester's path to a wall screen runs through the CLI. | `setup_unlocked_1440_node_viewport.jpg` (whole group, no address) | Print the LAN URL under SHARE_LEVEL. | no | **fixed** `47beab1` |
| S13 | P2 | Medium | §1 `keyboard-nav` | keyboard | The form is not a `<form>`: Enter does nothing, there is no submit relationship, and the save is a click handler. Everything is reachable by Tab and operable, so the pass is on reachability only. | probe `targets_setup` | Wrap it in a `<form>`. | no | open — P2 |

**`NODE_ISSUES`** is present in the issues group with the strongest help text in the product. It does
**not** say what reordering does to the page — that the first name is where the page starts and that a
name nothing declares is dropped with a log line — in the interface; that is in the help string but
not next to the consequence.

**Clean:** §8 `password-toggle` for *saved* secrets (masked, never echoed, `Set — type to replace`),
§5 (no overflow at 390 or 1440), §8 `progressive-disclosure` (bootstrap last and read-only, with the
restart instruction).

---

## Wall

**Who it is for.** A room at three metres, in a lit room, with nobody touching it.

**What is coherent.** One sentence and one number carry the screen, and they are the right two things.
The register switch is correct and automatic. R6 is honoured where it counts: `controls: false` is
passed explicitly to the satellite card, so the wall's loop has no play button and no slider.

**The three-metre check** (no skill rule exists for this reader; the check is: render at 1920, scale
the image to a quarter, write down what can still be read — `wall_populated_1920_base_quarter.jpg`).

*Readable at a quarter:* the sentence, the numeral, the ρ row as a texture (roughly half green).
*Not readable:* the kicker, the WHO line, all four issue index lines, the ρ caption, the node name,
the cell caption, **and the word `stale`**.

| id | P | skill | rule | reader | what happens | evidence | fix in one line | collides | status |
|---|---|---|---|---|---|---|---|---|---|
| **L1** | **P0** | High | §8 `error-recovery` | household | `SHARE_LEVEL=off` renders the wall as a **completely black 1920×1080 screen** — no sentence, no node name, nothing. The refused branch writes `#hero`, which `body.wallview` hides, and returns before `#wallbox`. A household reads a dead node. | `refused_wall_1920.jpg` | Draw the refusal in `#wallbox` too. | no | **fixed** `e4a810a` |
| **L2** | **P0** | — | no rule for this reader; check written here | household | On a fresh node the wall reads **"Holding at 6 µg/m³ over this square of the map"** in 120 px type with the WHO line under it, and **never names a source or a provenance word**. `ANATOMY.wall` has no `chips`, and `miniStack` (which carries the pills) is not on it. The Now view names the source; the wall drops it. | `wall_empty_1920_base.jpg` vs `now_empty_1440_base.jpg`; `dashboard.js:1143` | Put the source and the word on the wall. | no | open — the wall still names no source and no word |
| **L3** | **P1** | — | no rule for this reader; check written here | household | The one word that tells a room the wall is lying — `stale` — is 11 px muted mono in the footer and is illegible at a quarter scale. Nothing on the wall ever says **when**: there is no `as_of`, only the presence or absence of `stale`. | `wall_populated_1920_base_quarter.jpg` | Make staleness the size of the thing it contradicts. | no | **half** — the wall says when (`47beab1`); how loud `stale` is at three metres is Claude Design's |
| L4 | P1 | — | §1 `color-not-only` (nearest) | household, wall | N1 again, at 1920: `AIR QUIET · QUIET; THE DAY'S HIGH WAS 17 MG/M³ AT 08:00`. | `wall_populated_1920_base.jpg` | see N1 | no | **fixed** `7745e01` |
| L5 | P2 | Medium | §8 `empty-states`, §10 `empty-data-state` | tester | The wall's empty states are bare fragments in body type — `no frames yet` floats in a thin box in the middle of the screen where the photograph belongs; `no asks yet` sits where ρ belongs. At three metres they read as a rendering fault. | `wall_empty_1920_base.jpg` | Say what would fill them, or draw nothing. | no | open — P2 |
| L6 | P2 | — | check written here | stranger | The wall prints the node's res-8 cell id and the caption `THE CELL THIS NODE STANDS IN` across the footer. A wall screen visible from a street publishes a 525 m location to anyone who can read it. | `wall_empty_1920_base.jpg` | — | no | open — see Decisions to revisit 6 |
| L7 | P2 | Medium | §1 `heading-hierarchy` | screen reader | axe `page-has-heading-one` on the wall too. | axe | see H2 | no | **fixed** `47beab1` + `3a2237f` |

**The `?only=` bug is fixed.** `?only=nonesuch` renders the whole page (9 bands, 5,819 characters of
text), and `?only=place` renders one band. `docs/archive/handoffs/HANDOFF_dashboard_violations.md` finding 3 and the
review's §1 finding 7 can both be closed.

**`?kiosk=1` and the Wall view are the same view**, correctly: `KIOSK` only adds `body.kiosk` and
forces the dark register and a boot to `wall`.

**Clean:** §7 `reduced-motion` (measured under `prefers-reduced-motion`: **0** elements with a running
animation or transition, **0** SMIL nodes; the satellite loop stands on its latest year), §7
`auto-rotation-controls` — see Decisions to revisit, §6 `color-dark-mode` (the register switch is the
layer's own `data-theme`), §5 (no overflow at 1920 or 390).

---

## Arrange

**Who it is for.** The keeper, once, deciding what this household's page shows.

**What is coherent.** There is **no drag anywhere** — the whole mode is three buttons per band — so
§1 `dragging-alternative`, §2 `drag-threshold` and §2 `gesture-alternative` pass by construction, and
they pass at 390 as well as 1440. Moving a band works and the new order renders immediately.

| id | P | skill | rule | reader | what happens | evidence | fix in one line | collides | status |
|---|---|---|---|---|---|---|---|---|---|
| **A1** | **P1** | High | §9 `modal-escape`, §1 `escape-routes` | keeper | `.arrbar` has **no CSS rule** (`grep '\.arrbar' dashboard.css` → nothing), so it is `position: static` at the end of `<body>`: measured at y **3,746** on a **3,789** px page. The mode's only instructions, its **Default** button and its **Done** button — the only thing that saves — are all below nine screens of content. Escape does nothing. | probe (`position:static, top:3746, inViewport:false`), `arrange_populated_1440_base.jpg` | Make the bar fixed. | no | **fixed** `4157d20` |
| **A2** | **P1** | High | §8 `error-recovery`, `undo-support` | keeper | ✕ hides an **issue** band and silently does nothing on `hero`, `index`, `place`, `loop` and `figures` — `render()` skips a hidden id without clearing the mount element `index.html` provides. Measured: hiding `issue:heat` removed it; hiding `place` left it VISIBLE. | probe `afterHideIssue`/`afterHidePlace`, `arrange_populated_1440_hide-attempt.jpg` | Clear the mount when the id is hidden. | no | **fixed** `4157d20` |
| **A3** | **P1** | High | §8 `error-recovery` | keeper | `#arr-restore` — *"Restore a hidden band…"* — is referenced **once, in `index.html`, and nowhere in `dashboard.js`**. It is never populated and never read. A hidden band can only come back via **Default**, which discards every other choice too. | `grep -n arr-restore app/static/*`, probe `restoreOptions` | Fill it, or remove it. | no | **fixed** `4157d20` |
| A4 | P1 | Medium | §8 `success-feedback` | keeper | Moving or hiding a band produces no toast, no announcement and no visible acknowledgement (`toast: "", on: false` after both). The only confirmation in the whole mode is at Done. | probe `toast` | Say what happened. | no | **fixed** `4157d20` |
| A5 | P1 | High | §9 `nav-state-active`, `state-preservation` | keeper | Leaving via the nav leaves the mode running: nine sets of ← → ✕ stay on the page, `arrbar.hidden` stays false, the nav says **Now**, and the work is lost on reload. | probe `leftArrange`/`afterReload`, `arrange_populated_1440_left-without-done.jpg` | End the mode on any view change. | no | **fixed** `4157d20` |
| A6 | P2 | Medium | §5 `content-priority` | keeper | Entering Arrange **changes the layout of the thing being arranged**: `arrangeControls()` prepends the bar as a grid child, so the hero's sentence moves into the right column and the numeral orphans. | `arrange_populated_1440_base.jpg` vs `now_empty_1440_base.jpg` | Overlay the bar, don't add a grid child. | no | open — P2 |
| A7 | P2 | Medium | §1 `aria-labels` | keyboard | The move buttons are labelled `Move up` / `Move down` and drawn `←` / `→`, and the instruction line says "← and → move a band". Three vocabularies for one action. `#arr-restore` has no label at all (`labelledRestore: false`). | `dashboard.js:1861`; `index.html:105` | One vocabulary. | no | open — P2 |
| A8 | P2 | Medium | §8 `disabled-states` | household | **Arrange** is in the nav for everyone, including a phone with no token. The mode runs, the bands move, and only at **Done** — nine screens down — does a toast say *"Arranging needs the admin token."* | `arrange_populated_390_base.jpg`; `dashboard.js:1887` | Say it on entry. | no | open — P2 |

**At 390** the mode works: the bar is 390×68 and does not overflow, and the controls are 42×43 —
above the 24 px floor, two pixels under the 44 pt advisory. Whether a phone should rearrange the
house's wall is a question for Tomas, not a finding.

`UI_LAYOUT` surviving a version update could not be tested — it needs two tagged releases on one
node — and nothing in the interface states it either way.

---

## The refused page

**Who it is for.** A phone on the house WiFi with no token, at the default `SHARE_LEVEL=off`.

**What is coherent.** On **Now**, the design works exactly as written: the shell renders, and the
node's own sentence explains itself rather than going blank.

What the stranger gets, measured from a non-loopback address (the host, which `_is_local` correctly
treats as remote):

| path | status | what comes back |
|---|---|---|
| `/` and `/static/*` | 200 | the whole shell, CSS, JS, fonts, the sign sprite |
| `/health` | **200** | `node`, `version`, `schema`, `uptime_s`, `lat 41.387`, `lon 2.169`, `polls`, `last_poll`, `ingested`, **`cell.id 8839446033fffff`, `res 8`, `edge_m 525`**, caption `THE CELL THIS NODE STANDS IN` |
| `/settings` | 200 | every key, label and help text; values masked to `UI_LAYOUT` and `SHARE_LEVEL` |
| `/presence` | 200 | `{"enabled": false}` |
| `/export` | 422 | (needs a day parameter) |
| `/issues`, `/place/geojson`, everything else | **403** | the node's sentence |

| id | P | skill | rule | reader | what happens | evidence | fix in one line | collides | status |
|---|---|---|---|---|---|---|---|---|---|
| R1 | — | — | no rule; check written here | stranger | **Moved to Decisions to revisit, item 7, with a corrected mechanism.** The cell is not the leak — it is 77× coarser than the coordinates beside it — and the coordinate precision is deliberate. | see Decisions to revisit | — | **yes — A12** | withdrawn on measurement — Decisions to revisit 7 |
| **R2** | **P0** | High | §8 `error-recovery` | household, stranger | The wall is black and Network is blank — L1 and W1, filed there. | `refused_wall_1920.jpg`, `refused_network_1440.jpg` | | no | **fixed** `e4a810a` |
| R3 | P1 | High | §8 `error-clarity`, §1 `consistent-help` | household, stranger | The refusal is written for a developer: *"this node is set to SHARE_LEVEL=off, so /issues answers only this machine or a request carrying a token. Set SHARE_LEVEL to open in the dashboard's Set up view…"* It names an environment variable, a route path and an action the reader — who by definition has no token — cannot take. `WORDS.refused` above it is the household sentence, and it is the only one of the two that is translated. | `refused_now_390.jpg` | Tell the reader to ask the keeper. | no | **routed to Tomas** — the 403's words are the node's and are copy |
| R4 | P2 | Minor | §1 `aria-prohibited-attr` | screen reader | axe `aria-prohibited-attr` serious ×1 on the refused Now view only. | axe `refused_now_390` | | no | **fixed** `3a2237f` |

---

## Cross-view

### 2.1 Vocabulary — one word per thing?

| thing | words in use | where | verdict |
|---|---|---|---|
| a message the node sent | **ask** (ρ, hero, wall), **alert** (`/alerts`, ledger `level`), **message** (Telegram) | `WORDS.rho`, `ledger`, `askStrip` | **two words on one screen**: the ρ caption says "14 of 28 **asks** answered" directly above a ledger whose column header is the **alert** level. Finding V1, P2 |
| another node | **peer** (`peers()`), **neighbour** (`ring.none`: "No neighbours yet"), **nearby** (`/nearby`), **other PLANETAI nodes** (`net.others`), **child** / **parent** (the tree) | `dashboard.js:1500`, `WORDS.ring`, `WORDS.net` | **"neighbour" means a public air station, "peer" means a PLANETAI node, "nearby" is the endpoint for the first.** Finding V2, P2 |
| a unit of map | **cell** (H3), **square** ("over this square of the map"), **cell** (Fab City Index cell), **tile** (not used) | `stamp`, node sentences, `cellRings` | **"cell" carries two unrelated meanings** — an H3 hexagon and an Index indicator — in the same product, one on Now and one on Network. Finding V3, P2 |
| how sure a number is | `live` · `partial` · `model` · `cached` · `example` | `ctx.pill`, Figures | **one word per thing, consistently, everywhere the pill appears.** Clean. |
| distance | room · yard · ring · region | `DISTANCES`, `labels` | clean, and translated by the node |

### 2.2 Controls

| view | control | does | confirms | keyboard | focus | 390 size | 24 px | 44 pt | name | rule |
|---|---|---|---|---|---|---|---|---|---|---|
| all | Now / Network / Set up / Wall | switch view | — | yes | 2px outline | 62–86 × 32 | ✓ | ✗ | text | §9 `nav-state-active` |
| all | Arrange | enter mode | no | yes | 2px outline | 81 × 32 | ✓ | ✗ | text | A5, A8 |
| Now | index row (×4) | anchor to band | — | yes | 2px outline | 354 × 76 | ✓ | ✓ | run-together | N14 |
| Now | **I did this** | POST /actions | prompt, then toast | yes | 2px outline | 76 × 36 | ✓ | ✗ | text | N10, N11 |
| Now | plan legend (×5) | toggle layer | no `aria-pressed` | yes | 2px outline | not reachable on pai-clean | — | — | text + swatch | unverified |
| Now | satellite play / slider / what changed | run the years | `aria-pressed` on mode only | yes | 2px outline | not reachable on pai-clean | — | — | `aria-label` | unverified |
| Set up | admin / act token | unlock | toast on a wrong one | yes | 2px outline | 320 × 39 | ✓ | ✗ | **placeholder only** | S9 |
| Set up | Unlock / Back | gate | — | yes | 2px outline | 79 × 43 | ✓ | ✗ | text | — |
| Set up | group tab (×9) | switch group | — | yes | 2px outline | — | ✓ | — | text | S4 |
| Set up | switch (×10 keys, ×N packs) | toggle a setting | no | yes | 2px outline | — | ✓ | — | **none** | **S2 critical** |
| Set up | locale select | set language | no | yes | 2px outline | — | ✓ | — | **none** | **S1 critical** |
| Set up | Save changes | PUT /settings | toast, 4.2 s | yes | 2px outline | — | ✓ | ✓ | text | S3, S10 |
| Set up | Lock | clear tokens | no | yes | 2px outline | — | ✓ | — | text | — |
| Arrange | ← → ✕ (×27) | move / hide | **no** | yes | 2px outline | 42 × 43 | ✓ | ✗ (2 px) | `aria-label` ≠ glyph | A2, A4, A7 |
| Arrange | restore select | **nothing** | — | yes | 2px outline | — | ✓ | — | **none** | **A3** |
| Arrange | Default / Done | reset / save | toast | yes | 2px outline | below the fold | ✓ | — | text | A1 |
| Wall | **Now** (exit) | leave the wall | — | yes | 2px outline | — | ✓ | ✗ | text | R6 collision |

**Nothing measured anywhere is under the WCAG 2.2 `web-target-size` floor of 24 px.** Everything in
the header nav and the two act buttons is under the 44 pt `touch-target-size` advisory.

**After the fixes** the keyboard-reachable surface of Now went from **11 tab stops to 26** — the
Figures table, both token reveals, the Arrange restore menu and every named form control joined it —
and every one of them still measured a `solid 2px` focus outline.

### 2.3 Status and time

| surface | says when | says stale | rule |
|---|---|---|---|
| header, live | `As of HH:MM` in the **viewer's** locale and timezone, plus a `live`/`cached` pill whose timestamp is hover-only | via the pill word | W4, H7 |
| header, fixture | **nothing** — the fixture has no `as_of` and no `city`, so the place line is empty | `cached`, always | H7 |
| header, refused | `As of …` absent; the pill says **`live`** | — | **W2** |
| per figure | the Figures band carries `as_of` per row; source cards carry "last reading N min ago" | the pill word | clean |
| wall | **nothing** | the word `stale`, 11 px, illegible at three metres | **L3** |

One rule, not kept: the page has three different ways of saying how old a number is, and the wall —
the surface most likely to be showing an old number — has the weakest of them.

### 2.4 The tester's first hour

| step | clicks | where it stops |
|---|---|---|
| `planetai setup` → open the page | — | The address comes from the terminal. The interface never prints it (**S12**). |
| first open | 0 | The hero reads a confident model number; room/yard/ring are three em-dashes labelled "not watched here", which is the wrong sentence for a node whose sensors are not connected yet (**N8**). |
| add the first sensor | 3 (Set up → unlock → Sources) | Every field is unlabelled (**S1**), the value box is blank where a default applies (**S8**), and a wrong value returns `Could not save (400)` (**S3**). |
| first sensor arrives | 0 | Nothing on the page marks the arrival, and no empty state changes wording between "no sensor" and "first reading". |
| first ask | 0 | — |
| close the loop | 2 | `prompt()` opens before the token check, so the note is typed and then discarded (**N10**). |
| read the report | 1 | The loop band says `no report yet` with no indication of when one is due (**N9**). |
| turn the wall on | 2 | The Wall button works. `SHARE_LEVEL` defaults to `off`, so the second screen the tester opens is **black** (**L1**), and the setting that fixes it is a free-text box (**S5**) with no LAN address beside it (**S12**). |

Seven of the eight steps have a moment where the page could have said what to do next and did not.
The two that are handled well — the place and forecast empty states, which name the exact command —
show that the house style for this already exists.

### 2.5 Locales

**Fixed in `ece79b7`; what follows is what this section found before that, and what the first real
render in three languages then showed.**

id and es were captured at 390 and 1920, on the fixture and on live data with `ALERT_LOCALE=es` set
on the node. **Every one rendered in English** (`now_populated_390_locale-id.jpg`,
`wall_populated_1920_locale-es.jpg`, `now_live_390_locale-es-node.jpg`). This is N3, and it makes the
other locale checks unanswerable: no placeholder can be left unfilled and no sentence can overflow a
card in a language the page cannot reach.

Two consequences worth recording separately:

- The `WORDS` table's id and es branches — several hundred lines, marked in the source as
  assistant-written and unread by a native speaker — have **never been rendered**.
- A design round using `?fixture=` cannot see any locale but the fixture's own, and the one committed
  fixture is `en`. The locale layer has no proving surface. **Still true, and now self-correcting**: a
  fixture keeps rendering in its own captured locale — which is what keeps `?fixture=` renderable with
  no network call — and a snapshot taken from now on carries the node's locale in its health block.

**What the first render in Bahasa and Spanish showed** (`FIX2_now_live_390_locale-id.jpg`,
`FIX2_wall_live_1920_locale-es.jpg`). The hero, the issue names, the distance labels, the band
sentences and the chrome all follow. Four of this file's own empty states were still English and are
now in `WORDS` (`eaad3c4`). **Five strings remain English on an otherwise translated page, and none
of them was mine to write**: the line's source (`WHO 2021 global air quality guidelines, 24-hour
mean`), a stack cell's source (`CAMS air quality (model point sample)`) and the cell caption (`THE
CELL THIS NODE STANDS IN`) all come from the node; the five nav labels and the five state words are
the product's own vocabulary. The last of those needs a decision before it needs a translation — a
state word may be a word or it may be a token, and it is rendered as both today.

### 2.6 Weight

| | |
|---|---|
| first load, Now, 1440 | **379,525 B**, and **411,978 B** after the fixes — of which the two variable `.ttf` faces (Funnel Sans, Figtree) are the bulk |
| one refresh | **46,008 B**, and **48,556 B** after the fixes, against the §2.7 budget of 60 kB — **13 API calls every 20 s** |
| kiosk, per day | 46 kB × 4,320 refreshes ≈ **199 MB/day**, plus the satellite frames once per document load |
| fonts | **self-hosted** — the `HANDOFF` item "Figtree and Funnel Sans still load from Google Fonts" is **fixed**. They are `.ttf`, not `.woff2`, which is roughly twice the bytes for the same faces. |
| render-blocking | three stylesheets in `<head>`, all local; `dashboard.js` is a plain `<script>` at the end of `<body>` |
| Fast 3G (1.6 Mbps, 150 ms) | Now: DOM 1.81 s, sentence **2.42 s**, settled 3.37 s · Network 2.83 s · Wall 2.42 s |
| one 404 on every load (**still open** — X1) | `GET /static/fonts/jetbrains-mono-latin.woff2` → **404**, from `planetai-theme.css:27`'s `@font-face src:url("fonts/…")`. Silent: the same face is served from `/static/jetbrains-mono-latin.woff2` by a second rule, so nothing looks broken and the mono renders. Finding **X1, P2**, §3 `font-loading`. The other console error on a live node is `GET /place/geojson` → **403**, which is correct and by design — the plan is refused without a token at every share level and the card says so. |

### 2.7 Coverage

Findings per section, per view. "clean" means walked and nothing found. Denominator: the 217 rule ids
in the appendix.

| | header | Now | Network | Set up | Wall | Arrange | refused |
|---|---|---|---|---|---|---|---|
| §1 Accessibility | 4 (H2,H3,H6,H7) | 3 (N5,N6,N14) | 2 (W6,W7) | 3 (S1,S2,S7) | 1 (L7) | 1 (A7) | 1 (R4) |
| §2 Touch & Interaction | clean | 2 (N10,N15) | clean | clean | clean | clean | clean |
| §3 Performance | clean | clean | clean | clean | clean | clean | clean (X1 is cross-view) |
| §4 Style Selection | clean | clean | clean | clean | clean | clean | clean |
| §5 Layout & Responsive | 1 (H4) | 1 (N13) | clean | clean | clean | 1 (A6) | clean |
| §6 Typography & Colour | 1 (H9) | 1 (N1) | clean | clean | 1 (L4) | clean | clean |
| §7 Animation | clean | clean | 1 (W3) | clean | clean | clean | clean |
| §8 Forms & Feedback | clean | 3 (N9,N10,N11) | 1 (W1) | 8 (S3,S4,S5,S6,S8,S9,S10,S13) | 2 (L1,L5) | 4 (A1,A2,A3,A4) | 2 (R2,R3) |  <!-- R1 withdrawn -->
| §9 Navigation | 4 (H1,H5,H6,H4) | clean | 1 (W7) | 1 (S4) | clean | 2 (A1,A5) | clean |
| §10 Charts & Data | clean | 5 (N2,N4,N7,N8,N16) | 1 (W5) | clean | 1 (L2) | clean | clean |

Sections with a finding in no view: **§4 Style Selection** — the language gate (`check_ui.py`) already
enforces this category and passes. **§3 Performance** — measured and within budget everywhere.

**After the fixes**, of the 64 findings in the tables above: **44 closed**, 2 half (N9, L3), 1
withdrawn (R1), 1 routed to Tomas (R3), and **16 open — every one of them P2 or advisory**. The open
list, in full: H3 `skip-links`, H8 the header is not sticky, N13 chip reflow at 390, N14 the index
rows' run-together accessible names, N15 the 44 pt advisory, N16 hover-only `<title>` tooltips, W5 an
em dash where a zero belongs, W6 the network figure's six facts hidden from a screen reader at width,
S10 the save button has no in-flight state, S13 the form is not a `<form>`, L2 the wall names no
source and no provenance word, L5 the wall's bare empty states, L6 the wall prints the cell caption,
A6 Arrange relays the hero it is arranging, A7 three vocabularies for one action, A8 Arrange runs
without a token and only says so at Done, and X1 the font 404 on every load.

**L2 is the one to look at first.** It is a P0 in the tables and it is still open: the wall shows a
model estimate in 120 px type and never says `model`, because `ANATOMY.wall` carries no `chips` and
`miniStack` — which holds the pills — is not on it. Putting a source and a word on the wall is a
composition decision about the most designed surface in the product, which is why it was not taken
here.

**Searches run** (query · domain · top result · used):

| query | domain | top result | verdict |
|---|---|---|---|
| `focus states` | ux | Interaction / Focus States (High) | proof query, passed |
| `number formatting units` | chart | Performance vs Target / Gauge | **off-topic, dropped** — matched a chart type, not a formatting rule |
| `uppercase label legibility` | ux | Content / **Compact Label Overflow** (High) | used for N13 |
| `text case transform meaning` | ux | Animation / Transform Performance | **off-topic, dropped** — "transform" matched CSS transforms |
| `missing data gaps line chart` | chart | Data Type **Trend Over Time** / Line Chart | used for N2 and N4 (its A11y Fallback row) |
| `time axis labels` | chart | Trend Over Time / Line Chart | same row, used for N4 |
| `chart empty state` | chart | Performance vs Target / Gauge | **off-topic, dropped** |

Retries were one per concern, as the contract requires. Three queries were dropped after one retry
and the finding written against the code and the layer instead; each is marked "no rule; check
written here" in its row. `--design-system`, `--stack` and the `style`/`color`/`typography`/`landing`/
`gsap`/`icons`/`google-fonts` domains were not run.

---

## The known list

| # | source | item | status at v0.52 | evidence |
|---|---|---|---|---|
| K1 | AUDIT § dashboard, review §1.7 | `MG/M³` on the wall from `text-transform:uppercase` on µ | found **REGRESSED** — on the Now hero and every band head as well as the wall — and **now closed** (`7745e01`), with a gate in `check_ui.py` and three mutations in `tests/test_check_ui.py` | N1 |
| K2 | AUDIT § dashboard, review §1.7 | `?only=` with an unknown name blanks the page | **FIXED** — falls back to the whole page | `dashboard.js:1653`, probe `onlyUnknown` |
| K3 | AUDIT § dashboard, review §1.7 | SMIL animations ignore reduced motion | **FIXED** — 0 SMIL nodes; all motion is CSS and stops | probe `reducedMotion` |
| K4 | AUDIT § dashboard, review §1.7 | 11 of 15 SVGs with no accessible name | **FIXED** — every SVG carries `role="img"` + `aria-label` or `aria-hidden` | axe: no `svg-img-alt` violations |
| K5 | AUDIT § dashboard, review §1.7 | 246 MB a day in kiosk mode | **FIXED** — 46 kB/refresh ≈ 199 MB/day, and the 7 MB of frames load once per document | probe `bytes` |
| K6 | AUDIT § dashboard, review §1.7 | an unhealthy model number painted in the clean colour on an empty node | **FIXED** — colour is a role; `crossed_` drives the red and it comes from the node's own line | `now_empty_1440_base.jpg` |
| K7 | AUDIT § dashboard | the Now view's cards carry no provenance | **FIXED** — every stack cell and every Figures row carries a pill | `now_empty_1440_base.jpg` |
| K8 | AUDIT § dashboard | `#earth-prov` hard-coded to `Derived` | **FIXED** — the component is gone; the satellite cards take their word from the data | `dashboard.js:1000` |
| K9 | AUDIT § dashboard | the Neighbourhood band opens on nothing | **FIXED** — `planCard` returns '' when the table does not exist | `dashboard.js:1046` |
| K10 | AUDIT § dashboard | `layoutReset` clears localStorage but not `UI_LAYOUT` on the node | **FIXED** — reset writes the same empty `UI_LAYOUT` | `dashboard.js:1885` |
| K11 | AUDIT § dashboard | the wall says nothing about how old the reading is or where it came from | **STILL PARTLY** — the wall says *when* now (`47beab1`); it still names no source and no provenance word | L2, L3 |
| K12 | AUDIT § dashboard | tabular figures miss SVG text | **FIXED** — `.num,.mono` carries `font-variant-numeric:tabular-nums` (`dashboard.css:66`) and the SVG text nodes carry `class="mono"`, so it applies. Measured on the rendered page: `svg.scale text.mono` computes `tabular-nums`. I first filed this as still-there from reading the code; the measurement says otherwise. | measured, `dashboard.css:66` |
| K13 | review §1.1 | the headline is chosen by metric, not by what matters | **FIXED** — `/issues` picks the headline by state; the hero and the ask strip carry the same issue by construction | `dashboard.js:1327` |
| K14 | review §1.2 | one issue's evidence spread across four bands | **FIXED** — the Stack puts all four distances on one row and one scale | `now_empty_1440_base.jpg` |
| K15 | review §1.3 | six card grammars | **FIXED** — `COMPONENTS` + `ANATOMY`; a band is a list of named components | `dashboard.js:681`, `:1136` |
| K16 | review §1.4 | numbers without a comparison | **MOSTLY FIXED** — the Stack and the line supply "compared to what" for sensed issues; context readouts (coast, land) still carry a number with a source and no comparison | `now_empty_1440_base.jpg` |
| K17 | review §1.5 | the page is the dark register everywhere | **FIXED** — paper by default, dark on the wall — except H9, where `?theme=dark` leaks into Now | H9 |
| K18 | review §1.5 | ρ as a radial gauge | **FIXED** — one sign per ask, answered first | `now_populated_390_fold.jpg` |
| K19 | review §1.5 | staggered entrances, hover lifts, grain overlay | **FIXED** — none in `dashboard.css` | `check_ui.py` pass |
| K20 | review §1.5 | Google Fonts on a LAN page; mono declared `100 800` | **FIXED** — all three faces self-hosted; see X1 for the two dead requests that remain | probe `bytesPaths` |
| K21 | review §1.5 | coloured status dots carrying state by hue | **FIXED** — state is a word, `.state`/`.iss` | `now_empty_1440_base.jpg` |
| K22 | review §1.5 | emoji parsed out of alert text | **FIXED** — `plain()` strips them; decision 18 | `dashboard.js:672` |
| K23 | review §1.6 | trust in the room band; the report above the readings | **FIXED** — trust is in the place band, the report in the loop band | `ANATOMY` |
| K24 | HANDOFF finding 1 | `node-ground.svg` is node #1's cell on every node | **FIXED** — `/static/node-ground.svg` is generated from `NODE_LAT`/`NODE_LON`; the shipped fallback claims nothing | `app/main.py:1503` |
| K25 | HANDOFF "not touched" | `.hero .tri`, the three-colour ribbon | **GONE** — no `.tri` in the CSS | `grep` |
| K26 | design-log, six violations | clip-path hexagons, iso mesh, web-green, glow, rounded pills, orange act button | **ALL SIX GONE**, held by `check_ui.py` | gate pass |
| K27 | LANGUAGE_GAP check 8 | the dashboard does not speak the state vocabulary | **STILL TRUE**, and recorded there as a design round rather than a bug | — |

One of the twenty-seven is open as written (K11, partly), one has regressed (K1), and one was already
routed to a design round (K27). The other twenty-four are closed.

---

## What the fixing found that the review did not

Eleven commits against these findings turned up five things worth recording, because each one is a
place where a method failed rather than a place where code was wrong.

1. **`tools/check_ui.py`'s hidden-vs-display rule was blind to how this renderer hides things.** It
   matched `$('#x').hidden =` and `const x = $('#x')`, and `dashboard.js` writes
   `getElementById('x').hidden =` — which is every hide in the file. I found this by shipping the
   exact bug the rule exists for: a `display:flex` on `.arrbar` that un-hid the Arrange bar on every
   view, past a green gate. Widening the rule caught mine **and a pre-existing one**: `#setup-body`
   has been un-hidden by `.setup{display:grid}` since the renderer landed, which is why the locked
   Set up screen kept putting its empty heading, its blurb and its save bar into the accessibility
   tree behind the unlock card. That is finding S11, and nobody had connected it to its cause.
2. **Two gates for finding N1 were written and thrown away before one worked.** Looking backwards
   from the node's prose for its enclosing class found a *sibling's* `class="state"` and passed the
   markup that shipped `MG/M³`; looking forwards read one component's prose as the next one's.
   Template literals are not a DOM. The gate that ships is three string checks and a tripwire on any
   new `text-transform:uppercase` rule — a parser there would have been bigger than the defect.
3. **A chart that stretches cannot keep its text inside itself.** The axis labels for N4 went into
   the day chart's SVG, which carries `preserveAspectRatio="none"` over a 720-unit viewBox: at 390
   that is a 0.49 horizontal scale, so a 10 px label rendered at about five real pixels. They are
   HTML beside the drawing now. The same trap is still live in `scale()`, which also puts 10 px text
   in a scaled SVG — **not fixed, and not in this review's findings; it should be.**
4. **The same contrast mistake was made twice in one afternoon, in two different colours.** `.done`
   was `--rings` green at about 3.1:1 and the chart's line label was `--signal-worse` red at about
   4:1 — both right for the mark they name and both under AA as 11–13 px type. Neither was caught by
   reading the stylesheet; both were caught by axe on the rendered page. The rule worth keeping: a
   role colour belongs to the drawn thing, not to the words beside it.
5. **A harness can lose the very thing it is testing.** The scroll restore for H4 measured as broken
   because Playwright scrolls a control into view before clicking it. A reader hits the same wall for
   a different reason — the header is not sticky (H8), so reaching the nav means scrolling to the top
   anyway. The restore is verified through `show()` and the browser's own Back button instead, and
   H8 matters more than its P2 says.

## Where the skill and the language disagree

Read from `planetai-design/references/planetai-layer.md` and `decisions/design-log.md` against Quick
Reference §2, §4, §6 and §7 **before** the walk. None of these is filed as a finding.

| skill rule | what the layer says | clause |
|---|---|---|
| §7 `spring-physics`, `duration-timing`, `exit-faster-than-enter`, `stagger-sequence`, `hierarchy-motion`, `motion-consistency` | Motion is bound to the cadence of its own datum, not to a feel. Six tokens, each named after a datum. A motion with no datum is **deleted**, not tuned. | layer §Reduced motion; design-log R6 |
| §7 `fade-crossfade` | The satellite years are a **hard cut, never a cross-fade or a morph** — an interpolated frame is a year that never existed. | design-log R6, Decision 2 |
| §7 `loading-states`, §3 `progressive-loading` (skeleton shimmers) | A card that goes blank "reads as a broken node rather than a private one": the page draws the node's own sentence instead of a placeholder. | `dashboard.js:1005` |
| §7 `auto-rotation-controls` / §1 same | **The wall is an instruction, not a control. No buttons on the wall.** The satellite loop therefore has no pause on the wall, by decision. | design-log R6; `dashboard.js:1372` |
| §2 `hover-vs-tap`, `press-feedback`, `cursor-pointer` | Hover is not a feedback channel on a surface nobody touches; the wall has no pointer. Hover states as a primary signal are out. | design-log R6 |
| §4 `no-emoji-icons` — **agrees**, and the language goes further | Signs are lifted or built on a 24-unit grid and must read at `--sign-floor` 12 px; emoji in alert text are stripped to words (decision 18). | layer `--sign-floor`; design-log R9 |
| §4 `color-palette-from-product` | **Colour is an argument, not an accent.** Green = a loop closed, red = a line crossed, blue = data or identity, orange = what only the satellite knows, everything else ink. A hue may not be spent on decoration or on a category. | design-log R5, R9 |
| §6 `color-dark-mode`, `color-accessible-pairs` | Two registers with **guards**, not a palette inversion: `#7FA5E8` may appear only under `[data-theme="dark"]`, `#20388D` never on ink, `#DB7200`/`#FF931E` split by register. Checked by `test/theme.test.js`. | layer §Guards |
| §6 `truncation-strategy` | Provenance is a glyph **and a word**, ink only, square — never a coloured pill and never a colour alone. | layer `--prov`; design-log R5 violation 5 |
| §5 `spacing-scale` (a 4/8 pt scale) | Spacing comes from the programme layer and `clamp()`, not from a modular scale; the HANDOFF records that layout, spacing and the type scale were deliberately left alone. | HANDOFF § "What I did not touch" |
| §10 `chart-type` (gauges for a KPI vs target) | **No gauges.** A proportion drawn as arc length is forbidden outright; things are counted, not sized. The Index dials were deleted, not resized. | design-log R7; LANGUAGE_GAP check 4 |
| §5 `scroll-behavior` (smooth scroll) | Nothing in the language asks for it and nothing implements it; the anchor jump is instant. No clause either way — **the skill's rule stands and is not violated**. | — |

Where the language is silent — heading structure, form labelling, deep linking, keyboard escape,
error placement, chart axes, locale delivery — the skill's rule stands, and every finding above sits
in that space.

---

## Decisions to revisit

Not bugs. Each is a place where the walk found a real cost attached to a settled decision.

1. **R6: "the wall is an instruction, not a control", against §7/§1 `auto-rotation-controls`.** The
   satellite loop on the wall auto-advances every 4 s with no pause, which the skill treats as a
   High-severity failure for anyone who cannot read at that pace. The wall already carries one
   control — the `Now` exit, added because "a laptop that reached the wall from the nav has no other
   way back" (`dashboard.js:1370`). The decision has one exception already; whether legibility earns a
   second is Tomas's. Evidence: `wall_populated_1920_base.jpg`, `dashboard.js:1372`.
2. **R6 "a motion with no datum is deleted", against the Network figure's wires and dot** — restored
   "by Tomas's call: the figure is of a thing at work, and drawn still it read as a diagram of one"
   (`dashboard.js:1400`). The walk found the cost: on a **fresh** node the wires and the travelling
   dot animated along links carrying `0 sensors` and `0 public stations`, out to `nowhere yet`. The
   tester's first Network view showed an instrument at work that is not working. Evidence:
   `network_empty_1440_base.jpg`. **Half-settled in `1c446db`**: a link with nothing on it keeps its
   wire, as a dashed hairline, and loses its dot. That treats the zero case as outside the decision.
   The decision itself — a dot travelling along a link that is merely *slow* rather than empty, at a
   300 s poll — is untouched and still Tomas's.
3. **Decision 11 — "quiet issues collapse to their index line on the wall and at phone width" —
   against `none`-state issues at 1440.** An issue in state `none` gets a full band with a
   headline-sized sentence: on the fresh node, `No marine model for this point` occupies a screen.
   The collapse rule names `quiet`; `none` was not decided. Evidence: `now_empty_1440_base.jpg`.
4. **Decision 15 — "paper by day, dark on the wall" — against `?theme=dark` persisting into Now.**
   Filed as H9 because the leak looked unintended, but the parameter is deliberate and a keeper may
   want a dark Now view. **`4157d20` made the register follow the view**: `?theme=dark` still boots
   the wall, and no other view is dark any more. That is a choice made on Tomas's behalf and it is
   the one to overturn first if a dark Now was ever wanted. Evidence:
   `now_populated_1440_dark-leak.jpg`.
5. **Decision 2 — the satellite frames are "brightness matched across years", to be said on the
   surface** — against the wall's satellite card, which carries the credit lines but was captured
   empty on both test nodes, so the claim could not be seen in place. Not a finding; a gap in
   evidence. Evidence: `wall_populated_1920_base.jpg` (`no frames yet`).
6. **The wall shows the cell caption.** `stamp` is in `ANATOMY.wall` by R5's anatomy. On a screen
   visible from outside the house it publishes a 0.72 km² location — coarser than the street, and
   coarser than what `/health` already answers. Evidence: `wall_empty_1920_base.jpg`.
7. **The fixes made four more choices that are really Tomas's**, all small and all reversible.
   Timestamps are formatted 24-hour in the node's own timezone rather than the household's locale
   (`1c446db`) — right for a mono numeric field, wrong if a household reads 12-hour. `settings.OUTWARD`
   is fourteen keys chosen by me (`47beab1`); the set is a product judgement and the list is in
   `app/settings.py` to be argued with. The stack says `nothing here yet` where it said `not watched
   here` — truer on a fresh node, but it is copy. And every string the fixes added — the Arrange
   toasts, `leaves this machine`, `24 h ago`, `Open this on another screen in the house` — is in my
   voice, in three languages, and none of it has been read by a native speaker of two of them.
8. **A12 — "3 decimals, for every caller at every level" — against `RETICULUM_PRESENCE_RES`'s floor of
   res 6.** Measured at node lat 41.3874: `/health`'s rounded point is **0.0093 km²** (111 × 84 m);
   the res-8 cell published beside it is **0.716 km²**, so the cell adds nothing — `app/main.py:772`
   is right about that, and about 5 decimals being the doorway. What it does not address is that the
   *same node* refuses to **announce** a cell finer than res 6 — **35.1 km²** — because *"a node
   announcing its street to an open radio network is not a thing anyone should be able to do by
   typing a number"* (`app/main.py:786`). So the node answers a tokenless caller on the WiFi with a
   position ~3,800× more precise than the finest thing it will say about itself over radio, at the
   share level named `off`. Both behaviours are deliberate and neither is a bug; whether they should
   agree is Tomas's. The counter-argument is on the record too: `/export` has always published 3 dp
   under CC BY, so lowering `/health` alone would not make the position private. Evidence: `curl
   /health` from a non-local address; `app/main.py:772`, `:786`, `app/settings.py:82`.

---

## What could not be verified

- **The wall in a real room at three metres.** The check here is a quarter-scale render, which
  approximates angular size and not contrast under room light, viewing angle, or a glossy panel. O2
  and O10 in the layer record the same gap from the design side. The check itself is mine; the skill
  has no rule for this reader.
- **Live data.** Everything above ran on pai-clean against a committed fixture and a fresh node. No
  reading in this document came from node #1 or node #2, and neither was contacted.
- **The plan card's legend and the satellite card's controls.** Unchanged by the fixes and still
  unverified. Both need `planetai run place refresh` and `planetai run earth-engine timelapse` to have run. Neither pack had data on pai-clean,
  so five legend toggles and three satellite controls are in the control table as **unverified** —
  including whether `aria-pressed` is set on the layer toggles, which the code says it is not.
- **A native reader for `id` and `es`.** Was moot at v0.52 because the page could not render either
  (N3). It renders both now, so this is no longer moot and is the largest unverified thing in the
  document: several hundred lines of assistant-written Bahasa and Spanish, plus everything the fixes
  added, rendered for the first time and read by nobody who speaks them.
- **Node #2's actual screen.** Out of scope by the brief and not contacted.
- **`UI_LAYOUT` across a version update.** Needs two tagged releases on one node.
- **The act loop end to end.** `POST /actions` was exercised against a fixture alert id, which the
  node correctly refuses. A real closed loop on a real alert was not available on pai-clean, so N11
  is evidenced by the node's 404 and the page's message, not by a closed ring — **and that is still
  true after the fix**: the message it now shows is the node's own 404 sentence, verified, but a ring
  actually closing has not been seen on this rig.
- **The skill's version.** No `skill.json` exists in this install; see the header.
- **Checks I wrote because the skill has none:** the wall at three metres (L1–L3, L6), the stranger's
  read of `/health` (R1), a case transform that changes a unit (N1), a setting that changes what
  leaves the machine (S6), and the LAN address a keeper needs (S12).

---

## Appendix A — the rule ids walked

217 ids, extracted from `references/quick-reference.md` §1–§10. This is the denominator for the
coverage table.

**§1 Accessibility (25)** `color-contrast` `focus-states` `alt-text` `aria-labels` `icon-context`
`keyboard-nav` `form-labels` `skip-links` `heading-hierarchy` `color-not-only` `dynamic-type`
`reduced-motion` `voiceover-sr` `escape-routes` `keyboard-shortcuts` `focus-not-obscured`
`focus-not-obscured-enhanced` `focus-appearance` `dragging-alternative` `web-target-size`
`consistent-help` `redundant-entry` `accessible-authentication` `auto-rotation-controls`
`contextual-live-badge-updates`

**§2 Touch & Interaction (17)** `touch-target-size` `touch-spacing` `hover-vs-tap` `loading-buttons`
`error-feedback` `cursor-pointer` `gesture-conflicts` `tap-delay` `standard-gestures`
`system-gestures` `press-feedback` `haptic-feedback` `gesture-alternative` `safe-area-awareness`
`no-precision-required` `swipe-clarity` `drag-threshold`

**§3 Performance (19)** `image-optimization` `image-dimension` `font-loading` `font-preload`
`critical-css` `lazy-loading` `bundle-splitting` `third-party-scripts` `reduce-reflows`
`content-jumping` `lazy-load-below-fold` `virtualize-lists` `main-thread-budget`
`progressive-loading` `input-latency` `tap-feedback-speed` `debounce-throttle` `offline-support`
`network-fallback`

**§4 Style Selection (12)** `style-match` `no-emoji-icons` `color-palette-from-product`
`effects-match-style` `platform-adaptive` `state-clarity` `elevation-consistent` `dark-mode-pairing`
`icon-style-consistent` `system-controls` `blur-purpose` `primary-action`

**§5 Layout & Responsive (18)** `viewport-meta` `mobile-first` `breakpoint-consistency`
`readable-font-size` `line-length-control` `horizontal-scroll` `spacing-scale` `touch-density`
`container-width` `z-index-management` `fixed-element-offset` `scroll-behavior` `viewport-units`
`orientation-support` `content-priority` `visual-hierarchy` `compact-label-overflow`
`chip-collection-reflow`

**§6 Typography & Colour (17)** `line-height` `line-length` `font-pairing` `font-scale`
`contrast-readability` `text-styles-system` `weight-hierarchy` `color-semantic` `color-dark-mode`
`color-accessible-pairs` `color-not-decorative-only` `truncation-strategy` `letter-spacing`
`number-tabular` `whitespace-balance` `heading-line-balance` `long-token-wrapping`

**§7 Animation (22)** `duration-timing` `transform-performance` `loading-states` `excessive-motion`
`motion-meaning` `state-transition` `parallax-subtle` `spring-physics` `exit-faster-than-enter`
`stagger-sequence` `shared-element-transition` `no-blocking-animation` `fade-crossfade`
`scale-feedback` `gesture-feedback` `hierarchy-motion` `motion-consistency` `opacity-threshold`
`modal-motion` `navigation-direction` `layout-shift-avoid` `cancellable-state-transitions`

**§8 Forms & Feedback (31)** `input-labels` `error-placement` `submit-feedback` `required-indicators`
`empty-states` `toast-dismiss` `confirmation-dialogs` `input-helper-text` `disabled-states`
`progressive-disclosure` `inline-validation` `input-type-keyboard` `password-toggle`
`autofill-support` `undo-support` `success-feedback` `error-recovery` `multi-step-progress`
`form-autosave` `sheet-dismiss-confirm` `error-clarity` `field-grouping` `read-only-distinction`
`focus-management` `error-summary` `touch-friendly-input` `destructive-emphasis`
`toast-accessibility` `aria-live-errors` `contrast-feedback` `timeout-feedback`

**§9 Navigation Patterns (26)** `bottom-nav-limit` `drawer-usage` `back-behavior` `deep-linking`
`tab-bar-ios` `top-app-bar-android` `nav-label-icon` `nav-state-active` `nav-hierarchy`
`modal-escape` `search-accessible` `breadcrumb-web` `state-preservation` `gesture-nav-support`
`tab-badge` `overflow-menu` `bottom-nav-top-level` `adaptive-navigation` `back-stack-integrity`
`navigation-consistency` `avoid-mixed-patterns` `modal-vs-navigation` `focus-on-route-change`
`persistent-nav` `destructive-nav-separation` `empty-nav-state`

**§10 Charts & Data (30)** `chart-type` `color-guidance` `data-table` `pattern-texture`
`legend-visible` `tooltip-on-interact` `axis-labels` `responsive-chart` `empty-data-state`
`loading-chart` `animation-optional` `large-dataset` `number-formatting` `touch-target-chart`
`no-pie-overuse` `contrast-data` `legend-interactive` `direct-labeling` `tooltip-keyboard`
`sortable-table` `axis-readability` `data-density` `trend-emphasis` `gridline-subtle`
`focusable-elements` `screen-reader-summary` `error-state-chart` `export-option`
`drill-down-consistency` `time-scale-clarity`

**Ids the brief named that are spelled differently in the Quick Reference**, mapped so the rows above
can be checked: `password-visibility` → `password-toggle`; `autofill` → `autofill-support`;
`focusable-error-summary` → `error-summary`; `error-messages` → `error-clarity`;
`confirmation-messages` → `success-feedback` / `confirmation-dialogs`; `input-affordance` →
`input-helper-text` / `input-type-keyboard`; `continuous-animation` → `excessive-motion`;
`date-formatting` → **no such id** (W4 is filed against `contextual-live-badge-updates`).

## Appendix B — how to reproduce

```
limactl shell pai-clean            # both containers run there, built from v0.52's app/
  uxreview  :8081  bootstrapped, SHARE_LEVEL=open, placeholder ADMIN_TOKEN/ACT_TOKEN
  uxempty   :8082  BOOTSTRAP=0, PACKS_ENABLED=none — the tester's fresh node
```

The capture harness is in the session scratchpad, not in either repo; it imports Playwright and
axe-core from `planetai-design/node_modules` and writes only into the shot library. It reads the
node over HTTP and changes nothing on it, except two settings rows on `:8081` (`SHARE_LEVEL`,
`ALERT_LOCALE`) which were set and restored.
