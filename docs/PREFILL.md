# What a node knows before it has a sensor
<!-- checked: v0.80.10 -->

On first start, with an empty database, the node pulls for its coordinates:

| source | what | span | cost |
|---|---|---|---|
| Copernicus CAMS (via Open-Meteo) | hourly PM2.5, PM10, O₃, NO₂, dust, UV, 11 km grid | PM2.5 and PM10 for the last 92 days, then all of them live | free, no key |
| NASA POWER | monthly temperature, humidity, rain normals | 1981 to now | free, no key |
| Open-Meteo | weather now: temp, humidity, wind, rain | live | free, no key |
| OpenStreetMap Nominatim | the place name | once | free |

So `planetai status` has something to say within minutes, anywhere on Earth: today's modelled air against three months
of history, today's weather against normals since 1981. `BOOTSTRAP=0` skips it.

## The number this makes possible

The gap between the model and your first sensor. At node #1 the CAMS cell tracks the street at r = 0.51 and the room at
r = −0.18. The model knows the district; a sensor knows the address. The node can put a number on that difference the day a
sensor arrives.

## Opt-in, because they need a key

OpenAQ (global public sensors), Google Flood Hub, Sentinel-5P via Earth Engine, NASA FIRMS. None is written yet in
v0.80; each would be a code pack or an adapter behind a flag, off by default. Nothing that needs an account runs
unless you turn it on.

## Presets

`presets/<city>.env`: bali, barcelona, boston, santiago, menorca, delhi. Coordinates, time zone, city key, the
open-data portal where there is one, and for Bali the public station feed. `planetai setup` picks one when your place
falls inside one of the four Index pilots (Bali, Barcelona, Boston, Santiago); `./install.sh --preset <city>` takes any.

## Not embedded

No copies of datasets, no model weights, no map tiles. The node fetches what it needs when it needs it and keeps only
what it computed. A node is a download of a few megabytes. Two small exceptions since v0.80: a 200 kB outline of the
world's land (Natural Earth, public domain) that the doors' Node view draws, and map tiles you ask for:
`planetai run place basemap` and `planetai run earth-engine basemap` keep them in `out/ground/` (on node #1, 6 MB of
street map, 49 MB of drone and about 12 MB of satellite), and nothing runs them unless somebody types the command.

## Attribution

Copernicus Atmosphere Monitoring Service (CC BY 4.0); NASA POWER; Open-Meteo (CC BY 4.0); OpenStreetMap (ODbL). The
model sensors carry their attribution or licence in `meta` on `/sensors`; the daily export states only its own
CC BY 4.0.
