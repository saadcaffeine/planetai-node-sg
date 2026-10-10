# The source registry
<!-- checked: v0.80.10 -->

A node measures what its adapters read. The registry is the network's shared list of what could be measured
at each pillar and scale, and of the places a person could go to act on it, carried inside every node as a
pinned copy. With it, a node can answer a question `/cells` cannot: not only "what does this place measure",
but "what has anyone filed that it could measure, and does any code read it yet". The route's own
docstring: "`/cells` says what this node computes. This says what the network has registered — including for
the cells no adapter fills yet, which have no `/cells` row at all."

A source with a blank adapter column is an adapter nobody has written yet. The dashboard's note on that
column says so: "naming it is how somebody comes to write it."

## What the node carries

The source of truth is [`awesome-fabcity-data`](https://github.com/fabcity/awesome-fabcity-data): one YAML file
per source at `data/<pillar>/<scale>/<slug>.yaml`, validated against the schema in that repository's own CI.
Each node carries a copy at `data/sources/`, mounted read-only into the app container:

| path | what it is |
|---|---|
| `data/sources/REGISTRY_VERSION` | the pin: `sha=851b8db91c046c13c1e232f6e8e61f7a4911270f`, `short=851b8db`, `synced=2026-10-09`, `entries=269`, and the upstream URL |
| `data/sources/data/<pillar>/<scale>/<slug>.yaml` | the 269 entries as filed |
| `data/sources/schema/dataset.schema.json` | the schema they are validated against |
| `data/sources/index.json` | the YAML folded into one JSON list, with `slug` and `cell` derived from each file's path |

`app/registry.py` reads `index.json`, the same file `bin/planetai` reads with a host Python that has no YAML library, and caches it on the file's
modification time, so a re-pin that arrives with `planetai update` is picked up without a restart. The
directory is `SOURCES_DIR`, default `/app/data/sources`. Nothing in this repository edits an entry:
`tools/check_registry.py` re-derives `index.json` from the YAML and fails `make lint` if they differ.

Since v0.73 `tools/sync_registry.sh` also copies the
registry's `reviews/` and `cells/` trees, with their schemas, when the pin has them, and `index.json` gives
every entry a `reviews` list: the reviews filed for it, oldest first, `[]` when there are none.
`tools/check_registry.py` then fails when a review names an entry the pin does not carry, or when a
`cells/` file is not named for its own `cell`. The `851b8db` pin has both: four reviews, so four entries carry a
`reviews` list that is not empty, and one `cells/` file for each of the twenty cells.

It is pinned rather than fetched, and [`docs/SOURCES.md`](../SOURCES.md) gives three reasons: a node with no
uplink answers the same question as one in Barcelona, every node in a release answers it the same way, and a
change to what a node believes about the network is a diff somebody reviewed. `tools/sync_registry.sh`
refuses a branch or a tag for the same reason: only a commit is a pin.

At `851b8db` the 269 entries are 119 economic, 68 governance, 56 environmental and 26 social. By status, 212 are
`live`, 41 `candidate`, 8 `deprecated`, 4 `stale`, 3 `planned` and 1 `paywalled`. Sixteen carry an `adapter`.
Sixteen are act sources.

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
| `adapter` | what in this repository reads it: `core:<function>` in `app/sources.py` or `app/bootstrap.py`, or `pack:<id>`. Absent means no adapter exists: the source is registered and unread |
| `feeds_cells` | the Index cells a node fills from it, which need not be the entry's own `cell` |
| `role` | `observe`, `act`, or both. Absent means `observe` |
| `act_kind` | for an act source: `facility`, `equipment`, `design`, `repair`, `material`, `match` or `network` |
| `notes` | the long form: quirks, rate limits, and the licence clauses a source turns on |

`wired_in_planetai`, the hand-set boolean that `adapter` replaced, is still in the files and is deprecated
upstream; the node reads `adapter` and nothing else.

`cell` and `feeds_cells` answer different questions. Bali Air Dispatch is filed under
`Environmental|Community`, where it publishes its strongest signal, and feeds `Environmental|City`, because
its stations are other people's and fill the public-reference cell, never the in-custody one.

## Three counts per cell

Since v0.73 the node counts each cell three ways, from the entries a node could fill it from:

| count | what it counts |
|---|---|
| `capable` | status `live` and an `adapter`: code here reads it |
| `reviewed` | status `live` and either an `adapter` or a review whose verdict is `usable` or `usable-with-caveats` |
| `candidate` | status `candidate`: verified, and nobody has read it for a real territory |

An entry counts against every cell in its `feeds_cells`, and against its own `cell` only when it has no
`feeds_cells` key. An entry with `feeds_cells: []` counts in no cell. No `deprecated`, `stale`, `paywalled`
or `planned` entry counts anywhere. `capable` is always part of `reviewed`.

At `851b8db` that is 12 capable, 17 reviewed and 51 candidate across 19 cells, from 269 entries. Sixteen
entries count nowhere: 8 `deprecated`, 4 `stale`, 3 `planned`, 1 `paywalled`. Of the sixteen entries with an
`adapter`, six say `feeds_cells: []` (`fablabs-io`, for one), and two (`airgradient`, `smart-citizen`) feed
two cells each, so 12. Reviews add five to `reviewed`: of the four reviewed entries three are `live`, and two of
those feed two cells each. The 41 `candidate` entries make 51 for the same reason: ten of them feed two cells
each. `Governance|City` has 32 entries filed under it and counts capable 4, reviewed 4, candidate 0: the four
CKAN portals read by `core:ckan`.

## Reading it, step by step

**1. List it.** Run `planetai sources`. It prints `registered in awesome-fabcity-data, read from the node:`,
then one line per entry: the slug, the status, the first 40 characters of the licence, the pilots, and the
code that reads it. By default it shows this node's pilot (`NODE_CITY`) plus the `global` rows; on a
`bali` node that is 102 entries. `--all` shows every entry. It ends:

```
  102 of 269 entries. The last column is the code that reads it. A cell with sources and a blank column is one nobody has written an adapter for yet.
```

Since v0.73 two lines follow it, the three counts summed over every cell and what they mean:

```
  across 19 cells: capable 12 / reviewed 17 / candidate 51
  capable = live with an adapter. reviewed = live, backed by an adapter or a usable review. candidate = verified, unread.
```

With `--all` a last line names what counts nowhere:

```
  counted nowhere: 8 deprecated, 1 paywalled, 3 planned, 4 stale. A node cannot call them, so they are in no cell number.
```

With the containers down it reads `data/sources/index.json` off the disk and says `read from data/sources
(the node is not answering)`. The answer is the same either way, because the registry is a file in the
release, not something the node works out.

**2. Filter it to one cell.** `planetai sources --all --cell 'Social|City'` lists the 12 entries filed for that
cell, from the Barcelona electoral sections to the US Census ACS, and the last column is blank on every
one. That is the part of the Index no node fills yet, with the sources that could fill it named. Since v0.73
the footer then says `Social|City: capable 0 / reviewed 1 / candidate 7`, the one reviewed entry being
`social/city/ine-spain`, whose review found it usable. The counts are the registry's
whole count for that cell, whatever the other filters, and come from `feeds_cells`, so they include
`social/region/worldpop`, which is filed under `Social|Region`. The `counted nowhere` line counts the whole
registry too. The other filters are `--pillar`, `--scale` and `--json`. Over HTTP the same filters are query
parameters, plus `wired`: `GET /sources?wired=false` is every registered source nothing reads. Since v0.73
there is also `status`: `GET /sources?status=candidate`.

**3. Read one entry.** Ask the node for it by slug:

```bash
curl -s -H "Authorization: Bearer $(grep '^ADMIN_TOKEN=' ~/planetai/.env | cut -d= -f2)" \
  localhost:8080/sources/environmental/community/bali-air-dispatch
```

The answer is the entry as filed: `"adapter": "core:baliairdispatch"`, `"feeds_cells":
["Environmental|City"]`, `"auth": "none"`, the licence text, and notes that name every reader (the core's
`baliairdispatch()` ingests the ring, `packs/nearby` verifies it, `packs/season` reads it over 68 days).
The same text is in `data/sources/data/environmental/community/bali-air-dispatch.yaml`. A slug that is not
in the pin answers 404 and names the pin.

**4. See it on the Network view.** Open the dashboard's Network view. The section headed **What this place
could read, and where it could go** has three rows, with `GET /sources` beside its title. *Registered, and
*Registered, and read* shows `pin 851b8db · synced 2026-10-09`, and the pin is a link to the registry on GitHub at that
commit. It says "269 sources registered; 16 have code on this node that reads them", naming the twelve
adapter strings (`core:airgradient` to `pack:place`), then "The rest have no adapter yet, which is a thing
nobody has written rather than a thing this node refuses." Its figure is `16/269`. *What a cell could use*
reads `across 19 cells` and shows the three counts the node computes, added up: `12 capable`,
`17 reviewed`, `51 candidate`. *Places to act* counts the 16 act sources by kind: `6 directories of fab labs
· 1 directory of repair cafés · 7 libraries of open designs · 1 matcher of designs to workshops · 1 list of
places that pledged`, and says how many state in the registry's own words that no licence is published (4).
A line under the rows links to `GET /sources?status=live`, `GET /sources?status=candidate`, `GET /cells` and
[Adding a source](#adding-a-source). The fold under it lists all sixteen with each licence as the registry
wrote it. The page fetches `/sources` the first time somebody opens Network, and never before.

> **Gap in v0.80.10.** The registry counts `core:airgradient` among the sources that are read, and the
> AirGradient function exists in `app/sources.py`, but the poll loop never calls it. The registry records
> that the code exists, not that a node runs it.

## Act sources

Sixteen entries carry `role: act`: places to go and things to build with, rather than things to read. The
`make` pack reads the first two. What each says about its licence, in the registry's own words:

| entry | act_kind | status | read by | licence, as filed |
|---|---|---|---|---|
| `economic/community/fablabs-io` | facility | live | `pack:make` | NOT OPEN — no data licence published. Platform ToS §7.4 restricts mass harvesting, §7.5 restricts commercial use, §8.1 leaves copyright with each lab. See notes. |
| `economic/community/fablabs-network-data-archive` | facility | live | `pack:make` | No licence published — the repository has none, and the records are fablabs.io's, under its Terms of Use. See economic/community/fablabs-io. |
| `economic/community/hackerspaces-org` | facility | live | — | not stated |
| `economic/community/maps-of-making` | facility | live | — | not stated |
| `economic/community/precious-plastic-community` | facility | live | — | NOT OPEN — the Terms reserve database rights to Precious Plastic. The MIT licence covers the platform code only. See notes. |
| `economic/community/spaceapi-directory` | facility | live | — | not stated |
| `economic/community/repair-cafe-directory` | repair | planned | — | not stated |
| `economic/planet/appropedia` | design | live | — | CC-BY-SA-4.0 (site default; proprietary licences allowed only on approval) |
| `economic/planet/field-ready` | design | live | — | CERN-OHL variant per catalogue metadata on 156 of 193 items — the organisation's own site says All rights reserved. Confirmation pending, see notes. |
| `economic/planet/okh-losh` | design | planned | — | not stated |
| `economic/planet/okh-search` | design | live | — | Creative Commons — version and variant not stated by the publisher (see notes) |
| `economic/planet/open-lab-starter-kit` | design | live | — | CERN-OHL-W-2.0 on eight of the nine repositories; OLSK-Large-3D-Printer is GPL-3.0. Per-repository, verified 2026-09-22 — see notes. |
| `economic/planet/oshwa-certification` | design | live | — | CC-BY-SA-4.0 |
| `economic/planet/things-that-work` | design | live | — | CC-BY-SA-4.0 (content); MIT (code); third-party assets under their own terms |
| `economic/planet/open-hardware-manager` | match | live | — | not stated |
| `governance/city/fab-city-pledged-cities` | network | live | — | No licence published — the repository carries none. The Foundation's own list, and the one source here it could license with a sentence. |

Four name an open licence outright (`appropedia`, `oshwa-certification`, `things-that-work`, and
`open-lab-starter-kit` per repository). Four say no licence is published or the data is not open. The other
eight state none, or a licence whose variant or scope is still unconfirmed (`okh-search`, `field-ready`). The dashboard does not sort these into open and not open, and
neither does this page: that is a judgement about somebody else's terms.

## Elsewhere in the node

- **`GET /cells`.** Every row carries `registered`, `adapter`, `reviewed`, `candidate` and `capable`, grouped
  by `feeds_cells` as above. Since v0.73 `registered` keeps its name and carries the `reviewed` count, and
  `adapter` is true when `capable` is above 0; before, both grouped by the entry's own `cell` and counted every
  entry filed there, so `Governance|City` went from 32 to 4. A cell
  with registered sources and no adapter has no `/cells` row at all, because a node only emits rows it can
  compute; that half of the question is `planetai sources --cell`.
- **`planetai doctor`.** One row: `source registry: 269 entries · awesome-fabcity-data @ 851b8db · synced
  2026-10-09`. It goes amber when the pin is over 180 days old and red when `data/sources/` is missing.
- **Packs.** Every id in a pack's `sources:` must resolve to an entry at the pin, or `make lint` fails and
  names the id. At v0.80, 13 pack source ids resolve.

## The endpoints

### GET /sources
Access: open

The registry as this node carries it. Query parameters, each optional and combined with AND: `pillar`,
`scale`, `pilot`, `cell`, and `wired` (`true` or `false`, read from each entry's `adapter`). `pilot` also
returns the `global` rows, because an entry relevant everywhere is relevant to every pilot. Returns
`{registry: {sha, short, synced, entries}, count, sources}`. Since v0.73 there is one more parameter,
`status` (`live`, `candidate`, `stale`, `deprecated`, `paywalled` or `planned`), and the answer is
`{registry, counts, count, sources}`: `counts` is `{cell: {capable, reviewed, candidate}}` for every cell
the registry counts, whatever the filters. Answers 503 when `data/sources` is empty or
unmounted. It is on the `open` list on purpose: a copy of a public registry of public datasets, the same on
every node in a release, that says nothing about the house.

### GET /sources/{pillar}/{scale}/{slug}
Access: open

One entry, as filed. 404 names the pin the node carries and points back at `/sources`.

## Adding a source

1. Open a pull request to `awesome-fabcity-data` with the entry, one pillar and one scale, following its
   `CONTRIBUTING.md`. The schema allows no key it does not name. Nothing on any node changes yet: the
   entry is a proposal to the network, and the network decides whether it is a source.
2. Wait for the merge. A pack may name only what the registry has published. Keep the merge commit's sha:
   the next step takes a commit and nothing else, and answers a branch or a tag with `x '<ref>' is not a
   commit sha.`
3. On a development machine, re-pin: `tools/sync_registry.sh <the merge sha>`. It prints
   `data/sources is https://github.com/fabcity/awesome-fabcity-data @ <short> — <n> entries`.
4. Commit `data/sources/` and nothing else, with one line in `CHANGELOG.md`. `docs/NEXT_RELEASE.md` makes
   "sync the registry, then tag" a rule of every release. Before committing, `python3
   tools/check_registry.py` (part of `make lint`) should print `<n> registry entries @ <short>, <m> pack
   source ids resolve`, with the new count and pin; `x the vendored registry does not hold` is followed by
   one line per thing that is wrong, a sync stopped half-way among them.
5. Only then may a `pack.yaml` name the id in `sources:`. The same check then counts one more pack source
   id; an id it cannot find fails `make lint` with `` `<id>` does not resolve ``, followed by a guess or
   `no entry in the registry`. The entry reaches every node in the next release, and on a node running it
   `planetai doctor` shows the new count and pin in its `source registry:` row.

To fill a blank adapter column, write the adapter: a function in `app/sources.py` or a code pack (see
[Packs](packs.md)), and then the `adapter` string upstream, which the registry's CI checks against this
repository.

> **Note.** "Registry" names two things in this repository. This page is the source registry, `data/sources/`.
> `registry.json` at the repository root is the node directory, described on [Federation](federation.md).

> **Gap in v0.80.10.** Comments in `app/registry.py`, `app/main.py` and `bin/planetai` still say the registry
> holds 209 entries, and a docstring in `app/registry.py` says sixteen of 225 entries count nowhere. The pin
> carries 269, and sixteen is right.

## Where this leads

The registry is the same list on every node, which is what lets nodes compare what they measure. The next
part is joining them: [Sharing](sharing.md) decides who on your own network may read the node, and
[Federation](federation.md) is how a house becomes one cell in a district's picture without its readings
leaving the house.
