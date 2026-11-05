# SPEC: what the Place door works out from open maps

*Asked, 23 October 2026, by Tomas, after reading urban:SCAN (urban-scan.ildar.space): "draft a short spec for the
Place-door analyses worth taking from urban:SCAN, using only sources that pass the open rule, with modelled values
labelled."*

**Status: proposed 23 October 2026. Nothing is built.** Each step in §7 is its own pull request, run on node #1
before it merges.

## 1 · Where this comes from

urban:SCAN runs about thirty urban analyses on any site, in the browser, from open data. Its code carries no licence,
so this node copies none of it and takes only the methods, which are published ones and are named below.

Four of the thirty answer a question this node already asks. The second table in §2 gives the reason each of the
others is left out.

## 2 · What it serves

The pack design record asks every new thing on a node which decision it informs.

| analysis | issue | the decision |
|---|---|---|
| Sun and shade | heat | Which hours the yard, the street and the roof are in sun, and where a panel gets the most. Also whether the outdoor sensor itself sits in sun, which is when its temperature reads high. |
| Trees, 3-30-300 | heat, land | Whether three trees stand within 30 m of the home, whether the cell has 30% canopy, whether a park of 1 ha or more is within a 300 m walk, and where one more tree would shade the most. |
| Built form | land | How densely the cell is built, how tall, and how that changed from 2016 to 2023. |
| Street structure | air | Which streets near the sensor carry through movement, to help read a PM2.5 spike. It reads the network's shape and counts no traffic. |

Left out:

| urban:SCAN analysis | why not |
|---|---|
| Residents and jobs | Floor area divided by an assumed m² per person. A model with nothing measured under it, and nothing on the node decides on it. |
| Housing value | No open source. Its index is stretched ±60% around a city average. |
| Pedestrian and car flows, traffic noise | Models fed by models. Noise needs traffic counts the node does not have. |
| Pedestrian wind | A 2D slice, which its own code says is "an estimate, not CFD". The forecast pack already gives the node its wind. |
| 15-minute city | The place pack already gives the walk to the nearest school, clinic, market and place of worship. |
| Heat island | The surface-heat pack already reads it from Landsat. |
| Building change, satellite image, tree detection | Built on Esri World Imagery and Wayback, whose terms fail the open rule. |

## 3 · Sources

Each one checked against the registry's open rule (CONTRIBUTING.md in awesome-fabcity-data) on 23 October 2026.

| source | licence | used for | verdict |
|---|---|---|---|
| OpenStreetMap, already in PostGIS through the place pack | ODbL | footprints, `height`, `building:levels`, streets, `natural=tree`, parks | passes; share-alike, see §6 |
| Google Open Buildings V3 and 2.5D Temporal, already fetched by the place pack | CC BY 4.0 | footprints and heights where the map has none, the 2016–2023 series | passes |
| Microsoft Global ML Building Footprints | ODbL | footprints where Open Buildings does not reach (Europe, North America) | passes |
| DLR WSF 3D v2 | CC BY 4.0 | mean building height per ~90 m cell, the last fallback | passes |
| ESA WorldCover 10 m 2021 | CC BY 4.0 | tree cover share | passes |
| Meta and WRI canopy height, 1 m | CC BY 4.0; source imagery © 2016 Maxar | tree crowns and their heights, for shade | passes; the imagery is years old in most places, so its date is shown |
| Copernicus DEM GLO-30 | Copernicus WorldDEM-30 licence: free use and change, its own notice and liability sentence | the ground, for shade on slopes (later, §8) | passes; carry its notice word for word |
| Sun position | NOAA and Meeus formulas | arithmetic | no data |

Not used: Esri World Imagery and Wayback (Esri's terms). Mapterhorn, whose terrain tiles mix many national sources
under licences listed one by one, so the node reads GLO-30 directly. Overture buildings, which merge the sources
above plus Esri Community Maps and add nothing the node needs.

## 4 · Derived or modelled

None of these values is measured here, so no cell they feed is ever `live`. Each value carries one of two words, and
the page shows it with the provenance sign it already has:

- **Derived** (`partial`): a calculation on mapped inputs that adds no assumption. Ground coverage from footprints,
  street integration from the map's network, sun hours where every building's height is mapped.
- **Modelled** (`model`): any input is an assumption or a model's output. A height filled from Open Buildings, WSF
  or a default of 3 m per floor, a canopy from the 1 m model, the 2.5D Temporal series.

**A value is modelled when any one of its inputs is.** Every figure that rests on heights prints how many were
mapped beside it, as in "heights: 412 mapped, 2,492 filled". Where few heights are mapped, most sun figures will read
`model`, which is correct.

Every output row carries exactly one of the two words, and the test asserts that `derived + modelled` equals the
rows, so a category cannot hide inside the other.

## 5 · The four analyses

Each runs on the node, over the place pack's circle (`PLACE_RADIUS_M`), and is recomputed when the place pack
refreshes. The page draws what the node says, as the doors decision requires.

**Sun and shade.** Shadows are cast as polygons on the CPU: each building's footprint is pushed away from the sun by its
height over the tangent of the sun's altitude, every 10 minutes from sunrise to sunset, on today and on the two
solstices and the equinox. Trees cast a disc of their crown at their height. The node keeps sun hours on a 2 m grid
and per roof, and reads three numbers from them: the hours of sun at the outdoor sensor's point today, the share of
the cell's ground in shade at 13:00, and the roofs with the most sun hours in a year. Sun hours on a roof follow §4:
derived when every height and crown that shades the roof is mapped, modelled otherwise. kWh from a panel would be a
second model on top, so it is not computed. Method: NOAA solar position; the
same shadow casting as urban:SCAN's, on a CPU.

**Trees, 3-30-300.** Konijnendijk's rule, three parts read separately. *3*: mapped trees and canopy crowns within 30 m of
the home's point. The rule asks for three trees seen from the home, and the node draws no lines of sight, so the count
within 30 m stands in for it and the page says "within 30 m", never "seen". *30*: canopy share of the node's res-8
cell. *300*: a park of 1 ha or more within a 300 m walk, on the place pack's own walking network. The rule says 300 m
to the nearest park; the 1 ha floor and the walk are this spec's choices, so a verge of grass does not count and a park
behind a wall with no gate is not near (§8). A tree mapped in OpenStreetMap is derived; a crown from the 1 m model is
modelled. Where one more tree would shade the most is the sun grid's longest-lit ground within 20 m of a path.

**Built form.** Berghauser Pont and Haupt's Spacematrix per res-9 child of the node's res-8 cell: ground space index
(footprint over area), floor space index (floor area over area), open space ratio, and mean floors, with the
Spacematrix class. The 2016–2023 series uses Open Buildings Temporal's counts and heights and is always modelled.

**Street structure.** Angular segment analysis (Turner 2007) on the walking network within 2 km: normalised choice and
integration at radius 800 m and at n. One readout: where the street nearest the outdoor sensor ranks by choice within
800 m ("in the top 10% of through-streets"). It describes the street's place in the network and says nothing about
how many cars use it.

## 6 · What leaves

Nothing new leaves at first. The sun grid and the per-building and per-segment values are built from OpenStreetMap,
which makes them a derivative database under ODbL, so they stay where `/place/geojson` already is: on the node,
behind the token.

The readouts in §5 are a few numbers per cell, kept as readings on `place-point` with the attribution the place pack
already writes. Whether such numbers can go into the CC BY export as they are is the question SPEC_inventory.md §7
left open. This spec does not decide it.

## 7 · Steps

1. **Heights with their source.** One height per building with where it came from (mapped, Open Buildings, WSF,
   floors × 3 m) and its word, derived or modelled, plus the "heights: mapped, filled" line. Every other step reads
   this, so it goes first.
2. **Built form.** The cheapest analysis, and the one that checks step 1 against the map.
3. **Sun and shade**, buildings first. The sun on the sensor's own point answers a trust question on its own, before
   any tree is added.
4. **Trees, 3-30-300**, which adds crowns to the shade.
5. **Street structure.**

## 8 · Open

- **Cost on a small node.** About 2,900 buildings × 70 sun positions × 4 days of shadow polygons is unmeasured. Time
  it on node #3, the class 0 bench, before step 3 merges.
- **The ground.** On a slope the hill shades too. GLO-30 is 30 m, coarse beside a 2 m grid; it waits until the
  flat version has run on node #1.
- **The 300 m park.** The 1 ha floor and the walk are this spec's choices (§5). A smaller floor, or a straight
  line, would count more homes as near a park.
- **The ODbL export question** (§6).
- **One pack or two.** This spec puts it in the place pack, which already holds the geometries. Splitting it out is
  open if the place pack grows too large to read.
