# The page draws the day: figures, strips, and a keeper's Grafana

*Approved in brainstorming with Tomas, 6 October 2026, section by section. §3 (the server piece) is built on branch figures-wire-2026-10-06; §4 and §5 are not built yet.*

The page draws one day four times and never more than one day. Its graphs do not answer a pointer, the house's bad
hours have to be read off curves, and a station that falls silent for a day disappears. This spec replaces the four
drawings with one figure per issue, adds a strip of hours that reaches back as far as the node holds, keeps silent
stations on the page, and answers the September question about Grafana by giving it to the keeper, beside the page.

It is page work for **v0.79**, beside `docs/SPEC_dashboard_events.md` §4, and it follows `docs/NEXT_RELEASE.md`
item 1b's open question ("Grafana, and which surface it is for").

## 1. What the page does today (node #1, 6 October 2026, `main` at v0.77, advanced, 1440 px)

- **One day, drawn four times.** Observe's barcode and its per-issue traces, the station sparklines, and Measure's
  second copy of the headline trace all read the same 24 hourly buckets from `GET /issues`. Measure calls the same
  `series()` a second time.
- **Nothing answers a pointer.** No drawing has a crosshair or a readout. The hour a reader points at has to be
  estimated from the axis.
- **One day is all there is.** Now draws 24 hours. Historical's "The day this place usually has" averages the whole
  record into one curve per hour of day, which hides which days were bad.
- **A floor below zero.** The air trace prints `floor -20 µg/m³, not zero`: the floor rule pads below the lowest
  reading even when the quantity cannot be negative.
- **A silent station vanishes.** The `stats` view reads the last 24 hours only, so a station silent for a day is no
  longer in `stations` and leaves the page with no word. Node #1 has 26 rows of kind `sensor` and draws 17. Eight
  reported in the last 30 days and not in the last 24 hours, among them two kits in this house.
- **The station rows share a scale that flattens them.** One scale for every row is right, and the air scale reaches
  2015.5 µg/m³ from one room's spike on 6 October, so every other row is a flat line.

## 2. Decisions

| question | answer |
|---|---|
| Who the work is for | **both**: the household on the page, the keeper beside it in Grafana. Grafana never draws the household's page |
| What the page fails to tell | **fewer, denser pictures**: one figure per issue in place of four drawings of one day |
| How it is drawn | **Observable Plot with its D3, vendored** as two static files. Nothing loads from outside the node |
| Which forms | **the day figure**, with the usual band and the event's rooms inside it, and **the strips**, one row a day and one cell an hour. The clock is a wall drawing and waits for the wall |
| Borrowed from Bali Air Dispatch | **hours over the line, counted**, and **the archive of silence**: a station that stopped is kept and named |
| Order | **the server piece first** (§3), **then the page** (§4), in **v0.79**. Grafana (§5) is independent and may go first |

The prototypes are in `fabcity/planetai-design`, branch `day-figure-prototype-2026-10-06`, under
`prototypes/day-figure/`: `index.html` (the day figure and the stations, on node #1's 6 October wire) and
`forms.html` (four forms on 35 days of node #1). The first `forms.html` drew plain temperature for heat and the outdoor
kit for air; both issues draw the indoor rooms, and heat is apparent temperature. Its corrected numbers are the ones
quoted here.

## 3. The server piece (PR 1)

### 3.1 `GET /issues`: each issue gains `usual`

```
usual: {
  window_days: 14,                 // usual_by_hour's window, complete local days before today
  distance: "room",                // the issue's hero distance
  hours: [ {hour, median, p90} ×24 ] // local hours 0–23
} | null
```

- **What it is.** The mean, across the sensors at the issue's hero distance, of `usual_by_hour.median` and `.p90` for
  the issue's own metric. That is the same reading of the same view `app/events_wire.py`'s `USUAL_SQL` makes for an
  event's context, so the band on the page and "usual at this hour" on the event card agree.
- **When it is null.** An issue whose hero distance is not read from `stats` (land, coast), or whose metric
  `usual_by_hour` does not hold (it holds `temp`, `humidity`, `pm25` and `apparent`), or a node whose view is still
  empty after a start. The page then draws no band and says why in the legend.
- **Replay.** Replay carries each issue's `usual` from the capture's own `/issues`, as it carries the events block;
  a capture from before v0.79 has none, so `usual` is `null` with `usual_absent: "unread"` rather than the
  `LookupError` the five required tables raise. `usual_absent` is one of `unread`, `no_source`, `no_history` or
  `not_watched`.

### 3.2 `GET /issues`: an open event gains `series`

```
events.open[].series: { rooms: [names], values: [ ×24 ] }   // on /issues' own buckets
```

The event's rooms, combined the way the issue combines its hero distance (air: the mean; heat: the median of each
room's apparent temperature), hour by hour. The page draws it inside the day figure beside the house. The node
computes it because heat's apparent temperature is a function of two stored metrics, and a page that combined them
would be computing a number.

### 3.3 `GET /issues`: the stations that stopped, beside the ones heard

`stations` stays the stations heard in the last day. The top-level `stations_silent: {read, within_days, stations}`
says whether the stopped ones were read and how far back, and its `stations` lists every `kind = 'sensor'` station
that reported in the last 30 days and not in the last 24 hours, with `read: {}`, `series: {}` and `last_heard` (the
time of its last reading). One query on `readings`, in `_read`, beside the five tables; a replay carries the
capture's own. They are kept apart because `geometry`'s cells name their sensors by position in `stations`, and every
reader of `stations` means a station heard now.

**Not every silent row is a silent kit.** Of node #1's eight, "Ungasan Kit - TEST (Smart Citizen)" and "BAYU NEW
ENCLOSURE (Smart Citizen)" were last heard on 4 October, while kits of the same names report today under other ids.
Listing them as "no longer heard" would tell the household two working kits are dead. A silent row is not listed when a station heard in the last day stands at the same point, to five decimal places. On node #1 that drops the three `bad-sc-*` relays and the OpenAQ relay of Padang2 Uluwatu, and keeps four. The stopped stations are published, never counted: `digest` (simple mode's sentence, "observing N stations", the neighbours within a kilometre) and `geometry` (the grain table) read only `stations`.

### 3.4 `GET /issues/days?days=7` (1 to 90)

```
{
  as_of, tz,                                   // tz: NODE_TZ; every bucket carries its own offset
  days: 7,
  buckets: [ local hourly buckets, oldest first ],
  issues: {
    <key>: {
      distance: "room",                        // the hero distance, drawn by default
      series: { room: [...], yard: [...], ring: [...], region: null },   // what _series computes, per distance
      provenance: { room: "live", yard: "live", ring: "partial" },        // the stack's word for each distance
      per_day: [ {date, over, read, of} ],     // at the hero distance: hours over the line, hours read, hours in the day
      line: {value, unit, source} | null
    }
  },
  events: [ {id, issue, kind, level, opened_at, cleared_at} ]   // alert_events opened in the window or still open
}
```

- **One engine, a longer window.** The route calls the engine's own `_series()` with `readings_1h` rows for the window
  instead of the last 24 hours, so a cell is exactly what the lead's numeral would have said at that hour. There is
  no second definition of the house. The hours are stepped in UTC and shown in the node's zone, so a day with a daylight-saving change
  holds 25 or 23 hours, and `of` says so.
- **The node counts.** `per_day` is the node's count, so the page prints a number it did not compute.
- **Cost.** Node #1 reads 82,459 hourly rows for 90 days in 164 ms (6 October). No cache.
- **Wire format.** `days-v0`, pinned by `tools/check_wire.py` with a committed example, as `issues-v0` is.
- **Snapshot.** `planetai snapshot` fetches `/issues/days?days=7` and stores the answer as `issues_days`, and
  `tests/visual/measure.mjs` serves it verbatim, as it serves `/shape`. A fixture without it draws the strips' empty
  state.
- **Who may read it.** It is under the `/issues` prefix, so it is readable exactly where `/issues` is.

### 3.5 The floor

The node's figures are unchanged. The page's floor rule changes (§4.2), and the rule is written once, in `window.K`.

## 4. The page (PR 2)

### 4.1 Two vendored files

- `app/static/d3.min.js` (d3 7.9.0) and `app/static/plot.umd.min.js` (@observablehq/plot 0.6.17), both ISC, with
  their licence texts beside the fonts' OFL files. Together about 490 KB minified, against 988 KB of static files
  today. Served by name from `COMPANIONS` with `no-cache, must-revalidate`, so a reload costs a 304.
- `index.html` loads them before `dashboard.js`.
- `data/vendor.sha256` holds their hashes and `make lint` runs `shasum -a 256 -c` on it, so neither can drift
  without a commit that says so. The frozen layer and `tools/check_theme.py` are untouched: these files are not the
  design kit's.
- Plot names its own SVG class (`plot-` and a hash) and labels its marks with `aria-label`, not classes. Every class
  the page writes for a figure starts with `f-`, and Plot's own are `plot-` and a hash, so neither can meet a theme
  binding class (`.ring`, `.cell`, `.sat`, `.label`).

### 4.2 The day figure

One `series` card per issue with a day, in Observe, in place of the barcode and the traces. The four card kinds stay
four. Top to bottom:

```
Heat  sensed                               42.8 °C top · floor 28.0, not zero · the line 35.0
 ─────────────────────────────────────────────────────── sustained · 13:21  ━━━━━○ 
 [usual band, median to p90]
 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  the line (red, dashed)
 house ━━━━   street ╍╍╍╍   ring ┈┈┈┈   K ROOM ━━━━ (the event's room, ink)
 ▏▏▏                                         ▏▏▏▏▏▏      hours over the line (red ticks)
 15:00    18:00    21:00    00:00    03:00    06:00    09:00    12:00   now
 07:00  house 29.6  street 31.8  ring 33.2  usual 30.1–31.0     ← the readout, under the crosshair
```

- **The event lane.** A muted ink bar from `opened_at` to `cleared_at` or now, with its kind and hour at the start
  (at the end, for one that opened in the last fifth of the window). The answer is a ring at its own time: green and
  closed for **Done**, ink for **Not now** and **Doesn't fit**. An answer after the clear is joined to its bar by a
  dotted hairline.
- **The traces.** Ink only, dashed by distance as today, full opacity for the house. A null is a gap and a lone
  reading is a dot; Plot breaks a line at a null by itself, so the page carries no geometry for it.
- **The usual band.** `usual` from §3.1, median to p90, under the traces, named in the legend as "usual at this hour,
  last 14 days". An hour above the band and under the line is marked as an ink tick, so "unusual" is drawn, not only
  said.
- **The event's rooms.** With an event open, `events.open[].series` is drawn as a second full-ink trace named by its
  rooms. A one-room event inside a cooler house is then visible as the room it is.
- **The line and the hours over it** as today: red dashed, red ticks on the floor, counted in the readout.
- **The floor.** The data's own, printed in the head. A quantity whose readings are all non-negative never gets a
  floor below zero. This is the one rule both the figure and the strips use, on `window.K`.
- **The readout.** Under the drawing, in mono, the hovered hour and every distance's value or "nothing recorded",
  the usual, "over the line", and the event open at that hour with its answer and who gave it. Idle, it says how the
  day opened and closed and how many hours were over. Every value it shows is also in the alt sentence or the
  matrix, so nothing needs a pointer. Keyboard focus moves the crosshair hour by hour.
- **Time.** Labels are formatted in the bucket's own offset from the wire, never the browser's zone.
- **Width.** The figure draws at its column's width and redraws when that changes by more than 20 px. Under 600 px it
  shows fewer ticks and shorter event labels.
- **Simple mode** draws no figure, as today.

### 4.3 The strips

One row a day and one cell an hour, newest at the bottom, from `GET /issues/days`.

- **Shade.** Ink on the issue's own square-root scale, from the data's floor (0 for air, the lowest reading for
  heat) to the darkest hour, so one 2,000 µg/m³ hour does not wash every other hour white. Red is an hour over the
  line. An outlined empty cell is an hour with nothing recorded, never a pale cell that looks low.
- **Right column.** The node's `per_day.over` ("3 h over"), then any event that opened that day, by kind and span.
- **Distance.** The hero distance, the one the lead's numeral reads. A switch to the street or the ring waits until a
  reader asks for it: `/issues/days` already carries every distance, so it is a page change only.
- **Hover.** The hour, the value, and the event open then, in the same readout line as the figure.
- **On Now:** the last seven days, under the day figure. **On Historical:** every day `/issues/days?days=90` returns, in
  place of the averaged curve in "The day this place usually has". That section's sentence about how many days the
  node holds stays, and a node installed this morning draws one row.
- What node #1 shows, 2 September to 6 October: indoor air over 15 µg/m³ in 48 of 819 hours, most often at 07:00 and
  08:00; heat over 35 °C apparent in 27 hours, most often between 13:00 and 17:00, 21 of them in the first three days.

### 4.4 The stations

- **A drawing per row.** Each station row draws its day with Plot, on the one scale every row shares (the band is the
  hour's spread, the line the hourly mean, the issue's line where it applies), and answers a pointer. The tabs and the
  fold to eight stay.
- **The event's rooms first.** With an event open, its rooms' rows lead and are named as the event's.
- **The archive of silence.** A station silent over an hour keeps its row, its last reading as a tick, and
  "silent 3 h". A station from §3.3 goes to a fold at the bottom, "no longer heard: N stations", each with when it was
  last heard. Nothing leaves the page because it stopped.
- **A spike on a shared scale.** The scale stays shared. Each row prints its own day's high beside its last value,
  so a flat row says "high 6.4", not nothing.

### 4.5 Measure

The second trace goes. In its place, one `row`: hours over the line today (the node's local day) and in the days `/issues/days` covers, per
issue, from `/issues/days` `per_day`, with the hours nothing was recorded named beside them. The ρ row and the funnel stay.

### 4.6 Plot's chrome

One block in `dashboard.css`: mono for every number, the hairline grid, muted axis text, no colour but the four tokens
with their one meaning each. Both registers, from the tokens, so the dark register needs no second drawing.

### 4.7 Absence

| state | how it is drawn |
|---|---|
| a distance with no source | not drawn, named in the legend with its reason, as today |
| an hour with nothing recorded | a gap in the trace, an outlined empty cell in the strip |
| a station that stopped | kept, with "silent" or in "no longer heard" |
| a node or capture older than the field | "this node does not send the usual yet", or the strips' empty state, never a blank |

### 4.8 Docs and learn

`docs/site/dashboard.md` and `docs/site/design.md` describe the figure, the strips and the vendored files. The
figure and the strips get learn marks; `tools/build_learn.py` re-cuts `learn.json`. The page's new words are English,
as the events PR's are.

## 5. Grafana, for the keeper (PR 3)

- **A profile.** A `grafana` service in `docker-compose.yml`, `profiles: [grafana]`, a pinned `grafana/grafana-oss`
  image, ports `127.0.0.1:3000:3000`, never `env_file`. It reads two keys under `environment:`.
- **`planetai grafana on`** generates `GRAFANA_DB_PASSWORD` and `GRAFANA_ADMIN_PASSWORD` into `.env`, creates the
  login role `planetai_grafana` as a member of `planetai_ro` (SELECT on every table but `settings`), and adds
  `grafana` to `COMPOSE_PROFILES`. `planetai grafana off` removes the profile and drops the role. It prints the
  address and how to reach it from another machine (an ssh tunnel); exposing it on the tailnet is a later decision.
- **Provisioned, in the repo.** `config/grafana/` holds the datasource and two dashboards as JSON:
  - readings per station and metric, 30 and 90 days, with "connect null values" off so a silent hour is a gap;
  - alert events and their messages, as a table and as annotations on the readings.
- **It says what it is.** Each dashboard's title ends "keeper's view · no provenance". It carries none of the
  page's rules, and the page never links to it as the household's view.
- **Docs.** A section on `docs/site/dashboard.md` and the `COMPOSE_PROFILES` row of `docs/site/configuration.md`.

## 6. Testing

- **The rules the page keeps.** The floor, the gap runs, the hours-over count used by the readout and the strips'
  shade floor are small functions on `window.K`. `tests/test_dashboard.py` lifts and runs them in node, including:
  no floor below zero for non-negative readings; a run of nulls makes two segments, not one.
- **The server.** `tests/test_figures_wire.py` covers `usual` (null, present and carried by a replay),
  `events.open[].series` against node #1's 6 October capture, §3.3's silent stations on node #1's eight rows of that
  day, and `/issues/days`: one day reproduces `/issues`' own 24 values, `per_day` counts what the series shows, and
  the window is held to 1–90 days.
- **The wire.** `tools/check_wire.py --update` for `issues-v0`, and `days-v0` added.
- **The visual gate.** A new fixture of node #1 with `issues_days` and `usual_by_hour`; `measure.mjs` serves `/issues/days`; the
  heights re-baselined at 390 and 1440 px and the wall, in the page PR, with the numbers in its description.
- **Two checks that would have caught this session's faults.** No `floor -` printed for a non-negative quantity, and
  no unit inside an uppercased rule (`µ` uppercases to `M`; `tools/check_ui.py` already holds this for the stylesheet).
- **On a node.** Before merging the page, serve the new `dashboard.js` into node #1's live page and read every
  section for "did not render" (the memory note on dashboard closures). After merging, update node #1 and node #3
  and look at both.

## 7. How it lands

Milestone **v0.79**, three pull requests, each with its `CHANGELOG.md` line and `needs testing`:

1. **The wire** (§3). Server only.
2. **The page** (§4). After 1, and after `fabcity/planetai-node#176` if it merges first, which touches `dashboard.js`
   and the forecast pack.
3. **Grafana** (§5). Independent; may land first.

## 8. Not in this spec

- **The clock.** A wall drawing, not evidence: a radial scale misstates magnitude and the design page refuses dials.
  It waits for a wall spec.
- **The forecast on the figure.** "The day it is about to have" stays its own section; node #1 has no forecast set
  (`/forecast` returns no hours), so there is nothing to draw right of now yet.
- **A longer usual.** Fourteen days is short: a smoky fortnight makes smoke usual, and on 6 October the band sat above
  a clean day. Changing `usual_by_hour` changes the event engine's rules too, so it is the engine's decision.
- **Translation** of the page's new words.
