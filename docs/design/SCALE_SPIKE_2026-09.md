# The scale spike: three sources the redesign has to be drawn against

**19 September 2026.** Not a release, not a pack, not a promise to a household. Three real numbers,
fetched once, turned into a fixture, so that direction H is drawn against the data that is coming
rather than against the data that is here.

## Why this is not "add three packs"

`awesome-fabcity-data` carries **209 sources**. Its centre of gravity is nowhere near this page:

| | city | region | bioregion | planet | community |
|---|---|---|---|---|---|
| economic | 35 | 28 | 10 | 5 | 2 |
| governance | 31 | 23 | 7 | 5 | 0 |
| environmental | 16 | 7 | 10 | 9 | 4 |
| social | 5 | 6 | 2 | 4 | 0 |

The node is the mirror image: **eight of its sixteen packs are `community` scale**, and the page is a
household reading its own air. Of the 209, roughly half have no API at all — they are annual file
downloads, not streams.

Wire those before the page has a place for them and you get one of two failures: numbers nobody can
see, or a section bolted on per source, which is the exact thing direction H was chosen to stop.
Draw the page first against today's fixtures — a sensor every fifteen minutes — and it gets drawn
for one shape of number and redrawn the first time a yearly city figure arrives.

So: three sources, one fixture, before the redrawing. Not 186.

## How they were picked

1. **Open, and no credential.** A fixture that needs a token is a fixture one person can make.
   ENTSO-E was the strongest candidate for the region rung and was dropped for this: registration,
   and "free for non-commercial" is not an open licence.
2. **One place, so the four rungs belong to one node.** Barcelona — Poblenou has a tester, Fab Lab
   Barcelona is there, and `presets/barcelona.env` exists. A fixture that mixes a Bali sensor with a
   Catalan budget is four numbers about nowhere.
3. **Each one a shape this page cannot draw today**, and a different one.

## The three, and the fourth rung that is already here

| rung | source | registry id | shape |
|---|---|---|---|
| community | this node's own kit | — | a reading every fifteen minutes, at an address |
| **city** | Barcelona — Pressupost municipal i execució | `economic/city/barcelona-pressupost-execucio` | money, by chapter, **annual**, whole city |
| **region** | Generalitat de Catalunya — Dades Obertes | `governance/region/generalitat-dades-obertes` | per-capita municipal waste, 947 municipalities, yearly |
| **planet** | UNEP IRP Global Material Flows | `environmental/planet/unep-irp-global-material-flows` | material footprint per country, **annual, no API**, a file |

All three are CC-BY-4.0 and `status: live`. The first two have CKAN/Socrata APIs and no key. The
third is a CKAN resource download whose signed URL expires in an hour — fetch the resource route,
not the link, which is the sort of thing a fixture finds out once so a pack does not find it out on
a node.

The region source is deliberately one the node already touches: `packs/open-data-health` reads that
same portal for *freshness*. Reading a dataset **out of** it at region scale is the ambiguity the
page will meet constantly — the same source, two scales, two meanings — and it is better met in a
fixture than in a release.

## What each one breaks, precisely

Read against the issue files (then `app/issues/*.yml`, each pack's `issue.yml` since 23 Oct 2026), `app/issues/schema.py` and the engine as they stand.

**1. `distances` has four rungs and they are all radii.** An issue declares `room`, `yard`, `ring`,
`region`, and `land.yml` already shows the honest way to have only one of them — the other three are
`~` and the page says so rather than drawing three empty boxes. But `region` means *a radius around
this point*. A city budget is not a radius; it is an administrative boundary, and the number is the
same at every resolution inside Barcelona and absent one street outside it. There is no rung above
`region`, and nothing anywhere that says *which* city, region or country a number is about.

**2. The dial is H3 resolution 2 to 12, and these numbers do not re-derive.** H's whole idea is that
the page re-derives as the dial turns. Turn it under a municipal budget and nothing happens, because
nothing can. The page must either grey it, or say plainly that this number is true for a boundary and
not for the disk — and *that sentence does not exist yet*.

**3. `live · partial · stale` has no meaning for an annual figure.** Provenance is computed from
`silent_minutes`. UNEP IRP's newest year is 2024 on the primary and 2019 on the mirror. Both are
current *and* years old. A page that says `stale` says the sensor is broken; a page that says `live`
says something it cannot support.

**4. None of the four issues can host these.** `NODE_ISSUES=air,heat,land,coast` is the page's spine.
Money and materials are not any of them. `land.yml` proves the *mechanism* is there — `kind: context`,
`line: ~` ("nothing to cross"), `readouts` instead of a stack — so the gap is the taxonomy, not the
engine: a fifth issue, or a second axis, and that is a decision about what a node is for, not a page
change.

**5. The grammar is µg/m³ and °C.** Euros, tonnes per capita and kilograms of waste per person need
their own band, their own rounding and their own sentence. `land.yml`'s `unit`/`dp`/`scale` fields
cover the arithmetic. Nothing covers what a household is supposed to *do* with a budget figure, and
a number on this page that asks for nothing has to say so, the way land does.

## What to actually build

1. Fetch the three, once, by hand. Record the request and the date.
2. Extend `app/issues/fixtures/node1-2026-09-06.json`'s shape into a second fixture — Poblenou, four
   rungs — with a `provenance` block saying which parts were read verbatim and which were
   reconstructed, exactly as the node #1 one does.
3. Draw H against it. The five points above are the acceptance list: each is answered in the drawing
   or named as still open.
4. **Then** the redesign, and only then the other 186.

Nothing here ships. No pack, no `.env` key, no tarball. If one of the three turns out to be worth a
pack later, it goes through `docs/site/packs.md` and the six gates in `docs/NEXT_RELEASE.md` like any
other source, and it gets a live run somewhere before a household sees it.
