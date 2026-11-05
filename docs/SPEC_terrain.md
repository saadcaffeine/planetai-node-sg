# SPEC — terrain: where the rain goes, from the node's own square of elevation

*Asked, 23 October 2026, by Tomas, after reading landscope.earth: a terrain/water pack on Copernicus GLO-30 for node
#1, flow accumulation and wetness joined to the rain forecast, a coverage check, and the licence checked first.*

**Status: built, 23 October 2026, as `packs/terrain` with the `water` issue.** Tomas answered §9.1 the same day:
water does stand or run at node #1 sometimes. §6 was measured at node #1's own point from `planetai run terrain
fetch`. Every other number is the publisher's.

## 1. The decision

Rain is coming. Does the water that falls uphill of this house pass through it or stop near it? Is there anything
to clear, lift or move before tonight? The household decides. The pack says how much ground drains through this
point, whether the point is a hollow, and how much rain the forecast puts on that ground.

If nobody at a node has ever seen water pond or run where they live, this pack has no decision there, and the page
says so (§9, question 1).

## 2. Licence — passes, as an open permission rather than a named licence

Read 23 October 2026, from the text and not the field. The AWS bucket carries **COP-DEM-GLO-30-F** ("Full, Free &
Open"), under the *Licence for the use of the Copernicus WorldDEM-30*. ESA's June 2025 licence bundle
(`copernicus_contributing_mission_data_access_v2_cop_dem_licenses.pdf`) has the same -F text, with the same
Article 4 and the same notices.

- **Grant (Art. 4–5):** reproduction, distribution, communication to the public, and "adaptation, modification and
  combination with other data". Free of charge, worldwide, with no time limit. There is no non-commercial clause.
- **Notice, original data (Art. 6a):** `© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided
  under COPERNICUS by the European Union and ESA; all rights reserved.`
- **Notice, derived data (Art. 6b), which is what this pack publishes:** `produced using Copernicus WorldDEM-30 ©
  DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union
  and ESA; all rights reserved`
- **Liability sentence (Art. 6c), required wherever we distribute:** "The organisations in charge of the Copernicus
  programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30".
- **It passes downstream (Art. 6e).** Anyone we hand derived data to is bound by the same notices, so the
  attribution travels with `/geo/*` and any export. This is the OECD shape: open, with attribution that passes on.
- **No endorsement (Art. 6d)** and no use of the Copernicus or WorldDEM marks beyond naming the source.
- **Trap: do not download from the Copernicus Data Space.** The same ESA bundle covers **GLO-30-R** and EEA-10-R,
  which are licensed "for non-commercial activities" only. Read the -F COGs from AWS and nothing else.

Owed: a registry entry in awesome-fabcity-data (`status: candidate`, licence quoted as above). The pack's `sources:`
field names it, as `earth` names AlphaEarth.

## 3. The data

- `s3://copernicus-dem-30m/`, eu-central-1. Anonymous HTTPS range requests, no key. One-degree COG tiles named
  `Copernicus_DSM_COG_10_<S09_00>_<E115_00>_DEM.tif`.
- Node #1 (−8.819, 115.164) fits in one tile, `S09_00_E115_00`: 16.4 MB, last modified 9 May 2022. That is the 2021
  release. The Data Space lists 2024_1, but under the restricted licence (§2). The pack keeps 2021 and says so in
  provenance.
- **It is a surface model, not bare earth.** The publisher's words: "including buildings, infrastructure and
  vegetation". Roofs and tree crowns are in the heights. At 30 m one pixel is a house block, so the pack never
  speaks at room or yard distance. Its rows are `region`, the distance `schema.py` gives a model sampled at a
  point.
- Heights are metres above EGM2008. The sea has no tiles: tiles that do exist hold 0 over water.

## 4. Coverage check, before anything is fetched

`planetai run terrain coverage` answers in this order, and the page says which one applies:

1. **A DEM the operator supplied** (`TERRAIN_DEM_PATH`, any GeoTIFF: a drone survey, a national LiDAR). Used as
   given, with its own resolution, and its licence typed by the operator into `TERRAIN_DEM_LICENCE`. If that is
   blank, the node computes but publishes nothing.
2. **GLO-30**, when the node's own tile answers a HEAD request in the 30 m bucket (a missing key is a 404).
3. **GLO-90**, when only the 90 m bucket names it. On 23 October the 90 m list had 25 tiles the 30 m one lacks, all
   in N38–N41 / E043–E050 (Georgia, Armenia, Azerbaijan; the Data Space says they were released in 2023_1, but not
   on AWS). Of the 61 Index places, 60 centroids sit on a 30 m tile; Georgia's is one of the 25. At 90 m the page
   says "region" and nothing finer.
4. **No tile in either list.** Open sea, or nothing published. The issue is `none`, with the reason.

The square may also cross into another tile: the pack reads every tile it touches and mosaics the window.

## 5. The arithmetic: numpy and heapq, no new dependency

`rasterio` and `numpy` are already in `earth`'s `pip:`. pysheds and richdem are GPL-3, which does not go into an
Apache-2.0 node. WhiteboxTools would be a binary download. None of them is needed:

1. Read the window (`TERRAIN_RADIUS_M`, default 5000, the same square as `earth`).
2. **Priority-flood fill** (Barnes 2014). Seed a heap with the window's edge and the sea, then pop and raise each
   neighbour to at least the cell it came from plus 1e-4 m, so that flats still drain. `fill = filled − original`
   is how deep water would stand before it overflows.
3. **D8 on the filled surface:** each cell drains to its steepest neighbour, with distances in metres at the
   window's latitude. Accumulate in order of falling height. Upslope area = count × pixel area.
4. Keep three numbers for the node's point, computed once and cached as a file like `earth`, because the surface
   does not change between releases: `terrain_upslope_ha`, `terrain_hollow_m`, and `terrain_upslope_near_ha`,
   the largest upslope area within 60 m. A typed address is rarely right to the pixel, and at node #1 the flow line
   within 60 m was 7 times the point's own. Slope and the per-H3-cell numbers were left out: nothing reads them
   yet.

The probe ran this on node #1's square from a laptop: 4.9 s to read 323 × 327 pixels over HTTPS, 0.2 s to fill,
0.1 s for D8. The pack's own `fetch` mosaics through `rasterio.merge`, which read the same window in 5–25 s.

## 6. What node #1's square shows (23 October 2026)

- Pixels are 30.6 × 30.9 m. 27.6 % of the square is sea. Land runs from −1.4 to 219.6 m.
- 6.3 % of the land is filled, up to 15.3 m deep. Nobody has walked those hollows yet. On a surface model some of
  them will be rooflines and tree edges, not ground.
- **The node's point** (`NODE_LAT`/`NODE_LON` from node #1's own `.env`): 156.8 m high. 0.09 ha drains through
  it, which is its own pixel alone, and there is no hollow: the house's pixel is a local high. The largest flow
  within 60 m (a circle, measured from the pixel centres) drains 0.6 ha.
- The draft of this spec measured 1.04 ha and a 0.32 m hollow, at −8.819, 115.164. That is the published,
  rounded point, 330 m west of the house. On a 30 m surface, 330 m is somewhere else, so the pack reads the
  node's own coordinates and never the published ones.

So at node #1 the water that stands or runs is most likely the street's, or the yard's, which 30 m cannot see. The
60 m figure is the one that speaks to it. A drone survey in `TERRAIN_DEM_PATH` would see the yard.

## 7. Wetness: no index, no percentile

At the draft's rounded point the pixel had a wetness index (TWI, ln(a / tan β)) of 12.74. That is above the square's 90th percentile
(11.73), so under LandScope's rule node #1 sits in "the wettest 10 % of the landscape". It is an artefact. The fill
flattened the pixel, the slope was clipped to 0.001, and ln(1/0.001) contributes 6.9 of the 12.74. Any filled
pixel scores high, on a roof as much as in a hollow. A percentile ranks a square against itself, so every square
has a wettest tenth, even a dry plateau. It is the reverse of showing a full cell as empty: a number invented for
every place.

So the pack publishes the two physical numbers TWI is made from: **how much ground drains here** (ha) and **how
deep water would stand here before it runs on** (m). Each has a unit, and neither needs the rest of the square to
mean something.

## 8. The join with rain

- Rain is `fc_rain` from the forecast pack: mm per forecast step, stored with a **future** `ts`. The read is
  `ts > now() AND ts <= now() + interval '24 hours'`, the inverse of the `ts <= now()` bound every other read uses.
- **Sum one source, never two.** The forecast pack can run BMKG and Open-Meteo together, at different step
  lengths, and adding both doubles the rain. Node #1 has `FORECAST_BMKG=1` and `FORECAST_OPENMETEO=0` (read 23
  October), but a node with both on must take the source the forecast page shows first, and name it in provenance.
- **Water arriving, as an upper bound:** `rain_mm / 1000 × upslope_m²`. On node #1's point, 40 mm on 0.09 ha is
  36 m³.
  The sentence says "if none of it soaks in", because some will, and the node cannot say how much.
- A **context** issue, like `land`: readouts, no line, no alert. An alert waits until a household tells us that
  water stood or ran at this place on a day the forecast said X mm. Until then there is no line to set.

The issue's `context_plain`, once it has a hero (below): "36 m³ could run onto this point in the next day, if none of it soaks in.
Rain forecast 40 mm, ground draining here 0.1 ha, hollow 0.0 m, largest flow within 60 m 0.6 ha."

**No hero yet.** A context issue's figures sentence is rendered inside its hero (`engine._plain`), and a hero needs a
sign in `app/static/signs.svg`. There is no water sign, and a new sign is design work in planetai-design, held to the
signs' distinctness test. Until one exists the issue is watched, drawn in the matrix and never leads, and its
`context_plain` waits in the yml.

## 9. Decided

1. Water does stand or run at node #1 sometimes (Tomas, 23 October). The pack is built and tested there first.
2. A new `water` issue, in `packs/terrain/issue.yml`, context, no hero, so it never leads. Land stays yearly.
3. Its own pack, `terrain`: different data, licence and cadence from `earth`.
4. Core, as built, beside `earth`. It works wherever a tile exists. If it should start wild, moving it is the
   folder and one table row.

## 10. Not in v1

Contours, aspect, landform classes, 3D, cross sections and exports. Each one waits for a decision it informs.
One exception is worth noting: an **elevation profile between two radio nodes** would use the same window to check
line of sight before a Meshtastic node is placed. It is small, and it can follow once the cache exists.

## 11. Done means

1. ✓ Registry entry filed as a candidate: awesome-fabcity-data #96. `sources:` in `pack.yaml` waits for it in
   the vendored pin, like `surface-heat`.
2. ✓ `packs/terrain/` with `coverage`, `fetch` and `verify`. `verify` re-runs the fill and asserts that every
   land cell drains to the edge or the sea.
3. ✓ The `water` issue, with the derived-data notice and the liability sentence in the row's `meta.attribution`
   and the pack's `attribution`.
4. ✓ `tests/test_terrain.py`, a line in `tests/all`, the count at 90.
5. Node #1 runs the branch through a real rain forecast before merge (the standing rule).
