# What is core, what is a pack, and how long raw readings stay

**Question.** A read of the whole node on 21 October 2026 (main 479eabf) found the core and the packs mixed in both
directions. About 1,500 of `app/main.py`'s 3,900 lines serve one pack, one vendor or one integration, and two packs
(`place` and `trust`) are core in everything but name. Before the code moves, five things needed an answer: whether
`place` and `trust` are core, where species, things and offers belong, whether vendor and integration code becomes
packs, how long raw readings are kept, and whether the first fixes (Phase 0) are done.

## What Tomas has said

On 21 October 2026:

- **Place: core. Trust: core.**
- **Species, and things and offers, are a category like air or heat**, or whatever else the node watches.
- **Home Assistant, Smart Citizen, AirGradient and the like should be packs.**
- **Raw readings are kept forever**, unless there is a reason to recommend otherwise.
- **Phase 0 is done** (#302 to #306: the up-link, where a model runs, `/health`, `private`, the Wall).

## Recommendation

**1. `place` and `trust` are core.** `place` already behaves as core: its four tables, the installer's prompt, the plan
view and six dashboard sections all assume it. `trust` has its rules in a pack and the same SQL again in `GET /trust`.
Both move under the core's name: their rules and cells go with the core's own (`config/`), their tables into
`init.sql`, and `GET /trust` reads the one copy of its SQL. A node that lists them in `PACKS_ENABLED` loses nothing:
the update removes the two ids from that list, because there is nothing left to switch.

**2. Domains are packs, and a domain brings its own issue.** Air and heat are a pack each (`air-quality`, `heat`) plus
an issue file in `app/issues/`. Species, things and offers become the same shape: a pack that carries its rules,
cells, readouts and its issue, so a node that does not watch species never loads them. That needs one thing the
loader does not do yet, and `docs/PACKS.md` already describes: an `issue.yml` inside a pack. When that lands, the
four issue files in `app/issues/` (air, heat, coast, land) move into their packs too, and the core keeps only the
engine that reads them.

**3. Vendors and integrations are packs; open protocols stay in the core.**

| becomes a pack | stays in the core, as a driver |
|---|---|
| Home Assistant (discovery and alerts over MQTT) | MQTT, the generic `planetai/sensors/#` topic |
| Smart Citizen (the cloud adapter, the account adapter, the MQTT relay) | Meshtastic over MQTT (the radio is the node's own transport) |
| AirGradient and PurpleAir (written, never wired) | `POST /readings` |
| the CAMS air history and the EPA correction, into `air-quality` | CKAN, any portal |
| | Telegram, Reticulum and LXMF as the alert channels |

Open-Meteo stays on by default as the zero-configuration fundamental, and moves into a pack only if a node ever needs
to run without it.

**4. Raw readings are kept forever.** Recommended as asked. Node #1 writes about 430,000 rows a month, close to
100 MB with its indexes, so ten years is about 12 GB, which any disk a node runs on can hold. It stays fast
because every query reads only the window it asks for: Phase 1 adds an index on time and an hourly table for that,
whatever the table's age. The case that would change this is sensors at one reading
a second, about 1.3 GB a day for a hundred series. Then the answer is monthly partitions, still kept, and any
deletion is a choice the household makes per node, never a step of an update.

**5. Phase 0 is done.** What follows is Phase 1, the core made able to scale, then Phase 2, the pack boundary made
true, in the order of the review.

## What every move must keep

A node that updates across these changes keeps everything it had:

- the schema only grows: a table or column is added, never dropped or renamed;
- a feature that leaves the core for a pack is added to `PACKS_ENABLED` by the update wherever a node lists its packs,
  as Bali Air Dispatch was in `update.sh` step 5b;
- a pack's own tables keep their names and their rows when the pack declares them;
- nothing deletes a reading, and `out/captures` joins the nightly backup, because a picture exists nowhere else.

## What this record does not do

It moves no code. Each move is its own pull request, run on node #1 before it merges.

Decided: Tomas, on 21 October 2026.
