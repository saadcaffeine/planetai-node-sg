# How it works
<!-- checked: v0.91.0 -->

A node is two containers on one machine. `db` is Postgres with PostGIS, reachable only from the machine itself.
`app` is one Python process that answers the HTTP API on port 8080 and runs thirteen loops in the background, a
fourteenth when the Reticulum bridge is on. Five more containers are optional: the Mosquitto broker for radios and
DIY sensors, the `agent` container for the Telegram bot, the Reticulum bridge, an IPFS node for the export and
Grafana, with a one-shot `grafana-role` that makes its login. Everything a node
does is one of those loops or one of the API's answers, and this page follows a reading through all of it.

![The containers on the machine, and what they reach outside](img/containers.svg "The app and the database always run; the dashed containers run only when their profile is on.")

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
dashboard, the four-sentence digest in `GET /issues` and `docs/GUI.md` split the same machinery into the four
stages above, and every section on the page belongs to one of them.

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
English, Bahasa Indonesia and Spanish, the open alerts and a 24-hour series. It also names a headline issue and
writes a digest of four sentences, one per stage.

Two more reads sit beside it. `GET /shape` is "the day this place usually has", indoor against outdoor, hour
by hour; it needs 7 days of the node's own readings for a day, 14 for a week, 60 for a month and 365 for a
year. `GET /reach` says how far back each kind of source can be asked. Every node exposes the same read
[API](api.md), and the dashboard, the CLI, the bot and a NAS are all clients of it.

### Decide

On the page, Decide is What to do on Now, under the sentence and its day. It draws a card for
each issue with an open act-level alert, showing what was seen and "what this node suggests", which is the
rule's own last line when that line begins with 👉. A node running the event engine draws one card per open
event instead, with the action for the readings as they are now and three answers. A person may record a
decision on an alert's card. It is written to `actions` with `stage: decided`, and it moves nothing: it closes
no alert, it is not in ρ and it is not a stage in the funnel.

`ARCHITECTURE.md` maps decide to the `acknowledged` row of its ledger; the page's `decided` row is a separate
record. With `DECISION_REQUIRED=1` (off by default) the node refuses an `acted` with HTTP 409 unless a
`decided` row exists for the same alert, whichever way the act arrives.

### Act

A rule is SQL that returns rows, plus a message template, a level and a cooldown, and if it wants an answer, buttons. The rules loop runs every
rule once a minute as the read-only role `planetai_ro`, and every row that comes back is a candidate alert.
A cooldown per rule and sensor stops it repeating, the level decides whether it interrupts anyone, and quiet
hours hold everything but `act`. The alert goes out on [Telegram](channels.md), the LoRa mesh, LXMF and Home
Assistant.

When a person does something about it, that is a row in `actions`, and it can come from five places: the
dashboard's **I did this** (which needs `ACT_TOKEN` or `ADMIN_TOKEN` in the browser), `planetai act`,
`/act <id> <what you did>` in Telegram, the MCP `act` tool, or an `act <id>` message over Reticulum. A rule's buttons
are a sixth, on Telegram with `TELEGRAM_BUTTONS=1` and under What to do on Now: each press is a row with a `choice`. An agent
drafts and never dispatches, so nothing is recorded as done without that row.

A rule that declares a `kind` (the heat and air-quality rules do) takes another path when `ALERT_ENGINE` is
`shadow` or `events`: its rows are folded into one [alert event](concepts.md#rules-alerts-actions) per issue
per house. In `shadow` the engine records what it would send and sends nothing. In `events` it sends that one
message, only danger in quiet hours and at most `ALERT_MAX_PER_DAY` (4) pushes a day outside danger, and the old
heat and air rules stop sending. The default, `rules`, runs no engine. See [Alerts](alerts.md).

### Measure

[ρ](rho.md) is the share of act-level asks in the last 30 days that had an `acknowledged` or `acted` row
within 24 hours. An ask is an alert that was sent, or an event the engine sent at act level, and a node pools its
children's alert timestamps with its own. It is the core's own Index cell,
`Governance|<Scale>`. Only the node that sends the alert also receives the answer, so only a node can measure
it.

Beside ρ the funnel counts the same alerts four times: asked, acknowledged, acted, measured. Nothing posts
`measured`. The node derives it: an act followed by 2,880 minutes (48 hours) of silence from the same rule on
the same sensor, counted only for rules the node still runs. `GET /effect` asks the same question per rule over
the whole record, how many acts and how many cleared, and gives a recovery time in hours only for a rule that
declares `watch: {metric, over}`. Four do, two in the air-quality pack and two in heat.

A pack's `cells.yml` computes the other Index cells the node has the data to fill, each with a state; see
[Concepts](concepts.md#the-index-and-its-cells).

## The loops

| loop | every | what it does |
|---|---|---|
| poll | `POLL_SECONDS` (300) | asks every enabled adapter for sensors and readings and upserts them; a source that fails leaves its error in `/health.last_error`, and a loop that fails outright appears under its name in `/health.errors` |
| rules and report | 60 s | writes the [report](report.md) if its hour is due, then runs every rule as `planetai_ro` |
| hourly means | hourly | fills `readings_1h_done` with the finished hours, the last 26 every hour and all of them on the first run after a start and of each local day; `readings_1h` reads it |
| usual for the hour | hourly | rebuilds `usual_by_hour`, each room's usual for each local hour over the fourteen complete days before today, which the event rules read |
| push aggregates | hourly | if `PARENT_API_URL` is set, posts the last two hours of hourly means to the parent's `/aggregates` |
| push events | hourly | if `PARENT_API_URL` is set, posts this node's alert timestamps of the last 36 hours to the parent's `/events` |
| release check | hourly | unless `UPDATE_CHECK=off`, asks planetai.fab.city which version is current and says so in `/health`, the page's top bar and once per version on Telegram. It installs nothing |
| node list | hourly | unless `UPDATE_CHECK=off`, reads the programme's `registry.json` from GitHub and serves it at `/nodes`, each other node's point to one decimal and no contact |
| wild packs | hourly | unless `UPDATE_CHECK=off`, reads the list of wild packs from GitHub and tells the household once about a pack that is new on it |
| workbench firmware | 6 hours | unless `UPDATE_CHECK=off`, keeps a copy of the Bayu and Meshtastic firmware in `out/firmware/`, so the workbench flashes with no internet |
| introduced species | hourly | only with the `eyes` pack on and `SPECIES_MATCH=on`: once a week reads the country's GRIIS checklist from GBIF |
| others' records | hourly | only with the `eyes` pack on and `SPECIES_MATCH=on`: once a week counts GBIF's open records in each of the node's seven res-8 cells |
| what the house learned | hourly | once a local day, in its first hour: what worked, what is usual, the alerts that may not fit, and the diary's entries |
| Reticulum | 300 s | only with `RETICULUM_URL` set: asks the bridge for its health and the peers it has heard, for `/health.reticulum`. The bridge itself turns an `act <id>` message into `POST /actions` |

With `MQTT_HOST` set, one more thread subscribes to the broker for Meshtastic radios, DIY sensors and the
topics a loaded pack's `hooks.py` names in `MQTT_TOPICS` (the `smartcitizen` pack's `device/sck/#`). That pack
passes the messages of the devices listed in `SC_FORWARD` on to smartcitizen.me unchanged, on a thread of its
own, and with `HA_DISCOVERY=1` the `home-assistant` pack publishes discovery entities after every batch of
readings.

Every document the node sends or serves as a contract carries a `schema` key: `issues-v0`, `days-v0`,
`export-v0`, `report-v0`, `forecast-v0` (what `GET /forecast` returns), and the two pushes, `aggregates-v0` and
`events-v0`. See [Federation](federation.md).

## One shape at every scale

The same code and the same contracts run at a house that polls its devices, at a lab that also watches its
city's open-data portal, and anywhere a global model can be sampled. What differs is the `kind` of each source
and the `scale` the node declares:

| `sensors.kind` | what it is | cadence | lands in |
|---|---|---|---|
| `sensor` | a device on your LAN, or a nearby public one | minutes | `stats` |
| `portal` | an open-data or statistical API | days to months | `observations` |
| `model` | a global model sampled at a point | hours | `observations` |
| `map` | what is around the node, from OpenStreetMap | monthly | `observations` and PostGIS tables |
| `child` | a node below this one, pushing hourly means | hourly | `readings`, as `<child>/<sensor_id>` |
| `peer` | another node whose numbers are shown, never counted | none | display only |
| `facility` | a named place with a point and no readings, such as a fab lab from the `make` pack | monthly | `sensors` only |

Index cells roll up only as far as Region; [Concepts](concepts.md#the-index-and-its-cells) has what a cell
needs at each scale. The node also carries a pinned snapshot of the source registry, served at `/sources`;
see [The source registry](sources.md).

## What leaves the machine, and what never does

Raw readings stay. What travels is a summary: hourly means and alert timestamps to a parent node, if
`PARENT_API_URL` names one; the daily [export](storage.md), with hourly means, your own sensors named by role
(`indoor-1`, `outdoor-2`), the Index cells, each alert's first line, ρ, the household's offers and its res-8 cell's centre, never its
point, under CC BY 4.0. The export is readable at every [sharing level](sharing.md).

![What leaves the machine, to whom, and which are off by default](img/what-leaves.svg "Raw readings stay. A dashed line leaves only when somebody here turns it on.")

Exact coordinates and a household's own sentences never leave in a push or the export. The events push carries
rule, level and timestamps, and no alert text, actor, note or sensor id. Your own sensor ids leave only in the
hourly means pushed to a parent you chose. Nothing finer than the node's resolution-8 cell (about 500 m to an
edge) reaches a reader the node does not know: `/health`, `/export`, and the household's own sensors in
`/sensors` and `/stats` give the centre of that cell, and only this machine or a token gets three decimals. The
shape of the building behind `/place/geojson` needs a token at every sharing level.

Alerts go out on the channels you connect, so an alert sent by Telegram passes through Telegram's servers.
Every hour the node asks planetai.fab.city which version is current and reads the programme's list of nodes and
the list of wild packs from GitHub, and every six hours it fetches the workbench's firmware from planetai.fab.city
and Making Sense Bali. None of these requests carries anything about the house, but each shows the house's
internet address to the host it asks; `UPDATE_CHECK=off` in Set up → Sharing stops them all.

Everything else leaves only when somebody here turns it on:

| what | when | what the other side learns |
|---|---|---|
| Reticulum presence | `RETICULUM_PRESENCE=1` | a coarse H3 cell, resolution 3 by default and never finer than 6 |
| live map tiles | `MAP_TILES=on` | which square of the planet the browser showing the dashboard is looking at, at resolution 8 and coarser |
| an online model | `AGENT_PREFER` is `fallback` or `strongest` and an online key is set | the question asked of the bot or the ask pane, and the node's answers to the model's tool calls. At the default, `private`, both use a model on this machine or your own network |
| species names | Name species with GBIF (`SPECIES_MATCH=on`) | a finding's scientific name; the weekly reads tell GBIF the country and the shapes of the seven cells |
| offers | the household marks a thing to lend or give | its class, name, condition and count at the node's cell, public at `GET /offers` and in the export |
| a detailed basemap | somebody types `planetai run place basemap` or `planetai run earth-engine basemap` | Protomaps, OpenAerialMap or Earth Engine learn once which square the node is in; after that the map is read from the node |
| Smart Citizen forwarding | a device token listed in `SC_FORWARD` | smartcitizen.me gets that device's messages exactly as the device sent them |
| IPFS | `IPFS_PUBLISH=1` (`planetai ipfs` sets it and starts the container) | the daily export, added to IPFS; never the dump |
| an off-machine backup | `BACKUP_REMOTE` names an rclone remote | the whole backup, the database dump included, goes to the remote you named |

## Where the decisions live

| decision | where |
|---|---|
| what a metric means, thresholds, messages | a pack's `rules.yml`; see [Packs](packs.md) |
| which cells the node fills | a pack's `cells.yml` |
| what a metric *is*: ambient, the box, battery, derived | `channels.yml`, core and per pack |
| what a place watches, and in which order | `NODE_ISSUES`, declared in each pack's `issue.yml`; see [Issues](issues.md) |
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

> **Gap in v0.91.0.** Some of that staging is not built. The Act layer in `ARCHITECTURE.md` ends in a
> fabrication ticket when a decision is physical; there is no such ticket and no `fabricate` stage, and no job
> has been handed to a workshop. The `make` pack, off until `MAKE_ENABLED=1`, only names the nearest fab lab.
> Nodes finding each other (`docs/SPEC_discovery.md`) is not built. A node as a key rather than a name
> (`docs/SPEC_identity.md`) and the second ρ, which would ask whether the reading recovered
> (`docs/SPEC_rho.md`), are Phase 1 with nothing built. A decision on the dashboard is one person deciding for
> one node; how several households' decisions become a street's is not on a node at all.

## Where this leads

The words this page used, `custody`, `kind`, the four distances, the H3 cell, are defined in
[Concepts](concepts.md). To run the loop yourself, [install](install.md) a node and spend the
[first ten minutes](first-ten-minutes.md) closing one.
