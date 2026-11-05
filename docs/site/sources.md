# The source registry
<!-- checked: v0.91.0 -->

A node measures what its adapters read. The registry is the network's shared list of what could be measured at
each pillar and scale, and of the places a person could go to act on it, carried inside every node as a
pinned copy. With it the node can say what anyone has filed that this place could measure, and whether any code
here reads it yet. A blank adapter column is an adapter nobody has written, and naming the source is how somebody
comes to write it.

## Reading it, step by step

1. **List it.** Run `planetai sources`. It prints `registered in awesome-fabcity-data, read from the node:`, then one
   line per entry: the slug, the status, the first 40 characters of the licence, the pilots, and the code that
   reads it. By default it shows this node's pilot (`NODE_CITY`) and the `global` rows, 111 entries on a `bali`
   node; `--all` shows every entry. It ends with the totals:

   ```
     111 of 284 entries. The last column is the code that reads it. A cell with sources and a blank column is one nobody has written an adapter for yet.
     across 19 cells: capable 12 / reviewed 17 / candidate 55
     capable = live with an adapter. reviewed = live, backed by an adapter or a usable review. candidate = verified, unread.
   ```

   With `--all` it adds `counted nowhere: 8 deprecated, 1 paywalled, 3 planned, 4 stale.`

   With the containers down it reads `data/sources/index.json` off the disk and says `read from data/sources (the
   node is not answering)`. The answer is the same either way, because the registry is a file in the release.
2. **Filter it to one cell.** `planetai sources --all --cell 'Social|City'` lists the 13 entries filed for that
   cell, from the Barcelona electoral sections to the US Census ACS, and the last column is blank on every one.
   That is a part of the Index no node fills yet, with the sources that could fill it named. The footer says
   `Social|City: capable 0 / reviewed 1 / candidate 8`; the reviewed entry is `social/city/ine-spain`, whose review
   found it usable. The counts are the registry's whole count for that cell whatever the other filters, and they
   come from `feeds_cells`, so they include `social/region/worldpop`, filed under `Social|Region`. The other
   filters are `--pillar`, `--scale` and `--json`.
3. **Read one entry.** Ask the node for it by slug:

   ```bash
   curl -s -H "Authorization: Bearer $(grep '^ADMIN_TOKEN=' ~/planetai/.env | cut -d= -f2)" \
     localhost:8080/sources/environmental/community/bali-air-dispatch
   ```

   The answer is the entry as filed: `"adapter": "pack:bali-air-dispatch"`, `"feeds_cells":
   ["Environmental|City"]`, `"auth": "none"`, the licence, and notes naming every reader. The same text is in
   `data/sources/data/environmental/community/bali-air-dispatch.yaml`. A slug that is not in the pin answers 404
   and names the pin.
4. **See it on the Network view.** On the dashboard, Network has a section headed **What this place could read,
   and where it could go**, with three rows. *Registered, and read* shows `pin 7bf12a4 · synced 2026-11-04` (the
   pin links to the registry on GitHub at that commit), says `284 sources registered; 18 have code on this node
   that reads them` with the fourteen adapter strings, and draws `18/284`. *What a cell could use* reads `across 19
   cells` with `12 capable`, `17 reviewed` and `55 candidate`. *Places to act* counts the 16 act sources by kind
   and says how many state that no licence is published (4); a fold under it lists all sixteen with each licence
   as filed. The page fetches `/sources` the first time somebody opens Network, and never before.

The registry records that the code exists on node main, not that a given node runs it: an adapter in a pack reads
only on a node with that pack on. Up to v0.83.0 it counted `core:airgradient` while the poll loop never called it.

## Three counts per cell

The node counts each cell three ways, from the entries it could fill that cell from:

| count | what it counts |
|---|---|
| `capable` | status `live` and an `adapter`: code here reads it |
| `reviewed` | status `live` and either an `adapter` or a review whose verdict is `usable` or `usable-with-caveats` |
| `candidate` | status `candidate`: verified, and nobody has read it for a real territory |

An entry counts against every cell in its `feeds_cells`, and against its own `cell` only when it has no
`feeds_cells` key. An entry with `feeds_cells: []` counts in no cell. No `deprecated`, `stale`, `paywalled` or
`planned` entry counts anywhere. `capable` is always part of `reviewed`.

At `7bf12a4` that is 12 capable, 17 reviewed and 55 candidate across 19 cells. Of the eighteen entries with an
`adapter`, eight say `feeds_cells: []` (`fablabs-io` is one) and two (`airgradient`, `smart-citizen`) feed two
cells each, which makes 12. Reviews add five to `reviewed`. The 56 `candidate` entries make 55, because ten
of them feed two cells each and eleven feed none. `Governance|City` has 32 entries filed under it and counts capable 4,
reviewed 4, candidate 0: the four CKAN portals that `core:ckan` reads.

## One entry

The fields a node uses, from the schema at the pin:

| field | meaning |
|---|---|
| `slug` | `pillar/scale/slug`, from the file's path. The id a pack's `sources:` names |
| `cell` | the Index key for the entry's own pillar and scale, e.g. `Environmental\|Community` |
| `status` | `live` (a named person's review, or code that reads it), `candidate`, `stale`, `paywalled`, `deprecated`, `planned` |
| `license` | the licence of the data itself, as free text |
| `api`, `auth` | the endpoint, and what a node must hold to call it (`none`, `key-free-rate-limited`, `api-key`, `registration`, `paid`) |
| `pilot_relevance` | which pilots it covers: `barcelona`, `boston`, `santiago`, `bali`, `global` |
| `adapter` | what in this repository reads it: `core:<function>` in `app/sources.py` or `app/bootstrap.py`, or `pack:<id>`. Absent means no code reads it |
| `feeds_cells` | the Index cells a node fills from it, which need not include the entry's own `cell` |
| `role` | `observe`, `act`, or both. Absent means `observe` |
| `act_kind` | for an act source: `facility`, `equipment`, `design`, `repair`, `material`, `match` or `network` |
| `notes` | the long form: quirks, rate limits, and the licence clauses a source turns on |

`wired_in_planetai`, the hand-set boolean that `adapter` replaced, is retired upstream: no entry carries it now,
and the node reads only `adapter`.

`cell` and `feeds_cells` answer different questions. Bali Air Dispatch is filed under `Environmental|Community`,
where it publishes its strongest signal, and feeds `Environmental|City`, because its stations are other people's:
they fill the public-reference cell, and the in-custody cell is left to the household's own sensors.

## What the node carries

The source of truth is [`awesome-fabcity-data`](https://github.com/fabcity/awesome-fabcity-data), one YAML file per
source at `data/<pillar>/<scale>/<slug>.yaml`, checked against the schema in that repository's CI. Each node carries
a copy at `data/sources/`, mounted read-only into the app container:

| path | what it is |
|---|---|
| `data/sources/REGISTRY_VERSION` | the pin: `sha=7bf12a49bc6e70e5c38592fdef6b217b5ee18eb4`, `short=7bf12a4`, `synced=2026-11-04`, `entries=284`, and the upstream URL |
| `data/sources/data/<pillar>/<scale>/<slug>.yaml` | the 284 entries as filed |
| `data/sources/schema/dataset.schema.json` | the schema they are checked against |
| `data/sources/reviews/`, `data/sources/cells/` | the reviews filed for entries, and one file for each of the twenty cells |
| `data/sources/index.json` | the YAML folded into one JSON list, with `slug` and `cell` taken from each file's path, and a `reviews` list on every entry (`[]` when there are none) |

At `7bf12a4` the 284 entries are 121 economic, 68 governance, 68 environmental and 27 social. By status, 212 are
`live`, 56 `candidate`, 8 `deprecated`, 4 `stale`, 3 `planned` and 1 `paywalled`. Eighteen carry an `adapter`,
four carry a review, and sixteen are act sources.

`app/registry.py` and `bin/planetai` read `index.json`, so the CLI needs no YAML library on the host. The app
caches it on the file's modification time, so a re-pin that arrives with `planetai update` is picked up without a
restart. The directory is `SOURCES_DIR`, default `/app/data/sources`. Nothing in this repository edits an entry:
`tools/check_registry.py` rebuilds `index.json` from the YAML and fails `make lint` if they differ, if a review
names an entry the pin does not carry, if a `cells/` file is not named for its own cell, if a pack reads an entry
that names no `adapter`, or if an `adapter` names a pack or a core function this tree does not have.

The copy is pinned rather than fetched. [`docs/SOURCES.md`](../SOURCES.md) gives the reasons: a node with no uplink
answers the same question as one in Barcelona, every node in a release answers it the same way, and a change to
what a node believes about the network is a diff somebody reviewed. `tools/sync_registry.sh` takes a commit and
refuses a branch or a tag for the same reason.

## Act sources

Sixteen entries carry `role: act`: places to go and things to build with. The `make` pack reads the first two. The
licence column is a summary; the entry's own `license` and `notes` say it in full.

| entry | act_kind | status | read by | licence, in short |
|---|---|---|---|---|
| `economic/community/fablabs-io` | facility | live | `pack:make` | not open: no data licence published, and the platform's terms restrict mass harvesting and commercial use |
| `economic/community/fablabs-network-data-archive` | facility | live | `pack:make` | none published; the records are fablabs.io's, under its terms |
| `economic/community/hackerspaces-org` | facility | live | | not stated |
| `economic/community/maps-of-making` | facility | live | | not stated |
| `economic/community/precious-plastic-community` | facility | live | | not open: the terms reserve database rights; MIT covers the platform code only |
| `economic/community/spaceapi-directory` | facility | live | | not stated |
| `economic/community/repair-cafe-directory` | repair | planned | | not stated |
| `economic/planet/appropedia` | design | live | | CC-BY-SA-4.0 (site default) |
| `economic/planet/field-ready` | design | live | | a CERN-OHL variant on 156 of 193 items, while the organisation's site says all rights reserved; unconfirmed |
| `economic/planet/okh-losh` | design | planned | | not stated |
| `economic/planet/okh-search` | design | live | | Creative Commons, version and variant not stated |
| `economic/planet/open-lab-starter-kit` | design | live | | CERN-OHL-W-2.0 on eight of nine repositories; one is GPL-3.0 |
| `economic/planet/oshwa-certification` | design | live | | CC-BY-SA-4.0 |
| `economic/planet/things-that-work` | design | live | | CC-BY-SA-4.0 for content, MIT for code |
| `economic/planet/open-hardware-manager` | match | live | | not stated |
| `governance/city/fab-city-pledged-cities` | network | live | | none published; the Foundation's own list |

Four name an open licence outright, four say no licence is published or the data is not open, and the other eight
state none or one whose variant or scope is unconfirmed. Neither the dashboard nor this page sorts them into open
and not open, because that is a judgement about somebody else's terms.

## Elsewhere in the node

- **`GET /cells`.** Every row carries `registered`, `adapter`, `reviewed`, `candidate` and `capable`, grouped by
  `feeds_cells` as above. `registered` carries the `reviewed` count, and `adapter` is true when `capable` is above
  0. A cell with registered sources and no adapter has no `/cells` row at all, because a node only emits rows it
  can compute; `planetai sources --cell` answers that half.
- **`planetai doctor`.** One row: `source registry: 284 entries · awesome-fabcity-data @ 7bf12a4 · synced
  2026-11-04`. It goes amber when the pin is over 180 days old and red when `data/sources/` is missing.
- **Packs.** Every id in a pack's `sources:` must resolve to an entry at the pin, or `make lint` fails and names
  the id; 18 resolve. The `fire` pack's is `environmental/bioregion/nasa-firms`, a `candidate` filed with
  `adapter: pack:fire`, `auth: none` (only its area API needs a key) and `feeds_cells: []`: read, and feeding no
  cell yet.

## The endpoints

### GET /sources
Access: open

The registry as this node carries it. Query parameters, each optional and combined with AND: `pillar`, `scale`,
`pilot`, `cell`, `status` (`live`, `candidate`, `stale`, `deprecated`, `paywalled` or `planned`) and `wired`
(`true` or `false`, read from each entry's `adapter`). `GET /sources?wired=false` is every registered source
nothing reads. `pilot` also returns the `global` rows, because an entry relevant everywhere is relevant to every
pilot. Returns `{registry: {sha, short, synced, entries}, counts, count, sources}`, where `counts` is `{cell:
{capable, reviewed, candidate}}` for every cell the registry counts, whatever the filters. Answers 503 when
`data/sources` is empty or not mounted. It is open at `SHARE_LEVEL=open` because it is a copy of a public registry,
the same on every node in a release, and says nothing about the house.

### GET /sources/{pillar}/{scale}/{slug}
Access: open

One entry, as filed. A 404 names the pin the node carries and points back at `/sources`.

## Adding a source

1. Open a pull request to `awesome-fabcity-data` with the entry, one pillar and one scale, following its
   `CONTRIBUTING.md`. The schema allows no key it does not name. Nothing on any node changes yet: the entry is a
   proposal, and the network decides whether it is a source.
2. Wait for the merge, and keep the merge commit's sha. A pack may name only what the registry has published, and
   the next step takes a commit and nothing else: a branch or a tag is answered with `x '<ref>' is not a commit
   sha.`
3. On a development machine, re-pin with `tools/sync_registry.sh <the merge sha>`. It prints the upstream URL,
   the short sha and the number of entries.
4. Run `python3 tools/check_registry.py` (part of `make lint`). It prints `<n> registry entries @ <short>, <m> pack
   source ids resolve, <k> adapters name something here` with the new count and pin. If something is wrong it prints `x the vendored registry does
   not hold` and one line per problem, a sync stopped half-way among them.
5. Commit `data/sources/` and nothing else, with one line in `CHANGELOG.md`. Every release syncs the registry
   before it is tagged (`docs/NEXT_RELEASE.md`).
6. Only then may a `pack.yaml` name the id in `sources:`. The check then counts one more pack source id; an id it
   cannot find fails `make lint` with `` `<id>` does not resolve `` and a guess, or `no entry in the registry`.
   The entry reaches every node in the next release, and `planetai doctor` there shows the new count and pin.

To fill a blank adapter column, write the adapter, a function in `app/sources.py` or a code pack (see
[Packs](packs.md) and [Adding a source](sensors.md#adding-a-source) on the sensors page), and then set the
`adapter` string upstream; once it is re-pinned, `tools/check_registry.py` checks it against this tree in `make lint`.

> **Note.** "Registry" names two things here. This page is the source registry, `data/sources/`. `registry.json`
> at the repository root is the list of nodes, described on [Federation](federation.md); the node reads it from
> `main` every hour and serves it at `GET /nodes`.

## Where this leads

The registry is the same list on every node, which is what lets nodes compare what they measure.
[Before a sensor](before-a-sensor.md) is what a node reads for its place on the first day, before any sensor of
its own. When you are ready to join other nodes, [Sharing and security](sharing.md) decides who on your network may
read the node, and [Federation](federation.md) is how a house becomes one cell in a district's picture without its
readings leaving the house.
