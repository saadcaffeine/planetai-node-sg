# The dashboard
<!-- checked: v0.80.10 -->

The dashboard is where a node is read. Once it is open, the loop the node runs becomes something a person
can follow and take part in: what it observed about the place, what it suggests, what it has asked of the
people there, and whether that worked. The page's script says it in its own words: a node observes its place, "It
ACTS by asking somebody to do something. It MEASURES whether that worked and how long it took, and the loop
closes." Two of those stages need a person. The answer to what the node asked, Done, Not now or Doesn't fit,
is written on this page, and so is the note that says what was done.

The node serves `index.html` and a fixed list of companion files by name from `GET /static/{name}`: three
stylesheets (`tokens.css`, `planetai-theme.css`, `dashboard.css`), `dashboard.js`, the drawing library
(`plot.umd.min.js` and `d3.min.js`), two SVGs, `kilometre-cells.json`,
`learn.json` and the self-hosted fonts; for the map ground, `maplibre-gl.js`, `maplibre-gl.css` and `deck.gl.min.js`;
and for the five doors (`doors.html`, served by default at `/`; `/?layout=classic` serves `index.html`), thirteen `doors-*.js`, `world-land-110m.json` and `docs_site.json`. The node computes and the page draws. A number the page works out
for itself is a bug.

## A first read

1. **Open it.** `planetai ui` prints the addresses: `On this machine: http://localhost:8080/`, `On your
   network: http://<ip>:8080/`, and the tailnet address once `planetai mesh` has run. It also prints the admin
   token and the act token. Open one of the addresses. At `SHARE_LEVEL=off` a browser with no token gets
   "This node is not sharing its readings with the network"; `planetai config set SHARE_LEVEL open` lets
   every screen in the house read the page (see [Sharing](sharing.md)). What you should see is the header
   (Now, Historical, Network, Wall, Arrange, Set up) and, for about three seconds, the page listing what it
   asked the node and how many milliseconds each answer took. Each row there is one route the page read,
   with its time or `no answer`; a `no answer` row is the part of the node that is not answering, and
   nothing in that panel is a reading yet.
2. **Step the ladder.** The strip of eleven rungs above everything is the ladder (the wall and
   `planetai ui` carry the same control under the same name). Press 6, then 10. The
   ground and the station groups re-draw at each rung, and so do the resolution figures on Network; rungs 6 and coarser are dotted
   because a cell that coarse may leave the machine. This is the node telling you how coarse each thing you
   are about to read is.
3. **Read the lead.** The sentence under the ladder is the headline issue in the household's language, with
   its rule under it, a dot per distance and the line in red. The why line says why this issue leads. The last
   line says what is open and links to Decide. On a node that tells events it counts events, for example
   `1 event open · heat · sustained since 13:00 · in Decide`, or `nothing open · 2 cleared today`; a node
   still on the old engine counts alerts, `2 alerts open · in Decide`. The node chose this issue, not the page:
   the why line ends on the node's own `headline_rule`, and the pill at the end of the last line (`live`,
   `stale` or `cached`) says how current it is.
4. **Find what is open.** The link in that line goes to Decide, the first section under the lead. On a node
   that tells events there is one card for each open event: the issue, the kind of event and when it began,
   the peak with what it is compared to, the one action the node chose, and **Done**, **Not now** and
   **Doesn't fit** under it. The evidence that explains it is the Observe section below. On a node still on
   the old engine, Decide says "This node sends alerts, not events" and draws one card for each issue with an open alert.
5. **Answer it.** Press **Done** when it is done. The first press asks for your name, and this browser keeps it
   for the next. The page answers "Recorded." and the card shows a closed ring with your name and the time.
   If it answers with the node's own 401 or 403 sentence instead, go to Set up, paste the act token that
   `planetai ui` printed, and press it again. On an alert card the buttons are **Decide about this**, which
   records what will be done, and **I did this**, which records who did it and what; the page answers
   "Recorded. The node watches what happens next."
6. **Find the record.** Act's "What was asked, and what was answered" has a ring for your event, closed, and a
   row with the action the node sent and your answer. "What was decided, and by whom", just below, has your
   name at the top of its fold with the button you pressed. Pressing Done on an event does not change ρ yet; an act on an
   alert is in `actions`, closes the alert, and counts towards ρ in Measure, with `decided first` if you
   decided before it.
7. **Press "Not now" on another.** The card stays on the page, muted: `held until 16:20 unless it reaches
   danger`. It is an answer, and it is in the record.

## Views

In the order the header draws them:

| view | URL | what it shows |
|---|---|---|
| **Now** | `#now` | the ladder, the lead, then the four stages in the order a person reads them: Decide, Observe, Act, Measure. The default view |
| **Historical** | `#historical` | the day this place usually has, what the satellite says year by year, how far back this node can be asked, and what the node doubts about its own sensors |
| **Network** | `#network` | this node in relation to the network and nothing else: what moves through it, what this place could read and where it could go, what leaves by radio, the mesh in the house, the hardware, and what this node may say and send: what this page is made of, what it asked of the world, whose word it speaks with over how much ground, and what each rung is worth |
| **Wall** | `#wall` | the dark register, for a screen on a wall; see [Wall mode](wall.md) |
| **Arrange** | `#arrange` | Now in another mode: move a section within its stage, hide one, restore it, Default, Done; saved as `UI_LAYOUT`. The ladder, the lead and the ground are fixed and carry no controls. An arrangement that names a section now on another view is ignored for that section, never an error |
| **Set up** | `#setup` | the settings, behind a token, and every registered section with whether it is drawing |

The ladder is Now's (and Arrange's) control and is drawn nowhere else. The resolution still travels in the URL
as `?res=`, so a link into any view keeps its resolution. The header also carries the mode switch,
**ask the node** right of it (see [below](#ask-the-node)), the Paper / Dark register switch (kept in this browser; `?register=` reads first and remembers nothing) and **↻**, "Ask
the node again".

Other query keys: `?view=` works as the hash does (a hash that names no view is a link to a section on the page you are on, so
it keeps the view), `?fixture=<name>` replays a committed snapshot (see
below), `?state=empty` or `?state=refused` draws those states for a capture, `?worth=1` opens the ladder's
fold, and on the wall `?var=` and `?vars=all`.

## Modes

How much of the page is drawn. Three, in the header beside the register:

| mode | what it draws |
|---|---|
| **simple** | offered on Now, Historical and Network only. On Now it is what a person in the house asks: is it fine, is anything changing, is there something to do. See below. On Historical it draws "What the satellite says"; on Network, "This node, and what moves through it" |
| **advanced** | every section registered for the view: on Now in the order Decide, Observe, Act, Measure, and elsewhere in the loop's order. The default |
| **learn** | advanced, with a question mark at each part of the page: every section, the ladder, the lead and the foot. Learn opens the ask pane, and pressing a mark puts a card in it that quotes this node's own documentation for that part, names the page and section the words came from by their titles, links out, and walks to the next. The chips under it become two questions about that part. Not on the wall, which has no header to switch it on |

**Simple on Now** draws, in order: the header and the modes; the lead, with the issue and when it was read
in place of the kicker, the numeral and its pictogram, the node's sentence (words only), one plain sentence of the
distances and the line, and the rule; the open event, if there is one, with the sign of its issue, **the action the node chose** and **Done**, **Not now** and **Doesn't fit**
(with more than one open it adds `and 1 more open · in advanced`, and in shadow it says nothing was sent); on a node still on the old
engine, the open alert instead, with its first line, its number and **I did this**; the ground, with a one-line key (this house, and how many other stations
are within a kilometre) in place of the cell, the plan caption and the resolution line; one paragraph the node
writes, `digest.simple`; and **also watched here**, every other issue this node watches, its sign and value.
Pressing one draws that issue in the lead and says so ("you are looking at this · the node's pick is heat"),
with **back**. That choice is the reader's view, not a setting: it is kept only until the page reloads, and a
poll in between does not undo it. There is no ladder, no matrix, no stage names, no provenance chips and no
figures in simple; they are one press away in advanced. A node too old to send `digest.simple` gets a note
naming the version it is talking to, never a paragraph composed in the browser.

`UI_MODE` is what the page **opens** as, chosen by the household. A reader who switches is switching their
own copy and nobody else's: the choice is kept in this browser, the way the register is. `?mode=simple` is
read first and remembers nothing. It is how one person sends another the short answer without changing
their page, and how the measuring rig renders all three.

The learn cards are quotations, not summaries. The node does not serve this documentation (the site build
does), so `tools/build_learn.py` cuts the spans out of these pages at build time into `app/static/learn.json`,
which the page fetches only when somebody turns learn mode on. The quote therefore reads on a network with
no route out, and `make lint` fails when a span is no longer in the page it names. Every registered section
carries at least one mark, and the foot carries the node's purpose and its doors on every view but the wall.
The bar under the header says how many marks are on the view you are looking at; *walk the page* starts at
the first of them, and **previous** and **next** on the card follow the view from top to bottom, in the order the marks are drawn; walking replaces the card rather than stacking one per mark. With a model on the node, a question asked while a card is last in the thread is sent with that part's documentation. Without one, the card stands alone and its chip searches the documentation for its title. The quotes are in English
only, whatever language the rest of the page is drawn in, because the documentation is. The wall has no
Learn mode: it draws no header, so there is nothing on it to switch one on, and no marks.

## Ask the node

**ask the node**, right of the modes (in the foot on a phone), opens a pane beside the page that asks a model
about what the page shows: the one Set up → Model names, the same as the Telegram bot's. That is the model
`planetai agent local` set up on this machine, one on another machine of yours, or an online one only when
`AGENT_PREFER` allows it; the pane's header names the model and where it runs. It runs the read tools and
changes nothing: a setting or an **I did this** it reaches for is a card the person presses. The thread lives
in the browser tab until it closes, **new conversation** is pressed, or half an hour passes with no question, and
the node keeps nothing asked or answered. With no model it still searches this
documentation (`GET /docs/search`). `UI_ASK=off` removes the toggle and the pane, and the wall never shows
it. The whole of it is on [Ask the node](ask.md).

## The lead

The **ladder** sits above the lead: eleven rungs, one per H3 resolution from 2 to 12, opening at 8. Rungs coarse enough that the cell may leave the machine (resolution 6 and coarser, the presence floor) are dotted rather than blue; rungs finer than the node says where it is are struck through.

The zones are texture, not hue, so the cells blue keeps its one meaning and the ladder survives being printed.
Each rung names its edge length, and pressing one re-derives the whole page. The ladder is one row of rungs,
and under it one chip, "one cell here", opens a fold, *What one cell at resolution N is worth*. The fold holds,
above 860 px, a log ruler from 10 m to 200 km that runs the same way as the ladder, coarse on the left; the
key that names both zones; three hexagons to true relative scale (the rung you are on, filled, against the
rungs either side); and a table of what each thing the node speaks for costs to cover at it. Each rung is
about seven times finer by area than the one above. The fold's state is `?worth=1`, so it survives the ladder
it is read against.

The first thing on Now is the ladder, and under it the lead: the headline issue's kicker, its numeral and pictogram, the title (the sentence's qualitative head — no number, no indicator) with its tagline smaller beneath (the line, the comparison, the day's event), a why line and the rule. The last line gives when the numeral was read, the as-of time, what is open and a link to Decide, and a pill: `live`, `stale` or `cached`.

What that line counts follows the node. With an event open it reads `1 event open · heat · sustained since
13:00 · in Decide`, and `· shadow` is added on a node that only records what it would have sent. With none open
it reads `nothing open · 2 cleared today`. A node on the old engine, an older node, or one whose events could
not be read counts alerts instead: `2 alerts open · in Decide`. So does a node that tells events when none is
open but an act-level alert that no event covers is: that alert is drawn in Decide, and the line counts it.

The lead draws the issue's `hero` from `/issues` and nothing else there, so a new issue leads the page with no change to the page. The rule's two ends are the issue's own, so a reading looks the same size tomorrow as tonight; a reading past an end sits on it and prints its real number. Coast has a rule and no line. Land has no rule, and its last line says when the satellite looked and when it looks next. The four distances in full are in the matrix. The why line ends on the node's own
`headline_rule`, so a reader can check why this issue is on top. The ground's drawing follows. What the lead says is open is
answered in Decide, the first section under it, and the **resolution line** is on Network, in "What each rung is
worth", as a readout of the cells occupied at the current rung.

At resolution 8 one cell is 639,778 m² on node #1, about 0.64 km², with an edge of 497 m. The resolution line counts the cells this node's stations with a coordinate fall in, how many of those stations sit in the node's own cell, and how many of those are its own.

## The ground

The section behind the lead is the node's own ground at the current rung, drawn under the cells: the node's
own cell in the cells blue, its neighbours as ink hairlines, its own stations filled and other stations
hollow. A node with no `NODE_LAT` and `NODE_LON` draws the grid from `/static/node-ground.svg` and says it
stands for no particular place yet.

Three bases: `plan`, offline, from `/place/geojson`: the building footprints within `PLACE_RADIUS_M`, projected in the browser with every vertex kept, nothing leaving the house; `sat`, Sentinel-2 cloudless tiles; `osm`, OpenStreetMap tiles.

Live tiles need `MAP_TILES=on` and are offered only at resolution 8 and coarser, because from 9 inward the
plan fills the frame. Each base's tab says what it costs before it is pressed: `sends nothing` for the plan,
a count of requests for the others. A press may only ever reduce what leaves the house. The plan needs a
token at every sharing level, because it is the shape of your building. An H3 id is printed in full, once
per object, never truncated.

With `UI_GROUND=map` the same ground is drawn by MapLibre and deck.gl and pans and zooms (the plan freely; a live
base stays put, because every drag would be tiles nobody priced). On that ground the strip also offers what the node
keeps of its own map, once `planetai run place basemap` or `planetai run earth-engine basemap` has run: `street map,
on this node` (OpenStreetMap vector tiles with names), `satellite, on this node` (its Sentinel-2 composite) and `drone,
on this node` (OpenAerialMap mosaics, from zoom 14). Each says `sends nothing`, because it is read from
`/ground/*` on this node with the page's token. Without WebGL2 the page draws the svg ground and says why.

Three things the grid forces the page to say: a cell is not the thing (three indoor sensors share one
coordinate); containment is exact in the index and approximate on the ground; and the four distances are
not four resolutions.

## The sections

Every section is registered with the page contract: `id`, `pack`, `stage`, `title`, `reads` and `render` (or `lead`), and optionally `order`, `needs`, `controls`, `wall`, `learn`, `notes`, `level` and `anchor`. The shell draws each one in the stage it belongs to. The loop runs observe, decide, act, measure, and Now draws Decide first.

`reads` names the routes the band's data comes from, the one it leans on most first. The shell prints them
beside the band's title, small, in mono and in their own case, as links: `GET /effect` on "Which of these
worked", `GET /issues` and `GET /actions` on the ledger. Pressing one opens the JSON the band was drawn
from, with whatever the sharing level allows that browser. `tools/check_ui.py`, in `make lint`, fails a
section with no `reads` and a route `app/main.py` does not define.

Each stage has a head with its name and a line saying what it holds, and a small loop mark that says where in
the loop it sits. The heads carry no numbers, because on Now the drawn order is no longer the loop's order.
Twenty-four sections are registered, in this order within each stage:

| stage | view | sections (pack) |
|---|---|---|
| **observe** (what is read, seen and heard about this place) | Now | The ground (place) · Every issue, at every distance · The day this place just had · The day it is about to have (forecast) · What the stations read (air-quality) |
| | Historical | How far back this node can be asked · The day this place usually has · What the satellite says (earth) |
| | Network | This node, and what moves through it · What this page is made of · What leaves this house by radio (reticulum) · The mesh in this house (meshtastic) · The hardware in this house (hardware) · What this place could read, and where it could go · What this page asked of the world (place) |
| **decide** (what to do about it) | Now | What to do about it |
| | Network | Whose word, over how much ground · What each rung is worth |
| | Historical | What the node doubts about its own sensors (trust) |
| **act** (what has been asked, of whom) | Now | What was asked, and what was answered · What was decided, and by whom |
| **measure** (whether it worked, and how long it took) | Now | Whether it worked · Which of these worked · Every figure on this page, and where it came from |

Sections with no pack named are `core`. The stages hold observe 15, decide 4, act 2, measure 3: on Now 5, 1, 2 and 3, on Network 7 and 2 of the first two, and on Historical 3 and 1. A section a pack
registers that is on none of these lists is drawn on Now, in its own stage and order.

A section whose `needs` are not on this node prints one line in their place, "The <pack> pack has nothing
here yet: … is not on this node.", never a blank and never a guess. A
section that throws prints that it did not render and why, and every other section still draws: a failure
is not an answer. The explanations every section wants to make are gathered into one folded band at the
foot, *Where these numbers come from*: one fold per section, and every note in it names its own subject
(84 labelled notes in `dashboard.js`).

Four card kinds and no fifth: readout, stack, series, row. A gap in a series is a gap in the line, never a ramp across the WHO line nobody measured. The node's own words are never uppercased: `µg/m³` once became `MG/M³` on the hero, a factor of a thousand.

### Observe

What the node read. Nothing here asks anything of a person. On Now it is the evidence for Decide, in the
order a decision reads it: "Every issue, at every distance", "The day this place just had", "The day it is about
to have" and "What the stations read". "The day this place usually has" draws the strips of every day this node holds (up to 90, `GET /issues/days?days=90`), and above them, once it has 7 local days, the hour inside and the hour outside are worst (`GET /shape`, which needs 14 days for a week, 60 for a month, 365 for a year); until then it says how many days it has. "How far back this node can be asked" gives, per kind of source, the oldest and newest
hourly reading (`GET /reach`). "What this place could read, and where it could go" reads the pinned source
registry (`GET /sources`, fetched the first time somebody opens Network). Its pin links to the registry on
GitHub at that commit. It says how many sources are registered and how many have code on this node; the
three counts the node computes per cell (`capable`, `reviewed`, `candidate`, see
[The source registry](sources.md#three-counts-per-cell)), added up over the cells; and the places to make
things and the designs to build that the registry lists, with each licence as the registry wrote it. A line
under the rows links to `GET /sources?status=live`, `GET /sources?status=candidate` and `GET /cells`, and to
[Adding a source](sources.md#adding-a-source).

"What the stations read": each row draws its day and answers a pointer; a station that stopped reporting in the last
30 days is listed in a fold, with when it was last heard.

### Decide

What a person adds here is an answer. Decide is the first section under the lead on Now, and on a node that tells
events it is the only thing in its stage there.

An event is the bot's own unit: one issue in one house, from when its rule first fires to when it clears, however many rule rows that took. Decide draws one card for each open event: the peak with its comparisons, the action the node chose, and the message it sent.

The numeral is red only when the peak is past the issue's line. The action and the message are the node's words,
in the household's language, and the page keeps no copy of either; in shadow the card says "shadow — nothing was
sent" and the message reads "would have sent". Under the card are links to the issue's row in the matrix, to the
day and to the stations, and "from 9 rule rows", which opens the rows in `alerts` the event covers: id, rule and
age. An open act-level alert that no event covers is drawn after the cards, in the same way, with **I did this**,
so nothing that asks a person something disappears.

**Done**, **Not now** and **Doesn't fit** each write one answer to the event: who pressed, and when. Done closes the loop and shows a closed ring. Not now holds the card, muted, for three hours unless the reading reaches danger. Doesn't fit asks one optional question, what did you do instead, and keeps the answer as the note.

The card stays until the event clears, and then it moves to Act. The first press asks for a name, and this browser
keeps it for the next. The words on the buttons are the node's own (`events.buttons`). From a browser the answer
needs `ACT_TOKEN` or `ADMIN_TOKEN`, entered once in Set up, and the form that opens for the name says so before
anybody records: "From another device this needs the act token: planetai ui prints it on the node, and Set
up → unlock holds it in this browser." When the node refuses, the page prints the node's own sentence, and it
refuses outright on a fixture, whose events belong to another node. ρ does not count events yet, so none
of the three buttons moves it, and `DECISION_REQUIRED` applies to alert acts only: an event's buttons are the
decision.

Decide says which of five states it is in, each in words and none as a zero or a blank:

| state | what Decide says |
|---|---|
| events or shadow, an event open, or an alert no event covers | the cards |
| events or shadow, no event open and no alert left uncovered | "Nothing open. 2 cleared today, the last at 14:40 (air)." |
| the old engine (`rules`) | "This node sends alerts, not events.", then one card for each issue with an open alert, or "Nothing is asking for anything." |
| a node older than v0.77, with no events | "This node is v0.76: it sends alerts, not events", then the alert cards |
| the events could not be read | the node's own sentence, then the alert cards |

On a node whose alert engine is `shadow` or `events`, an issue's state follows the alert events: `act` while an act-level
event is open and unanswered (a `danger` event stays `act` whatever the answer), `notable` once somebody has answered
it, while a warn-level event nobody has answered is open, and for a day after an event clears. The old heat and air rules' alerts are not asks there,
so they are not in `open_asks`. See `docs/SPEC_event_led_state.md`.

If `/issues` itself did not answer, the figures stay and the pill says `stale`; that is the pill's state, not
Decide's.

An alert card is the page as it was before events. It shows "what was seen", the alert's first line, and "what
this node suggests", the rule's own recommendation (the paragraph its author started with 👉), or a line saying
the rule carries none and the page will not invent one. **Decide about this** records `stage: decided` with who is
deciding and what will be done, or the rule's own line if **Take its word** is pressed; **I did this** records
`stage: acted`, with who and what was done. A decision moves nothing: it is not in ρ, not in the funnel, and
closes no alert. With `DECISION_REQUIRED=1` (Set up → Alerts, off by default) the node refuses an act with 409
unless a decision was recorded against the same alert first, and the page prints the node's sentence as it wrote
it: "this node is set to DECISION_REQUIRED, so an act needs a decision recorded against the same alert first.
Decide on the dashboard, then record what you did." Three more sections of this stage are not on Now: the two
resolution sections, which say at what resolution a thing may be said, and the trust section, which says which of
the node's own sensors it doubts.

"Whose word, over how much ground" covers with H3 cells the six footprints this node already declares,
from `COAST_MAX_KM` for the sea to the three decimals `/health` rounds a position to. Each produces one
number, and its card says how many cells of the rung you are on that one number has to cover. The other
four are `BAD_RADIUS_KM`, `EARTH_RADIUS_M`, `PLACE_RADIUS_M` and `LOCAL_RADIUS_M`. The node computes the
coverings and sends them in `GET /issues` as `geometry.claims`, widest first.

### Act

What was asked, and what was answered. "What was asked, and what was answered" is the record of the asking. On a
node that tells events it is one ring for each event of the last seven days, closed if somebody answered it and
hollow if not, and a row under them for each: the issue and the kind of event, when it began and when it
cleared (or `open`), the rooms, the action the node sent in quotes, and the answer in the button's word. "Cleared
40 min after" is the node's own number, and appears only on a Done that a clear followed. A day with no event
says so: "No event in the last 7 days: nothing was asked, and nothing needed asking." On a node on the old
engine Act says "This node sends alerts, not events" and keeps one row for each rule, with one ring for each
alert it sent. The strip of open alerts is gone from every node: Decide holds the buttons, and on a node on the
old engine **I did this** is on the alert card there. Below the record sit the row with the nearest place that
could make something, where the `make` pack is on, and the filter life of a purifier the household owns.

"What was decided, and by whom" is the
ledger, newest first, all of it in one fold: who, which button or stage, how long ago, and `decided first` on an
act that had a decision before it. An answer to an event reads Done, Not now or Doesn't fit, in the node's words,
and the issue it was about. Its head counts how many acts had a decision first. The note somebody
wrote is shown only to a reader with a token, because `GET /actions` is on no sharing allowlist.

### Measure

What the node measures about itself. Measure counts the hours over the line, today and this week, from the node's own count. "Whether it worked" draws ρ as a row of rings, answered first, with the
median minutes from alert to answer. Its caption says what it counts: alerts, because the node's ρ does not
count events yet, and the page never relabels a number the node published. The funnel is beside it: `asked`, `acknowledged`, `acted`, `measured`,
each a count against `asked`. `measured` is derived, not recorded: an act followed by 48 hours of silence
from the same rule on the same sensor, and the funnel says so. A zero says why it is a zero. The care label
under it is the five refusals of [Architecture](architecture.md) section 7, as signs. "Which of these
worked" reports per rule, over the whole record, how many acts there were and how many were followed by the
condition stopping within that window; only a rule that declares `watch: {metric, over}` also gets a typical
recovery time in hours. It is evidence that the condition ended, never that the act ended it. See
[ρ](rho.md). "Every figure on this page, and where it came from" is the node's own provenance for each
figure, from `GET /issues`, and under it one line links the same day as open data, CC BY 4.0:
`GET /export?day=<the day of the reading>`, and the days before it at `GET /exports`.

## The day figure

Each issue with a day has one drawing of its last 24 hours. Every distance is a trace in ink, dashed by distance, and
an hour nothing was recorded is a gap in it, never a line drawn across. The grey band is the usual for each hour,
from the node's own last 14 days. The red dashed line is the issue's line and the red ticks under the drawing are the
hours over it. An alert event is a bar from when it opened to when it cleared, and its answer is a ring: green for
Done. When an event is open, its own rooms are a heavier trace beside the house. Point at an hour, or focus the
drawing and use the arrow keys, and the line under it says that hour in words.

## The strips

One row a day and one cell an hour, the newest day at the bottom: the last seven days on Now under each day figure (the oldest row starts at this hour a week ago), and every
day the node holds on Historical. A darker cell is a higher reading on that issue's own scale, a red cell is an hour
over the line, and an outlined empty cell is an hour nothing was recorded. The column on the right is the node's own
count of hours over the line that day. An alert event outlines the hours it was open.

## Issues, states and distances

`GET /issues` is the whole of what the page knows about the place. For every issue the keeper declared in `NODE_ISSUES` (an undeclared one is still shown, as `watched: false`), the node computes a `state`: `act` (something is asked), `notable` (something changed), `quiet`, `context` (an issue that informs and never asks) or `none` (no record).

With it come the four distances, each with its value and its provenance word. The wire keys are `room`,
`yard`, `ring` and `region`; the page prints them as house, street, ring and region. Then the sentence
in three languages, the open alerts (`open_asks`), the series for the day, the `digest`, the geometry the
ladder is drawn from, the `asks` ledger, and `events`: the alert events (what is open, its one action, its latest
answer, the alerts it covers). Decide draws them, one card per open event.

The `headline` is the issue of the most serious open event, when the node has one (`lead.by` is `event`). With none open it is the issue with the highest state. Among issues in the same state, the one that moved most
in the last three hours leads, and an exact tie goes to the declared order. The node sends that rule as
`headline_rule` and the lead prints it. The same object comes back from the `issues` MCP tool, so an agent
and the household describe the same evening in the same words. The declarations are one file per issue in
`app/issues/*.yml`; see [Issues](issues.md).

## Keeping up

The page re-reads `/issues`, `/health` and `/rho` every `POLL_SECONDS`, the node's own polling interval,
clamped to 20 to 600 seconds (60 if the setting cannot be read). Settings, the plan, the satellite record,
the sensor list and the cells are read at load and not on a poll. A poll keeps the scroll position and the
open folds, and holds off while the tab is hidden, while a Set up group has an unsaved edit, and on a fixture.
When a poll gets no answer the figures stay, the pill says `stale`, and the as-of line reads "Read at … · the
node has not answered for N min". **↻** asks again at once.

While the node has not answered, the page shows what it asked and how long each read took. On a load or a
press of **↻** that state is held for at least `--motion-asking-hold` (3 s), so it can be read. A routine poll never
shows it; the first poll after the node stopped answering shows it without the hold. Under reduced motion
it is not held at all.

## Set up

Behind a token, once per browser. The admin token is kept in the browser's local storage as `planetai_admin`;
the act token, the weaker one that can only close a loop, as `planetai_act`. Eight tabs, in the order
somebody setting up a node needs them:

| tab | what is in it |
|---|---|
| **Basics** | what this place watches, in order; what kind of node it is; its language; how the page opens. Its name, city, position and time zone are shown read-only: edit `.env`, then `planetai restart` |
| **Sources** | sensors and data: Smart Citizen, AirGradient and PurpleAir hosts, the mesh radios, Bali Air Dispatch, Open-Meteo, open-data portals. A source that comes as a pack is set in its card under Packs |
| **Alerts** | alerts and reports: Telegram chat ids, when reports go out, what interrupts, quiet hours, which engine sends the heat and air messages (`ALERT_ENGINE`), how many it may send a day (`ALERT_MAX_PER_DAY`), what this home has (`HOME_HAS`), mesh alerts, whether an act needs a decision first |
| **Model** | ask and model: which model answers, on the ask pane and on Telegram alike; the remote and online models |
| **Packs** | which packs load, and one card per pack with its switch, what it is, and its own settings; a key the pack lists under `secrets:` is masked once saved |
| **Keys** | every secret: the Telegram bot token, the two model keys, and the backup, parent, aggregate and act tokens |
| **Sharing** | sharing and network: who may read this node, live map tiles, the Reticulum announce and alerts, Home Assistant, the parent node |
| **System** | tuning numbers, how the ground is drawn (`UI_GROUND`), the layout Arrange writes, and what is read once at start (port, extra containers, backups, poll interval), read-only |
 A value set here is live
within 20 seconds and wins over `.env`; the page says so beside it; a blank returns the key to `.env`. Every
change is an `actions` row with `stage='settings'` and the actor `dashboard` (`planetai-cli` from the command
line, the agent's name over MCP). The section list under it names every registered section by pack and
whether it is drawing or has nothing here yet.

A save sends only the fields somebody edited, in every group. Before it writes, the page reads `/settings`
again. If one of those keys changed on the node after the form was drawn (from the CLI, an agent or another
screen), nothing is saved: the field says what the node holds now and the last change the ledger has for it,
read from `GET /actions?stage=settings`, and a second press of Save replaces it. In the packs group a pack
switch decides `PACKS_ENABLED` only when one was moved; otherwise the text field does.

A pack's own keys save the same way, and the pack has the new value at its next run, whether or not the pack
is switched on yet. A node older than this refuses them with 400 `<KEY> is not a runtime setting`; see
[Configuration](configuration.md#keys-the-packs-declare).

## What a reader without a token sees

At `SHARE_LEVEL=off` a browser gets the dashboard shell, the node's name and city from `/health`, and the
refused page: "This node is not sharing its readings with the network", the node's own 403 sentence, and
"Ask whoever set this node up to turn sharing on, or open this page on the machine the node runs on." A
blank would be the node lying about being broken. A browser on the node's own machine counts as a reader on
the network here, because inside Docker it arrives as the bridge gateway. At `open` the whole read API
answers and the page draws; the plan still needs a token at every level. See [Sharing](sharing.md).

> **Gap in v0.80.10.** At `SHARE_LEVEL=off` a browser that has never stored a token draws the refused page
> on every view, Set up included, so there is nowhere on the page to enter one, and the refused page's advice
> to open it on the node's own machine does not get past the refusal. Turn sharing on, store the token in
> Set up, and turn it off again; or read the page at `open`. The doors are the way round it: at `off` without a token
> they draw the node's name, its refusal and the token field, so the default doors view is where a refused screen unlocks.

## The five doors

The node renders as five doors by default, the redesign worked out in planetai-design (R33 to R45): **Now**
(the moment, its decision with Done, Not now and Doesn't fit, and the stations around the house), **Place** (the
ground as a map with layers, scales and a measuring tool, the satellite years and what changed), **Data** (every
reading, drawn, the seven days of every issue, the models, the Index and the ledger), **Wall** (the keeper's one
dark screen) and **Node** (what comes in and goes out, the nodes around it, and how it is running). The classic
dashboard remains available at `/?layout=classic`.

The doors read the routes the dashboard reads, renamed and pivoted in the page and never recomputed
(`doors-load.js`), and they read them with the same token, kept in the same place in the browser. A screen without
the token draws what `SHARE_LEVEL` gives it and says, where a part is missing, why. At `open` that is the issues, the
events, the stations' 15-minute means, the models, the Index, the satellite years and the ledger without its notes.
The map, the cells, every distance and the hourly table are token-only at every level, because together they say
where the node is and what the household did hour by hour. **Set up → This screen** (the foot's "Unlock this screen") stores the act or admin
token in that browser. The gear in the bar opens **Set up**, a page of its own: every setting by group, saved only where it changed and never over a change made on the node meanwhile, the pack switches, who may read the node, this screen's token, updates, and **Machine**, the machine under the node (`GET /machine`) and how long its disk lasts (`GET /storage`). The bar says which version is running. The Wall's right column is **the node, thinking aloud**: every ten minutes, from another angle each time, the node's model (the one chosen under Set up → Model, through `POST /ask`) says in six to eight plain sentences what is happening inside, how it compares with the street and the neighbourhood, what it suggests for an ordinary day and what the next hours may bring, typed at a reading pace, with a countdown to the next. It names the model that answered, warns when the keeper's choice lets the question go online, and calls itself a model's words, never a reading; nothing is kept. Every door but the Wall ends in a foot with the documentation, Ask the node, the classic dashboard, today's open export and Fab City. `?fixture=<name>` works here too, and shows a screen without the token only what the node
would show it.

## Languages

The page reads the household's language from `/health.locale` (`ALERT_LOCALE`, which answers at every
sharing level) and draws the issue sentences, labels and distances in English, Bahasa Indonesia or Spanish.

## Looking at it without a node

`?fixture=<name>` replays a committed snapshot through the node's own engine, `GET /issues/fixtures/<name>`,
and the pill says `cached`. Eight ship: six captures of node #1, `node1-2026-09-06`, `node1-2026-09-21`,
`node1-2026-09-21b`, `node1-2026-09-21d`, `node1-2026-10-06-events`, taken with an air event open, and
`node1-2026-10-06-figures`, which carries the days the strips draw and is the one the visual gate measures, and two derived from `node1-2026-09-21d` for the visual tests,
`coast-led-2026-09-21` and `land-led-2026-09-21`, where coast and land lead; `GET /issues/fixtures` lists them. `planetai snapshot` writes a new one from a running
node. A snapshot missing a table the engine reads comes back with an error in place of the issues rather
than a half-drawn page, and the 6 September capture predates `planetai snapshot`, so some of its cards are
empty.

`python3 tools/shots.py` renders every fixture the node ships, with every request fulfilled from disk, at
375, 768, 1440 and 1920 px. It needs Playwright from the sibling design repository and is not a gate a node
runs. `tests/visual/gate.sh` measures what the section contract cannot enforce: the four card kinds and
numerals carrying `data-num` with a comparison beside them.

## Where this leads

The page answers when somebody is looking at it. [The report](report.md) is the same node speaking at the
hours the household chose, and [Alerts](alerts.md) and [Channels](channels.md) are how an alert reaches a
person who is not looking. What the Measure stage counts is explained in [ρ](rho.md). A screen on the wall
is [Wall mode](wall.md).
