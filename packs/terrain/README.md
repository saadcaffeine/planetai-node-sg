# terrain — where the rain goes

The node reads its own square of elevation once, fills the hollows, and routes water downhill across it. Two
numbers come out for the node's point: how much ground drains through it, and how deep water would stand there
before it runs on. Every poll multiplies the first by the rain the forecast puts on the next day. The household
decides what to clear, lift or move before tonight. The pack only says where the water is likely to go.

```
planetai run terrain coverage    # which elevation this point would use, before anything is downloaded
planetai run terrain fetch       # read the square (about half a megabyte), fill, route, keep the result
planetai run terrain verify      # five checks, and the one that fails if the fill breaks
```

Then add `water` to `NODE_ISSUES` to see it on the page.

## The elevation, and its licence

**Copernicus DEM GLO-30**, one-degree Cloud-Optimized GeoTIFFs in `s3://copernicus-dem-30m`, read anonymously over
HTTPS. The AWS copy is the 2021 release. Newer releases are only on the Copernicus Data Space, and the Data Space
instance (GLO-30-R) is licensed for non-commercial use only. This pack reads the AWS files and nothing else.

The AWS files are **COP-DEM-GLO-30-F**, under the *Licence for the use of the Copernicus WorldDEM-30*: reproduction,
distribution and adaptation, free, worldwide, no time limit. In return, every number this pack shows carries the
derived-data notice and the no-liability sentence (`attribution` in `pack.yaml`), and anyone the node passes it
to is bound by the same two (Art. 6e). The registry entry is `environmental/planet/copernicus-dem-glo30`.

Where the 30 m tile is not public, the pack uses **GLO-90**. On 23 October 2026 the 90 m bucket had 25 tiles the
30 m one lacked, all in the Caucasus (Georgia, Armenia, Azerbaijan). Where neither bucket has the node's tile, it is
open sea or nothing was published, and the pack says so.

**Your own DEM** (a drone survey, a national LiDAR) goes in `TERRAIN_DEM_PATH`, and its licence, in words, in
`TERRAIN_DEM_LICENCE`. With the licence blank the node computes from the file and sends no rows: a survey you paid
for is not automatically yours to publish. The licence is read on every poll, so clearing it stops new rows at the
next one. Changing `TERRAIN_DEM_PATH` does too, until `fetch` runs on the new file. Rows already stored stay in this node's database, like any source's, and the issue keeps showing the last
one with its age.

## The arithmetic

numpy and a heap, no hydrology library. pysheds and richdem are GPL-3, which does not go into an Apache-2.0 node.

1. **Fill** by priority-flood (Barnes, Lehman & Mulla 2014). The window's edge and the sea are outlets. Every
   other cell is raised to at least the cell it is reached from, plus 0.1 mm, so that flats still drain.
   `filled − original` is the hollow depth.
2. **Route** with D8 on the filled surface: each cell drains to its steepest neighbour, with distances in metres
   at the node's latitude.
3. **Accumulate** from the highest cell down. Upslope area = cells × pixel area.

At the node's point the pack keeps the upslope area, the hollow depth, and the largest upslope area within 60 m.
The last one is there because a typed address is rarely right to the pixel, and a flow line one pixel away is the
street.

`water_24h_m3` = next-24-hour rain × upslope area, **as if none of it soaked in**. It is an upper bound, and the
sentence says so. The rain is `fc_rain` from the forecast pack, summed over rows timestamped in the next 24 hours,
from one source only: BMKG if it has rows, else Open-Meteo. Adding both would double it.

## What it is not

- **Not bare ground.** GLO-30 is a surface model: "including buildings, infrastructure and vegetation". A roof
  is a hill and a row of trees is a ridge. At 30 m a pixel is a street block. The pack speaks at region
  distance only, never yard or room.
- **Not a flood forecast.** It does not know the soil, the drains, the gutters, or the river. It knows the
  shape of a surface and a forecast's millimetres.
- **Not a wetness index.** TWI is ln(a / tan β). On a filled pixel tan β is clipped to almost nothing, so the
  index is mostly the clip. A percentile ranks the square against itself, so every square has a "wettest tenth",
  even a dry ridge. The pack publishes the two physical numbers TWI is made from instead.
- **Not an alert.** The `water` issue is context. It gets a line only when a household has said that water stood
  or ran here on a day the forecast gave so many millimetres. That is the household's word, and nobody has said it
  yet.
- **Water from beyond the square is not counted.** The window's edge is an outlet. At the default 10 km, that only
  matters for a node near the edge of a large catchment.

## Where it was written

Node #1, Ungasan, Bali, 23 October 2026: one tile, 323 × 327 pixels of 30.6 × 30.9 m, read in 5–25 s over HTTPS
and computed in under a second. At the node's own point, 0.09 ha drains through it and there is no hollow: the
house's pixel is a local high. The largest flow within 60 m drains 0.6 ha. Nothing here was tuned for that place.
There is no threshold to tune.
