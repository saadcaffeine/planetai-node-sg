# SPEC: the node on a phone, one page that scrolls

*Asked, 11 October 2026, by Tomas: "a mobile version of the dashboard? The mobile version should be rolled out when
opened on a mobile device, and should be a simplified version of the dashboard, all in a simple scrollable page, no
wall. It should show now, place, node. Decisions and actions could be taken care in the mobile version too, or take
the user to telegram. Prefer not to touch settings in this version."*

**Status: proposed, 11 October 2026; nothing here is built.** Written against branch `past-hour-language-2026-10-11`
(v0.80.11 + PR #204). It builds on PR #204 (the Decide card's `asking`, the engine's past-hour words) and starts from
`origin/main` once #204 has merged. Three questions for Tomas are at the end; each section below says what it
assumes until he answers.

## 1. What a phone gets today (v0.80.11)

- **The doors, squeezed.** `/` serves `doors.html` (`app/main.py` `ui()`), which loads 3.6 MB of script before it
  draws a word: `deck.gl.min.js` 2.07 MB, `maplibre-gl.js` 1.06 MB, `d3.min.js` 280 kB and the thirteen door
  files, none of them compressed (the node has no gzip middleware). The doors have `@media` rules at 560, 760, 900 and
  1080 px, so a phone is laid out, but the Now door is a two-column instrument made for a desk, and Place opens a
  WebGL map whose tiles and cells are token-only.
- **`/issues` is half a megabyte.** On node #1's 6 October capture it is 507 kB, of which `stations` is 216 kB,
  `geometry` 185 kB and `asks` 65 kB. The four issues themselves are 28 kB. Gzipped, the whole answer is 73 kB.
  The doors also ask `/aggregates?hours=24` (558 kB on the same capture), `/alerts?limit=500` and
  `/actions?limit=2000` when the screen holds a token.
- **At the default `SHARE_LEVEL=off` a phone sees nothing.** Without a token only `/`, `/health`, `/settings`
  (reduced to two keys), `/export`, `/llms.txt` and `/presence` answer (`_SHARE_OFF`). `/issues` is refused, and the
  doors fall to `refused()`, which draws the unlock form on the Set up view.
- **Answering from the phone already works, in Telegram.** Since v0.80.8 an event's message carries Done / Not now
  / Doesn't fit when the bot has announced itself (`TELEGRAM_BUTTONS=1`), and a press is the same `POST /actions`
  the page makes. The wire says whether the message went out: `events.open[].message.sent`.

## 2. Goal and non-goals

**Goal.** A phone that opens the node gets one page, one column, read top to bottom: **Now**, **Place**, **Node**.
It reads the routes the doors read, fewer of them, draws the engine's words as they come, and lets the household
answer the node's question from the same card the doors draw.

**Non-goals for this version.**

- No Wall, no Data door, no Set up. The page reads `/settings` and never writes it. Storing a token in this browser
  is not a setting of the node (§6.3).
- No new route. Everything is read from routes that exist: `/issues`, `/issues/days`, `/health`, `/settings`,
  `/stats`, `/sensors`, `/reach`, `/observations`, `/earth`, and the one write `POST /actions`. The single
  server change in v1 is that `ui()` learns `?layout=mobile`.
- No map library, no d3, no Plot (§5.2).
- No hour scrubber and no day figure. The page is the present hour. The full dashboard keeps the week.
- No ask pane, no learn mode, no Arrange.
- No page-chrome translation. The engine's words arrive in the household's locale through `buildD()`, as on the
  doors; the section names and buttons the page owns stay English, as the doors' do.

## 3. Decisions

| question | answer |
|---|---|
| How "a mobile device" is decided | in the browser, once, at load: **a coarse pointer and a short screen side under 600 px** (§4.1) |
| Where the rule lives | a few lines at the top of `doors.html`'s `<head>`, before anything else loads; it `location.replace`s to `/?layout=mobile` |
| How a person leaves it | "Full dashboard" at the foot of the phone page, "Phone view" in the doors' header; the choice is remembered in this browser |
| The page | `app/static/mobile.html` + `app/static/mobile.js`, reusing `doors-load.js` for the data |
| Place on a phone | **no MapLibre**: the cell's facts, the ground it stands on, how far back the node reads, one satellite frame, and a link to the map on the full dashboard |
| Decisions and actions | **answered on the page**, the same `POST /actions` as `doors-now.js`, buttons only while the event's `asking` is true and the phone holds the act token. Otherwise the card says where the answer can be given: Telegram when the node sent it there, or this phone once unlocked |
| Telegram | named on the card, not linked: the wire carries no bot name, and a link without one opens nothing useful (question 1) |

## 4. "Opened on a mobile device"

### 4.1 The rule

```js
const PHONE = matchMedia('(pointer: coarse)').matches && Math.min(screen.width, screen.height) < 600;
```

Evaluated once when `doors.html` starts to parse, never on resize.

**Why not a width media query.** Width is a property of the window, not the device. A desk browser dragged narrow
would become the phone page; a phone turned to landscape (844 px on an iPhone 14) would leave it halfway through
reading; and the visual gate's 390 px renders of the doors, which run in desktop Chromium, would all redirect. The
doors already lay out at 390 px; this page is a different product for a different hand, and the hand is what the
rule asks about.

**Why not the user agent.** The server could choose in `ui()` and save one round trip, but iPadOS Safari reports a
desktop user agent, Chromium is reducing the string, and the escape hatch (§4.2) must live in the browser anyway: the
server cannot see `localStorage`, so it would need a cookie, which is one more thing this node would be setting on a
household's phones. `Sec-CH-UA-Mobile` is Chromium-only. The cost of deciding in the browser is that a phone fetches
the first bytes of `doors.html` before it moves; the script is the first thing in `<head>`, so it runs on the first
packet and the navigation abandons the rest.

**What the rule sends where.** A phone, upright or turned: the phone page. A tablet (short side 744 px and up): the
doors. A laptop with a touch screen: the doors, because its short side is over 600. A 7-inch touch panel used as a
wall screen (800 × 480): the phone page, unless it was opened at `/#wall` (§4.3) or someone pressed "Full dashboard"
once on it.

### 4.2 The way out, and back

- The phone page ends with **Full dashboard**, a link to `/?layout=doors` (the hash kept).
- `doors.html` gains **Phone view**, a link to `/?layout=mobile`, in its header, hidden unless `PHONE` is true.
- An explicit `?layout=doors` or `?layout=mobile` is remembered in `localStorage` as `planetai_layout`. On a later
  visit to `/` with no parameter, a remembered `doors` keeps the doors, and a remembered `mobile` (or none, on a
  phone) moves to the phone page. `?layout=classic` is never remembered: it is the legacy page, reached on purpose.
- `localStorage` that throws (a private window, storage blocked) means nothing is remembered and the rule decides
  every time. That is acceptable, and the code says so in its catch.

### 4.3 `?layout=`, the hash, and `UI_LAYOUT`

- `ui()` gains one branch: `layout == "mobile"` serves `mobile.html`. Same shell route, so the same share rule and
  the same `cache-control: no-cache, must-revalidate`.
- The redirect keeps the rest of the query string (`?fixture=` must survive it, the visual gate depends on it) and
  the hash.
- **A hash the phone page has no section for keeps the doors.** `/#setup`, `/#data`, `/#wall`, `/#setup/screen`
  and every hash the docs or the bot send people to stay on the doors on a phone. Only an empty hash, `#now`,
  `#place` or `#node` moves to the phone page. Without this, a link from the docs to Set up would land a phone on a
  page that has no Set up.
- **`UI_LAYOUT` is not involved.** Despite its name it is the classic dashboard's Arrange order, JSON written by
  Arrange mode (`app/settings.py`, `dashboard.js` `readLayout()`). It does not choose a page and this work does not
  read or write it. The spec says so because the name invites the mistake.

## 5. The page

One column, `max-width: 34rem`, a 16 px gutter, no horizontal scroll at 320 px. A thin bar at the top holds the
node's name, "as of HH:MM" (the wire's `as_of`, read as a string, as `hhmm()` does) and three anchors: Now, Place,
Node. They are anchors, not a router; the page is one document and scrolls.

### 5.1 Now

Reads `/issues` and `/issues/days?days=7` through `buildD()`. The lead issue is `D.lead`.

1. **The title and the tagline**, `it.title` and `it.tagline`, as the engine wrote them. Title at sentence size,
   tagline smaller and muted beneath, as on the doors (`docs/SPEC_language.md`, the table's "doors hero" row). An
   older node that sends no `title` falls back to `it.sentence`, as `readout()` does. The pictogram from
   `signs.svg#<it.pix>` sits before it.
2. **The numeral**, the hero distance's `stack[hero_distance].value` at the issue's `dp`, its unit, and its
   provenance pill. Beneath it, `it.plain`. Per Tomas's decision of 9 October the page may drop `plain`'s first
   clause here because the numeral is drawn above it; v1 does not, because dropping it means parsing an engine
   sentence on the page. If the repetition reads badly on a phone, the engine should send the clause apart.
3. **The four distances**, room, yard, ring and region, labelled with `D.labels[dk]`, each its value, unit and
   provenance pill from `it.stack`. An absent distance prints `none` in the gap style, as the doors do. A 2 × 2 grid;
   at 320 px it still fits.
4. **The Decide card** (§6).
5. **The other issues**, one row each in `D.order`: the issue's name, its state word, its hero value with unit, and
   its `title`. Pressing a row makes it the lead of this section, redraws 1 to 4 and scrolls to the title. Coast and
   land, which have no hours, show their region value and `title`, as `rowsValues()` does for them.

6. **A pack's declared bands** (added 1 Nov 2026, after PR #363 put them on the doors' Now). `buildD().sections`,
   drawn by `declaredBands()` in `doors-load.js`, the renderer the doors use, so the band is the doors' band to the
   character. Each sits by its stage: `decide` and `act` under the Decide card, `observe` under the other issues,
   `measure` after them, because the phone has no Did it work. Add an image stays last.
   `tests/test_mobile_sections.py` and the `mobile` pass of the visual gate hold the order.

Every number is a field of the wire. The page compares nothing against the line and counts nothing; the crossed
mark, if any, is the one the engine's `plain` carries.

### 5.2 Place

**MapLibre does not load on a phone.** It and deck.gl are 3.1 MB of script, uncompressed, before a tile; the street
tiles (`/ground/*`) and the cells (`/geo/*`) are token-only at every level, so a locked phone would download all of it
to draw an empty base; and a WebGL map in a scrolling column traps the scroll gesture. What Place keeps:

- **The cell**: `health.cell.id`, its resolution and `edge_m`, and its own area from `D.geometry.ladder` (the same
  figure `VIEWS.place` prints). No coordinates: the phone does not need them, and `/health` rounds them for a
  locked screen anyway.
- **What the ground is made of within 1 km**: the `ee-point` observations (`built_frac`, `tree_frac`, `crop_frac`,
  `water_frac`), each as a percentage with the `model` pill, as the What changed view prints them. Absent at
  `SHARE_LEVEL=off` without a token; the section then says the node did not share it with this screen.
- **How far back**: `/reach`, one line per kind, its days, as `reach()` prints it.
- **One satellite frame**: the latest year in `D.earth.sentinel`, `<img loading="lazy">` from `/earth/frame.png`, so
  it costs nothing until it scrolls near. Absent when the node keeps no frames.
- **Open the map**: a link to `/?layout=doors#place`, which also remembers the doors (§4.2). That is a choice the
  reader makes knowing it is the large page.

### 5.3 Node

Reads `/health` only, which answers at every share level, so this section always draws, even when Now cannot.

- `health.node`, in `health.city`.
- `planetai-node <version> · schema <schema>`, up for `uptime_s` in hours, the last poll at `last_poll`, readings
  taken in since the restart (`ingested`).
- The mesh and the radio: on or off, as `running()` words them.
- `health.release.newer`, when present: "A newer release is out." and nothing else. Updating is the keeper's, from
  the node.
- **This phone**: `SHARE_LEVEL=<level>` from `/settings`, and whether it holds a token. Locked, it names what it is
  not shown.

Not on the phone: the flow, the world, the machine's meters (`/machine` and `/storage` need the admin token).

### 5.4 When a route is refused

`loadD()` already leaves a refused route null. The phone page treats each null on its own:

| refused | what the page draws |
|---|---|
| `/issues` (the default `SHARE_LEVEL=off`, no token) | Now and Place are replaced by one block: the node's own 403 sentence, read from `/issues`' answer as `refused()` reads it, then the unlock field (§6.3). Node draws from `/health` as usual |
| `/observations`, `/earth`, `/reach`, `/stats`, `/sensors` | that part of Place is left out with one line: "The node does not share this with a screen at SHARE_LEVEL=off." |
| `POST /actions` 401 or 403 | the node's `detail`, then "Unlock this phone with the token for closing a loop." |

`loadD()` throws when `/issues` is missing; `mobile.js` catches it the way `doors-core.js` does and draws the
refused state rather than a blank page.

## 6. Decisions and actions

### 6.1 One path: answer on the page

The card on the phone is the doors' Decide card, condensed: the same event, the same three buttons, the same write.
The household's two places to answer, Telegram and this page, write one row to one table, so there is no reason to
send someone from the page to the chat when the page can take the answer.

For the lead issue, the open event is the one in `D.events` with that `issue` and no `cleared_at` (the live hour
only; the phone never shows a past hour).

- **Header**: the issue name, `e.kind`, "since" `hhmm(e.opened_at)`, "watching, last seen" `hhmm(e.last_seen_at)`,
  and the peak with its unit when `e.peak` is present.
- **The action**: `e.action`, the live one the engine re-chose for the present (`events_wire.py`: the card is the
  present). When it is null, the card says "The node asked for nothing specific.", the doors' words.
- **The buttons** Done, Not now and Doesn't fit, with the labels from `D.buttons` (the wire's, in the household's
  locale), **only while `e.asking` is true and the phone holds a token**. Each is `POST /actions` with
  `{event_id, stage, actor, note: ''}`, the stages `acted`, `acknowledged` and `dismissed`, exactly as
  `doors-now.js` sends them.
- **The name.** Since v0.80.8 an answer carries whose it is. The first press on a phone with no `planetai_actor`
  in `localStorage` opens one field, "Your name", in the card; the name is kept under that key and sent with every
  answer after.
- **After a press**: reload with `loadD()` and redraw. The card then shows `e.answer` from the wire: the words of
  the stage, who, when, and the note in quotes when there is one. A Not now shows `answer.held_until` as "held until
  HH:MM", read from the wire. The doors print "The node holds this for three hours, unless it reaches danger.",
  which is the page restating engine policy; the phone does not copy it.
- **No open event**: "Nothing is asked now." and the line with its source from `it.line` and `it.line_source`, or
  "this issue has no line" for coast and land.

### 6.2 When Telegram is the answer

When the card is asking and the phone holds no token, there are no buttons. In their place, one line:

- `e.message.sent` is true: "The node sent this to Telegram. Answer there, or unlock this phone to answer here."
- otherwise: "Unlock this phone to answer here."

No deep link in v1. A `t.me/<bot>` link needs the bot's name, which no route carries; the page would have to
invent it. Adding it means the agent container reading `getMe` once and the node publishing the name, which is a
new field on `/health` and a decision about who may read it (question 1).

### 6.3 Unlocking this phone

One field and one button, in the refused block and behind the card's "unlock" link: **the token for closing a
loop** (`ACT_TOKEN`), stored as `planetai_act`, the key `DOORS_TOKEN()` already reads. With it the phone reads what
any token reads (`_node_tokens()` lets it past `SHARE_LEVEL`) and can answer, and cannot change a setting. The
admin token is not offered on the phone: it is the key to `/settings/raw`, and this version does not touch settings.
A "Lock this phone" link under Node removes the token, as Set up's does.

## 7. Behaviour

- **The boot face.** `mobile.html` ships the doors' boot overlay already on (`.asking.on`): the brand line and the
  blink, CSS only, so the first paint is the loading face and not a blank page. No glyph globe: it is a canvas loop
  in `doors-core.js`, and a phone does not need to spend a frame budget on it. `mobile.js` removes the overlay when
  `D` lands or the refused state draws. `@media (scripting: none)` hides it, as on the doors.
- **Freshness.** No timer. When the page becomes visible again (`visibilitychange`) and `as_of` is more than five
  minutes old, it reloads. A phone in a pocket spends nothing.
- **Registers.** Paper and dark from the frozen layer (`planetai-theme.css`, `tokens.css`). The page follows
  `prefers-color-scheme` when it loads and sets `data-theme` to match; no toggle in v1. The Wall's always-dark rule
  does not apply.
- **Reduced motion.** Nothing moves: the blink stops, the scroll to an anchor jumps, nothing transitions.
- **Accessibility.** Headings in order (one `h1`, the node's name; an `h2` per section). The title region is
  `aria-live="polite"`. Every button and link that is pressed is at least 44 × 44 px. The comparison a numeral is
  read against is printed text, not a `title` attribute: a phone has no hover. `lang` is the locale from `/health`.
  At 200 % text size the column reflows without horizontal scroll. The buttons are real `<button>`s and the card's
  answer line is `role="status"`.
- **Fonts.** The frozen layer's three families, `font-display: swap` as they ship. The page draws before they land.

### 7.1 Performance budget

Measured in the visual gate with the throttle written into the script: **1.6 Mbit/s down, 750 kbit/s up, 150 ms
round trip**, a 390 × 844 viewport, `isMobile` and `hasTouch` on.

| mark | budget |
|---|---|
| The boot face painted | 1.0 s |
| The lead issue's title on screen | 4.0 s in v1; 1.5 s after the gzip change (§9) |
| Requests to `maplibre-gl.js`, `deck.gl.min.js`, `d3.min.js`, `plot.umd.min.js`, `/ground/*`, `/geo/*`, `/aggregates` | none |
| Script the page loads | `doors-load.js` and `mobile.js` only, under 40 kB together |

`/issues` is most of the 4 seconds: 507 kB on node #1, uncompressed. The page cannot ask for less of it without a new
parameter, and this version adds none.

## 8. Files

| file | change |
|---|---|
| `app/static/mobile.html` | new: the shell, one inline `<style>` (the doors' pattern), the boot face, the three sections' mounts |
| `app/static/mobile.js` | new: load, draw, answer, unlock, refresh. Copies the one-line helpers it needs (`esc`, `fmt`, `hhmm`, `said`, `sign`, `prov`, `num`, and since 1 Nov `ago`) from `doors-core.js` rather than loading it, because `doors-core.js` boots the doors on load. A third page that needs them is the time to lift them into one file |
| `app/static/doors-load.js` | `loadD(routes = DOORS_ROUTES)`: the phone passes its own subset (`issues`, `days`, `health`, `settings`, `stats`, `sensors`, `reach`, `observations`, `earth`) and never asks for the token-only three. `buildD()` already tolerates every missing part |
| `app/static/doors.html` | the rule and the redirect, first in `<head>`; the "Phone view" link in the header |
| `app/main.py` | `ui()` serves `mobile.html` for `layout=mobile`; `COMPANIONS` gains `mobile.js` |
| `tests/test_doors.py` | the phone page's checks (§8.1). In this file and not a new suite, because the phone reads the same loader through the same shell route, and a new suite would move the count in `tests/all` (rule 1) |
| `tests/visual/measure.mjs`, `tests/visual/gate.sh` | a `mobile` command and its line in the gate (§8.1) |
| `docs/site/dashboard.md` | a paragraph: what a phone gets, how to leave it. Re-read the page and move its stamp |
| `CHANGELOG.md` | one line under `## Unreleased` |

No file under `packs/`. By `docs/NEXT_RELEASE.md` rule 2 this ships in a release with no pack change, and by rule 3
as that release's one page change.

### 8.1 Tests and gates

In `tests/test_doors.py`, **above the `sys.exit(0)` that skips the loader checks when `node` is missing** (a block
below an exit passes by never running):

- `/?layout=mobile` serves `mobile.html`; `/` and `/?layout=doors` still serve `doors.html`.
- Every `/static/` name `mobile.html` and `mobile.js` use is in `COMPANIONS`, and `mobile.html` names no MapLibre,
  deck.gl, d3 or Plot file.
- `mobile.js` contains no `fetch('/settings` with a method other than GET, no `PUT`, and no `planetai_admin`
  write: the page does not touch settings.
- After the exit, with `node`: `loadD`'s route subset builds a `D` from the capture with `title`, `tagline`, `plain`
  and the open event's `asking` and `action` present.

In the visual gate, `node tests/visual/measure.mjs mobile`, against the committed fixture:

- **The rule.** `/` at 390 × 844 with touch lands on the phone page; at 1440 without touch it stays on the doors;
  `/#setup` at 390 with touch stays on the doors; a remembered `doors` stays on the doors.
- **No horizontal overflow** at 320, 360 and 390, both registers: `scrollWidth <= clientWidth`.
- **The engine's words only.** The title, tagline, `plain`, the action and the button labels in the DOM equal the
  fixture's fields, character for character.
- **Targets.** Every button and link is at least 44 × 44 px.
- **The budget** in §7.1, and the list of requests that must not happen.
- **Locked.** With the fixture's token-only parts removed (as `loadD()` already does without a token), Node draws
  and the refused block shows the node's sentence and the unlock field.
- `shots` gains `mobile_populated_390` in both registers, so the pair can be read beside the doors' 390.

`measure.mjs` maps `/` to `index.html` today; the `mobile` command has to honour `?layout=` as the node does, and
serve only names `COMPANIONS` names. A rig that serves what the node refuses is how a font that never loaded passed
the gate once.

## 9. Staging

**v1, one pull request: the phone page.** §4 to §8 as written. Releasable alone: on a desk nothing changes, and on a
phone the worst case is the page with "Full dashboard" at its foot.

**v1.1, its own pull request: gzip.** (Built 24 Oct 2026, level 5, `/mcp` and already-compressed types left out.) Starlette's `GZipMiddleware` on JSON, JavaScript and CSS above 1 kB, excluding
`/mcp`, `text/event-stream` and any response that already sets `content-encoding` (the vector tiles). It takes
`/issues` from 507 kB to about 73 kB for every screen, the doors included, and is the change that brings the title
under 1.5 s. Whether the Starlette in the app image already skips event streams and pre-encoded responses is
read from its source before the PR, not assumed. It is server-wide, so it is proven on node #1 by itself, with an MCP session and a tile load watched,
and never folded into the page PR.

**Later, only if asked.** The Telegram link (question 1); a 24-hour strip drawn from `/issues/days` without d3; the
then-and-now pair; the page's own words in `es` and `id`.

## 10. Questions for Tomas

1. **Telegram link:** is "The node sent this to Telegram" on the card enough, or do you want a button that opens the
   bot, which means the node publishing its bot's name on `/health`?
2. **Tablets:** phones only (short side under 600 px) get the phone page, and tablets keep the doors. Right?
3. **Unlocking a phone:** may the phone page offer the one field for the act token (it answers, it changes no
   setting), or should a locked phone only link to the full dashboard's Set up?
