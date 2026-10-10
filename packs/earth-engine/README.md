# earth-engine

What the land within a kilometre of the node did last year, from Google Earth Engine. A code pack with a dependency
and a credential; the worked example of both.

**Adds**, once a day, computed server-side over a 1 km buffer: tree, built, crop and water fractions (Dynamic World);
annual median NDVI (Sentinel-2, clouds masked); the latest night-lights radiance (VIIRS). Stamped mid-year; a daily
fetch inserts nothing new after the first. One `Environmental|Bioregion` cell, tree cover, and no rule. The
land-change score that was here moved to the `earth` pack in v0.33.1, which reads the same AlphaEarth embeddings
with no account.

## Setup

1. Register a project at code.earthengine.google.com/register. Creating a Cloud project and registering it for Earth
   Engine are separate; that page does both. Non-commercial, Community tier.
2. Cloud Console → IAM → Service Accounts → create one. Roles: **Earth Engine Resource Viewer**, **Service Usage
   Consumer**, and **Earth Engine Resource Writer** if you want the timelapse images. Keys → add key → JSON.
3. Copy the JSON to `config/ee-key.json` on the node. In `.env`: `EE_KEY_FILE=/app/config/ee-key.json`,
   `PACKS_ALLOW_CODE=1`. `EE_PROJECT` and `EE_SERVICE_ACCOUNT` can stay blank; the key names both. If you set
   `EE_PROJECT`, use the project id (`planetai-node`), not the service account's 21-digit number; Earth Engine reports that
   mistake as "project not found".
4. `planetai packs install` (installs `earthengine-api`), `planetai restart`.
5. `planetai run earth-engine verify`: library, settings, key, credentials, a real query, the three datasets. Names the step
   that failed.

Until configured the pack logs one line and idles.

## Images

```bash
planetai run earth-engine timelapse                              # 4 frames, 5 years apart, ending last year
planetai run earth-engine timelapse --n 5 --gap 2 --source sentinel --km 1
```

Each frame is the annual median of clear pixels: what you see is the year. Landsat by default, the only archive reaching
2010 with one instrument family; Sentinel-2 for 2016 onward at 10 m. If a year has no clear imagery (Landsat 5 over
Indonesia is thin), the nearest year within three is used and said so. PNGs and a side-by-side page land in `out/`.

## The node's own satellite map

`planetai run earth-engine basemap` builds the median of every clear Sentinel-2 pass over the last twelve months
(`--months`) in this node's own Earth Engine project, and keeps it as map tiles at zoom 8-15 in
`out/ground/imagery.mbtiles`: `GROUND_SAT_WIDE_KM` round the node for context, `GROUND_RADIUS_KM` for detail. The
node serves it at `/ground/imagery`, so the dashboard's map draws a satellite base without asking a tile server.
It is 10 m, Sentinel-2's own grain; only a drone mosaic is sharper (`planetai run place basemap --only drone`).
Copernicus data is free, full and open, so keeping it is allowed; Earth Engine learns the two squares, once.

## Node #1, 2025

91% built, 9% trees, no crops, NDVI 0.51, night lights 14.5. Land-change score 0.037, before it moved to `earth`: little changed, because on the
Bukit the change already happened.

## Not

A measurement of your place. Dynamic World is a classifier; the embedding shift says something changed, not what;
a kilometre around a house is mostly other people's land. `partial`, always.
