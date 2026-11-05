# SPEC: the things a home keeps

*Asked, 13 October 2026, by Tomas: "map all the categories of value flows in cells, by using cameras of different
types, or inputing data in other ways to create some sort of local inventory, from infrastructure to actual objects
such as cars, motorbikes, trucks in the street, to household inventories of resources." The same day he agreed the
order (the private role first, one spec with three sources, build first what serves a decision), chose (A) in the pack design
record (#175) and named the first source: "household idle things first".*

**Status: steps 1–4 built in v0.82 (#224, #225, #227, #228); step 5 (cell totals) waits on the upstream tiers. Proposed 13 October 2026.** Each step in §8 is its own pull request, run on node
#1 before it merges. The street and the place (§7) get their own specs later.

## 1 · What it serves

The pack design record asks every new thing on a node which decision it informs. This one informs two.

- **The household's:** what do we own and not use, what could somebody near us borrow, and what needs fixing?
- **The cell's:** how many drills, ladders, sewing machines and motorbikes already sit idle within a few hundred
  metres, before anyone here buys another, and how much is waiting for a repair a Fab Lab could do.

That is the Fab City question at the size of a street. A thing that is already in the cell and gets used does not
have to come from `beyond`.

## 2 · What exists

- **Flows 1.0** has the classes most household things fall in: `tool`, `appliance`, `furniture`, `electronics`,
  `garment`, `textile`, `micromobility`, `part`, `goods`. Flows records what moves (produce, consume, use, and the
  rest). A thing on a shelf is not a flow; it is what the flows leave behind.
- **The image model** (#217) already files what a photo shows under those classes, and a person confirms or edits
  each finding in the Data door.
- **Captures** show how the node keeps something to itself. They have their own table, they are not in the daily
  export, and pack SQL cannot read them (`REVOKE ALL ON captures FROM planetai_ro`).
- **The `private` role** (decision (A), 13 October) is decided and not built. Readings with that role can be used by
  the page, rules and cells. They never reach the export, the aggregates pushed upstream, `/readings` or `/series`
  without the admin token, the ask pane or the agent's read tools.

Missing: a car and a motorbike have no class. `micromobility` is a bicycle or a scooter, and flows 1.0 has nothing
bigger.

## 3 · A thing

A thing is one row in a new `things` table, kept as captures are kept:

| field | values | why |
|---|---|---|
| `class` | a flows 1.0 physical class | the same word every node uses |
| `name` | the household's words: "cordless drill" | what they call it |
| `count` | 1 or more | four chairs are one row |
| `used` | `weekly` · `monthly` · `yearly` · `never` | asked once, changed when it changes |
| `condition` | `works` · `needs_repair` · `broken` | repair demand |
| `offer` | `no` · `lend` · `give` | `no` by default |
| `capture_id` | the photo it came from, or none | |
| `note` | free text | |

**Idle means `yearly` or `never`.** The household says how often a thing is used, once, rather than logging every
use. Nobody records each time they pick up a drill, and a figure built on logs nobody keeps would read as idle when
it is only unlogged.

The table is not in the export and not readable by pack SQL. It is in the household's own backup, and Set up says
so.

## 4 · What the page reads

When a thing changes, the node rewrites three private readings on one `things:<NODE>` sensor, per class:
`stock.<class>` (how many), `idle.<class>` (how many used yearly or never), and `repair.<class>` (how many need repair
or are broken). These are counts with nothing else in them, so they fit the readings table. Readouts, sections,
rules and cells read them like any other reading, and the `private` role keeps them home.

- **On the page:** the Data door lists the things, and you add, edit and delete them there. The Now door has one
  line: "31 things, 9 idle, 2 need repair".
- **Alerts:** none. *(Built without the report sentence first drafted here: the report is written by a model from a
  bundle the `private` role keeps these counts out of, so a sentence there would send them. Decided again when the
  report can say a private figure without its model reading it.)*
- **Outside services:** none.

## 5 · How a thing gets in

Cheapest first:

1. **Typed** in the Data door: class, name, and the rest default.
2. **From a photo.** A confirmed finding under a household class gets an "add as a thing" button, and the photo
   stays linked. A photo of a shelf turns into many things at once.
3. **From Telegram or an agent:** `/thing drill` and an MCP tool, both behind the admin token.

No camera watches the home to count things. The household chooses what goes in.

## 6 · What leaves, and only by choice

Nothing leaves by default. A thing marked `lend` or `give` becomes an **offer**: its class, name, condition and the
res-8 cell, with no household, exact point or photo attached. Offers are served at `GET /offers` and carried in the
export, because the household chose to publish each one.

**Cell totals** ("12 idle tools in this cell") would let a community node see the idle stock without any single
offer. They leave only as sums over at least five homes, so no single home can be read off the total. They wait for
the upstream tiers design, whose pilot tier is still undecided.

## 7 · The other two sources, later

- **The street:** vehicles passing or parked. A camera counts on the device and keeps only the counts, never a
  frame, a face or a number plate. It needs the core camera feature, which the pack design record puts after
  (A).
- **The place:** roads, buildings, power and water lines. OpenStreetMap maps most of this per cell already, so the
  node reads it and a person confirms or corrects it. OpenStreetMap's data is ODbL, which is share-alike, so what
  the node derives from it cannot go into the CC BY export as it is.

## 8 · Steps

1. **The `private` role.** *Built 13 October 2026.* A role in `channels.yml`, one predicate used by the export, the aggregate push,
   `/readings`, `/series`, `app/ask.py` and `app/agent.py`, and a test that a private row appears in none of them.
   Core, and its own pull request.
2. **Things.** *Built 13 October 2026.* The table, `POST`/`PATCH`/`DELETE /things` behind the admin token, the Data
   door list, the three private readings and the Now line (the report sentence is left out, §4). Flows 1.0 gains `vehicle` (count, physical) for cars,
   motorbikes and trucks, before any place logs one.
3. **From a photo.** *Built 13 October 2026.* "Add as a thing" on a confirmed finding.
4. **Offers.** *Built 13 October 2026.* `lend` and `give` become public lines at the res-8 cell, answered through the
   node's Telegram bot.
5. **Cell totals.** Waits for the upstream tiers.

## 9 · Open

- **The threshold for cell totals.** Five homes is a placeholder.
- **Who answers an offer.** *Decided 13 October 2026 by Tomas: the node's Telegram bot.* An offer's link opens the
  bot, which passes one message an hour per sender to the household's chats with the sender's Telegram name.
- **`vehicle` as one class or three.** A car and a motorbike draw on very different amounts of material; flows 1.0
  sums by class. One class with the kind in the name is the smaller change.
