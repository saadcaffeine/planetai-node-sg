# How it works
<!-- checked: v0.80.10 -->

A node is two containers on one machine. `db` is Postgres with PostGIS, bound to the machine itself. `app` is
one Python process that answers the HTTP API on port 8080 and runs six loops in the background, a seventh when
the Reticulum bridge is on. An `agent` container for the Telegram bot and a Reticulum bridge are optional.
Everything a node does is one of those loops or one of the API's answers, and this page follows a reading
through the whole of it. The node's own description of itself, the one it hands every agent that connects,
is the short version: it "connects everything measuring one place, from sensors on the wall to satellites
overhead, decides where it stands, and tells the people there what to do. Raw readings never leave it."

## Sense, then one loop in four stages

```
   SENSE      adapters: your sensors · other people's stations · open data · Earth models
      │  (ts, sensor_id, metric, value)
      ▼
   OBSERVE  ──▶  DECIDE  ──▶  ACT  ──▶  MEASURE  ──▶  OBSERVE …
   what is read    what to do     what has been   whether it worked,
   about this      about it       asked, of whom  and how long it took
   place
```

`ARCHITECTURE.md` describes three layers, Sense, Observe and Act, measured against the Fab City Index. The
dashboard, the four-sentence digest in `GET /issues` and `docs/GUI.md` read the same machinery as four
stages, and every section on the page belongs to one of them. The descriptions under the stages above are the
page's own. Sense is what feeds them.

### Sense

Every adapter (a Smart Citizen kit, the ring of Bali Air Dispatch stations, a CKAN portal, the Copernicus
model sampled at your coordinates, a pack's own `adapter.py`) returns the same two things: a list of sensors
and a list of readings `(ts, sensor_id, metric, value)`. The poll loop asks every enabled adapter every
`POLL_SECONDS` (300) and upserts what comes back. The core does not know what `pm25` means. It stores rows,
and each sensor row says how its number was produced (`kind`), whether it is yours and within
`LOCAL_RADIUS_M` (500 m) of the node (`local`), and whether it may be counted (`custody`). See
[Concepts](concepts.md).

### Observe

Readings land in one table, and three views do the arithmetic. `stats` holds the last 24 hours per sensor and
metric (15-minute, hourly and 24-hour means, and how long a sensor has been silent), `readings_1h` holds hourly
means over all history, and `observations` holds the latest value from every slow source: a portal, a model,
a map. On top of them, `GET /issues` is the one document the dashboard draws. For every issue the keeper
declared in `NODE_ISSUES` it computes a state, the four distances with their provenance, a sentence in
English, Bahasa Indonesia and Spanish, the open alerts and a 24-hour series, and it names a headline issue and
writes a digest of four sentences, one per stage.

Two more reads sit beside it. `GET /shape` is "the day this place usually has", indoor against outdoor,
hour by hour; it needs 7 days of the node's own readings for a day, 14 for a week, 60 for a month and 365 for
a year. `GET /reach` says how far back each kind of source can be asked. Every node exposes the same read
[API](api.md). The dashboard, the CLI, the bot and a NAS are its clients.

### Decide

On the page, Decide is "what to do about it", the first section under the lead on Now. Its other sections, whose
word covers how much ground and what each H3 resolution is worth, are on Network, and what the node doubts about
its own sensors is on Historical. Since v0.72 Decide draws a card for each issue with an open act-level alert; a
node that tells events draws one card for each open event instead, with its action and three buttons. An alert's card shows what was seen and
"what this node suggests", which is the rule's own last line, the one that begins with 👉, written by
whoever wrote the rule. A person may record a decision there. It is written to `actions` with
`stage: decided`, and it moves nothing: it closes no alert, it is not in ρ and it is not a stage in the funnel.

Two words are easy to confuse here. `ARCHITECTURE.md` maps decide to the `acknowledged` row of its ledger;
the page's `decided` row is a separate record. With `DECISION_REQUIRED=1` (off by default) the node refuses
an `acted` with HTTP 409 unless a `decided` row exists for the same alert, whichever way the act arrives.

### Act

A rule is SQL that returns rows, plus a message template, a level and a cooldown. The rules loop runs every
rule once a minute as the read-only role `planetai_ro`, and every row that comes back is a candidate alert.
A cooldown per rule and sensor stops it repeating; the level decides whether it interrupts anyone; quiet
hours hold everything but `act`. The alert goes out on [Telegram](channels.md), the LoRa mesh, LXMF and Home
Assistant. When a person does something about it, that is a row in `actions`, from any of five places: the
dashboard's **I did this** (which needs `ACT_TOKEN` or `ADMIN_TOKEN` in the browser), `planetai act`, `/act
<id> <what you did>` in Telegram, the MCP `act` tool, or an `act <id>` message over Reticulum. An agent
drafts and never dispatches: nothing is recorded as done without that row.

A rule that declares a `kind` (the heat and air-quality rules do) takes a different path when `ALERT_ENGINE` is
`shadow` or `events`. Its rows are folded into one alert event per issue per house, which opens, escalates and
clears, with at most one action chosen from what is inside, outside and in the home. In `shadow` the engine records
what it would send and sends nothing. In `events` it sends that one message, only danger in quiet hours and at most
`ALERT_MAX_PER_DAY` pushes outside danger, and the old heat and air rules still record their alerts but stop
sending. The default, `rules`, runs no engine. A person answers an event with Done, Not now or Doesn't fit,
posted to `/actions` with an `event_id`; that answer is not in ρ yet.

### Measure

[ρ](rho.md) is the share of act-level alerts in the last 30 days that had an `acknowledged` or `acted` row
within 24 hours, pooled with the alert timestamps a node's children push up. It becomes the core's own Index
cell, `Governance|<Scale>`, which reads `partial` until five act-level alerts have been answered within a
day. Beside it the funnel counts the same alerts four times: asked, acknowledged, acted, measured. Nothing posts `measured`. The node
derives it: an act followed by 2,880 minutes (48 hours) of silence from the same rule on the same sensor,
counted only for rules the node still runs. `GET /effect` asks the same question per rule over the whole
record, how many acts and how many cleared, and gives a recovery time in hours only for a rule that declares
`watch: {metric, over}`. Two rules do, both in the air-quality pack.

A pack's `cells.yml` computes the other Index cells the node has the data to fill, each with a `state`: `live`
if measured here, `partial` if derived or modelled, `mock` if a placeholder. Two generations of the Index
measured a snapshot with ρ implicit at 1. A node measures it, because it is the thing sending the alert and
the thing receiving the answer.

## The loops

| loop | every | what it does |
|---|---|---|
| poll | `POLL_SECONDS` (300) | asks every enabled adapter for sensors and readings and upserts them; a source that fails leaves its error in `/health.last_error`; a loop that fails outright appears under its name in `/health.errors` |
| rules and report | 60 s | writes the [report](report.md) if its hour is due, then runs every rule as the read-only role `planetai_ro` |
| usual for the hour | hourly | rebuilds `usual_by_hour`, each room's usual for each local hour over the fourteen complete days before today, which the event rules read |
| push aggregates | hourly | if `PARENT_API_URL` is set, posts the last two hours of hourly means to the parent's `/aggregates` |
| push events | hourly | if `PARENT_API_URL` is set, posts this node's alert timestamps of the last 36 hours to the parent's `/events` |
| release check | hourly | unless `UPDATE_CHECK=off`, asks planetai.fab.city once a day which version is current, says so in `/health` and the page's header, and once per version on Telegram. It installs nothing |
| Reticulum | 300 s | only with `RETICULUM_URL` set: asks the bridge for its health and the peers it has heard, for `/health.reticulum`. An `act <id>` message is turned into `POST /actions` by the bridge itself |

One more thread runs when `MQTT_HOST` is set. It subscribes to the broker for Meshtastic radios and DIY
sensors and, with `HA_DISCOVERY=1`, publishes Home Assistant discovery entities.

Every document the node sends or serves as a contract carries a `schema` key: `issues-v0`, `days-v0`, `export-v0`,
`report-v0`, and the two pushes, `aggregates-v0` and `events-v0`. See [Federation](federation.md).

## One shape at every scale

The same code runs at a house, where it polls devices; at a lab, where it also watches its city's open-data
portal; and anywhere, sampling a global model at its coordinates. Same contracts too. What differs is the
`kind` of each source and the `scale` the node declares:

| `sensors.kind` | what it is | cadence | lands in |
|---|---|---|---|
| `sensor` | a device on your LAN, or a nearby public one | minutes | `stats` |
| `portal` | an open-data or statistical API | days–months | `observations` |
| `model` | a global model sampled at a point | hours | `observations` |
| `map` | what is around the node, from OpenStreetMap | monthly | `observations` and PostGIS tables |
| `child` | a node below this one, pushing hourly means | hourly | `readings`, as `<child>/<sensor_id>` |
| `peer` | another node whose numbers are shown, never counted | none | display only |
| `facility` | a named place with a point and no readings, such as a fab lab from the `make` pack | monthly | `sensors` only |

Aggregation of Index cells stops at Region. Bioregion and Planet enter as boundary conditions, context
published downward and never rolled up, which is the Index's own methodology and the architecture keeps it.

The node also carries a pinned snapshot of the `awesome-fabcity-data` registry, 269 entries at `851b8db`,
served at `/sources` and listed by `planetai sources`. Most of it is what this place could measure. Some of
it is where people could go to make or fix something, and the `make` pack turns the nearest fab lab into a
sentence when `PACKS_ALLOW_CODE=1` and `MAKE_ENABLED=1` are both set.

## What leaves the machine, and what never does

Raw readings stay. What travels is a summary: hourly means and alert timestamps to a parent node, if
`PARENT_API_URL` names one; the daily [export](storage.md), with hourly means, your own sensors named by role
(`indoor-1`, `outdoor-2`), the Index cells, the first line of each alert, ρ and the centre of the node's
resolution-8 cell (not its point), under CC BY 4.0. The export is readable at every [sharing level](sharing.md).

Once a day the node asks planetai.fab.city which version is current. The request carries nothing about the
house, but it shows the house's internet address to Fab City's host; `UPDATE_CHECK=off` in Set up → Sharing
stops it. Four more things can leave, and each only when somebody here turns it on. With `RETICULUM_PRESENCE=1` the
node announces a coarse H3 cell on the Reticulum network: resolution 3 by default, never finer than 6. With
`MAP_TILES=on` the browser showing the dashboard fetches live map tiles at resolution 8 and coarser, and each
tile request "tells a tile server which square of the planet this house is looking at". And a question to
the bot or the dashboard's ask pane goes to an online model, with the node's answers to the model's tool calls, only when `AGENT_PREFER`
is `fallback` or `strongest` and an online key is set. At the default, `private`, both use the model on
this machine or one on your own network, and nothing goes further. And `planetai run place basemap` or `planetai run
earth-engine basemap`, typed by somebody here, tells Protomaps, OpenAerialMap or Earth Engine once which square the
node is in, to keep a detailed map of it on the node; after that the map is read from the node and sends nothing.

Exact coordinates and a household's own sentences never leave in a push or the export. The events push carries rule,
level and timestamps and no alert text, actor, note or sensor id. Your own sensor ids leave only in the
hourly means pushed to a parent you chose. Since v0.73 nothing finer than the node's resolution-8 cell (about
500 m to an edge) reaches a reader the node does not know: `/health`, `/export`, and the household's own sensors
in `/sensors` and `/stats` give the centre of that cell, and only this machine or a token gets three decimals.
The shape of the building behind `/place/geojson` needs a token at every sharing level.

## Where the decisions live

| decision | where |
|---|---|
| what a metric means, thresholds, messages | a pack's `rules.yml`; see [Packs](packs.md) |
| which cells the node fills | a pack's `cells.yml` |
| what a metric *is*: ambient, the box, battery, derived | `channels.yml`, core and per pack |
| what a place watches, and in which order | `NODE_ISSUES`, declared in `app/issues/*.yml`; see [Issues](issues.md) |
| how the node speaks | `ALERT_LOCALE`, `ALERT_LEVEL`, `QUIET_*`, `REPORT_*`; see [Configuration](configuration.md) |
| whether an act needs a decision first | `DECISION_REQUIRED` (default `0`) |
| whether heat and air alerts are sent as events | `ALERT_ENGINE` (`rules`, `shadow` or `events`; default `rules`) |
| how much of the page opens, and in what order | `UI_MODE` (`simple`, `advanced`, `learn`) and `UI_LAYOUT` |
| whether the page may fetch live tiles | `MAP_TILES` (default `off`) |
| whether the ground is a drawing or a map that pans and zooms | `UI_GROUND` (`svg` or `map`; default `svg`) |
| whether the node asks which version is current | `UPDATE_CHECK` (default `on`) |
| whether the bot and the ask pane may use an online model | `AGENT_PREFER` (default `private`) |
| whether the node names the nearest fab lab | `MAKE_ENABLED` (default `0`) |
| who may read it | `SHARE_LEVEL` and the tokens; see [Sharing and security](sharing.md) |
| what is retired and when it returns | [`SPEC.md`](spec.md) §6 |

## Refusals that hold at every stage

No raw readings leave the instance that recorded them. No cell is upgraded from `mock` or `partial` to `live`
by aggregation. No agent dispatches without a human row in `actions`. No layer requires a cloud provider to
function. No scale is skipped: a city aggregator is built from nodes, not declared from above. The longer
form, with the staging from one node to a bioregion, is [Architecture](architecture.md).

Some of that staging is not built in v0.80. The fabrication ticket the Act layer ends in when a decision is
physical does not exist, and no job has been handed to a workshop. Nodes finding each other
(`docs/SPEC_discovery.md`) is not built; a node as a key (`docs/SPEC_identity.md`) and the second ρ, which
would ask whether the reading recovered (`docs/SPEC_rho.md`), are Phase 1 with nothing built.

## Where this leads

The words this page used, `custody`, `kind`, the four distances, the H3 cell, are defined in
[Concepts](concepts.md). To run the loop yourself, [install](install.md) a node and spend the
[first ten minutes](first-ten-minutes.md) closing one.
