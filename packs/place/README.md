# place

What is around the node, from OpenStreetMap, kept in PostGIS on the node, summarised once a month.

**Adds** the sensor `place-point` (kind `map`, scale `community`) with: buildings and the share of ground they cover;
the share of buildings that are commercial; mapped businesses per km²; places to eat, shops and markets, schools,
clinics and pharmacies, places of worship, lodging, services; kilometres of road; share of green; and the walk to the
nearest school, clinic, market and place of worship. One `Economic|Community` cell (businesses per km², `partial`). One
message a month.

**Setup.** Nothing to configure. `PACKS_ALLOW_CODE=1` (it is a code pack), `planetai packs install`, `planetai restart`. The
first poll fetches everything within `PLACE_RADIUS_M` (1000) from the Overpass API and stores the geometries in
PostGIS, which the node's database image now includes. Later polls recompute from what is stored; every
`PLACE_REFRESH_DAYS` (30) it fetches again. `planetai run place refresh` forces a fetch.

## Node #1, September 2026

Within a kilometre of bayu-2: 2,904 buildings, 540 road segments, 37 mapped places. Nineteen to eat at (Warung Made,
Bali Buda Bukit, Semboja), six markets (Alfamart, Indomaret, the Morning Market), sixteen villas and guesthouses, two
health, no school. That last number is OpenStreetMap coverage on the Bukit, not the Bukit.

## What it is, and is not

Structure, and change between refreshes. Not behaviour: three warungs on the map say nothing about how busy the street
is; the sensors do. Not production: the Fab City question for the Economic pillar is what a place makes, repairs and
sells, and the honest numbers for that are a fab lab's machine log and a market's stall count. Business density is the
proxy until those exist, and the cell says `partial`.

**Zeroes mean unmapped.** Every message and label says so. If the map is wrong about your place, fix the map: that
is what OpenStreetMap is for, and the node picks it up on the next refresh.

## Why PostGIS

The questions above are a fixed set and could be answered in Python. PostGIS is there because the next questions are
not fixed: distance from the kitchen sensor to the nearest busy road, how much roof is within 200 m of the outdoor kit,
which sensors sit downwind of the burning. The geometries are in the node's database, queryable by any pack.

## The satellite's buildings

With the earth-engine pack's credentials in place, the monthly refresh also fetches **Google Open Buildings** (CC BY):
the V3 footprints within the radius (confidence ≥ 0.65) into `place_buildings_sat`, and the Temporal dataset's yearly
building count and mean height, 2016–2023, into `place_yearly` and onto `place-point` as `sat_buildings_yearly` and
`sat_height_m_yearly`, dated 1 July of each year. The node can then say how many buildings the satellite sees, how many
the map has (`osm_building_coverage`), and how the count grew. `GET /history?sensor_id=place-point&metric=sat_buildings_yearly`
is the series; the bot's `history` tool reads it.

## Fixing the map

```bash
planetai run place verify   # PostGIS, OpenStreetMap, Earth Engine, Open Buildings: each step named
planetai run place gaps     # the mapping briefing: what is unmapped here, and how to fix it
```

`gaps` compares the satellite's footprints with the map's, counts the untyped buildings, the categories with nothing,
the named places without hours, the unnamed streets, and writes `out/place-gaps.md`: the briefing for a mapping afternoon
at the lab. StreetComplete asks the questions as you walk; Every Door adds places; iD traces buildings over Bing or Esri.
Never from Google Maps or Google imagery. Edits reach the node within minutes: `planetai run place refresh`.

## Moving a node

Everything here is a circle around `NODE_LAT` / `NODE_LON`. There is no stored drawing: the dashboard builds the
plan from `/place/geojson`, which reads the features in PostGIS. So a move is three steps, and the third one is the
drawing:

    # edit NODE_LAT and NODE_LON in .env (and NODE_TZ, NODE_CITY if the place changed)
    planetai restart                  # the coordinates are read once, at start
    planetai run place refresh        # replaces every feature with the ones around the new point

Then reload the dashboard; the plan is held in the page for its lifetime, so the page's own refresh will not redraw it.

The node also notices by itself: the next poll sees that the stored run was centred somewhere else and refetches,
and it clears the satellite footprints and the yearly series, which described the old circle. A correction smaller
than 1% of the radius (never less than 25 m) is not treated as a move, so retyping a decimal costs no fetch.
`planetai run place verify` names the mismatch while it lasts.

## A detailed map kept on the node

`planetai run place basemap` keeps two maps of this place on the node's own disk, in `out/ground/`, for the
dashboard's map to draw with nothing sent anywhere:

- **vector**: OpenStreetMap as vector tiles, cut out of Protomaps' daily planet build (ODbL) by HTTP range
  requests, in three rings (300 km to zoom 8, 60 km to zoom 11, `GROUND_RADIUS_KM` to zoom 15), with the Noto Sans
  label fonts. Node #1, 7 October 2026: 726 tiles, 6.4 MB, 26 requests, 19 s.
- **drone**: any OpenAerialMap mosaic (CC BY 4.0) crossing the `GROUND_DRONE_RADIUS_KM` ring, to
  `GROUND_DRONE_MAXZ`. Node #1: one, Saragis Multikencana's Benoa flight (7 cm, December 2024), 1,656 tiles, 49 MB.
  It stops 1.5 km east of the house: no open sub-metre imagery covers node #1's own cell.

The fetch tells build.protomaps.com and OpenAerialMap which square the node is in, once, and says so before it
runs. `--only vector` or `--only drone` runs one half; `--dry-run` counts without fetching. The 10 m satellite
layer is the earth-engine pack's (`planetai run earth-engine basemap`).

## Next source

Overture Maps: monthly releases; diff two and see what opened, closed, was built. A second fetch into the same table.

© OpenStreetMap contributors, ODbL.
