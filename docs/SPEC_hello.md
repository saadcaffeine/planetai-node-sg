# SPEC: a node says hello, and the others list it

*Asked, 11 October 2026, by Tomas: "explore how can we create a feature for nodes to be able to discover each other,
or to just send a hello world and being able to be visible in others people network section, in the global map, and
be listed. Is that possible under the current design?" Answered the same morning with three steps; Tomas: "yes, 1 to
3 sounds good".*

**Status: step 1 built (#208, 11 October 2026); step 3 on `hello-cli-2026-10-11`; step 2 and the site not built.** Step 1 is built first, then step 2, then step 3, each
its own pull request, each run on node #1 before it merges.

## 1 · What exists, and what the page pretends

A node already has two ways to know about another node, and the page uses neither.

- **Listed.** `registry.json` at the root of this repo is the programme's list of nodes (`SPEC.md` §2). A node joins
  by pull request, and the merge is the approval. It lists one node, `bayu-ungasan`.
- **Heard.** With `RETICULUM_PRESENCE=1` a node announces its name, version and a coarse cell (res 3 by default,
  never finer than res 6) every 30 minutes, and keeps the nodes it hears in `/health.reticulum.peers`, each with a
  distance between cell centres. Off by default.

What the Node door draws instead is `KNOWN_NODES` in `app/static/doors-nodegeo.js`: three nodes typed into the page
on 6 October, two of them not in the registry, captioned "The programme's list on 6 Oct, not something this node
heard". The site's map (`planetai/web/src/data.js`, `SITES`) is a second hand-typed copy. The Reticulum section of
the classic dashboard never draws a live peer; the Node door shows only their count.

So the answer to "is it possible under the current design" is: listing is designed and half wired, hearing is built
and not drawn, and a live directory on the internet is refused by `SPEC_discovery` §1 and §8 and deferred by
`SPEC.md` §6 until about 30 nodes. This spec builds the first two and leaves the third alone.

## 2 · Two words, never mixed

Every node on a page is either **listed** (it is in `registry.json` on `main`) or **heard** (this node's radio heard
its announce), or both. The page says which, in words, every time. A listed node is a claim the programme approved;
a heard node is something this machine witnessed. Neither is proof the other node is up.

## 3 · Step 1: one list, read by everyone

**The node reads the registry.** `check_release()` already asks the site once a day; beside it, a `check_registry()`
on the same hourly loop reads the file once an hour, from
`https://raw.githubusercontent.com/fabcity/planetai-node/main/registry.json`.

`main`, not the release: a node merged today is listed on every node within the hour, without a release. The
answer is kept in memory (`state["registry"]`) with when it was read. `UPDATE_CHECK=off` asks nothing, the same
switch that stops the release check, because both are this node reaching out to the programme. A failed read keeps
the last good list and says how old it is.

> ponytail: in memory only. A node restarted while offline has no list until its first good read, and the page
> says so. Add a copy on disk when that happens to someone.

**`GET /nodes`** answers the list, open at every `SHARE_LEVEL` (it is on `_SHARE_OFF`): it is a public file about
the programme and says nothing about this house. It passes on, per node, only `name`, `place`, `scale`, `since`,
`operator`, `cell` and a point rounded to one decimal (about 10 km, the rule `KNOWN_NODES` already follows). It
drops `contact` and `sources`; a page has no use for them, and an address is not this node's to repeat.

```json
{"read": "2026-10-11T07:00:00+00:00", "from": "https://raw.githubusercontent.com/…/registry.json",
 "nodes": [{"name": "bayu-ungasan", "place": "Ungasan, Badung, Bali, ID", "scale": "community",
            "operator": "Meaningful Design Group", "since": "2026-09", "cell": "8895a4c843fffff", "ll": [115.2, -8.8]}]}
```

`read` is null and `nodes` empty until the first read; `error` says why when the last read failed.

**The Node door draws it.** `KNOWN_NODES` and its caption go. `knownNodes(D)` builds the list from `D.nodes`
(`GET /nodes`, read with the rest at load): this node is matched by name and drawn at its own point; a node not in
the registry is drawn as itself and says "not listed yet: `planetai hello`". The special case for node #3 (a ring
around #1) goes with the list: a node with no published point is not drawn.

**The site reads the same file.** `SITES` in `planetai/web/src/data.js` is built from `registry.json` at build time.
That is the site repo and a manual deploy (Tomas's), so it is its own pull request there, after this one.

**Who is on the list.** Today one node. `mahon1` (Menorca) is drawn on the page and is not in the registry; node #3
has no published point. Each operator adds their own node with `planetai hello` (Tomas, 11 Oct: "Lucas add
himself, same as node 3"). Until then the Node door shows one listed node, and that is the truth.

## 4 · Step 2: draw what the radio heard

`/health.reticulum.peers` already carries `node`, `cell`, `res`, `km`, `first`, `last`. The Node door draws each
peer's coarse cell as an outline on the globe (`GET /geo/cell` takes a cell id for this, a small addition) and adds
a row to the list: "heard by radio, 3 h ago, within 60 km". A peer that is also listed is one row with both words.
Nothing about a peer reaches custody, cells, aggregates or alerts (`AGENTS.md`: peers are display only).

## 5 · Step 3: `planetai hello`

Saying hello is a pull request to `registry.json`, written for the household and sent only after they read it.

```
$ planetai hello
This is what the whole programme will see about this node, on GitHub and on every node's map:

  name      bayu-ungasan
  place     Ungasan, Badung, Bali, ID
  cell      8895a4c843fffff   (about 0.7 km² — not the house)
  lat, lon  -8.816, 115.164   (the centre of that cell)
  operator  Meaningful Design Group
  since     2026-09

Send it? [y/N]
```

- The fields come from the node: `NODE`, `/health.cell`, and the point `/health` gives a reader without the token, which
  is the centre of the res-8 cell (the R25 rule). Place defaults to `NODE_CITY`; operator and contact are asked
  for, never guessed, and contact is left out when empty. A node saying hello again is told it is listed, its listed
  place, operator and contact are the defaults (read from `registry.json` on main, since `/nodes` leaves contact out),
  it keeps its `since` and `parent`, and the same entry again sends nothing.
- `sources` is every source the node reads, by name and never a kit or station id: each `source` in its sensors
  table, and the map layers it keeps (`openstreetmap`, `openaerialmap`, `sentinel-2`). Read fresh at each hello, so the
  list says how much of its context the node plays in (Tomas, 12 Oct 2026).
- With `gh` logged in, it forks, brings the fork's `main` up to fabcity's (`gh repo sync`, so an old fork never
  sends back an old list, #365), commits the entry and opens the pull request, and prints its link. Without `gh`, it
  prints the entry and the link to edit `registry.json` on GitHub.
- The merge is the approval, as `SPEC.md` §2 has always said. Nothing announces anything until a person merges.
- `planetai hello --remove` opens the pull request that takes the entry out.

`bayu-ungasan`'s entry already holds its cell's centre, so it needs no correction.

## 6 · What this keeps from SPEC_discovery §8

- No exact place leaves: the registry holds a res-8 cell and a point no finer than it; the radio holds res 3.
- No reading, alert, sensor or household sentence is listed or announced.
- No write endpoint: `GET /nodes` is read-only and no other machine can add itself to this node's list.
- No new outward switch is turned on by an update: reading a public file is the same kind of act as the release
  check, behind the same `UPDATE_CHECK`, and being listed takes a person merging a pull request.
- The one bend: §1's "no central list". The registry is a central list, and it already was (`SPEC.md` §2). It is a
  file in a public repository, not a service that must be up: a node that cannot reach GitHub keeps working and
  says the list is old. A live directory nodes write to themselves stays refused until Tomas decides otherwise.

## 7 · Files

| Step | Files |
|---|---|
| 1 | `app/main.py` (`check_registry`, `GET /nodes`, `_SHARE_OFF`), `app/static/doors-nodegeo.js`, `app/static/doors-node.js`, `app/static/doors-core.js` (one read at load), `tests/test_nodes_registry.py`, `docs/site/api.md`, `CHANGELOG.md` |
| 1b | site repo: `web/src/data.js` built from `registry.json` |
| 2 | `app/main.py` (`/geo/cell?id=`), `app/static/doors-node.js` |
| 3 | `bin/planetai` (`cmd_hello`), `tests/test_hello.sh`, `docs/site/cli.md` |
