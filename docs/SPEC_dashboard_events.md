# The dashboard tells the bot's story

*Approved in brainstorming with Tomas, 5 October 2026, section by section. Nothing here is built yet.*

The alert events of `docs/SPEC_alerts.md` fold a burst of rule rows into one event per issue per house, give it
one action, and (with Plan 2) three buttons: **Done**, **Not now**, **Doesn't fit**. The page still speaks the old
engine's language. This spec makes Now read the way the bot does: each open event appears once, with its one action
and the three buttons, and the rest of the page is the evidence for deciding, not a second set of asks.

It is the work §7 and §11 of the alerts spec defer to v0.78, plus the layout cleanup that work needs.

## 1. What the page does today (node #1, 5 October 2026, advanced, 1440 px)

- **Too many alerts.** The lead's last line reads `238 alerts open · #578 · in 3 Act`. Act draws rows of hollow
  rings per rule: 157, 52, 44.
- **One ask, three places, two buttons.** The lead links to it; Decide's "What to do about it" shows it with
  **Decide about this**; Act's strip shows it again with **I did this**. The bot will send one message with three
  buttons.
- **Deciding is four screens down.** Observe draws seven sections before the first thing a person can do, and two of
  Decide's four sections ("Whose word, over how much ground", "What each rung is worth") are about resolution, not
  about deciding.
- **The lead and the asks disagree.** Air leads at 5 µg/m³ while heat reads 38.1 °C on the street and "dangerously
  hot" is open.

## 2. Decisions

| question | answer |
|---|---|
| What is messy | too many alerts; the same ask repeated across Decide and Act |
| Who the top of Now is for | **the keeper deciding**: open events, their context, the buttons, then the evidence |
| Events and the old alerts | **events replace alerts on the page.** An event's rule rows stay reachable inside its card and are never listed as asks of their own |
| Order of work | **a shared server piece first** (v0.77, used by Plan 2's bot and by the page), **then the page** (v0.78) |
| Layout | **Decide moves up; the four stages stay**, and each event card links to its own evidence |
| Shadow | answers pressed on the page in shadow **are recorded**: a real person answering a real condition |

## 3. The server piece (v0.77)

### 3.1 `GET /issues` gains one top-level key, `events`

```
events: {
  engine:  "rules" | "shadow" | "events",
  buttons: {done, not_now, doesnt_fit},          // in the household's language; the bot's own strings
  open: [ {
    id, issue, kind, level, opened_at, last_seen_at, cleared_at: null, peak, line,
    rooms, places,
    context: {usual, outside, outside_metric, outside_from},   // open events only
    action:  {id, text} | null,                  // the action line as it was sent
    message: {text, ts, sent} | null,            // the latest event_messages row, word for word; sent is false in shadow
    alerts:  [ids],                              // the alerts rows this event covers
    answer:  {stage, actor, ts, held_until} | null
  } ],
  recent: [ ...the same fields, no context, cleared in the last 7 days, plus cleared_after_min on a Done... ],
  cleared_today, last_cleared: {issue, ts} | null,   // today is the node's local day
  uncovered_asks: [ids]                          // open act-level alerts no open event covers
}
```

- **`engine`** is `ALERT_ENGINE` as `run_rules` reads it (anything else is `rules`), so the page can tell the states
  of §5 apart. On `rules` the engine is not running, so `open` is empty even if a shadow spell left rows open.
- **`context`** is read when `/issues` is served: inside and outside from `events_pg.context`, the resolver that
  chose the action, and `usual` as the median of the event's rooms at this local hour in `usual_by_hour`. For heat,
  `outside` is the air temperature (`outside_metric: temp`) beside an apparent-temperature peak, and the card says
  which. A value the node cannot read is `null`. The page derives no number.
- **`action.text`** is the line the engine sent, cut from the latest message that carried `action_id`. It is not
  re-rendered, so the page says what the phone said.
- **`alerts`** links by `alerts.event_id` once Plan 2 writes it. Until then, the node matches the `alerts` rows of
  the issue's packs whose `ts` falls between `opened_at` and `cleared_at` (or now). **`uncovered_asks`** is every
  open act-level alert in no open event's `alerts`; on `shadow` and `events`, leaving out the alerts of the packs the engine replaced. The node does both; the page never matches anything.
- **`answer`** is the latest `actions` row with this `event_id`. `held_until` is set for **Not now**: three hours
  after it, unless the event is `danger`. **`cleared_after_min`** is the minutes from a Done to the clear.
- **The headline.** When an event is open, its issue leads, ranked by kind (`danger` > `sustained` > `unusual` >
  `spike`), then by `opened_at`, and `lead.by` is `event`. `headline_rule` says so in words. With nothing open,
  today's rule stands.
- **`open_asks` stays on the wire** as it is, for a page or agent older than this.

`tools/check_wire.py --update` and `tests/data/wire/issues-v0.json` change in the same commit. Adding a key is not a
lost key, so the format stays `issues-v0`.

### 3.2 `POST /actions` takes an event

`{event_id, stage, actor, note}`, where the stage is the button:

| button | stage |
|---|---|
| Done | `acted` |
| Not now | `acknowledged` |
| Doesn't fit | `dismissed` |

How these count in ρ is Plan 2's decision record (alerts spec §7: any button is an answer). This piece writes the
rows and changes no published number.

- The token rules (`ACT_TOKEN` or `ADMIN_TOKEN` from a browser) and the refusal sentences (401, 403, 400) are
  today's.
- `DECISION_REQUIRED` applies to alert-based acts only: an event's buttons are the decision.
- The bot's Plan 2 handler calls the same function, so a press on the page and a press in Telegram write the same
  row.
- A fixture refuses, as it does today for alerts.

### 3.3 Fixtures carry the block they captured

`planetai snapshot` already stores `GET /issues` verbatim, and from v0.77 that includes `events`. A replay passes the
captured block to the engine, which ranks the headline and recomputes `uncovered_asks` from it, so the snapshot needs
no new table and no new route. A fixture captured before v0.77 has no block, and replays with `events: null`: the
"older node" state of §5.

### 3.4 `GET /actions?events=1`

`GET /actions` keeps answering alert rows only, with the same fields, so a v0.76 page reading it never meets a row
with no `alert_id`. With `events=1` it also returns the rows that carry an `event_id`, with that column. The page of
§4 reads it for the ledger.

## 4. The page (v0.78)

### 4.1 Now, top to bottom

| part | what changes |
|---|---|
| header | nothing |
| ladder | one row of rungs. The ruler and the two key lines move into the "one cell here" fold |
| lead · ground | the lead draws the node's headline (§3.1) and its last line counts events (below); the ground beside it is unchanged |
| **Decide** | the event cards (§4.2), and nothing else on Now |
| **Observe** | the evidence, in the order a decision reads it: Every issue, at every distance → The day this place just had → The day it is about to have → What the stations read |
| **Act** | the record of answers (§4.3) and the ledger |
| **Measure** | Whether it worked · Which of these worked · Every figure, and where it came from |

- **The lead's last line:**
  - an event open: `1 event open · heat · sustained since 13:00 · in Decide`, with `shadow` added in shadow;
  - nothing open: `nothing open · 2 cleared today`;
  - a `rules` node: `2 alerts open · in Decide`.
- **The stage heads lose their numbers.** The drawn order is no longer the loop order. Each head keeps its name and
  its line. Decide's line becomes "what to do about it". The loop mark and learn mode still explain the loop.
- **Four sections move from Now to Network:** `claims` (Whose word, over how much ground), `grain` (What each rung
  is worth), `sources` (What this page is made of) and `requests` (What this page asked of the world). They are about
  what this node may say and send, and Network is "this node in relation to the network".
- **Arrange keeps working.** `UI_LAYOUT` orders sections within a stage, and that holds. An arrangement naming a
  section that moved is ignored for that section, never an error.

### 4.2 The event card

One per open event, in the node's order. It is a **readout**, one figure with its comparisons, so the four card kinds
stay four.

```
[pix-heat] Heat · sustained · since 13:00 · K room, L room · watching — last seen 2 min ago   shadow — would have sent
35.8 °C  peak        usual at this hour 33.4 · outside 29.1 (own kit) · the line 35
Open up now: outside is 29.1 °C, inside 35.8.
[ Done ]  [ Not now ]  [ Doesn't fit ]
sent 13:02 to Telegram: "…"
evidence: heat at every distance · the day · K and L rooms' stations · from 9 rule rows ▸
```

- **The live stamp** ("watching — last seen …", from the wire's `last_seen_at`) rides the header. Everything else
  on the card is event-scoped — peak, message, context — so an event that stays open for hours (the margin doing
  its work on a hot night; `docs/decisions/2026-10-10-heat-margin.md`) would otherwise read as frozen while the
  engine steps every minute. The age ticks up on every poll: the visible proof the feed is alive. No current
  *value* rides here — the hero's figure is not in the event's measure (heat's hero is air temperature, the event
  is apparent), and the card does not mix the two. No `last_seen_at`, no stamp: the card never invents one.
- **The numeral** is the peak, with `context` beside it. It is `--signal-worse` only when past the issue's line,
  which is what that colour already means.
- **The action** is in body type, under an ink rule, not a coloured one.
- **The buttons** are ink. Green is a loop closed, so it appears only after **Done**, as a closed ring:
  `Done · tomas · 13:20`. The card stays until the event clears, then moves to Act.
  - **Not now** leaves the card on the page, muted: `held until 16:20 unless it reaches danger`.
  - **Doesn't fit** opens one optional field, "What did you do instead?", the bot's own question, kept as the note.
    The answer line carries it, in quotes: `Doesn't fit · tomas · 13:20 — "opened the west side"`. An answer
    without a note invents none.
  - Labels come from `events.buttons`.
- **Who pressed.** The first press asks for a name, and the browser keeps it for the next. The form does not send
  an anonymous answer — five nameless rows landed on node #1 the morning the card looked frozen, and ρ is built
  out of who answered. (The node still takes an empty `actor` from curl; a LoRa bridge may not know names. The
  card says "somebody" for those.) The line saying a device
  needs the act token stays under the card. The node's refusal is printed as it wrote it.
- **The message** is printed small, word for word, as sent (or "would have sent" in shadow).
- **The evidence links** go to the issue's row in the matrix, its day series and the stations section, with the
  event's rooms marked. "From N rule rows" opens, inside the card, the rows in `alerts` it covers: id, rule,
  room, time.
- **Alerts no event covers.** On a node running events or shadow, an open act-level alert that is in no event's
  `alerts` (today `nearby/only_here`) is drawn after the event cards in the same shape, with **I did this**. Nothing
  that asks a person something disappears.
- **Gone for good:** "Decide about this" and its form.

### 4.3 Act and Measure

**"What was asked, and what was answered"** replaces the alert strip and the per-rule rows of rings. It is a
**row**, counted in signs:

```
○●●○●  5 events in 7 days · 3 answered
heat · sustained   Sat 13:00–17:40   K, L    "Open up now"          Done · tomas · cleared 40 min after
air  · spike       Sat 19:10–19:50   K       "Open the kitchen…"    Not now
heat · unusual     Fri 02:00–03:10   L       "Cool the room…"       no answer · held for quiet hours
```

- One ring per event: green and closed if answered, hollow if not. Seven days are shown, and older ones are in a
  fold.
- "Cleared N min after" appears only on a Done followed by a clear, and it is the node's number.
- On a `rules` node, Act keeps today's per-rule rows under "this node sends alerts, not events", because that is its
  record. The strip goes on every node: Decide holds the buttons now.

**"What was decided, and by whom"** stays.
- Event answers read `done`, `not now` or `doesn't fit` with their issue.
- A note shows only to a reader with a token, as today.
- `decided first` stays for alert acts.

**Measure** draws what `/rho` and `/effect` return. The ρ row's caption takes its unit from the node ("30 of 271
alerts", later "3 of 5 events"). The page never relabels a published number.

### 4.4 Modes, views, languages

- **Simple mode on Now.** The open-alert row becomes the lead issue's open event: its sign, **the action**, and the
  three buttons. With more events open it adds `and 1 more open · in advanced`. A `rules` node keeps today's row.
- **Learn mode.** Every new or changed part has a mark. Its card quotes `docs/site/dashboard.md` as rewritten, so
  `tools/build_learn.py` and `tools/check_ui.py` keep holding.
- **Network** draws the four sections it gains. **Historical** and **the wall** do not change. The wall draws no
  asks.
- **The ask pane** sees events through `/issues` with no change. Its act card is out of scope.
- **Language.** The action, the message and the button labels all come from the node. The page holds no copy of any
  of them.

## 5. Absence

Each state is said in words. None is drawn as a zero or a blank.

| state | what Decide says |
|---|---|
| events or shadow, an event open | the cards (§4.2) |
| events or shadow, nothing open | "Nothing open. 2 cleared today, the last at 14:40 (air)." |
| `rules` | the alert cards with **I did this**, under "this node sends alerts, not events" |
| a node older than v0.77 (no `events` key) | "This node is v0.76: it sends alerts, not events", followed by the alert cards |
| the events block could not be read | the node's sentence (`events.error`), followed by the alert cards |
| `/issues` did not answer | as today: the figures stay, and the pill says `stale` |

## 6. Proof

**The server piece:**
- Tests against both shapes the engine meets: a capture (strings) and a live row (datetimes). v0.75's `/ask`
  returned 500 on node #1 while every fixture test passed.
- Each button's stage, each refusal, and the fixture refusal are tested. The `alerts` match by window is SQL, and
  CI has no Postgres, so it is proven on the nodes below.
- On node #1 (`events`) and node #3 (`shadow`) after the update: `/issues.events.open` is read and compared with
  `alert_events WHERE cleared_at IS NULL`, read-only.

**The page:**
- A fixture captured from node #1 once it has a day of events, with at least one open event and one answered, is the
  visual gate's new baseline. The move is recorded in the PR as deliberate.
- The new `dashboard.js` is served live from node #1, as the sections are closures and a lifted test misses their
  scope. It is checked at 390 and 1440 px, in each state of §5. `?fixture=` covers the states node #1 cannot show.
- One real press of each button on node #1, by Tomas or with his go: it writes real `actions` rows.

**Before either piece is proven on a node:** on 5 October node #1 ran in shadow for about four hours with its heat
rules returning rows, and `alert_events` and `event_messages` stayed empty. That is being found in its own session.
The server piece's code and tests can proceed, but its proof on a node waits for that answer.

## 7. Releases

| PR | contents | milestone |
|---|---|---|
| A: events on the wire | §3: the `events` key, the event-led headline, `POST /actions` with `event_id`, `GET /actions?events=1`; `docs/site/api.md` | v0.77, `needs testing` |
| B: the page | §4 and §5; `docs/site/dashboard.md` rewritten, `docs/GUI.md` | v0.78, `needs testing` |

B is one PR because the layout and the cards share every line of Decide. The plan may split it if the diff argues
for it. `docs/site/design.md` does not change: no new card kind, colour or sign. Each PR carries a CHANGELOG
`Unreleased` line. `docs/NEXT_RELEASE.md` rule 2 holds: `app/static/*` lands in v0.78, apart from v0.77's packs.

## 8. Not in this work

- The Telegram buttons themselves and the learning from them (the rest of Plan 2).
- ρ over events and its decision record (Plan 2).
- Anticipation (Plan 3) and reports built from events (Plan 4).
- The wall, the ask pane's act card, and Historical.
