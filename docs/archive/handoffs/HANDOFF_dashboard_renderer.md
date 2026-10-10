# Handoff: the dashboard as a modular renderer (Release 2 of prompt 5b)

11 September 2026. Branch `the-dashboard-draws`, worktree `planetai-node-dashboard/`.

**`bash tests/all` is 31 of 31 and `make lint` passes.** The page has been rendered in a browser —
`docs/design/shots/` — and **nothing has been seen by a person other than Tomas, and nothing has
reached a beta tester.** §2.9's rule stands.

What is left is at the bottom, under "Still open".

Release 1 (`GET /issues`, the four issue declarations, the engine) shipped in **v0.44** and is live
on node #1. Read `docs/archive/handoffs/HANDOFF_issues.md` first — it carries the information model, the five things
the original brief had wrong, and the decisions this release is built on.

## Where to stand

```bash
cd "planetai-node-dashboard"          # a worktree; the main checkout has another session in it
git log --oneline origin/main..HEAD
bash tests/all                        # 31 of 31
make lint                             # includes check_theme now, and it fails rather than reports
python3 tools/shots.py                # renders every fixture, four widths, Now and the wall
```

`planetai-node/` (the main checkout) is a **different session's** working tree — the earth-cache
task. Leave it alone. If you need another tree, make another worktree.

## What is done

**The three files exist and the page is three files.**

| file | what |
|---|---|
| `app/static/index.html` | a skeleton: head, header, four view shells, mount points, Arrange bar, one `<script>`. No logic, no style. |
| `app/static/dashboard.css` | 283 lines, ported from the prototype, re-scoped from `.pai` to the node's `html[data-theme]`. No data URI, no CDN. The only literals are the four page-local tokens the layer does not name (`--mute --dim --hair --raise`). |
| `app/static/dashboard.js` | ~1,050 lines. `snapshot()` · `COMPONENTS` (20) · `COMPOSITES` (5) · `ANATOMY` · `layout()` · `render()` · `ctx`. |

**The contract holds.** `snapshot()` is the only fetcher. `render()` is the only DOM writer. Every
component is `(data, ctx) => string`, carries `data-component`, draws its own empty state, and runs
inside `piece()`'s guard — a throw draws that component's own box and names itself in the console,
and nothing else goes dark. That is improvement-plan PR 11's guarantee, structurally, so **PR 11
should be skipped**; PR 5's three fixes are carried here (`act()` returns on Cancel, `esc()` handles
`'`, Reset writes the same empty `UI_LAYOUT` that Done writes).

**The frozen layer is on the node.** `planetai-theme.css` byte-identical to the design repo;
`signs.svg` and `kilometre-cells.json` copied; `tokens.css` **adapted** and saying so at the top (its
Google Fonts `@import` removed, its four `@font-face` paths flattened). Funnel Sans, Figtree and
JetBrains Mono are self-hosted with their SIL OFL licences beside them and named in `NOTICE`.
**Circular Std is deliberately absent** — a commercial Lineto face that must not go into a public
tarball.

**`check_ui.py` learned the three files, and four of its rules were dead.** Worth knowing, because
they had been passing for weeks while checking nothing:

- rules 2/5/6/7 keyed on `--red` / `--blue` / `--green` / `--orange`, tokens the layer replaced with
  `--signal-worse` / `--cells` / `--rings` / `--satellite-only`. They could not have fired again.
- the orange rule exempts a line that mentions the satellite — and the token is *called*
  `--satellite-only`, so it exempted every use of itself.
- `BODY` was "whatever follows `</style>`", and the skeleton has no inline style, which silently
  switched off every rule that reads markup.
- rule 8 collected only refs already under `static/`, so a reference that *dropped* the prefix
  dropped out of the check with it. It also never looked at the three `<link>` hrefs, nor at
  anything the renderer writes — which is now where every image comes from.

New **rule 9** covers the stylesheets: a `url()` naming a file nothing serves, or an `@import` to a
CDN. `tokens.css` arrived with one of each. **Sixteen break-on-purpose gates fire**
(`tests/test_check_ui.py`).

## What Release 2 added after the WIP commit

**The five pieces the skeleton had lost are back, as components.**

| component | where it sits | what it reads |
|---|---|---|
| `trustCard` | the place band, beside the sensors it doubts (§2.3) | `/trust` |
| `ring` (`drawRing`) | the air band | `/nearby` |
| `stations` (`drawStations`) | the air band, under the ring | `/nearby` |
| `forecast` (`drawForecast`) | heat or air, whichever this place declared first | `/forecast` |
| the kits under each source card | every sensed band's Sources | `/sensors` |

`drawRing` and `drawForecast` keep their old top-level names: `tests/test_shipped.py` has asserted
`function drawRing(` since v0.30 and a method on an object literal is invisible to it. They are
registered in `COMPONENTS` and obey the same contract as everything else. The ring and the forecast
are reached through `COMPOSITES.ringCards` / `COMPOSITES.forecastStrip`, which gate on the issue the
band is about — the same shape as `satellites`, which is land's.

**The ring card shows the shape and no median**, per the decision below. Its axis runs lowest to
highest with nothing trimming it: the fence moved to the node in Release 1, all four numbers are in
the sentence underneath, and one station at 152 squashing the box against the left edge is the true
shape of that ring rather than a picture to be corrected.

**Attribution comes from the endpoint** (`/nearby.attribution`, `/forecast.attribution`) with the
literal as the fallback a node that has never fetched shows. Both archives are named on the cards
that use them.

**A kit links to its own page where `/sensors` gives one.** An account kit has a `url` in its meta;
a public station never does, and `/sensors` strips the key entirely for a reader the node does not
trust — so the link appears exactly where somebody can open it.

**Sources is still one card per distance**, carrying the value the node computed, with the kits
behind it listed under it. Not one card per sensor with its own number: `engine._cell` keeps the
sensor ids and not their values, and working a per-sensor figure out in the page would be the page
computing again. §3 wants one card per sensor; that lands when `/issues` publishes the per-sensor
values, and the names under each card become their headings.

**`tests/test_dashboard.py` calls the engine.** It used to lift the fence out of `index.html` with a
regular expression and run it in node. Its docstring is kept — the reasoning about Tukey failing at
three stations is the valuable part — and it gained the other half: a `mad =` or a `fence =` in
`dashboard.js` fails the suite.

**`tools/check_theme.py` is a gate.** It holds `planetai-theme.css`, `signs.svg` and
`kilometre-cells.json` to the sibling design checkout line by line, forgives the one `src:` line by
decision (normalised on the basename, reported) and nothing else, and is blocking in `make lint`.
Six break-on-purpose cases. The design repo is absent on a node and in CI, where it prints one line
and exits 0.

**`tools/shots.py` renders the page.** Every fixture, Now and the wall, 375 · 768 · 1440 · 1920. It
fails on a page error, a component that drew its guard box, a page that scrolls sideways, or a
request the fixture path should not have made. No node, no database, no port: playwright fulfils
every request from disk, mirroring `COMPANIONS` including its refusals. Shots are JPEG in
`docs/design/shots/` and are excluded from the tester tarball along with the tool.

### What the first render found

Eight shots, and the first run was red on all eight. Worth reading, because four of the five were
invisible to every static gate in the repo:

1. **Every paragraph rendered in the browser's default serif, on white.** `tokens.css` puts the base
   typography on `body.fc`, and this body carries no `fc` class on purpose: that rule pins the
   background and the text colour to fixed Fab City values the wall's dark register could never
   flip, and its `.fc a` outranks the page's link colour. So nothing set a body font, a background
   or a colour at all. `dashboard.css` declares the base in the programme layer's own roles now.
2. **The ground drew at 900×600 in the corner.** The rules said `.hero .bg svg`, `.wall .bg svg`,
   `.plan>svg`; the renderer writes an `<img>` — one cached request instead of 4 kB in every
   document. The plan's copy pushed the page sideways at 375 and 768.
3. **Figures pushed the page sideways at 375.** It scrolls inside its own box now.
4. **`?fixture=` still fetched `/settings`**, which is the one request that stopped the page being
   renderable from a fixture alone — the property a design round depends on.
5. **The wall carried the header**: five buttons on a screen across a room, against R6. Gone, with
   one `NOW` exit in its place, because the wall is reachable from the nav and a laptop that got
   there had no way back. The wall's kicker ran its words together (`HEATACT· AN OPEN ASK`).

Also: the trust card said "No local sensor yet." and "Every sensor reported all week." at once, and
the four new eyebrows carried full stops that no other eyebrow on the page has.

## Proven on `pai-clean`, 11 September

The branch rsynced into `~/planetai` in the lima VM (excluding `.env`, `VERSION`, `data/`,
`config/`, `backups/`, `out/`, `exports/`), `docker compose up -d --build app`, at
`v0.44.2-8-g067a6d7`. Barcelona coordinates, Open-Meteo and CAMS, no sensors of its own — so this
proves the machinery, not the numbers.

**Every route the page needs answers, and exactly one 404s:**

```
/  /static/{dashboard.js,dashboard.css,planetai-theme.css,tokens.css,signs.svg,
   kilometre-cells.json,node-ground.svg,jetbrains-mono-latin.woff2}      200
/issues /issues/fixtures /health /trust /nearby /forecast /sensors /earth /rho   200
/static/fonts/jetbrains-mono-latin.woff2                                 404   ← by decision
```

And in a browser, against the running node — `python3 tools/shots.py --url http://127.0.0.1:8080
--token <admin>`, nine shots in `docs/design/shots/live-*.jpg`:

- **no token, SHARE_LEVEL=off**: the page draws the node's own sentence about why it is not sharing,
  and not a blank. Nine endpoints refuse; the browser logs each refusal, which is a refusal being
  answered rather than an error.
- **with a token, Now and the wall, 375 · 768 · 1440 · 1920**: 18 and 19 components, no component
  in its guard box, no sideways scroll, no console error, and no non-2xx request at all. The mono's
  nested path is never even requested: `dashboard.css` declares the same family at the flat name
  first, so the browser resolves it there and never reaches the 404.

**The live render found one more thing**, and it is fixed: the hero drew a red `17` next to the
words `AIR QUIET · NOTHING TO SAY`. Red is "a signal that crossed a line", and the page was deciding
that by comparing two numbers it happened to have — a model's point sample against the WHO 24-hour
line — while the node itself was calling the issue quiet. On a model-only node that is every
evening. The numeral and the stack column are red only when the node's own state is `act` or
`notable` now; `scale` and `day` still mark every value past the line, because there the line is
drawn beside the mark.

## After the first review (11 September, evening)

Tomas looked at the shots and asked for three things. The text and the insight work is his and is
out of this release; these are the three that were.

**Sensor graphics.** Every sensor card carries its 24 hours again, as the page this replaces did.
Nothing is fetched for it and nothing is computed from it: `/issues` already sends `series` per
distance, so the four Sources cards draw their own; `/sparks?metric=pm25` gives the ring's stations
theirs, which is one request and the only new one. The last reading carries a dot, because at 26 px
a label is five pixels tall and is not read. The kit list under each card is capped at four — the
ring card was stacking seven raw ids.

**The satellite data shows.** It never had: the committed fixture has no earth record, and the
live VM had none either. Node #1's derived images were copied to `pai-clean` — nine AlphaEarth
frames, four Sentinel, four Landsat, two change maps, ~19 MB — and **not the 1.1 GB of `.npy`
embeddings, so `/earth` reports `years: []` and a `hint` saying "no satellite record yet" while
serving nine frames.** Nothing displays that hint, but it is wrong, and a household that pruned its
embeddings to save a gigabyte would hit it. One line in `app/main.py`; left alone here.

Both records draw, side by side, told apart by the pill: the node's own AlphaEarth layer (`model`,
"Not a photograph") and Sentinel-2 (`partial`, with the Copernicus and USGS credits).

**Set up mirrors `planetai config`.** The dashboard hard-coded nine groups in its own order; the CLI
sorted them alphabetically; `app/settings.py` declared a third. All three take the node's
declaration now — `RUNTIME`'s own order, which says so at the top of itself, with `issues` first
because it is the one setting that says what this place is for. A group the node gains appears in
both surfaces; before, it appeared in the CLI and was unreachable in the dashboard, silently.
`tests/test_config.py` holds all of it, five break-on-purpose cases.

**The text, and what the node adds beyond the number (12 September).** Tomas's framing: this is
an anticipatory climate computer for local action, with history, that sends findings upstream. Three
additions in the engine, all from data the node already had, and a prose pass over every sentence a
household reads, in three locales:

- **Land says when, and since when.** "1.3 % of the square this node watches changed between 2024
  and 2025. 8.5 % since 2017." The span is the latest comparison; the since is the longest one the
  pack computed to the same year, from `/earth`'s `changes`. `{span}` and `{since}` are placeholders
  now; every other issue fills them empty.
- **Heat has a direction.** `Warming to` / `It feels like` / `Cooling to`, from the same three-hours-
  against-three rule air uses. The number alone could not tell a warming room from a cooling one.
- **The quiet line says the day's high.** "quiet; the day's high was 17 µg/m³ at 14:00" instead of
  "nothing to say", from the 24 hourly values the chart already draws, in the alerts' own clock (the
  snapshot had buckets in UTC and asks in +08:00; a node has one zone). A model-only node has no
  hourly series and its quiet line stays `quiet`, which is true.

Every reason line was reworded to say what happened rather than describe a state (`asked at 14:30;
the reading came back on its own, the ask is still open`), the em dashes came off the screen, the
ring's empty state stopped telling a Barcelona node to set a Bali flag, and the Network card says
what travels upward and what never does. The Bahasa and Spanish are still assistant-written.

### Three bugs the first review turned up, none of them cosmetic

1. **The page threw on its SECOND render, and had since the renderer landed.** `render()` replaces
   five mount points with `outerHTML` and the replacements did not carry the mounts' ids, so the
   next refresh — twenty seconds later, or the moment somebody opened another view — looked for a
   node that was no longer there. **Set up opened empty because of it**, and that is how it was
   found. Every screenshot ever taken was a first render. `tools/shots.mjs` now renders three times,
   through the page's own controls, and fails on a lost mount.

2. **The satellite images 403'd for a reader who had unlocked the page.** `/earth/year.png` and
   `/earth/frame.png` want the node's token at `SHARE_LEVEL=off` and a browser will not put a header
   on an `<img>`. Every frame came back 403 and the household saw every number and no pictures. The
   frames are fetched like the rest of the page now and handed to the `<img>` as object URLs —
   which is also the answer to the 7 MB: **the loop loads once and animates from memory**, keyed by
   URL at module level, so a re-render never goes back to the node. A kiosk that RELOADS still pays
   it; that wants a cache header and is still open.

3. **Set up had no styles at all.** They were never ported, because the view threw before anyone
   could see it. Re-scoped from the old page: square, ink, the layer's roles — the old ones hard-
   coded `rgba(244,236,226,…)` as "paper on ink", a colour that cannot follow the register. The
   toggle's on-state is ink, not green: green is a response, and a setting being on is not one.

Also: an empty `readouts` composite was eating half the Land band, so the two satellite cards were
squeezed into the right-hand column; the scale strip overprinted `REGION 28.1` through `RING 31.7`
when three distances read close together, and drops a label it cannot fit rather than overprinting
it (every dot names itself on hover, which is where the dropped one went).

## What node #1 showed, 12 September

v0.45 installed on node #1 and the place band came back wrong. Reviewed in a browser against the
live node — `tools/shots.py --url`, with a small proxy in front so an authorised reader could be
rendered without writing the node's token into a page (`/place/geojson` needs one at every share
level, and a browser cannot put a header on an `<img>`).

**The plan.** Roads drew as filled black wedges: a `<polyline>` with no `fill` declared is filled
black, `planetai-theme.css` has no `.road` binding class, and `dashboard.css` had not declared one.
Finding it turned up the larger thing — **`dashboard.css` re-declared all eleven of the layer's
binding classes**, copied from the prototype and loaded after the layer, so the page was quietly
overriding the frozen file. Two had drifted: `.veg` said ink where the layer says `var(--rings)`, so
every park drew in the building colour. `check_theme` holds the layer's *contents* and cannot see a
second file redefining its selectors — worth a rule if it happens again.

Also on that card: two `.cap` divs were both `position:absolute` at one corner and printed over each
other and over the legend's second row; the uses swatch was styled `.use` while the markup writes
the layer's key `poi`, so it was a black square beside blue dots; the unit rows counted every
building feature (2,714) while the legend counts the ones it can draw (2,699).

**Text.** The hero printed the reason three times — kicker, why line, ask strip. The why line now
carries the line and its source; the ask strip carries the alert's own headline. `{cmp}` groups by
relation, so three "level with" clauses became one. The Telegram emoji are stripped from the ledger,
the ask strip and the report (§3).

## The Network view, 12 September

**It was empty on every node since v0.45** and nobody had opened it: `render()` handled Now and the
wall, and the four cards in `index.html` were hard-coded markup nothing ever filled. The section is
a mount now, like the wall, and `networkView()` draws it — the figure, the other nodes, the machine,
and the four Index pillars, all as components under `piece()`'s guard.

**"Other PLANETAI nodes" answers what the node knows, not what it can find.** Nothing in this repo
scans a network and a household's LAN is not a thing to go knocking on uninvited, so the card lists
the three ways a node learns of another because somebody said so: a parent it was told to report to
(`PARENT_API_URL`), a child that arrived carrying this node's aggregate token (`POST /aggregates`
writes it as a sensor named `<their node>/<their sensor>`, `kind='child'`), and the mesh gateway its
radio hears — under its own heading, because a radio is not a node running this software. On node #1
that is: no parent, no children, one radio. The empty state says so and says where to link one.

`set` from `/settings` is truthful at every share level even when the value is masked, so a screen
with no token can say a parent exists without being told where it is.

**The class collision worth knowing about.** The frozen layer's binding classes bind on *any*
element, not only inside an SVG. A `<div class="ring">` takes `color: var(--rings)` and a
`<div class="cell">` takes `stroke: var(--cells)` — which is why the four Index numbers came out
green, and why the ring card's box plot had been drawing with a green stroke it never asked for
since the card was named `ring`. The page's own classes are `.ringcard`, `.pillar` and `.dial` now,
and the satellite card is `.satcard` with its year's orange set deliberately rather than inherited.
**Before naming a page class, check it is not one of: ground land cell chain lit ring hair fig label
sat veg.**

`tools/shots.py` renders the Network view too, and fails on a view that drew nothing.

## The radios, and what "nodes see each other" would take

The Network view carries a card for the radio networks this node is on.

**Meshtastic needs nothing collected.** Every packet the gateway uplinks already becomes a sensor row
carrying `meta.mesh_node`, `meta.channel`, `meta.root_topic` and the name from its nodeinfo
(`app/sources.py: meshtastic_message`), so the mesh is a group-by over `/sensors`. `mesh_state` in
`app/main.py` counts packets **since the node last started** while the radios themselves are in the
database, so a node restarted ten minutes ago knows six radios and has heard none — the card says
that rather than printing a dash as a fact.

**Reticulum is the interesting one.** `app/reticulum_bridge.py` already calls
`router.announce(me.hash)` every `RETICULUM_ANNOUNCE_S` with `display_name = "planetai <node>"`.
**Every node with the bridge is already broadcasting "I am here, I am planetai <name>" across every
transport it has, with no data attached.** That is half of a presence layer, running today. The other
half does not exist: nothing registers an `RNS.Transport` announce handler, so no node collects what
it hears. The card says so in those words rather than leaving it as an absence.

`/health` gains a `reticulum` key, filled by its own 300-second loop rather than per request — the
dashboard asks `/health` every twenty seconds from every screen in the house and a bridge that is
down must not turn that into a timeout.

### Presence, built — and what is proven about it

Done in v0.48, off by default. A node announces a `planetai.presence` destination every
`RETICULUM_ANNOUNCE_S` carrying `{node, cell, res, version, kind}` and nothing else, and an announce
handler on the same aspect collects the same from anyone else. The bridge has no settings and no h3:
it asks the node (`GET /presence`) and announces exactly what comes back, or nothing.

- **`/presence` is on the `off` allowlist**, not the `open` one. The bridge is another container with
  no token; on the `open` list it would be refused on a default node and presence would silently
  never announce. It is safe there by construction — it answers `{"enabled": false}` until somebody
  turns it on, and after that returns what is already going out over the radio.
- **`RETICULUM_PRESENCE_RES` is the whole privacy decision**, and `PRESENCE_RES_FLOOR = 6` is the
  guard: nothing finer can be set. Measured on node #1's own cell, the announced centre lands
  **46.5 km** from the house at res 3, 14.7 km at res 4, 1.5 km at res 5 and 6. `tests/test_ground.py`
  asserts the blur rather than describing it.
- **Distance is two cell centres.** Bali to Menorca reads 12,494 km against a true 12,414 — the error
  is the coarseness, which is the point. Neither node published a position.

**Proven, not assumed.** rns 1.5.4 (what `app/Dockerfile.reticulum` installs — it is unpinned, and the
module docstring's "written against 0.9.x" is stale). Two Reticulum instances over a localhost TCP
interface: the real bridge announced and a second instance's handler received the payload intact;
then a third announced as `menorca-1` and the bridge's `/peers` listed it. What is **not** proven is
two nodes over LoRa or over the open Reticulum testnet, and the Sideband display of the new
destination.

### What it did NOT need

Two nodes today see each other only if one is the other's parent or child. To have Lucas's node in
Menorca appear on node #1 as *"here, 12,700 km away"* without either sharing readings:

1. **An announce handler in the bridge** (`RNS.Transport.register_announce_handler`, aspect filter
   `lxmf.delivery`), keeping what it hears: display name, address, first and last seen.
2. **A coarse place in the announce's app_data.** Not coordinates. The node already computes its own
   H3 cell (`app/ground.py`), and a low resolution is the whole privacy control: res-8 is this
   street, res-4 is about 22 km, res-3 about 59 km. A cell at res-3 says "Menorca" and distance
   follows from two cell centres without either node publishing an address.
3. **A rule for who announces.** `SHARE_LEVEL` governs what this node *answers*; announcing is the
   node speaking unprompted, so it wants its own setting and a default of off.

**The resolution is the decision, and it is Tomas's.** The default is 3.

## Still open

- **No beta tester has seen anything, and nothing has run on a real node.** `pai-clean` is a VM with
  no sensors: the room, the yard and the ring are all empty there and the page is region-only.
- **The committed fixture renders three cards empty.** `node1-2026-09-06.json` predates
  `planetai snapshot` and carries no `/nearby`, `/forecast`, `/trust` or `/sensors`, so the ring,
  the stations, the forecast and the trust card come out as their empty states — which is worth a
  picture, but is not the populated page. `planetai snapshot` answers all twelve endpoints; a
  capture taken with it renders the whole thing. **Committing a live capture of somebody's house is
  Tomas's call, not a session's.**
- **The plan's green is loud.** The layer says vegetation is `var(--rings)` at full strength and
  node #1's kilometre is a third fields, so green is the first thing the eye lands on. That is the
  layer's call (R3 accepted the collision with "a loop closed"); changing it is a design decision,
  not a bug fix.
- **`/place/geojson` declares `radius_m` from the current setting and filters nothing spatially**, so
  it serves whatever the pack ever stored — node #1's features reach 2.4 km with `radius_m: 1000`,
  and the plan clips the rest. Harmless today because Overpass returns whole ways that merely cross
  the circle; wrong the day somebody lowers the radius.
- **More to anticipate.** The forecast is on the page and not yet in a sentence: "wind from the SE
  through the evening" beside an air reading is the next honest addition, and it needs the engine to
  read the forecast rows it currently ignores.
- **`/earth`'s hint lies on a node that pruned its embeddings** — see above.
- **The satellite loop is still ~7 MB** — see below. Not solved.
- **`app/main.py`'s COMPANIONS comment says the three `.css` files are copied from planetai-design
  and held there by `check_theme`.** Only `planetai-theme.css` is: `tokens.css` is adapted and
  `dashboard.css` is ours. `tokens.css` says so accurately at its own top. Left alone because
  Release 2 touches no `.py` under `app/`; fix it when something else opens that file.
- **2.6 · 2.7 · 2.8 are done.** `check_theme`, the baselines, and this file plus the CHANGELOG and
  `docs/DEVELOPING.md`.

## Things that will bite

- **The satellite loop is ~7 MB.** Nine AlphaEarth frames at ~780 kB, four Sentinel at ~320 kB.
  §2.7 budgets 60 kB per refresh. It must load once and animate from memory; a kiosk that reloads
  pays it again. This is not solved yet.
- **`main` moves roughly hourly.** It took four merges during this session (#25–#29). Rebase before
  you start and again before you open anything.
- **Two other sessions are live** in this repo. `tests/all` writes `/tmp/stub/httpx.py` at the start
  of every run, so two concurrent runs race on it: a suite that fails once and passes on a retry is
  that, not your diff.
- **Node #1 has a yard now**, so the Stack fills all four columns where the prototype shows three,
  and `{cmp}` can reach three clauses. The hero's 26ch/52ch budget has not been checked against that.

## Verified, and not

**Verified:** `bash tests/all` is 31 of 31. `make lint` passes, `check_theme` included. The page
renders in Chromium from the committed fixture at four widths in both views with no page error, no
component falling into its guard, no sideways scroll and no request outside the fixture — eight
JPEGs in `docs/design/shots/`.

**Not verified:** nothing has run on a node or on `pai-clean`. No live data has reached the page —
every number in those shots is the 6 September capture replayed. Nobody but Tomas has looked, and
**nothing reaches a tester before Tomas looks.** The Bahasa and Spanish in `WORDS` and in
`app/issues/*.yml` are assistant-written; PR #1 (`es-messages`) is the review channel.
