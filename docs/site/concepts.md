# Concepts
<!-- checked: v0.91.0 -->

The words the other pages use, each with what it means in the code. Several come in pairs that sound alike
and are not (`local` and `custody`, domain and issue, `kind` and `scale`, decided and acted). Most of them
answer one question: which numbers belong to this place, and which may be counted for it.

## The node and its place

**Node.** The program at one address: two containers, one database, one API. It has a name (`NODE_NAME`,
lowercase with dashes), a position (`NODE_LAT`, `NODE_LON`), a time zone (`NODE_TZ`) and a city key
(`NODE_CITY`). Node #1 is `bayu-ungasan` in Kuta Selatan; node #2 is in Menorca.

![Nested H3 cells around the node, resolution 6 to 12](img/cell-ladder.svg "The edges are H3 averages. The node's own resolution 8 cell is drawn heavy.")

**Kind** (`NODE_KIND`): `home`, `business`, `community` or `district`, what the node is for. No code reads
it for a default or a pack; `/presence` announces it. It is separate from the Index scale; the setup wizard sets
`NODE_SCALE=city` when the kind is `district`.

**Scale** (`NODE_SCALE`): `community`, `city` or `region`, one of the Full Stack Metrics Framework's
scales. It is stamped on every push and names the core's own cell, `Governance|<Scale>`. It changes no code.

**The H3 cell.** The node stands in a hexagon of the H3 grid at resolution 8, with an edge of about half a
kilometre: 497 m for node #1's cell, measured from the cell itself. The page prints it in the mono as a
fifteen-character id such as `8895a4c843fffff`, with its edge length beside it. Resolution 8 is coarser than
the three-decimal rounding of the node's position, so publishing the cell does not put the position back.

**The ladder.** The same place at eleven rungs, resolution 2 to 12, opening at 8, on the dashboard and on
the wall. Each rung carries one cell's size and how many stations fall in it. The node publishes its own resolution 8 cell, in `/health`,
the export and the node list, and announces nothing finer than resolution 6 over Reticulum. Rungs finer than about
110 m are finer than the node says where it is, because `/health` rounds its position to three decimals. The
node computes the whole table and the page draws it.

**Issue.** What a household calls a quality of its place: `air`, `heat`, `land`, `coast`, `water`, with noise
and energy designed. Declared one file each, an `issue.yml` in the pack that watches it, ordered by `NODE_ISSUES`, the keeper's
order, most important first. An issue is *sensed* when it has eyes on it and rules that can ask for
something, *context* when it informs and never asks. See [Issues](issues.md).

**Domain.** What a pack declares it is about. There are more domains than issues: weather feeds air and heat,
but nobody asks how the weather is doing as a quality of their place. `place` is the ground, `governance` the
loop and the Index. Trust in the instruments has no pack: its rules are the core's.

## Sources and sensors

**Adapter.** One function returning `(sensors, readings)`. In `app/sources.py` for the sources that ship
with the core; in a pack's `adapter.py` for a code pack. The contract is on the [sensors](sensors.md) page.

**Sensor.** A row in `sensors`: `sensor_id`, `source`, `name`, `lat`, `lon`, `indoor`, `local`, `kind`,
`scale`, `cadence`, `meta`. The id is `<source>-<upstream id>` (`sc-19880`, `bad-pa-46949`), stable and
never reassigned.

**`local`.** Two facts at once: an adapter says whether a sensor is *yours*, and the node checks whether it
is *here*, within `LOCAL_RADIUS_M` (500 m) of the node. A kit on your account 1.2 km away is yours and is
not this node's measurement. A sensor with no coordinates that arrives over your own gateway stays local.

**`indoor`.** Carried on every sensor and honoured by every rule. An indoor sensor measures a room and never
enters an ambient average.

**`kind`.** How the number was produced: `sensor`, `portal`, `model`, `map`, `child` or `peer`. Two more
kinds carry no measurement: `facility`, a named place with a point (a fab lab from the `make` pack), and
`survey`, what the household tells the node (the `things:<node>` sensor of the things it keeps). Only
`sensor` rows enter `stats`.

**`custody`.** A generated column: `kind = 'child' OR (local AND kind <> 'peer')`. The only thing a cell may
count. Custody splits geography from responsibility: a peer's station can be closer than your own kit and
still never be counted.

**Peer.** Another node whose numbers you may show and must never act on. A `kind='peer'` row reaches no
cell, no custody count, no aggregate, no alert, no report line.

**Channel role.** What a metric *is* for a given source, declared in `channels.yml` and written to
`channel_roles`: `ambient` (the air, water or land at a place, comparable between sensors there),
`enclosure` (the inside of the instrument's own box: a BME680 sealed in a radio reports the box, not the
street), `device_health` (battery, radio utilisation), `derived` (computed by the node), `index` (a vendor's
own composite, never pooled), `private` (the house's own: used here, never sent).

**Metric names.** Lowercase, no units in the name, for example `pm25 pm25_raw pm10 pm1 temp humidity pressure aqi
gas_resistance noise light eco2 tvoc co2 tvoc_index nox_index`. Units are fixed: µg/m³, °C, %, kPa. `pm25`
is the published value; if a correction was applied, the uncorrected figure sits beside it as `pm25_raw`.
Raw is never overwritten.

**The four distances.** Where a reading comes from, nearest first. The wire keys are `room` (local, indoor),
`yard` (local, outdoor), `ring` (somebody else's device near here) and `region` (a model, a portal). The page
prints them as house · street · ring · region; in Bahasa, rumah · jalan · sekitar · wilayah. In Spanish
they are casa · calle · alrededores · región. The keys stay as they are on the wire. A child node is a fifth
place that is not a column. A distance says whose instrument it is and has no scale: nothing maps a distance
to an H3 resolution.

**Registry.** A pinned snapshot of `awesome-fabcity-data`, 284 entries at `7bf12a4`, served at `/sources` and
listed by `planetai sources`. Most entries are things this place could measure; some are places to go and
designs to build. See [The source registry](sources.md).

## Rules, alerts, actions

**Rule.** SQL that returns rows, plus a message template with `{placeholders}` for the row's columns, a
`level` and a `cooldown_minutes`. There is no rules engine or expression language; if Postgres cannot
express the condition, the condition is wrong. Core rules live in `config/rules.yml` and know no metric; a pack's
rules live in `packs/<id>/rules.yml`, namespaced `<pack>/<id>`. A rule's message ends with its recommendation;
where that line begins with 👉, the alert's card in Decide shows it as "what this node suggests". A rule can also
return a `buttons` column to ask with buttons, and write `{act}` in its message for the alert's own number to answer.

**Level.** `act`: something needs doing. `warn`: something changed. `info`: everything else.
`ALERT_LEVEL` is the floor for interrupting a person; below it an alert is still recorded, still on the
dashboard, still in the next report.

**Alert.** A row in `alerts` (`ts`, `rule_id`, `sensor_id`, `level`, `text`, and `buttons` when its rule offered some), whether or not it was sent.
Three paragraphs: what is happening, what it means, what to do. An act-level alert that no one has answered
is an *open alert*.

**Cooldown.** Per rule and sensor, enforced in SQL against `alerts`: a rule does not fire again for the same
sensor until its cooldown has passed.

**Action.** A row in `actions`: `alert_id`, `stage`, `actor`, `note`, and `choice`, the button pressed. `SPEC.md` calls this table "the
Index's instrument, not an app feature", and ρ is computed from it and nowhere else. A row has one of six
stages:

| stage | means |
|---|---|
| `acknowledged` | someone saw it |
| `acted` | someone did the thing |
| `decided` | someone said what will be done; it moves nothing |
| `measured` | the outcome was checked; the schema allows it, nothing writes it, and the funnel derives it instead |
| `settings` | an audit row for a setting change, with no alert |
| `dismissed` | an alert event's advice did not fit the house |

`POST /actions` takes `acknowledged`, `acted` or `decided` for an alert, and `acknowledged`, `acted` or
`dismissed` for an alert event. A `choice` replaces the stage: the button sets it.

**Alert event.** One story per issue per house, folded from the rows of rules that declare a `kind`: it opens,
escalates and clears, and has at most one action chosen from what is inside, outside and in the home. It is a row
in `alert_events`, its messages are in `event_messages`, and `GET /issues` carries it under `events`. It runs with
`ALERT_ENGINE=shadow` (records what it would send, sends nothing) or `events` (sends); the default, `rules`, runs
no engine. Its answers are Done (`acted`), Not now (`acknowledged`) and Doesn't fit (`dismissed`), posted with an
`event_id`. Done and Not now on an event sent at act level count in ρ; Doesn't fit does not. On `shadow` and `events` the event stands for the alerts of the heat and air rules
it replaced: those are no longer open alerts, and an issue's state follows its event. See [Alerts](alerts.md).

**Decision.** A `decided` row, recorded from an alert's card in Decide. It closes no alert, is
not in ρ and is not a stage in the funnel. With `DECISION_REQUIRED=1` (off by default) an `acted` with no
`decided` row before it is refused with HTTP 409.

**ρ (rho).** The share of act-level alerts in the last 30 days that had an `acknowledged` or `acted` action
within 24 hours, pooled with the children's events. It is the one number on the page that comes from a person.
See [ρ](rho.md).

**Funnel.** The same alerts counted four times: asked, acknowledged, acted, measured. `measured` is derived:
an act followed by 2,880 minutes (48 hours) of silence from the same rule on the same sensor, for rules the
node still runs. The funnel counts this node's own alerts only.

**Effect.** `GET /effect`, per rule over the whole record: how many acts, how many *cleared* (the same
derivation), and a recovery time in hours only for a rule that declares `watch: {metric, over}`.

**Contributor.** A rule with `contributes: report` and no message. It is never sent; its first row lands in
the report bundle under the rule's id.

**Report.** The node's one scheduled message: every `REPORT_EVERY` hours from `REPORT_ANCHOR`, local time,
four parts, under a hundred words, written by the node itself from SQL. See [The report](report.md).

## The page and its stages

**Stages.** The loop runs observe, decide, act, measure, and the dashboard has a stage for each; Now draws
Decide first. Every section the page draws is registered under one of them.

**Digest.** Four sentences, one per stage, written by the node in English, Bahasa Indonesia and Spanish from
figures already in `GET /issues`. Beside them, `digest.simple` is the paragraph simple mode draws, and
`digest.prompts` the questions the ask pane offers, three at a time.

**Headline.** The issue the lead is about. The issue of the most serious open alert event leads first. After
that the highest state wins; between two issues in the same state, the one that moved most in the last three
hours; an exact tie goes to the order in `NODE_ISSUES`. Only an issue that declares a `hero` (how it is drawn
when it leads) can lead. The page prints that rule under the lead, and `lead: {issue, by}` says which of the
four steps picked it: `event`, `state`, `moved` or `order`.

## Packs

**Pack.** A folder in `packs/` with a `pack.yaml`. A *core* pack ships in this repository; every other pack is
*wild*, added with `planetai packs add` and pinned to a commit, and marked by a `.wild` file. A *data pack* is
YAML only: rules, cells, channel roles. A *code pack* also ships Python (an `adapter.py`, `hooks.py`, `routes.py` or
scripts); its adapter and hooks run only when `PACKS_ALLOW_CODE=1`, or, for a core pack that names its own
`switch:`, when that switch is on. The `make` pack, which names the nearest fab lab, needs `MAKE_ENABLED=1` as well, because
the directory it reads is not openly licensed. See [Packs](packs.md).

## The Index and its cells

**Cell.** One of the twenty cells of the Fab City Index, four pillars (Environmental, Economic, Social,
Governance) by five scales (Community, City, Region, Bioregion, Planet), written `Pillar|Scale`. A node can
fill cells at any scale with the same code; what changes is the kind of source. A pack's `cells.yml` computes
a value with SQL that returns one `value`. The core adds `Governance|<Scale>`, which is ρ and reads `partial`
until five act-level alerts have been answered within a day. `planetai cells` lists what a node fills.

![Twenty Index cells, four pillars by five scales](img/index-cells.svg "Community, City and Region roll up from nodes; Bioregion and Planet only send context downward.")

What a cell needs at each scale:

| scale | describes | arrives as | cadence | `kind` |
|---|---|---|---|---|
| Community | this address, this lab | a device you own, or a nearby public sensor | minutes | `sensor` |
| City | a district, a municipality | an open-data portal, a municipal network | days | `portal` |
| Region | a province, a metro | statistical APIs, grid operators | months | `portal` |
| Bioregion | a watershed, a biome | hydrology, biodiversity, satellites | months to years | `portal`, `model` |
| Planet | boundary conditions | Earth models sampled at your coordinates | hours | `model` |

**State.** Where the number came from, which is a different question from how sure it is. `live` means measured here, in custody, in the last 24 hours; a model
or a portal is `partial` whatever its quality, as is anything derived; `mock` means a placeholder. The core
demotes `live` to `partial` when there are too few hourly buckets or too few sensors, and aggregation never
upgrades it. A cell with no source stays empty: the node does not fill what it cannot measure.

**Aggregation stops at Region.** Community, City and Region roll up from nodes. Bioregion and Planet enter as
boundary conditions, context published downward and never rolled up, which is the Index's own methodology.

## Reaching the node

**`SHARE_LEVEL`.** What a request with no token may read. At `off` that is the dashboard shell, `/health`,
`/presence`, `/llms.txt`, the daily export, the programme's node list at `/nodes`, `/offers` while the
`things` pack is on, and `/settings` reduced to
the layout and the sharing level. At `open` it is the whole read API, which is what a wall screen without a
token needs, plus the map's public layers under `/ground/*` and `/geo/cell` without its node-relative fields.
Two more levels, `cell` and `means`, are named and refused. Every untrusted JSON answer names the house's rooms
and sensors only as "Room A" and "Sensor 1". See [Sharing](sharing.md).

**Tokens.** `ADMIN_TOKEN` unlocks every write and the agent surface. `BACKUP_TOKEN` is read-only, for a NAS
pulling dumps and the report bundle. `ACT_TOKEN` closes a loop, from a phone or from the dashboard's **I did
this**, and can read no secret. `AGGREGATE_TOKEN` is what this node demands from its children; it opens only
`POST /aggregates` and `POST /events`, and anything else a child asks is answered as to a stranger.
`PARENT_TOKEN` is what it presents to its parent. All travel as `Authorization: Bearer <token>`.

**Loopback.** A request from `127.0.0.1` inside the container (the node's own MCP tools, a shell in the
container) is trusted without a token. A browser on the host machine arrives from Docker's bridge and is
not loopback.

**Parent and child.** A child posts the hourly means of its own sensors to its parent's `/aggregates` and alert timestamps to
`/events`; the parent stores the means under `<child>/<sensor_id>` with `kind='child'`. Raw never travels the
link. See [Federation](federation.md).

**The tailnet.** Tailscale, joined with `planetai mesh`. The node is reachable by its MagicDNS name,
`<name>.<your-tailnet>.ts.net`, from your devices with no open port. This is how you reach it from outside;
do not forward a port.

## Provenance words on the page

`live`: measured by this node, in the house or on the street. `partial`: derived, a portal, the ring.
`model`: a model row. `cached`: a committed fixture replayed through the node's own engine. `stale`: the
last figures the node gave, once it has stopped answering. When a poll fails the lead's pill says `stale`
and the as-of stamp says "Read at HH:MM · the node has not answered for N min"; the classic wall's foot
carries a fixed `stale` label, and the doors' Wall says it only when its last poll is over 15 minutes old.
`refused` is a whole page: what a reader without a token sees at `SHARE_LEVEL=off`, with the node's own
sentence explaining why. Provenance words are drawn in ink, in a square box, and never as a coloured pill.

## Words

The dashboard and these pages use the programme page's words for what a person reads. The wire keys and
fields behind them stay as they are.

| The word a person reads | What it means | Wire key or field behind it | Retired word |
|---|---|---|---|
| alert | what the node sends a person when an act-level rule crosses its line | `alerts`, `asks` in `GET /issues` | ask |
| open alert | an act-level alert no one has answered yet | `open_asks` on each issue | open ask |
| ladder | the control that sets the H3 resolution, 2 to 12 | `geometry.grain_table`, the `res` query key | rail, grain rail, dial |
| rung | one step of the ladder: one H3 resolution | `res` on each `grain_table` row | stop, grain |
| resolution | how fine a cell is, as an H3 number | `res` | grain |
| house | local and indoors | `room` | room |
| street | local and outdoors: the household's own kit outside | `yard` | wall outside |
| ring | somebody else's public stations near here | `ring` | street |
| region | a model or a portal for this point | `region` | model |

The retired words stay out of every other page.

## Where this leads

These words are enough to read [How it works](how-it-works.md) end to end. To see them on a running node,
[install](install.md) one.
