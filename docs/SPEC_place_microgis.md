# SPEC: Place, the small GIS a place keeps about itself

*Asked, 4 November 2026, by Tomas: "look at this project: https://github.com/opengeos/RustGIS, and take it as reference
to re-design the Place tab of the planetai node to make it a hyperlocal GIS". Then, in the same conversation: "a PLACE
tab for the home/individual node, runs on browser, and with basic analysis options, which I think it should include
agent readiness and more analysis tools than now, but not as many as a local GIS (to be built in the fab lab node)";
"more about the context and the influence of things happening outside the house, not inside the house, as I think that
is a feature Home Assistant does better"; "I want also that the logic of this microGIS follows the work of Ian
McHarg … I want to recover the capacity of a place to know about itself"; "it can go to light fitness, as it also
matters for the index and the response capacity to act"; "the cake layering from McHarg is the root of thinking for
the Fab city Full stack. We dont need to explain it in the dashboard, but makes sense in the docs … it should be
canonical"; "this is a hyperlocal and distributed inventory with a compute and intelligence layer on top. We need to
be also able to incorporate tools for hyperlocal observation, like drone mapping, microscopy, cameras, soil sampling,
and other data that it is not trivial". Tomas approved the design described here: "all good, lets go". On reading the
first draft: "we should add artificial observations as part of nature, meaning: roads, built environment, they have an
effect in natural flows (wind, water, growth of plants). And second, the categories shouls be aligned with the fab city
flows work we did based on the value flows, make sure we are matching that".*

**Status: proposed 4 November 2026. Nothing is built.** Each step in §12 is its own pull request, run on node #1
before it merges.

## 1 · What it serves

Place today is a map you look at. It has fourteen layers behind six tabs, four tools (inspect, measure, back to the house,
PNG), three separate views (Map, From orbit, What changed), and below the map a report-like strip: where the readings
come from, the species, what is changing. You can't select, filter or ask anything, and no analysis gives a result.

This spec turns Place into a small GIS for the home node: the place's own inventory of what surrounds the house, how its
parts act on each other, and where a few home-scale things would fit best. Every tool is a named command, so a person
can press it or the Ask agent can run it from a sentence ("where does the afternoon sun hit us?").

**Outside the house only.** Rooms, indoor sensors and floor plans belong to Home Assistant. On node #1, 4 November, the
label margin listed Room A–G and Sensors 4–6 in 10 of its 11 rows, all at "416 m" from the house. Those rows leave
Place. (The 416 m is wrong somewhere on its own account. That gets checked separately, not here.)

## 2 · Goals, non-goals, anti-goals

**Goals**

- The inventory: the place's layers, ordered as McHarg's layer cake (§3), each saying what the node holds, holds in part,
  or does not hold yet.
- Interactions: the analyses in SPEC_place_analyses (sun and shade, trees 3-30-300, built form, street structure), plus
  sealed ground, rings and distance, walk to, what changed and where the rain goes, each as a tool.
- One vocabulary: the cake's layers and the fitness answers use the classes, verbs and rings of `fabcity-flows` 1.0.
- Light fitness: four home-scale questions (§6) with fixed rules.
- Agent-ready: one registry of commands that the panel, the Ask box and the Ask agent all call.
- Observation: people add what no archive holds, such as drone flights, microscope slides, camera pictures, and soil
  and water samples (§7).
- Runs in the browser of the node the household already has, with no new dependency and no build step.

**Non-goals**

- A desktop GIS. There is no ribbon, no toolbox of hundreds of tools, no ModelBuilder, no print layouts, no
  free-form weighted overlay. Those belong to the fab lab node (SPEC_fablab).
- Editing the map's geometry. Observations add points and areas; the base maps stay what their sources publish.
- Explaining McHarg on the page. The method lives in the docs (§10).

**Anti-goals: it fails if any of these happen, even when it works**

- Anything from inside the house shows on Place.
- A fitness answer reads as a score, or hides that a layer under it is missing or modelled.
- The page computes geography itself. The node computes and the page draws, as every door has since R40.
- A tool exists that the agent cannot call, or the agent can do something the panel cannot.
- It gets heavier than the page it replaces. v2 was asked for because v1 "still looks a bit bulky".

## 3 · The method: inventory, interaction, light fitness

Ian McHarg's *Design with Nature* (1969) built the inventory as a layer cake. Each layer is a part of the natural and
human environment, stacked in order of cause and time, so each is partly explained by the ones under it. The order in
his diagram (reproduced as Fig. 1 in Cohen 2019, from McHarg 1996a p. 258) runs from groundwater hydrology and bedrock
geology at the bottom, up through surficial geology, physiography, surface hydrology, soils, plants, animals and people,
to microclimate, mesoclimate and macroclimate. McHarg cared less about each layer than about how they interact.
Fitness, the second step, reads the overlay for a given human use: where the "intrinsic opportunities and constraints"
favour it, and where it would do least harm.

Place follows the same three steps: **inventory → interaction → light fitness**.

**What is new here.** McHarg's inventory was regional or national, mapped once, from above, by experts. In 1973 he
proposed a national one. This one is hyperlocal and distributed. Each node holds the cake for its own cells, inventories join upward
through the tiers already designed (home → community → pilot → Index), and the compute and intelligence sit on top
of each node: the node's geometry routes, its models and the Ask agent read how layers interact and answer fitness
questions on the node itself.

**Microclimate is the layer the node measures.** McHarg had to estimate the top of the cake. The outdoor kit, the
public stations and the forecast read it every few minutes.

**Every layer has three sources.** Open archives seen from above, sensors reading continuously, and people with
instruments (§7). Observation is how a place gets to know itself cell by cell: a soil sample at a corner means
"where something could grow" there rests on a measurement instead of a 250 m model.

## 4 · The page

The layout was settled in the v2 mockup, 4 November 2026. It lives at
`FAB CITY/.superpowers/brainstorm/7690-1793751265/content/place-v2.html`, outside the repo, as design reviews are kept
out of a repo households install from. Its references are Teenage Engineering (thin type, flat surfaces, one signal
colour), mono (the node's grid and 1 px rules, its existing lock), OP-XY (the black screen, dot switches, eight grey
steps, state by stroke) and OneSoil's field map (layers as a plain list, the date pill on the map, the controls in
one column).

**Desktop, three columns over a lower band**

| region | holds |
|---|---|
| header | "The ground around the house", the cell line (id, res, edge, area, point if a token is held), and the **Ask box**: one underlined line that takes a question or `/` to focus |
| left, 216 px | **the cake** (§5): a section per layer, results on top, each row a dot switch, the name and its source |
| centre | **the screen**: the map in a black bezel, with the hour pill (top centre), the legend (top left), the tool column (select, measure, draw an area, back to the house, export) and zoom apart at the bottom right, the scale rungs (street, block, cell, village, district) at the bottom left, attribution |
| under the screen | **the hours bar**: 48 h of the outdoor kit's feels-like, a play button, one cursor. The hour it holds is the hour every hour-dependent tool reads ("14:00 from the hours") |
| status line | pointer coordinates, res, scale, selection count, sources |
| right, 286 px | **the tools**: find (⌘K), the list of tools with their command ids, the open tool's settings, Run (↵), the same run printed as the command the agent sends, and the steps the agent took when it was asked |
| lower band | the **table of what is selected or returned** (left), and **the place in figures** (right): the yearly issues (Land, Coast, Water) and the Index cells, as the strip below the map shows them today |

**Controls**

- Layer switch: an OP-XY dot. Filled with a ring means on, hollow means off, dotted means not yet.
- Tool list: plain rows. The chosen tool is a filled ink pill showing its id. A tool that does not run yet has a dotted
  "not yet" pill.
- Settings: small segmented pills (today | solstice | equinox), values in mono, no input boxes where a choice will do.
- Run is the one filled button. Clear is a text link.
- Provenance pills use stroke alone, from the existing words: `live` filled, `partial` outline with a dot, `model`
  dashed, not yet dotted. This is the eighth check of the design language (state by solid, dashed and hairline, never
  hue), which no surface speaks today.
- Colour: the node's `--cells` blue for the cell and the selection only, including a blue tick beside each selected
  row in the table. Results are drawn in the eight grey steps. Orange stays the satellite's alone.

**Registers.** The page follows the node's paper and dark registers. The screen is black in both (Tomas, 4 November
2026). A black screen on the paper page changes the frozen layer's map palette, so step 1 carries a line in
planetai-design's design log and goes through planetai-design before any copy of the frozen layer changes.

**Phone (390 px).** One column: the screen first, full width, then the cake and the tools as a sheet that slides up
from the bottom, as in ArcGIS Field Maps, then the table. Tools stay 44 px, as the node's rule says. The rest is the
builder's.

**What leaves the page.** The three views become one map: From orbit becomes the satellite base with its year compare,
and What changed becomes a tool (§6). The species table becomes what the animals and plants rows open into. "Where the
readings come from" disappears as a block, because each layer row now names its source.

## 5 · The cake

The left column, from top to bottom: results, then the cake from the sky down to the ground, then the frame. The order
on screen is McHarg's turned upside down, so the layer the household lives in comes first. Each row says its source and
count. A row the node cannot fill yet stays, with the dotted mark: the place says what it does not know.

**The cake speaks the flows vocabulary.** Every layer names the classes of `fabcity-flows` 1.0 (the Fab City profile of
ValueFlows, its `resources.yml` on branch flows-pack-2026-09-28, published at planetai.fab.city/vocab/flows/1.0/) that live in it, and the
ceiling those classes carry. A ceiling is one of the nine planetary boundaries, or the material footprint. The Place
door, the flows log, the inventory of things and the Index then all use the same words for the same things: a tree
is `plant` on the map, in a fitness answer and in the line a household logs when it plants one.

**The built environment is part of the cake.** Roads, buildings, walls and paved ground are observed like any other
layer, because they act on the natural flows: buildings cast shade and turn the wind, roofs and roads shed water and
send it along the street, sealed ground stops plants and soil. McHarg had a layer for people, and this one holds what
people built. In the flows vocabulary a building is a stock, not a flow: it is what earlier flows left behind, as
SPEC_inventory says of a thing on a shelf. Its materials fall in the EW-MFA bins the profile already tags. Its effects
on the other layers are interactions (§6).

| section | rows on node #1 today | flows classes | ceiling | state |
|---|---|---|---|---|
| results | whatever the last runs returned, with a clear button | — | — | — |
| microclimate | outdoor kit, public stations, wind now (`/ground/wind`), surface heat (Landsat pack), sun and shade (a result) | `electricity` (the sun a roof could turn into it) | climate | live / partial |
| flows | what this place made, used, fixed and took in, by class and ring, from the flows log | all 30, by verb and ring | each class's own | not yet: the flows pack is not on main |
| built | buildings with their heights (OSM, Open Buildings), streets, sealed ground, radio mesh | stock, no class; EW-MFA bins | materials | partial |
| animals | species confirmed here (`/species`), GBIF records counted in the seven cells | `animal` | biosphere | partial |
| plants | canopy (Meta/WRI 1 m), land cover (WorldCover 10 m), paddy where the wild pack runs, satellite year compare (AlphaEarth) | `plant`, `habitat` | biosphere, land system | model |
| soil | SoilGrids 2.0, 250 m (CC BY 4.0, in the registry), soil samples (§7) | `compost` | biogeochemical | model / not yet |
| water | where the rain goes (terrain pack), coast, water samples (§7) | `water` | freshwater | model / not yet |
| ground | terrain (GLO-30), geology | — | land system | model / not yet |
| frame | this cell, the grid by zoom; base: street map, satellite 2025, drone mosaic | — | — | — |

The flows row sits beside the built one, where McHarg put people: the place's own economy, counted the way the flows
log counts it. Rings show as the profile defines them (cell, city, region, beyond), so physical things from `beyond`
read as products in (PITO) and things made in the cell as DIDO.

The base map is a choice in the frame section, not a layer of the cake. Which rows exist depends on the packs a node
runs. A row is drawn when a pack declares it, as packs already declare their sections on Now.

## 6 · Tools are commands

One registry on the node lists every tool. The panel draws from it, and the Ask agent calls it, so the panel and the
agent always offer the same tools.

- `GET /place/tools` returns each tool with its `id`, its name, its kind (look, interaction, fitness), the layers it
  reads, its arguments as JSON Schema, and whether it can run on this node now.
- `POST /place/run/<id>` with the arguments returns `{features, figures, word, inputs, as_of}`. `inputs` lists each layer
  the answer rests on, with its own word. `word` is the weakest of them (SPEC_place_analyses §4: a value is `model` when any one input is).
- Each run is kept in the node's log of runs, newest first, so "the steps the agent took" are the log's rows.
- Token-only, like `/place/geojson` and `/geo/*`.
- The page prints every run as the call the agent would send, for example
  `place.sun {"day":"2026-11-04","at":"14:00","on":"kit:roof","radius_m":300}`.

**Where a run computes** *(my call, settling a builder's question)*. Two kinds, and the registry says which:

- **Look tools compute on request** in `app/geo.py`, as `/geo/*` does today. They are cheap and need no new library.
- **Analyses and fitness read what the place pack worked out**, as SPEC_place_analyses §5 already says: recomputed
  when the pack refreshes, kept on the node. A run filters and draws those results, so its arguments are the choices
  the pack computed (today, solstice, equinox; the hour in the pack's 10-minute steps; a radius from a short list),
  never free values. A tool "can run now" when its results exist. The app image gains no numpy, shapely or rasterio;
  the heavy work stays in the pack, behind `PACKS_ALLOW_CODE`.

**The Ask agent keeps every promise `app/ask.py` makes today** *(my call)*. Place tools are offered to the pane only
on a screen holding a token. Every result passes through `scrub` before the model reads it, so the model sees figures,
words and layer names, never features or sensor ids; the page draws the features from the run itself. A run the agent
starts is not stored: its steps show in the pane while the conversation lasts, and the run log keeps only runs a
person pressed. Whether place tools also join the MCP surface for remote agents (`agent.py`, `TOOL_CLASS`) waits
until the pane has run on node #1.

**The first tools**

| id | kind | reads | notes |
|---|---|---|---|
| `geo.select`, `geo.measure`, `geo.area`, `geo.rings` | look | the map | the inspect, measure and rings Place has today, behind the registry |
| `place.sun` | interaction | buildings, heights, sun position | SPEC_place_analyses §5 |
| `place.trees` | interaction | canopy, mapped trees, distance to parks | 3-30-300, as SPEC_place_analyses §5 words it |
| `place.built` | interaction | buildings, heights | Spacematrix per res-9 child |
| `place.sealed` | interaction | buildings, streets, land cover | the share of each res-9 child under roofs, roads and paving: the ground where rain runs off instead of soaking in and nothing grows. *New here* |
| `place.streets` | interaction | street network | angular segment analysis; needs the street graph (below) |
| `place.walk` | interaction | places | the distance to the nearest school, clinic, market and place of worship the place pack already gives |
| `place.changed` | interaction | AlphaEarth | the What changed view, as a tool |
| `water.runoff` | interaction | terrain | the terrain pack's figures for the node's point, drawn on the map |
| `fit.tree` | fitness | sun, buildings, paths, canopy | where one more tree would cool the most → `produce.plant.cell` |
| `fit.roof` | fitness | sun, heights | which roof gets the most sun for a panel → `produce.electricity.cell` |
| `fit.grow` | fitness | sun, soil, samples, sealed ground | where a garden bed could go → `produce.habitat.cell`, yielding `food` |
| `fit.rain` | fitness | terrain grid, roofs | where rain could be caught → `produce.water.cell`; waits for the terrain pack to keep its routed grid |

**Fitness names the flow it would start.** Each fitness tool ends in the flows line the household would log if it
acted on the answer, in the profile's own words: the profile says `produce.electricity.cell` "is the roof", and rain
harvested is `produce.water.cell`. A fitness answer is the place's capacity to make something in its own cell, which
is what the Index counts as DIDO. When the household acts and logs the flow, the loop from knowing to acting is
closed in one vocabulary.

**How built things act on the flows.** Three of the interactions read the built layer against a natural one:
`place.sun` (buildings on microclimate), `place.sealed` (roofs and roads on water and plants) and `water.runoff`
(streets carrying the rain). The wind around buildings stays descriptive: SPEC_place_analyses left pedestrian wind out
as a 2D estimate rather than a model, and nothing here changes that.

**Distances are straight lines for now** *(my call)*. The place pack measures "walk to the nearest" as a straight
line (`ST_Distance`), and no street graph exists on the node. `place.walk` and the 300 m in `place.trees` say
"straight line" beside every figure until a street graph exists. Building that graph (from the OSM roads the node
already holds, with no new database extension) is its own step, and `place.streets` waits for it. SPEC_place_analyses
§8 already lists the straight line against the walk as open.

**Water stays at the terrain's scale** *(my call)*. The terrain pack keeps figures for the node's point and is accurate
to a street block, never a yard. `water.runoff` draws those figures. Flow lines need the pack to keep its routed
grid, a change to the pack in its own step, and `fit.rain` waits for that. Water running off a roof onto the ground
is out of scope.

**Light fitness.** Each fitness tool is a fixed rule over a few layers, written in its own docs line, with no
weights for the household to tune. Its answer points at an action ("this corner of the yard, 6 h of sun, 20 m from the
nearest canopy") and never gives a score. Every answer names the layers it rests on and carries the weakest word. Its rule changes only by a pull request.

## 7 · Observation

Today's "+ Add an image" becomes **"+ Add an observation"**. Two families:

- **Captures**, as SPEC_eyes built them: `phone`, `camera`, `microscope`, `drone`, `balloon`. The picture stays home,
  the exact point stays on the node, and EXIF location is stripped on arrival. A finding is what travels, and only by the household's offer.
- **Samples**, new here: a set of values at a point with its method, who took it and when. The first kinds are `soil`
  (pH, texture, organic matter, nitrate) and `water` (pH, turbidity, nitrate, E. coli presence). `method` tells a kit
  test from a lab result. More kinds come by pack, as capture kinds do. A sound recording is a capture.

A sample carries the provenance word `cached`, with its date beside it: a measurement made once and held, which ages
(Tomas, 4 November 2026). The language and the pill strokes do not change.

An observation lands on the layer it informs: a soil sample on soil, a pond-water slide on water, a camera trap on
animals, a picture of a blocked drain or a new wall on built, a drone mosaic on ground, plants and built at once. It shows at its point on the map and is counted in its
row ("soil · 2 samples · 3 weeks ago"). Fitness and interaction tools read it where it exists. That is how an
observation upgrades a cell's word.

**Heavy work goes to the lab.** A home holds and draws. A fab lab node runs OpenDroneMap, microscopy identification and anything with a large model, and hands the result back. The drone path already exists: the lab publishes to OpenAerialMap, and `planetai run place basemap --only drone` fetches it (SPEC_fablab §7).

## 8 · Privacy

Nothing changes in who sees what:

- The map, the runs, the captures and the samples are token-only, as `/place/geojson`, `/geo/*` and `/captures` are.
- A screen without a token sees the cake's rows with their sources and counts, and the yearly figures. It sees no map of the house and no
  points, and it says what it is not drawing and why, as Place does now.
- The house's own res-10 cell blurs on anything that leaves, as SPEC_eyes §2 says.
- No room, under any name, ever shows on Place. The Wall rule (14 October) extends here.
- Run results built from OpenStreetMap are a derivative database under ODbL and stay on the node (SPEC_place_analyses §6).

## 9 · The Index and the capacity to act

Tomas: light fitness "matters for the index and the response capacity to act". A fitness answer is something the house
can act on, and a decision is what Now already handles. How a fitness result reaches the Index is left open here (§13).
It could count as an action taken, or as a capacity the place has.

## 10 · Where McHarg is written

Tomas ruled on 4 November 2026 that McHarg's layer cake is the root of thinking for the Fab City Full Stack, and is
canonical in docs and research, but never explained on the dashboard.

- **On the dashboard:** the cake's order, with no explanation.
- **In the node docs:** a page on how Place reads the ground (inventory, interaction, light fitness, observation),
  citing McHarg 1969 and Cohen 2019. A new docs page also needs the site repo (NAV and `docsPages`).
- **In the concept canon** (per CANONICAL.md, the Core Ideas Paper source in fabcity/planetai): a short passage tracing the
  Full Stack back to the layer cake. It changes the concept canon, so it ships only with Tomas's yes and in his own words.

Source: Cohen, W. J. (2019). The legacy of *Design with Nature*: from practice to education. *Socio-Ecological
Practice Research* 1:339–345. https://doi.org/10.1007/s42532-019-00026-2

## 11 · What exists and is reused

- `app/static/doors-place.js` (the door) and `app/static/doors-placemap.js` (MapLibre 5.24 UMD + deck.gl, the scale
  rungs, the label margin, the tools). The new page replaces both. It keeps their traps learned: no h3-js on the page,
  PathLayer `widthUnits`, TextLayer `characterSet:'auto'`, zoom `interpolate` outermost.
- `app/geo.py`: `/place/geojson`, `/geo/grid|cell|measure|planet|rings`. The registry goes beside them.
- `/ground/*`: own vector tiles, S2 composite, drone mosaics, wind field.
- `/captures`, `/species`, the image model (SPEC_eyes, SPEC_species).
- The four analyses and their order in SPEC_place_analyses §7. Each lands as a tool here.
- The frozen layer and its three byte-identical copies under the lint gate: any token change goes through
  planetai-design first.

## 12 · Steps

1. **The page, with what exists.** The new layout, the cake list with today's layers, dot switches, the tool list
   showing today's tools, the lower band. Rooms leave Place. No new compute. Includes the design-log line for the
   black screen (§4).
2. **The registry.** `GET /place/tools`, `POST /place/run/<id>`, the run log, the look tools behind it, the Ask
   agent wired to it, the printed command. Node #1 has no model on its own machine and the pane refuses any other, so
   a small local model goes on node #1 first, and the agent wiring runs there before it merges (Tomas, 4 November 2026).
3. **The hours bar**, and `place.changed` and `water.runoff` from data the node already holds.
4. **Samples**: the `soil` and `water` kinds, "+ Add an observation", the rows' counts.
5. **The analyses**, one pull request each, in SPEC_place_analyses' order: heights with their source, `place.built`
   with `place.sealed`, `place.sun`, `place.trees`. The flows row of the cake fills when the flows pack lands, in its
   own release.
6. **Light fitness**: `fit.roof` and `fit.tree` once sun and trees exist, `fit.grow` once a soil layer and samples
   exist.
7. **The street graph**, then `place.streets`, and walking distances along streets in `place.walk` and `place.trees`.
8. **The terrain pack keeps its routed grid**, then flow lines in `water.runoff`, then `fit.rain`.
9. **The docs page** on the method. The concept canon passage only on Tomas's word.

## 13 · Open, for Tomas

- **How fitness reaches the Index** (§9). §6 now names the flow each fitness answer would start, which suggests the
  answer is a capacity and the logged flow is the action. The Index side is still undecided.
- **Built stock in the flows profile.** Flows 1.0 has no class for a building, a road or paved ground, and this spec
  adds none: the built layer is a stock, read from the map. Whether the profile gains stock classes for them (as
  `vehicle` was added for SPEC_inventory) is a minor version of the profile and Tomas's call.
- **Where the air came from** (`air.upwind`): left out of the first tools. `/ground/wind` holds only the next day's
  forecast, and the hours bar reads the past 48 h, so the tool would have no wind for the hours it asks about. It
  needs the node to keep the wind that blew, and a short spec of its own.
- **Geology and groundwater** have no source checked against the open rule for Ungasan.

## 14 · Left to the builder

The phone layout inside §4's rules, the run log's storage, the JSON Schema for each tool, the exact grey-step mapping
per result, how the cake rows collapse when a section has nothing on, keyboard shortcuts beyond `/`, ⌘K and ↵, and the
order of tools inside the list.
