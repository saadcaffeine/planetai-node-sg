# SPEC: a node sees its place, and maps beyond its own cell

*Asked, 12 October 2026, by Tomas: "the node needs to add its own capabilities to map a locality, and it is where we
can add eyes where nobody has. That means the node being able to capture the context by using microscopy, phone or
normal cameras (human eye), or drone/balloon mapping … a visual data base, but also computing identified species,
pollution sources, green areas, spills, or anything the local or online model selected by the node owner maps. I
also would like the node to be able to expand its mapping capabilities beyond its own cell, being able to map the six
contiguous cells and still being a private node. When a node decides to map more, it can be promoted to a community
node." The five points below were put to him the same morning; Tomas: "All looks fine".*

**Status: step 1 and most of step 2 built in v0.82 (#217, #250); findings are not readings yet, online models (step 3) not built. Proposed 12 October 2026.** Each step in §7 is its own pull request, run on node #1
before it merges.

## 1 · What exists

Every picture a node holds today is somebody else's, taken from above: the Sentinel-2 composite its Earth Engine
builds, the OpenAerialMap drone mosaic and the OpenStreetMap vector tiles under `/ground/*`. They describe the place
the way the world's archives see it, and nothing in them was taken by the household.

The one pack that looked through a camera, `wyze-camera` (wild, 3 October), kept motion and nothing else. What it
taught is the starting point here:

- **Privacy became invisibility.** It wrote no readings so that nothing private could leave, and so nothing reached
  the page, a rule or an alert either. The node has no tier for data it keeps and uses but never exports. The draft
  decision record in pull request #175 proposes one.
- **It informed no decision.** A picture is worth keeping when it answers something the node already asks: is the
  air dirty because of something you can see, is the green going, is that water clean.

## 2 · A capture is a reading

A capture is one picture or one clip with the facts a reading has: when, which cell, who took it, with what. The
kinds are the ones Tomas named, and a pack can add more:

| kind | what takes it | typical cell |
|---|---|---|
| `microscope` | a USB or phone microscope over a sample (water, soil, a leaf, a filter) | where the sample came from |
| `phone` | a person, on the phone page | where they stood |
| `camera` | a fixed camera the household points | where it is mounted |
| `drone`, `balloon` | a flight or a kite or balloon line, stitched into a mosaic | every cell the mosaic covers |

The node keeps each one on its own disk with its hash, its time, its **exact point** and the res-10 cell that point
falls in. A tree, a dump or a spill is worth its precise position, and the point stays on the node like the picture
does: token only. Location metadata **in the file** (EXIF, GPS) is removed on arrival, so a picture that is ever shared
carries no hidden place; the point travels beside it, on purpose. A capture anywhere in the node's seven cells (§5) is
the node's own; one outside them is kept and marked as outside. Tomas, 12 October 2026: "It is better for precise
position of a tree or trash source".
The visual database is this list, and the phone page's walk can show a cell's captures at its step.

**Precision when it leaves.** A finding or an offered picture goes out with the precision its subject needs: the
exact point for a tree, a dump or a spill in public space. The one exception is the house: a capture inside the res-10
cell of the node's own point (`NODE_LAT`, `NODE_LON`), about 130 m across, leaves blurred to that cell by default, the
way iNaturalist's "obscured" geoprivacy works, and the household can lift that per picture.

## 3 · Pictures stay home; what a model finds is what travels

A picture never leaves the node on its own: not in `/export`, not in `/aggregates`, not to a parent, not on any
`SHARE_LEVEL`. It is shown to this machine and to a screen holding a token. The one way out is the household's offer
to an open platform (below), made per platform.

**Kept forever, where the household says.** Captures are kept until the household deletes them. They live in a
folder of their own, apart from the database and its backups, and the household can point that folder at another
disk, a NAS share or any mounted storage; the node writes there and checks it is there before it takes a capture.

**Offered to open platforms.** What the node makes is offered back to the commons, each by its own yes in Set up:
a drone or balloon mosaic to OpenAerialMap, a species finding with its picture to an open biodiversity platform
(iNaturalist, and GBIF through it), litter and dumping to OpenLitterMap (data under ODbL), and the same for the other
findings where an open platform for them exists. The
offer names the platform, its licence and what it publishes, before the first send. Tomas, 12 October 2026: the
photos and the node's other services, such as identifying species, "should be offered to open source platforms".

What a model **finds** in it is a reading like any other and follows the rules readings already follow: a species
and its count, the outline of a spill, the share of a cell that is green, a pollution source and its kind. Each
finding names the capture it came from, the model that found it and its provenance word, `model`, until a person on
the household confirms it, after which it is theirs. A finding without its model's name is not drawn.

People are the one thing no finding may name. A model that is asked to count species is not asked who walked past.

## 4 · The owner picks the model

Set up lists the models this node may run on its captures, one row each, off by default.

- **A local model** runs on this machine. Nothing leaves. This is the default, and the node says so.
- **An online model** sends the picture out. It gets its own yes, per model, in Set up, with the name of the service,
  what it keeps and for how long, shown before the first picture goes. Turning it off stops the next send; it cannot
  recall the last one, and the row says that too.

The model's job is the household's choice: species for one node, spills for another, green cover for a third. The
node records what each model was asked, so a finding can be read back to its question.

## 5 · Mapping beyond the cell

A private node may map its own cell and the six that touch it, seven cells at res 8, about 5.2 km² together. Captures,
sensors and findings in those seven count as the node's own; outside them they do not. This is the ring the walk
already draws, and it replaces `LOCAL_RADIUS_M`'s circle with cells the page can draw (Tomas: "Love the idea of the
seven cells").

One fact shapes what comes next. A res-8 cell's six neighbours are not its parent's other children: for node #1
(`8895a4c843fffff`) three of the six sit inside its res-7 parent `8795a4c84ffffff` and three in other parents, because
node #1 is not its parent's centre child. The seven-cell ring is the right shape for a private node, which maps what
is around it. A community node is held to its parent (§6), which is the shape the Index counts.

Mapping more stays private: a node can map its seven cells for years, and its listing (`docs/SPEC_hello.md`) shows
no more than it does today.

## 6 · A community node

A node that wants to map past its seven cells asks to become a community node, by pull request to `registry.json`
like any listing; the merge is the approval. The conditions:

- **Who:** a lab registered on fablabs.io, or a person registered as the representative of a Fab City member, or
  approved by one (decided 28 September 2026). Fab City checks this when it reviews the request; the node never reads
  fablabs.io to decide it.
- **Where:** it holds its res-7 parent cell: own or child measurements in at least four of its seven res-8 cells,
  each within the last 24 hours (the September draft's threshold, still open).
- **How it answers:** a public contact in its listing, and a written rule for pictures of people and private land,
  agreed with the community it maps.
- **What it gives back:** its findings, never its pictures, published at the community scale.

A community node that stops holding its parent says so on its page and in its listing, and keeps its history.

## 7 · Steps

1. **The capture tier.** A table for captures, a folder the household can place on any storage, the private tier #175
   proposes (kept, used, never exported), and `GET /captures` for this machine or a token. Upload from the phone page.
   **Built in #217** (12 Oct): the row keeps the exact point, token only, and only the file is cleaned (the CORRECTION
   of the same day); the walk counts a cell's pictures at its step.
2. **Findings.** A finding is a reading with a capture id and a model; one local model wired end to end (green share
   of a cell from a drone or phone picture is the smallest useful one).
3. **The model rows** in Set up, local and online, with the online yes.
4. **Seven cells.** The node's own cells become the res-8 ring; the walk and Place draw what is mapped in each.
5. **Community.** The `registry.json` fields and the check of §6, then the first promotion.
6. **Offers.** OpenAerialMap for mosaics, iNaturalist for species, OpenLitterMap for litter, each its own yes.

**What others already saw.** At setup, and from then on, the node also reads what open platforms hold about its seven
cells, as context beside its own captures: OpenLitterMap's verified litter points (a `candidate` in the source
registry since 12 October 2026, awesome-fabcity-data #81), iNaturalist's observations, OpenAerialMap's mosaics. Their
contributors' names stay on those platforms; the node keeps the point, the time and what was seen.

## 8 · Open

- The microscope's cell is where the sample came from, which the person says; the node cannot check it.
- Spills, pollution sources and green cover have no open commons to offer them to. A platform shared between nodes
  will come later, as its own spec (Tomas, 12 October 2026: "that will come later and probably won't be Ushahidi").
- What the node does when the captures folder is full or its disk is gone (`/storage` already measures the disk).
- The threshold in §6 and whether children, sensors or captures count toward holding a cell.
