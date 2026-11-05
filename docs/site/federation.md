# Federation and the Index
<!-- checked: v0.91.0 -->

This is the part that joins the network. With a parent set, a house becomes one cell in a district's picture
without its readings leaving the house: every hour it sends up hourly means and the timestamps of its alerts,
and nothing else. A node at a house and an aggregator for a district run the same code with different
sources, different rules and a different parent, which is how the architecture can say "a city aggregator is
built from nodes, not declared from above" ([Architecture](architecture.md), §7).

A child pushes two things to its parent, `POST /aggregates` and `POST /events`, and every node answers
`GET /cells`. What the Index cells are, and the words `live` and `partial`, are on [Concepts](concepts.md).

## Parent and child

![Home nodes push to a district parent; only a pilot's city node writes to the Index](img/federation.svg "Every hour a child sends hourly means and alert times, and nothing else.")

To make one node the child of another:

1. On the parent, set `AGGREGATE_TOKEN`: `planetai config set AGGREGATE_TOKEN <a long random string>`
   (`openssl rand -hex 16` makes one). Until it is set, both routes answer 403 `this node accepts no
   children: set AGGREGATE_TOKEN in .env and give it to them`. The token lets a child push and read nothing;
   a child reads its parent only as a stranger on that network would (see [Sharing](sharing.md)).
2. On the child, set `PARENT_API_URL` and `PARENT_TOKEN`: `planetai config set PARENT_API_URL
   http://<parent>:8080`, with the parent's tailnet hostname, then `planetai config set PARENT_TOKEN <the
   parent's AGGREGATE_TOKEN>`. Each answers `<KEY> is now …, on this node, within 20 s`.
3. Wait for the first pushes. The child posts to `/aggregates` two minutes after its app starts and to
   `/events` half a minute after that, then each every hour, with `Authorization: Bearer <PARENT_TOKEN>` and
   its `NODE_SCALE`. A child that was already running pushes on its next hourly turn, and `planetai restart`
   brings the first push to two minutes. In `planetai logs` the child says `pushed <N> hourly rows to
   parent`, and `pushed <N> alert events to parent` when it raised an alert in the last 36 hours. A wrong
   token shows as `push to parent failed:` with a 401. On the parent the child's sensors appear as
   `<child>/<sensor_id>` with `kind='child'`, in the parent's custody, so they count toward a `live` cell.
   The house's raw readings are still at home.

A parent never sees a child's raw rows, its room names, its people, its sentences or its coordinates.

### POST /aggregates

The last two hours of `readings_1h`, the node's hourly means, for its own sensors and its children's only
(custody), leaving out every channel whose role is `private`. A peer's station and a model sampled at the node
stay home: the parent would count them as its own.

```json
{"schema": "aggregates-v0", "node": "bayu-ungasan", "scale": "community",
 "rows": [{"bucket": "2026-09-16T05:00:00+00:00", "sensor_id": "sc-19880", "metric": "pm25",
           "mean": 12.4, "min": 9.1, "max": 17.0, "n": 12, "indoor": false}]}
```

The parent keeps each `mean` as one reading on the child's own hour, under the sensor `<child>/<sensor_id>`
with `source='child'`, `kind='child'`, `cadence='PT1H'` and `local=FALSE`. Custody is generated as
`kind='child' OR (local AND kind<>'peer')`, so those rows count toward a `live` cell. The metric keeps its own
name, so the parent's pack SQL matches it. `indoor` is kept on the parent's sensor row, so an indoor kit stays
out of outdoor means there too. `min`, `max` and `n` travel but the parent does not store them. A child's
sensors have no coordinates at the parent. The push sends the hour in progress and, an hour later, the same hour
complete; the parent keeps the later mean.

### POST /events

The last 36 hours of alerts, as timestamps only:

```json
{"schema": "events-v0", "node": "bayu-ungasan", "scale": "community",
 "rows": [{"alert_id": "812", "rule": "air-quality/indoor_pm25_high", "level": "act", "kind": "air-quality",
           "raised_at": "…", "responded_at": "…", "acted_at": "…", "measured_at": null}]}
```

`kind` is the pack prefix of the rule id, so the pack is the domain tag. `responded_at` and `acted_at` are the
first `acknowledged` and `acted` rows in the child's ledger. `measured_at` is the first posted `measured` row,
and it is null in practice, because the node derives `measured` from a rule's silence after an act and
`POST /actions` takes only `acknowledged`, `acted` and `decided` for an alert. The push is read from `alerts`,
so a `decided` row is not sent, and neither is an answer to an alert event. The window is 36 hours because an
alert raised yesterday can be answered today; the parent upserts on `(child, alert_id)`, so the row is updated
when its timestamps change. A row without `alert_id` or `raised_at` is skipped.

There is no text, actor, sensor, note or ratio in it. The parent computes [ρ](rho.md) itself, over its own
act-level alerts and its children's pooled together, because a mean of ten ratios is not the ratio of the
pooled counts. The Measure funnel under `/rho` stays the node's own: children push no stages, so a pooled
funnel would have a hole where each child's `measured` should be.

### Versions on the wire

Both bodies carry a `schema` key, and a receiver never refuses on it. A body with no `schema` is read as
`-v0`; one with a value the node does not know is read for the fields it recognises, and the rest are dropped.
Either case is logged once per value. So a parent one release behind keeps accepting a child one release
ahead.

## Cells: `fci-cells-v0`

Every node exposes `GET /cells`: the Fab City Index cells it can compute from what it holds, one row per cell,
in the shape of an `FCI Observations` row, with counts from [the source registry](sources.md):

```json
{"city": "bali", "cell": "Environmental|Community", "value": 11.8,
 "unit": "µg/m³ PM2.5 (24h mean, sensors in this node's custody)",
 "source": "planetai-node · pack:air-quality", "observed_at": "2026-09-16T06:00:00+00:00",
 "state": "live", "notes": "this node's own sensors and its children's hourly means; indoor and outdoor kept separate by the rules · <have>/12 hourly buckets",
 "registered": 2, "adapter": true, "reviewed": 2, "candidate": 1, "capable": 2}
```

`reviewed`, `candidate` and `capable` are counted from each registry entry's `feeds_cells`. `registered`
carries the `reviewed` count, and `adapter` is true when `capable` is above 0. [The source registry](sources.md)
says how an entry gets each label.

`state` is provenance and travels end to end, and it is never upgraded on the way ([Architecture](architecture.md),
§7). At a parent, `live` needs in-custody measurement at the parent's own rung from at least two sensors, and
from at least two children where there are children; otherwise the core demotes the claim to `partial`. One
child reporting is one household's kitchen. A cell with no source is absent, not zero.

Aggregation of cells stops at Region ([Architecture](architecture.md)). Bioregion and Planet publish context
downward as boundary conditions and are never rolled up.

## Publishing to the Index

One node per pilot writes to the Index, and a home node never does. A pilot city has one City-tier node, run by
the partner accountable for that city's numbers, and it is the only node in that city whose cells reach the
Index's spine. Every other node, at a home, a lab, a classroom or a community centre, computes its own cells,
shows them on its own dashboard, and passes them no further. That keeps readings where they were made and puts
one identified operator per city behind what the Index publishes.

The writer, `cells-ingest`, lives with the Index's own code, outside this repository. `docs/SPEC_custody.md`
and `skills/publish-to-index` describe it: it refuses to run without `FCI_PUBLISHER=1` and a per-pilot write
token issued by hand. Nothing in the node publishes, and `SHARE_LEVEL` has nothing to do with it; sharing is
who on your own network may read the node, and publishing is a separate act, gated by the tier and a token
issued to a person.

To publish:

1. Confirm the node is the pilot's City-tier node.
2. Run `planetai cells --json` and read every row's `state`.
3. If a row is wrong, fix the source or the pack, never the label.
4. Write to **info@fab.city** with the node's name, the city and that output.

The Index's own methodology, sources and cells are at [index.fab.city](https://index.fab.city). A source a pack
reads has to be an entry in [`awesome-fabcity-data`](https://github.com/fabcity/awesome-fabcity-data) first;
the copy every node carries is described on [the source registry](sources.md).

## The node directory

`registry.json` in the repository is the node directory: `name, scale, operator, place, cell, lat, lon,
sources, parent, since, contact`, where `cell` is the node's resolution-8 H3 cell and `lat`/`lon` are that
cell's centre, never the house. Adding a node is a pull request, and approval is a merge. It lists two nodes,
`bayu-ungasan` (node #1, in Ungasan) and `larsbcn` in Barcelona.

Every node reads the file from the repository's `main` once an hour and serves it at `GET /nodes`, with only
the name, place, scale, operator, `since` and cell, and each point rounded to one decimal; `contact`, `sources`
and `parent` stay in the file. The Node door and the phone's walk draw the nodes from it. `UPDATE_CHECK=off`
reads nothing. A registry service with a signed handshake comes back when pull requests stop scaling, roughly
thirty nodes or a second operator organisation, with its trigger written in [`SPEC.md`](spec.md) §6.

> **Note.** This file is not the source registry. `data/sources/` is the network's list of what can be
> measured; `registry.json` is the list of nodes.

## Peers and places

An observatory the node does not run, such as Bali Air Dispatch or a city's own portal, is a source. Its
readings enter through an adapter or a pack, flagged `local=FALSE` and credited. A `kind='peer'` row, another
node's numbers shown for context, reaches no cell, no custody count, no aggregate and no alert, whatever its
coordinates say. Nothing writes `peer` rows yet: listening to other nodes as peers is proposed and not built.

A `kind='facility'` row is the other kind of row that is not a measurement. The `make` pack writes one per fab
lab within reach: a place with a name and a point, no readings, never in custody, a cell or an alert. It is how
the node can say where somebody could go and make or fix something (see
[Packs that ship](packs-reference.md#make)).

## Not built: identity and discovery

Two specifications describe what the network would add next. Neither is built.

[`docs/SPEC_identity.md`](../SPEC_identity.md) is about identity. Today every child of a parent shares one
`AGGREGATE_TOKEN`, and the child's name is `body["node"]`, a string the child declares about itself, so any
child holding the district's token can push readings under a sibling's name or rewrite a sibling's ρ rows.
The spec gives each node an Ed25519 key generated in the app container at first boot, makes the node id the
public key, has the parent keep a `children` table filled by one enrolment command, signs the bytes on the
wire, and retires the shared token after one release. The two body shapes would not change.

[`docs/SPEC_discovery.md`](../SPEC_discovery.md) is about discovery. A node that chooses to be discoverable
would answer what `GET /presence` already returns: its name, a coarse H3 cell (resolution 3, about sixty
kilometres across), its version and its kind. On the tailnet the host would read the peer list and the node
would ask each peer's `/presence` once an hour; on radio, the Reticulum bridge already announces the same body.
Being discoverable gives nobody access: `SHARE_LEVEL` still decides who may read what, and nothing discovered
enters `sensors`, `cells` or any count.

## The commons

The daily export (`GET /export?day=`, written nightly to `exports/<node>/`, `schema: export-v0`) is what a
parent, the Index, a researcher or the commons should receive: hourly mean, min, max and count per sensor and
metric, the cells, the first line of each alert, ρ, what the household offers (`offers`, while the things pack is on), and the centre of
the node's resolution-8 cell in place of its coordinates. Your own sensors are named by role (`indoor-1`,
`outdoor-2`) instead of by id. There are no raw rows, no tokens and no chat ids, and CC BY 4.0 is stated in the
file as `licence`. Each source's own attribution is in its sensor's `meta` on `/sensors`, not in the export.
`planetai ipfs` pins the export on IPFS; the database and its dumps never go there.

## The refusals

No raw readings leave the instance that recorded them. No cell is upgraded from `mock` or `partial` to `live` by
aggregation. No agent dispatches without a human row in `actions`. No layer requires a cloud provider to
function. No scale is skipped: a city aggregator is built from nodes, not declared from above. Peers never roll
up and never drive an alert or a report line. Exact place never leaves; a coarse cell may, and says how coarse.
Exactly one node per pilot writes to the spine.

## Where the network is

We run node #1, `bayu-ungasan`, in Kuta Selatan, Bali, at community scale, with Smart Citizen kits and the
Bali Air Dispatch ring. Node #2 runs in Menorca. Stage 1 of the architecture, a district aggregator receiving
hourly means from five nodes over the tailnet, begins when five nodes have been alive thirty days with at least
one `acted` row each.

## Where this leads

A node that shares a summary upward can also be asked questions by an agent, under the same rule that nothing
dispatches without a person: [Agents](agents.md), then the [MCP tools](mcp.md) and the [bot](bot.md).
