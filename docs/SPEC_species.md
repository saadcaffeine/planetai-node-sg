# SPEC: a finding names its species

*Asked, 12 October 2026, by Tomas, after the image model shipped (#217): "we need a way to link the image analysis
with local species of trees, animals, or urban inventory, or issues", and the same evening, of the three next steps:
"The short Spec linking findings to species". Urban inventory and issues come after this one.*

**Status: steps 1–4 built, 13 October 2026 (#220, #221, #222 and the step 4 PR); §4 amended as built.** Each step in §6 is its own pull request, run on node
#1 before it merges.

## 1 · What exists

Since #217 an image carries `analysis`: a summary and a list of findings, each `{class, name, count, issue}`, with
`class` one of the physical classes of [flows 1.0](https://planetai.fab.city/vocab/flows/1.0/). A finding is the
model's until a person here edits or confirms it. A tree is `plant`, a bird is `animal`, and the name is whatever the
model or the person wrote: "coconut palm (Cocos nucifera)", "tree", "frangipani". Nothing ties that name to anything
outside the node, so two nodes that see the same palm cannot tell they saw the same thing, and nothing can count it.

## 2 · A name becomes a taxon

A `plant` or `animal` finding gains a `taxon`: the GBIF Backbone Taxonomy's key, its scientific name, its rank and
how well the name matched. The Backbone is CC BY 4.0 and is what iNaturalist, GBIF and most open biodiversity data
already share, so a key is the same word on every node and on every platform a finding may be offered to.

- **The match is a call off the node.** GBIF's species match answers a name with a key (`Cocos nucifera` →
  2735117, species, exact, 99). The node sends the name and nothing else: never the picture, never the point. It is
  still a request somebody else's server sees, so it is off by default and gets its own yes in Set up, marked as
  outward, like every key that sends anything.
- **Without that yes,** the person types the scientific name and the node keeps it as written, with no key. The
  finding still counts on this node; it just cannot be compared with another one until somebody matches it.
- **The rank is what the match says, never more.** A model that says "palm" matches the family Arecaceae, and the
  finding stays a family. A 7B model's species is a guess; it is shown as the model's, with its rank, until a person
  confirms it, and a person can change the taxon as they change any other field of a finding.
- **People are still the one thing no finding names** (SPEC_eyes §3). The match is asked only for `plant` and
  `animal`, and a person is not an animal here.

## 3 · What the place says about the species

Two facts make a species finding useful to a household, and both have an open source.

- **Introduced or invasive.** The Global Register of Introduced and Invasive Species publishes a checklist per
  country on GBIF under CC BY 4.0 (Indonesia's is `61fb216d-1216-4287-8b78-fdfef45e8e18`). The node fetches its own
  country's list once, under the same yes, keeps it, and marks a matched taxon `introduced` or `invasive`. A taxon
  not on the list is unmarked, not "native": absence from a checklist is not evidence.
- **What others already saw here.** GBIF holds occurrence records in the node's seven cells (924 inside a box about
  2 km across around node #1, read on 13 October 2026). The node reads the species list for its seven cells, so a
  finding can say "also recorded here by others, N times". It keeps the taxon, the cell and the count; the records'
  contributors stay on the platform (SPEC_eyes §7). Only records under CC0 or CC BY are read. iNaturalist's
  CC BY-NC records are not open, and the node does not keep them.

Threat status is left out. The IUCN Red List is the source everybody quotes, and its terms are not open; a node
that showed it would be republishing what it may not.

## 4 · A confirmed species is counted, not yet a reading

*Amended 13 October 2026, as built.* The first version made each confirmed finding a `seen.<class>` reading with the
taxon key "in its meta". Readings have no meta, and every reading leaves the house: the daily export carries its
hourly mean under CC BY, and the push to a parent sends it on. A confirmed species with the hour its picture was
taken would have been published before anyone chose that.

So the node answers from the images instead. `GET /species` reads the findings a person has confirmed and counts
them per taxon (a name typed without GBIF counts by its words): how many, in how many images and cells, with the
GRIIS mark and others' records beside each. `?cell=` answers inside any cell up to res 10, the house's, the street's,
the seven. It answers only the images' own token, because where a picture was taken is the household's. The Data
door lists them above the images. A model's unconfirmed finding is not counted. From these the node answers the
species confirmed in a cell and how many, which is the smallest honest biodiversity figure a household can stand
behind.

**Readings come with the `private` role** (decision (A) in the pack design record, step 1 of SPEC_inventory). A
confirmed species then becomes a `seen.<class>.<key>` reading, private unless the household says otherwise, so rules,
cells and the page can use it and the household decides whether it travels.

A finding is not a flow. Flows 1.0 records what a place makes, uses and moves; a palm in a picture is a living thing
that is there, not a line in that ledger. A household that planted it logs `produce.plant.cell` itself, as it does
today, and a finding may offer that line but never writes it.

## 5 · Better eyes, later

A 7B model on a Mac mini knows a coconut palm and not much past that. Identifiers trained for the job exist (Pl@ntNet
for plants, with a free daily quota). Each one sends the picture out, which makes it an online model under SPEC_eyes
§4: its own row in Set up, its own yes, the service's name and what it keeps shown before the first picture goes.
That is SPEC_eyes step 3, not this spec. Offering a confirmed species finding, its picture and its point to
iNaturalist is SPEC_eyes step 6, and the taxon key from §2 is what it needs.

## 6 · Steps

1. **The taxon.** `taxon` on `plant` and `animal` findings, the GBIF match behind its own outward yes, a typed
   scientific name without it, and the Data door's finding row showing and editing the taxon.
2. **Introduced or invasive.** The country's GRIIS checklist, fetched under the same yes, marks a matched taxon.
3. **What others saw.** The seven cells' species from GBIF's open records, as context beside each finding.
4. **The species confirmed here.** `GET /species` per cell from confirmed findings, and the Data door's list.
   Readings (`seen.<class>.<key>`) follow the `private` role.

## 7 · Open

- A node with no internet at setup has no checklist and no match; whether to ship a small regional list with the
  node, or wait for a connection, is decided at step 2.
- A country with no GRIIS checklist gets no introduced mark; the node says so rather than leaving it blank.
- Urban inventory (a bench, a bin, a streetlight) and issues (a dump, a spill, smoke) need their own shared words.
  Flows covers some of the things, not their condition. That is the next spec.
