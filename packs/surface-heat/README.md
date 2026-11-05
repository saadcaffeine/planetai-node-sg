# surface-heat — the ground around the house, from orbit

How hot the ground in this node's own cell got, against the land around it, and how warm the ground stays at
night. Two public-domain satellite products, read once a day from Microsoft Planetary Computer with no key and
no account. Written for Kuta Selatan, Bali, on 15 October 2026; nothing in it is specific to Bali.

A **code pack**: it ships `adapter.py`, so it runs only with `PACKS_ALLOW_CODE=1` in `.env` (default `0`). Read
`adapter.py` first: a code pack runs with the node's privileges. Then `planetai restart`. It needs no
`planetai packs install`: it adds no library.

## What it adds

On the heat issue, under Figures, three readouts:

| readout | metric | from |
|---|---|---|
| Ground in this cell at the last clear Landsat pass | `lst` on `surface-cell` | the mean of the clear land pixels in the node's H3 res-8 cell |
| Ground in this cell, minus the land 1 to 3 km around | `lst_delta` on `surface-cell` | that mean minus the mean of the clear land between 1 km and `SURFACE_HEAT_RING_KM` from the node |
| Ground at night (MODIS 1 km) | `lst_night` on `surface-modis` | the node's 1 km MODIS pixel at the last night pass that saw the ground |

Each readout carries the time of the pass, not of the poll, so a scene from twelve days ago says twelve days.
Read together they say, for node #1's test point on 27 Sep 2026 at 10:29: the ground in this cell was 41.3 °C,
0.3 °C hotter than the land 1 to 3 km around it, and in the middle (50th percentile) of the 24 cells of
that ring.

The report bundle gets `ground` (rule `surface-heat/ground`, `contributes: report`): the same pass, the ring, the
percentile, and the house's own outdoor air temperature within half an hour of the pass, or the weather model's
when the house has no outdoor sensor, and which one it was. The ground at 41 °C beside air at 30 °C is the point of
it: the sun heats a roof, a road or bare limestone far above the air, and that is the heat the walls take in.

Readings, all `kind='model'`, `scale='city'`, `local=False`, on two sensors:

| sensor | source | metrics | cadence |
|---|---|---|---|
| `surface-cell` | `landsat-lst` | `lst`, `lst_ring`, `lst_delta`, `lst_pctile` | a clear pass every one to three weeks |
| `surface-modis` | `modis-lst` | `lst_night`, `lst_day` | daily, about five days late |

`lst_pctile` is where the cell ranks among the res-8 cells whose centres are in the ring (100: hotter than all of
them). It is not written when fewer than five ring cells are clear.

The sensor's `meta` names the scene (`LC08_L2SP_117066_20260927_02_T1`), the platform, how clear the cell and the
ring were, the ring in km, the scale and offset used, the host and the attribution.

No alert, no Index cell, by design: a roof's skin temperature is not anyone's exposure, and a satellite retrieval
is never this node's measurement. Heat's line stays the house's own apparent temperature.

## Where the numbers come from

- **Landsat 8 and 9, Collection 2 Level-2, band ST_B10** (`landsat-c2-l2`). Surface temperature in kelvin, stored
  as an integer. The pack reads the scale and offset from the STAC item's `raster:bands` and refuses an item that
  publishes none; on 15 Oct 2026 they were 0.00341802 and 149.0, so °C = DN × 0.00341802 + 149.0 − 273.15. The
  thermal band is 100 m, resampled by USGS to 30 m, so a res-8 cell (about 820 pixels) holds roughly 75 independent
  thermal samples. Overpass about 10:30 local time; Bali sits under two paths (116 and 117), so a look every four
  days, most of them cloudy.
- **Cloud mask: QA_PIXEL.** A pixel counts when USGS's `clear` bit is set (neither cloud nor dilated cloud) and the
  shadow, cirrus, fill and water bits are not. A scene counts when at least `SURFACE_HEAT_MIN_CLEAR` (half) of the
  cell's land, and half of the ring's, is clear; otherwise the pack takes the next newest scene, up to three a day.
  On 28 Sep 2026 the cell was 5 % clear and the scene was skipped: that is the usual day, and the pack says so in
  the log and writes nothing.
- **Water is on neither side.** A coastal ring is otherwise half sea, and the house looks hot against it. A cloud
  over the sea is counted as not clear, which can only make a coastal node wait for a better scene.
- **Both sides are a plain mean** of clear land pixels, the same formula on each.
- **MODIS MOD11A1 (Terra) and MYD11A1 (Aqua) v061** (`modis-11A1-061`). `LST_Night_1km` and `LST_Day_1km`, scale
  0.02 from the item, 0 meaning "not produced" (cloud, or a retrieval MODIS discarded). MODIS's own "other
  quality" retrievals (±2–3 K) are kept. The timestamp is the nominal overpass in local solar time (Terra 10:30
  and 22:30, Aqua 13:30 and 01:30) folded into the file's UTC day; it can be an hour or so off at the swath edge.

## How it reads them, and what it does not add

The app image has no numpy or rasterio, and this pack does not add them. A Cloud-Optimized GeoTIFF is a TIFF header
and a grid of deflate-compressed tiles: the adapter reads the first 64 kB, finds the tiles a 7 km square around the
node touches, fetches only those with HTTP range requests, and decompresses them with `zlib`. UTM is computed with
Snyder's series (within 2 m of USGS's own corner coordinates, tested), and h3, already in the image, names the
cells. A Landsat scene is 68 MB; a day with a new clear scene reads about half a megabyte of it.

The SAS token is asked for by storage account and container (`/api/sas/v1/token/<account>/<container>`), not by
collection: on 15 Oct 2026 the MODIS collection's token was refused by its own container.

## Polite

- One STAC search per product a day. The day is kept in `out/surface-heat/state.json`, so a restart does not
  search again.
- A scene, or a MODIS day, is read once and remembered there, clear or not. A scene older than the newest stored is
  never read.
- At most three Landsat scenes and four MODIS days are read in one day. The first day reads about 40 small ranges
  (about 1.5 MB); a day with nothing new reads nothing past the two searches.
- When both products fail, the adapter raises (`planetai status` shows it) and tries again in an hour, not every
  poll.

## Settings

| setting | default | meaning |
|---|---|---|
| `SURFACE_HEAT_RING_KM` | `3` | the outer edge of the ring, in km. It starts at 1 km, so this must be more than 1 |
| `SURFACE_HEAT_MIN_CLEAR` | `0.5` | the share of the cell's land, and of the ring's, that must be clear for a scene to count |

## What it does not know

- **Not the air.** Surface temperature is the skin of whatever the satellite sees: roofs, roads, canopy tops. A
  roof at 45 °C does not mean a room at 45 °C. It says where heat is being stored around the house.
- **Not this hour.** One morning look every week or three. It is a picture of the place, not a reading of today.
- **Not exact at the cell edge.** 100 m thermal pixels blur across a res-8 cell's boundary; a house at the edge of
  its cell is described by a cell mostly on one side of it.
- **Not tested on node #1 yet.** The numbers above are from the earth suite's public test point in Ungasan, read on
  a laptop, not from the node.

## Sources and licence

Landsat Collection 2 data courtesy of the U.S. Geological Survey, public domain. MODIS MOD11A1/MYD11A1 v061 from
NASA's LP DAAC, public domain. Microsoft Planetary Computer is the host, not the publisher. The two registry entries
to file are `environmental/city/landsat-c2-surface-temperature` and `environmental/city/modis-lst-mod11a1`; once the
vendored registry pin carries them, `pack.yaml` lists them under `sources:`.

The test fixtures in `tests/data/surface-heat/` are two 64×64 crops of ST_B10 and QA_PIXEL from
`LC08_L2SP_117066_20260927_02_T1` (clear) and `LC09_L2SP_116066_20260928_02_T1` (cloud over the cell).
