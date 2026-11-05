# SPEC: a fab lab node

*Asked, 15 October 2026, by Tomas, answering the pre-launch audit: "We should add a node type: fab lab." Then:
"machines, services, courses, repair, optional to be a parent node (depends on compute capacity), it should for sure
take 7 cells by default."*

**Status: decided 15 October 2026 (Tomas: "A: ok, B: yes, and with possibilities of expanding to the next contiguous cells, expanded limit, minimum 7. C: not yet"). Nothing built.** Each step below is its own pull request, run on node #1 before it merges.

## 1 · What is there today

- **The kind.** `NODE_KIND` is `home`, `business`, `community` or `district` (`app/settings.py:46`). Apart from the
  installer's question 3, nothing reads it: `/health` echoes it and no route changes on it. The installer files a
  lab under "A community or lab node", together with a neighbourhood.
- **Labs a node can see.** The `make` pack lists the nearest labs from the fablabs.io directory, as display only. That
  data is not openly licensed: AGPL covers the app, not the 2,864 records. A node can say where a lab is, but must not
  republish the lab's description.
- **What a house offers.** `things` (SPEC_inventory) with `offer = lend | give` become public lines at the res-8
  cell (`GET /offers`), answered through the node's bot.
- **Seven cells.** A private node maps its own res-8 cell and the six that touch it (SPEC_eyes §5). Mapping past them
  means asking to become a community node, and a lab registered on fablabs.io qualifies (§6).
- **Parents.** Any node with `AGGREGATE_TOKEN` set takes hourly means and alert timestamps from children. Since #258
  that token pushes and reads nothing.

## 2 · The kind

`NODE_KIND=fablab` is a fifth kind. A lab is not a neighbourhood: it has an offer of its own, and it is the place the
other nodes send people to ("the nearest place to make or fix something").

- **Installer, question 3.** "A fab lab: machines, courses and repair for the people around it." It sets
  `NODE_KIND=fablab` and `NODE_SCALE=community`. It also asks for the lab's fablabs.io slug, if it has one. The slug
  links the node to its own directory entry, so the lab can import its own record (§3).
- **The seven cells by default.** A fab lab node maps and counts its seven cells from the first boot, as a private
  node may. The slug is what a lab later shows when it asks to map past them (SPEC_eyes §6).
- **Listed as a lab.** `planetai hello` carries `kind: fablab` into `registry.json`, so every node's map draws it as a
  lab rather than a house. The registry schema gains `kind`, which is optional and defaults to the scale's word.

## 3 · What a lab offers

Four kinds of offer, all of them the lab's own words about itself, published CC BY by the lab:

| offer | what it says | built on |
|---|---|---|
| **machines** | a laser cutter, a 3D printer, a CNC mill: name, kind, state (working, down) | `things` with `class=tool`/`appliance` and `offer=lend` |
| **services** | "we cut your file", "we print parts": what, and whether it costs | a new `offers` kind, `service` |
| **courses** | a title, the next date, how to join | a new `offers` kind, `course`, with a date |
| **repair** | repair café days, what they fix | a new `offers` kind, `repair`, with a date |

- **One list, one route.** These ride the same rails as a house's lend and give: `GET /offers`, at the res-8 cell,
  in the open daily export, and answered through the lab's bot. A house's node already reads the labs nearby (the
  `make` pack). Once a lab runs a node, the house reads that lab's own `/offers` in place of the directory. Then
  "the nearest place to fix something" says what the lab can actually do this week.
- **Importing its own record.** A lab may copy its machines and its description from its own fablabs.io entry once,
  by its slug. Importing your own record is the lab republishing itself, which the licence question does not touch.

## 4 · Optional parent, by compute

A lab can be the parent of the homes around it, and becomes one only when its machine can carry it.

- The installer reads what `planetai preflight` already measures (memory, cores, disk). It offers "Let homes nearby
  report to this lab" only above a floor.
- Proposed floor: 8 GB and 4 cores.
- Saying yes sets `AGGREGATE_TOKEN` and prints it to hand out. Saying no, or a machine below the floor, leaves the lab
  a leaf like any home.

## 5 · Steps

1. **The kind.** `fablab` goes into settings, the installer question with the slug, `/health`, `planetai hello` and
   the registry's `kind`. The seven cells are on by default for this kind.
2. **Offers.** Add `service`, `course` and `repair` to offers, with a date where one belongs. A lab's machines come
   from things. The Data door gets a "This lab offers" table. The `make` pack prefers a lab node's `/offers` to the
   directory.
3. **Import from fablabs.io** by the lab's own slug, once, on the lab's word.
4. **Parent by compute.** The installer question and the floor.

## 6 · Decided (Tomas, 15 October 2026)

- **A. The floor for parent: 8 GB and 4 cores.**
- **B. Seven cells is the minimum, mapped like a private node.** A lab may grow into the next contiguous cells. The
  next ring around the seven makes 19 at res 8. It grows ring by ring, up to a larger limit than a home's. The seven
  are never fewer. The limit itself is set when step 1 is built.
- **C. Not yet.** Node #1 will move to Fab Lab Bali later; for now it stays at Tomas's place, a home. The first lab
  node waits for that move.

## 7 · Work a lab can do for the nodes around it

*Asked, 23 October 2026, by Tomas, after reading [Aleph](https://github.com/Belluxx/Aleph): what does not fit a
home node can be mapped as a service for a bigger one, "a Fab Lab or community node could host tools like this or
drone image services", or other work heavy in computing or AI.*

**Status: a map. A and B below were decided 23 October 2026; nothing is built.** It applies to a community
node too, if its machine meets the same floors.

A home node is a small machine. Some work needs more than it has, and some is better done once for a whole
neighbourhood. A lab takes that work when its machine can carry it, the same way it becomes a parent in §4.

| work | why a home can't | what the lab runs | how a home gets it | floor |
|---|---|---|---|---|
| **Drone surveys** | OpenDroneMap asks for 16 GB and 100 GB of disk. With 4 GB it runs out of memory past 100–200 photos (its install guide, read 23 October) | OpenDroneMap on flights by the lab or by neighbours. Out come an orthomosaic, a surface model and a textured 3D mesh | The lab uploads the mosaic to OpenAerialMap (CC BY 4.0). `planetai run place basemap --only drone` already fetches every OAM mosaic that crosses the node's ring, so homes need no new code. The surface model can also go to the terrain pack as an operator DEM | 16 GB, 100 GB disk |
| **Street-level photos** | Thousands of photos need a host, and blurring the faces and number plates in them is GPU work | A [Panoramax](https://docs.panoramax.fr/) instance: federated, self-hosted, it blurs on upload | Read from the instance's API. No node reads it yet | Panoramax's own |
| **A language model** | The 26b model node #1 uses already runs on a second machine in the house, not on the node | Ollama, serving a model the nodes nearby can call | The agent's remote rung, `AGENT_REMOTE_URL`. A question sent there leaves the house. Under `AGENT_PREFER=private` a node never uses a rung at a public address (#305) | not set |
| **Parent** | §4 | §4 | §4 | 8 GB, 4 cores |

**Licences.** Each Panoramax instance states its licence at `/api/configuration`. On 23 October OSM-FR's was
CC-BY-SA-4.0 and IGN's was etalab-2.0, and both ask mainly for photos taken in France. A lab elsewhere would host
its own instance and set an open licence on it. A drone mosaic on OAM is CC BY, worldwide, and it shows roofs and
yards. Who has to agree before it goes up is decided below (A).

**What stays on the home.** Terrain: the terrain draft reads node #1's 5 km square in about 5 s and fills and
drains it in 0.3 s. The OSM street map and Sentinel-2 are fetched once, in a few minutes. A lab's surface model
only makes the terrain sharper.

**What no node runs.** Aleph pulls Street View, Google's satellite tiles and Google Earth meshes through
undocumented endpoints, and its own README says this goes against Google's terms. A bigger machine doesn't change
the licence. Its open parts (OSM extracts from Geofabrik, the AWS terrain tiles, Photon geocoding) repeat what the
place pack and the terrain draft already do. Aleph is not used at any size of node. The drone and photo rows above
are the open way to get the same pictures.

**Decided (Tomas, 23 October 2026).**

- **A. Drone surveys come first.** They need no node code, only a lab with a drone, a machine above the floor and
  an OpenAerialMap account.
- **B. The publisher and the lab agree, and nobody else has to.** The publisher is whoever flew and owns the
  photos. The service exists to make drone data open, so the lab processes a flight only when its publisher agrees
  to put the result on OpenAerialMap under CC BY. A flight the publisher wants to keep closed is not this service.

**How a home finds a lab, still open.** Tomas's direction, in his words: "I guess the home node sets the
lab/community node as parent", and Reticulum "needs to play a role". What the node already has for each:

- **The drone service needs neither.** A home reads the lab's mosaics from OpenAerialMap, as it reads anyone's.
- **Parent.** A home already names one in `PARENT_API_URL`. Today that link runs on one `AGGREGATE_TOKEN` shared by
  every child, which lets any child write as a sibling (SPEC_identity §1). A lab with many homes makes that worse,
  so the parent step waits for node keys. The link runs on HTTPS over the tailnet, never over Reticulum (Tomas, 23
  October).
- **Reticulum.** The node already runs it in its own container, built from fabcity/planetai-reticulum since 23 October.
  It gives each node an LXMF address and, with `RETICULUM_PRESENCE=1`, announces the body of `GET /presence` every
  half hour. SPEC_discovery puts Tailscale first and Reticulum after (22 September). A lab could add `kind: fablab`
  and the services it runs to that same body, so homes in radio or TCP reach hear what the lab offers with no
  registry and no internet. Its address is a key kept in `reticulum:/data`; the node key SPEC_identity needs stays
  the core's own, since the bridge is leaving the core. LoRa
  carries the announce and short messages, never a mosaic.
- **What Reticulum may carry, decided 23 October.** Its licence (MIT plus no use in a system able to purposefully
  harm people, and none "directly or indirectly" in making an AI training dataset) is read in
  [the decision record](decisions/2026-10-23-reticulum-licence.md). Tomas: the optional bridge is acceptable, it
  moves out of the core before the AGPL relicence, and it carries discovery and messages to people. Aggregates, and
  anything else that becomes an open dataset, go over HTTPS.

**Holochain, later, for bigger nodes.** Tomas sees it as a future feature of lab and community nodes, the base of a
data economy around them: who flew, who processed, who used the result. Read 23 October: 0.7.1 is the current
stable release (14 October), under the Cryptographic Autonomy License 1.0, which is OSI approved. The Sensorica
read (28 September) advised against a Holochain conductor on a home node and against a DHT as the registry, and
took Nondominium's resource fields and bilateral receipts as ideas for `fabcity-flows`. A lab is a bigger machine
than a home, so the compute objection weakens there. An economy also needs records to trade on, and the drone
service's flights (publisher, lab, mosaic, licence) together with `fabcity-flows` logs would be the first. Look
again once a lab has run the drone service for a while.
