# Federation and the Index
<!-- checked: v0.80.10 -->

This is the part that joins the network. With a parent set, a house becomes one cell in a district's picture
without its readings leaving the house: every hour it sends up hourly means and the timestamps of its alerts,
and nothing else. A node at a house and an aggregator for a district run the same code with different
sources, different rules and a different parent, which is how the architecture can say "a city aggregator is
built from nodes, not declared from above" ([Architecture](architecture.md), §7).

What connects them is three small contracts (readings up, cells out, actions in) and a set of refusals that
hold at every scale. This page is the contracts. The cells a node can fill today, and the ones nobody fills
yet, are on [Coverage](coverage.md).

## Parent and child

To make one node the child of another:

1. **On the parent, set `AGGREGATE_TOKEN`.** `planetai config set AGGREGATE_TOKEN <a long random string>`
   (`openssl rand -hex 16` makes one). Until it is set, both routes answer 403 `this node accepts no
   children: set AGGREGATE_TOKEN in .env and give it to them`. The token also reads this node's notes and
   the plan of its building (see [Sharing](sharing.md)), so give it knowing that.
2. **On the child, set `PARENT_API_URL` and `PARENT_TOKEN`.** `planetai config set PARENT_API_URL
   http://<parent>:8080`, where `<parent>` is the parent's tailnet hostname, then `planetai config set
   PARENT_TOKEN <the parent's AGGREGATE_TOKEN>`. Each answers `<KEY> is now …, on this node, within 20 s`.
3. **Wait for the first pushes.** The child posts to `/aggregates` two minutes after its app starts and to
   `/events` half a minute after that, then each every 3600 seconds, with `Authorization: Bearer
   <PARENT_TOKEN>` and its `NODE_SCALE`. A child that was already running pushes on its next hourly turn;
   `planetai restart` brings the first push to two minutes. In `planetai logs` the child then says `pushed
   <N> hourly rows to parent`, and `pushed <N> alert events to parent` when it raised an alert in the last
   36 hours. A wrong token shows as `push to parent failed:` with a 401 from the parent. On the parent the
   child's sensors appear as `<child>/<sensor_id>` with `kind='child'`: they are in the parent's custody and
   count toward a `live` cell. The house is now one cell in the district's picture, and its raw readings
   are still at home.

### POST /aggregates

The last two hours of `readings_1h`, the node's hourly means:

```json
{"schema": "aggregates-v0", "node": "bayu-ungasan", "scale": "community",
 "rows": [{"bucket": "2026-09-16T05:00:00+00:00", "sensor_id": "sc-19880", "metric": "pm25",
           "mean": 12.4, "min": 9.1, "max": 17.0, "n": 12}]}
```

The parent keeps each `mean` as one reading on the child's own hour, under the sensor `<child>/<sensor_id>`
with `source='child'`, `kind='child'`, `cadence='PT1H'`, `local=FALSE`. Because custody is generated as
`kind='child' OR (local AND kind<>'peer')`, those rows are in the parent's custody and count toward a `live`
cell. The metric keeps its own name, so a parent's pack SQL matches it. `min`, `max` and `n` travel and are not
stored in v0.80. A child's sensors have no coordinates at the parent, and a re-push of the same hour is a
no-op.

### POST /events

The last 36 hours of alerts, as timestamps only:

```json
{"schema": "events-v0", "node": "bayu-ungasan", "scale": "community",
 "rows": [{"alert_id": "812", "rule": "air-quality/indoor_pm25_high", "level": "act", "kind": "air-quality",
           "raised_at": "…", "responded_at": "…", "acted_at": "…", "measured_at": null}]}
```

`kind` is the pack prefix of the rule id: the pack is the domain tag. `responded_at` and `acted_at` are the
first `acknowledged` and `acted` rows in the child's ledger. `measured_at` is the first posted `measured` row,
and in practice it is null: since v0.69 the node derives `measured` from a rule's silence after an act, and
`POST /actions` accepts only `acknowledged`, `acted` and `decided` for an alert. A `decided` row is not sent, and
neither is an answer to an alert event (`dismissed`, or any row with an `event_id` and no `alert_id`): the push is read from `alerts`. The window is
36 hours because an alert raised yesterday can be answered today; the parent upserts on `(child, alert_id)`,
so the row is updated when its timestamps change. A row without `alert_id` or `raised_at` is skipped.

No text, no actor, no sensor, no note and no ratio. The parent computes [ρ](rho.md) itself, over its own
act-level alerts and its children's pooled together, because a mean of ten ratios is not the ratio of the
pooled counts. The Measure funnel under `/rho` stays the node's own: children push no stages, so a pooled
funnel would have a hole where each child's `measured` should be.

### What the parent requires

A parent accepts children only when `AGGREGATE_TOKEN` is set. Without it both routes answer 403 `this node
accepts no children: set AGGREGATE_TOKEN in .env and give it to them`; with a wrong token, 401. The child's
`PARENT_TOKEN` is the parent's `AGGREGATE_TOKEN`.

Raw readings never travel this link. A parent never sees a child's raw rows, its room names, its people, its
sentences or its coordinates.

### Versions on the wire

Both bodies carry a `schema` key since v0.63. A receiver never refuses on it. A document with no `schema`
predates the key and is read as `-v0`; one with a value the node does not know is read for the fields it
recognises, and the rest are dropped. Either case is logged once per value. So a parent one release behind
keeps accepting a child one release ahead, and nobody's district stops counting because a keeper updated.

## Cells: `fci-cells-v0`

Every node exposes `GET /cells`: the Fab City Index cells it can compute from what it holds, one row per cell, in the
shape of an `FCI Observations` row, plus two fields from [the source registry](sources.md):

```json
{"city": "bali", "cell": "Environmental|Community", "value": 11.8,
 "unit": "µg/m³ PM2.5 (24h mean, sensors in this node's custody)",
 "source": "planetai-node · pack:air-quality", "observed_at": "2026-09-16T06:00:00+00:00",
 "state": "live", "notes": "this node's own sensors and its children's hourly means; indoor and outdoor kept separate by the rules · <have>/12 hourly buckets",
 "registered": 2, "adapter": true, "reviewed": 2, "candidate": 0, "capable": 2}
```

`registered` carries the `reviewed` count (two for `Environmental|Community` at pin `851b8db`), `adapter` is
true when `capable` is above 0, and `reviewed`, `candidate` and `capable` are counted from each entry's
`feeds_cells`. Before v0.73 `registered` was how many entries were filed under the cell (four here) and
`adapter` whether any of them had code. [The source registry](sources.md) says how.

`state` is provenance and travels end to end: `live`, measured here, in custody, in the last 24 hours;
`partial`, derived, modelled, from a portal, or demoted for too few buckets or sensors; `mock`, a placeholder.
**It is never upgraded on the way** ([Architecture](architecture.md), §7). At a parent, `live` needs
in-custody measurement at the parent's own rung from at least two sensors, across at least two children where
there are children; the core demotes the claim otherwise. One child reporting is one household's kitchen. A cell with no source is absent,
not zero.

Aggregation of cells stops at Region ([Architecture](architecture.md)). Bioregion and Planet publish context
downward as boundary conditions and are never rolled up.

## Publishing to the Index

**One node per pilot writes to the Index. A home node never does.** A pilot city has one City-tier node, run by
the partner accountable for that city's numbers, and it is the only node in that city whose cells reach the
Index's spine. Every other node (every home, lab, classroom and community centre) computes its own cells,
shows them on its own dashboard, and passes them no further. That keeps readings where they were made and puts
exactly one identified operator per city behind what the Index publishes.

The writer, `cells-ingest`, lives with the Index's own code, not in this repository. `docs/SPEC_custody.md`
and `skills/publish-to-index` describe it: it refuses to run without `FCI_PUBLISHER=1` and a per-pilot write
token issued by hand. Nothing in the node publishes, and `SHARE_LEVEL` has nothing to do with it: sharing is
reach on your own network, publishing is a different act, gated by the tier and a token issued to a person.
To publish: confirm the tier; run `planetai cells --json` and read every row's `state`; if a row is wrong, fix
the source or the pack, not the label; then write to **info@fab.city** with the node's name, the city and that
output.

The Index's own methodology, sources and cells are at [index.fab.city](https://index.fab.city). A source a pack
reads has to be an entry in [`awesome-fabcity-data`](https://github.com/fabcity/awesome-fabcity-data) first;
the copy every node carries is described on [the source registry](sources.md).

## The node directory

`registry.json` in the repository is the node directory until there are too many nodes for a file: `name,
scale, operator, place, cell, lat, lon, sources, parent, since, contact`, where `cell` is the node's resolution-8 H3
cell and `lat`/`lon` are that cell's centre, never the house (since v0.73). Adding a node is a pull request; approval is
a merge. It lists one node, `bayu-ungasan`, node #1 in Ungasan. A registry
service with a signed handshake returns when pull requests stop scaling, roughly thirty nodes or a second
operator organisation, with its trigger written in [`SPEC.md`](spec.md) §6.

> **Note.** This file is not the source registry. `data/sources/` is the network's list of what can be
> measured; `registry.json` is the list of nodes.

## Peers and places

An observatory the node does not run (Bali Air Dispatch today, a city's own portal tomorrow) is a source. Its
readings enter through an adapter, flagged `local=FALSE`, credited. A `kind='peer'` row, another node's numbers
shown for context, reaches no cell, no custody count, no aggregate and no alert, whatever its coordinates say.
Listening to other nodes as peers (`PEERS`) is proposed and not built in v0.80.

A `kind='facility'` row is the second kind of row that is not a measurement. The `make` pack writes one per fab
lab within reach: a place with a name and a point, no readings, never in custody, never in a cell or an alert.
It is how the node can say where somebody could go and make or fix something (see
[Packs that ship](packs-reference.md)).

## Not built: identity and discovery

Two specifications describe what the network would add next. Neither is built in v0.80.

**Identity** ([`docs/SPEC_identity.md`](../SPEC_identity.md), "Nothing here is built"). Today every child of a
parent shares one `AGGREGATE_TOKEN`, and the child's name is `body["node"]`, a string the child declares about
itself. So any child holding the district's token can push readings under a sibling's name or rewrite a
sibling's ρ rows. The spec gives each node an Ed25519 key generated in the app container at first boot, makes
the node id the public key, has the parent keep a `children` table filled by one enrolment command, signs the
bytes on the wire, and retires the shared token after one release. The two body shapes would not change.

**Discovery** ([`docs/SPEC_discovery.md`](../SPEC_discovery.md), proposed 22 September 2026, "Not built"). A node
that chooses to be discoverable would answer what `GET /presence` already returns: its name, a coarse H3 cell
(resolution 3, about sixty kilometres across), its version and its kind. Tailnet first: the host would read
the tailnet's peer list and the node would ask each peer's `/presence` once an hour. Radio after: the
Reticulum bridge already announces the same body. Discoverable is not accessible: `SHARE_LEVEL` still decides
who may read what, and nothing discovered enters `sensors`, `cells` or any count.

## The commons

The daily export (`GET /export?day=`, written nightly to `exports/<node>/`, `schema: export-v0`) is what a
parent, the Index, a researcher or the commons should receive: hourly mean, min, max and count per sensor and
metric, the cells, the first line of each alert, ρ, and the centre of the node's resolution-8 cell rather than its coordinates. Your own sensors
are named by role (`indoor-1`, `outdoor-2`) rather than id. There are no raw rows, no tokens and no chat ids, and
CC BY 4.0 is stated in the file as `licence`. Each source's own attribution is in its sensor's `meta` on
`/sensors`, not in the export. `planetai ipfs` pins it on IPFS; the database and its dumps never go there.

## The refusals

No raw readings leave the instance that recorded them. No cell is upgraded from `mock` or `partial` to `live` by
aggregation. No agent dispatches without a human row in `actions`. No layer requires a cloud provider to
function. No scale is skipped: a city aggregator is built from nodes, not declared from above. Peers never roll
up and never drive an alert or a report line. Exact place never leaves; a coarse cell may, and says how coarse.
Exactly one node per pilot writes to the spine.

## Where the network is

Node #1, `bayu-ungasan`, has run in Kuta Selatan, Bali, since 2 September 2026: community scale, a Smart
Citizen kit and the Bali Air Dispatch ring. Node #2 runs in Menorca. Stage 1, a
district aggregator receiving hourly means from five nodes over the tailnet, begins when five nodes have been
alive thirty days with at least one `acted` row each.

## Where this leads

A node that shares a summary upward can also be asked questions by an agent, under the same rule that nothing
dispatches without a person. That is the last part: [Agents](agents.md), then the [MCP tools](mcp.md) and the
[bot](bot.md).
