# earth — the node's own square of AlphaEarth

Google's AlphaEarth Foundations model turns a year of satellite observation into a 64-number vector for every
10 m pixel of the planet. Two vectors for the same pixel in two different years point in almost the same
direction if nothing happened there, and apart if something did. That is the whole of this pack: download the
node's square, take the angle between years, report it.

The layers are published as Cloud-Optimized GeoTIFFs in a public bucket, `gs://alphaearth_foundations`, under
CC BY 4.0. The node reads the window it needs over HTTPS with no key and no account.

## What it is not

- **Not air, water or emissions.** The embeddings describe land surface and coastal water as seen from orbit.
  Nothing in them is a measurement of what you breathe. That is what the sensors on the wall are for.
- **Not monitoring.** One layer per year, published after the year ends. It is a retrospective record of
  structure, not a signal you can act on this week.
- **Not an explanation.** The number says this square looks different from last year. It cannot say a road
  was cut, a warung was built, a hillside was cleared or a field flooded. Someone who walks there can.
- **Not ours to reproduce.** It is a Google artifact. We can mirror it and do arithmetic on it because the
  licence allows that. We could not make it again, and we cannot check it against anything.

## The arithmetic

Each channel is a signed byte. The bucket's README gives the mapping to the analysis value:

    v = (raw / 127.5) ** 2 * sign(raw)

and the 64-vector has Euclidean length 1 **after** that mapping. This matters more than it looks: on the raw
integers the vectors have length about 321, so a dot product taken before de-quantising is wrong and still
looks like a number between plausible bounds. Measured on 20,000 pixels of the Bali tile, de-quantised norms
came out at 1.000093, spread 0.002, every one within 0.01 of unit length. `planetai run earth verify` re-runs
that check on whatever is cached here.

Because the vectors are already unit length, the cosine is just the dot product, and

    distance = 1 - dot(A, B)

per pixel, clipped to [0, 2]. `-128` in any channel means no data; the bucket's README says it is then in
every channel, and those pixels are excluded from every statistic. The comparison runs in bands of 100 rows,
because one de-quantised year is 256 MB of float and a node may have 2 GB of memory.

### Where "changed" starts

`CHANGED = 0.15`, one constant at the top of `packs/earth/change.py`. It is the only number in this pack that
was chosen rather than measured, and it was calibrated on one 10 km square of Kuta Selatan, Bali. There, it
sits at about the 99th percentile of a consecutive-year comparison: 0.96 % of the square for 2023→2024,
1.19 % for 2024→2025, and 4.9 % over the two-year gap 2023→2025. So in that square a quiet year stays quiet
and a real change stands out. A lower threshold is not more sensitive, it is noisier: at 0.05 a third of this
square is "changed" every year.

### Read the span first, then the years

`--all` computes every consecutive pair and the full span, and prints them as one table. That is the order
worth reading them in. Over eight years at node #1 the span flags 8.80 % of the square; the eight yearly
steps flag 0.16 % to 3.81 % each and sum to 8.51 %, so the areas agree — persistent local change accumulates.
What does not accumulate is the background: the yearly *means* sum to 0.2991 against the span's 0.0673, four
fifths of it cancelling out. So the span's p95 sits at 3.65 times its median where every single year sits at
2.1 to 2.8, and 92 % of the span's flagged pixels lie inside patches against 82–89 % for the years. The span
is the cleaner picture of what was built. The yearly rows say when.

They are worth having together. At node #1 the two quietest years in the whole record are 2020→2021 (0.16 %)
and 2021→2022 (0.19 %), and the busiest is 2019→2020 (3.81 %). Something stopped on the Bukit and started
again. The satellite cannot say it was the pandemic; someone who was there can.

### The number is not comparable between places, and there is no alert

Read the distribution in the JSON before you trust the hectares, because the baseline moves with the climate,
not only with what people build. Measured for 2024→2025 at the four pilot coordinates:

| place | mean | over 0.15 |
|---|---|---|
| Kuta Selatan, Bali | 0.0414 | 1.19 % |
| Boston | 0.0404 | 3.26 % |
| Barcelona | 0.0164 | 0.15 % |
| Santiago | 0.0151 | 0.10 % |

Boston and Barcelona sit at the same latitude and differ by two and a half times. Boston's change is spread
across built-up land, not water — the harbour is one of the quietest parts of its map — so the likeliest
explanation is snow and deciduous leaf-off between two annual composites rather than 326 hectares of Boston
being rebuilt in a year. That is a guess: nothing here has separated seasonality from construction.

Which is why this pack ships **no alert**. Any threshold that fires in Kuta Selatan, where the land really is
being built on, also fires in Boston every year for reasons nobody there can act on, and this node does not
send messages a household would ignore. The map and the number are on the dashboard for a person to look at.
When there is a way to tell a season from a bulldozer, the alert can come back.

## The cache

Files under `out/earth/<node>/`, which is the one writable path the app container has:

| file | what |
|---|---|
| `<year>.npy` | the raw signed bytes for the square, north up, 64 x H x W |
| `meta.json` | the point, the radius, the tile the index chose per year, the window bounds |
| `change_<A>_<B>.png` | the map: grey ramp, north up, the node ringed, 1 km scale bar |
| `change_<A>_<B>.json` | mean, median, p95, the share and hectares over the threshold, bounds, source objects |
| `change_<A>_<B>_wall.png` | the Wall's image: changed pixels only, inside the community's res-7 cells that fit a square centred on the house's res-8 cell; transparent elsewhere, no ring, no scale bar. Its box and hectares are `wall` in the JSON, and `GET /earth/wall.png` serves it. `wall` is null when no cell fits, or when a tile edge clipped the square read (where the edge cuts would say where the house is). A plain `earth change` rebuilds only the default pair: a pair from before this file gets its image there, and any other with `planetai run earth change <A> <B>`, or `planetai run earth change --all` for every pair. A crop cut round another res-8 cell than the house's now, or whose image is missing, is computed again |

Measured on node #1 (Bali, `EARTH_RADIUS_M=5000`, a 10 km square, 1000 x 1000 px):

- **64 MB on disk per year**, 576 MB for all nine.
- **about 103 MB pulled per year**, 925 MB for all nine. More than the file it keeps, because the source is
  tiled internally in 1024 px blocks and a square centred on the node straddles four of them. Aligning the
  window to those blocks would cost 14.5 MB, and would put the node 2 km from one edge of its own square.
- **about 150 seconds per year**, so all nine is roughly 22 minutes. Run it from a shell rather than over
  MCP, where a script is cut off at 15 minutes.
- one extra download the first time only: the dataset's tile index. It is 798 MB and has no GeoJSON form, so
  the pack binary-searches it by byte offset for the node's UTM zone and reads only that zone's block. For
  Bali that was 26 range reads, 189 kB, then one block of 8.8 MB. The result is kept in `meta.json`.

Nothing is downloaded on a poll. The pack fetches on command; the adapter only reads what is already here.

### The directory is named for the node, but it is keyed on the place

`<node>` is only a name. What decides whether a directory holds *this* node's square is its `meta.json`: the
point it was read around, within the same tolerance a move uses, and the radius. So a directory written under
an earlier `NODE_NAME` is adopted as it stands, and when several match, the one named for the node today wins.

Node #1 is why. It was renamed `bayu-2` → `bayu-ungasan`, and because the name was the key, `fetch` saw an
empty directory and re-read all nine years: about 930 MB pulled for data already on the disk, and 555 MB of
`out/earth/bayu-2/` left behind that nothing reads. A rename now costs nothing, and two nodes at one address
share one cache.

A real move still costs everything, unchanged: the tolerance is 1% of the radius with a 25 m floor, so a
corrected decimal keeps the cache and 1.1 km does not. A different `EARTH_RADIUS_M` is a different square too.
And nothing is moved or deleted to make this work — a directory that stopped being this node's square stays
exactly where it is, and `planetai run earth status` names it, its size and the point it was read around, for
a person to decide about. Nine years is expensive to fetch and cheap to keep; a node does not delete somebody's
data on its own.

## Moving a node

The cache is a square around `NODE_LAT` / `NODE_LON`, and the files are named by year. Change the coordinates (or
`EARTH_RADIUS_M`) and `planetai run earth fetch` re-reads every year it had: the pixels on disk are a picture of the
previous square, and keeping them would compare two different places. That is a real download again, about 103 MB
per year, so the node says how many years it is re-reading and why. A correction smaller than 1% of the radius
(never less than 25 m) leaves the cache alone and is recorded in `meta.json` as `point_drift_m`.
`planetai run earth verify` fails on a cache that was read around somewhere else.

## The commands

```bash
planetai run earth fetch            # every year the dataset has (or EARTH_YEARS); --force re-reads a cached one
planetai run earth fetch 2024 2025  # just these
planetai run earth change           # the two latest consecutive cached years
planetai run earth change 2023 2025 # any two
planetai run earth change --all     # every consecutive pair, plus the oldest-to-newest span
planetai run earth frames           # one picture of the place per cached year, for the card to animate
planetai run earth status           # years, bytes, comparisons, what the cell reports
planetai run earth verify           # the dataset's claims against the files, and whether the reading landed
planetai run earth similar          # the four pilots compared with each other and with their own tiles
```

`similar` is the odd one out: it is not about this node. It reads the dataset's own 128x overview layer (1.28 km
a cell, a few hundred kB a tile) for each of the four pilot sites in `presets/`, takes the mean embedding
around each, and reports the cosine similarity between every pair plus the ten closest cells inside each
pilot's own UTM tile. That tile is about 82 km on a side, so this is a regional search and every surface that
shows the result says so. A global search would need every tile of the dataset or a vector index over all of
it. `--out FILE` writes the JSON somewhere else; the observatory reads it from
`observatory/data/alphaearth_similarity.json` in the site repo.

The pack is code, so it needs `PACKS_ALLOW_CODE=1` in `.env` and `planetai packs install` for `rasterio` and
`numpy`. Read `packs/earth/adapter.py` before you enable it.

## The years, as pictures

`frames` renders each cached year to `year_<YYYY>.png`: the first principal component of the 64 embedding
dimensions mapped to grey, dark water and bright land, the node ringed, a 1 km bar, and the year burnt into
the corner so a frame that leaves the node still says when it is. The dashboard's card animates them and the
slider stops on any one. About 780 kB a frame; nine years is 7 MB and a few seconds, all from files already
on disk.

**They are not photographs.** This pack has never downloaded imagery. It holds a model's 64-number
description of every 10 m pixel, and a frame is that description flattened to one number and drawn. It looks
like a panchromatic satellite image because the strongest thing in the embedding is the same thing that
dominates such an image, but no camera saw these greys. For real Landsat and Sentinel-2 frames,
`planetai run earth-engine timelapse` downloads pictures and needs an Earth Engine key.

The projection is fitted once over every year cached at the time, then kept in `meta.json` and reused. A
sequence whose greys move between frames is not a sequence: when next year's layer arrives it is drawn
through the existing projection, so the new frame joins the record instead of changing every frame before it.
`--refit` redoes it and rewrites them all, which is what a moved square needs and a new year does not.

## The cell

One: `Environmental|City`, `partial`, the mean per-pixel distance for the latest consecutive pair. It stays
`partial` however good it is. The node did the arithmetic, but the input is a model's description of a place,
not a measurement anyone here could repeat, and `live` in this project means measured here.

The `air-quality` pack already contributes an `Environmental|City` cell (PM2.5 from public reference
stations). Two cells under one key is how this node already works — `Environmental|Bioregion` carries three —
and `/cells` lists both with their own units. Nothing overwrites anything.

## Where the land-change number used to live

Until v0.33.1 the `earth-engine` pack also published a `land_change_score`: 1 − cosine similarity of the
*mean* embedding vector over a 1 km buffer, computed inside Earth Engine, behind a service-account key. This
pack publishes the mean of the *per-pixel* distances over 10 km, computed here, from a public bucket, with no
key. They are different quantities and they did not agree — averaging vectors first cancels the noise that
averaging distances keeps, and on node #1 the two read 0.037 and 0.041 without any way for a reader to tell
why. Two numbers for one idea with different provenance is worse than one, so the Earth Engine one was
retired. Its `land_changed` alert was not carried over, for the reason under *there is no alert* above. `earth-engine` keeps what only Earth Engine can
give: Dynamic World, Sentinel-2 and VIIRS.

## Attribution

The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind. CC BY 4.0.

This is the wording the dataset's licence asks for, and it travels with every derivative: the pack manifest,
the `/earth` endpoint, the dashboard card, the PNG's own metadata, and the daily export.

This pack is beta, like the rest of the node. If the numbers look wrong for your place, that is worth an
email: info@fab.city.
