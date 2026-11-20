# hydro — rivers and basins

A node should know where its rivers are. This pack fetches HydroSHEDS once for the node's square and keeps the
rivers in it, the basins they drain, and the basin the node itself sits in. Every poll re-sends six figures for the
nearest river and the largest one in the square: how far, how much water on average, its order, how much ground
drains into it, how far it still runs to the sea.

```
planetai run hydro fetch     # find the region, download its rivers and basins (50-160 MB), keep the square, delete the rest
planetai run hydro verify    # four checks, and the one that fails if the nearest river is not the nearest line
```

On the Place map the rivers and the basin are rows of the water layer.

## The data, and its licence

**HydroSHEDS v1** (Lehner & Grill 2013): HydroRIVERS for the rivers, HydroBASINS levels 1, 4 and 12 for the basins.
They are traced from a 15 arc-second surface, about 500 m, and a river is drawn where at least 10 km² drains into it
or 0.1 m³/s flows. The discharge is a model's long-term average, not a gauge.

The same rivers and basins are published in **HydroATLAS v1.0** (Linke et al. 2019) under **CC-BY 4.0**, and that is
the licence this pack shows them under. The registry entries are `environmental/bioregion/hydroatlas-riveratlas`
and `environmental/bioregion/hydroatlas-basinatlas`.

HydroSHEDS' own download pages carry the HydroSHEDS v1 licence agreement, which says "free for scientific,
educational and commercial use" and also forbids distributing the data "as a stand-alone product". The pack fetches
from data.hydrosheds.org because HydroATLAS's own copy is several GB on figshare and refuses scripted downloads. It
keeps a square of under 100 KB and never passes the files on whole. Tomas Diez accepted this reading for
index.fab.city on 8 November 2026.

## How a fetch works

1. The **region** is the level-1 basin that holds the node's point. A box per region picks one or two candidates,
   1-3 MB each. The first digit of the basin's Pfafstetter code names the region.
2. The **level-4 basin** that holds the point: the same basin index.fab.city draws as the place's bioregion.
3. Every **level-12 basin** in the square, and the one that holds the point, with its own area and the area upstream.
4. Every **river reach** in the square, the distance from the point to each, the nearest and the largest by flow.

Each file is unpacked to disk, read with pyshp inside the square only, and deleted. A point that falls in the sea
under the 15 arc-second coastline finds no level-1 basin, and the fetch says so and writes nothing.

## What it is not

- **Not the streams on your street.** A canal, a subak channel or a stream under 10 km² of catchment is not here.
  OpenStreetMap's waterways are, on the street map.
- **Not a flood map.** Where the rain goes on the ground around the node is the terrain pack. This pack says which
  river that water reaches and how far it is from the sea.
- **Not an Index cell, not an alert.** kind `model`. The level-4 basin is the bioregion's boundary, a frame for a
  place, never a figure that rolls up.

Settings: `HYDRO_RADIUS_KM` (25), the half-width of the square.
